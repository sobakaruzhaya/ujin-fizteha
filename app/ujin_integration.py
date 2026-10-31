"""Employee-authenticated Ujin bridge. Never creates devices or changes dictionaries."""
from __future__ import annotations

import copy
import http.cookiejar
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser


class UjinError(ValueError):
    pass


def read_packet(path):
    """Read credentials in-place; an archive is never extracted into the repo."""
    try:
        if str(path).lower().endswith('.zip'):
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if n.rsplit('/', 1)[-1] == 'доступы.json']
                if len(names) != 1 or archive.getinfo(names[0]).file_size > 1024 * 1024:
                    raise UjinError('В архиве должен быть один документ доступы.json')
                data = archive.read(names[0])
        else:
            data = Path(path).read_bytes()
        result = json.loads(data.decode('utf-8-sig'))
        if not all(result.get('employee', {}).get(k) for k in ('login', 'password')):
            raise UjinError('В документе нет логина и пароля employee')
        if not isinstance(result.get('devices'), list):
            raise UjinError('В документе нет списка выделенных устройств')
        return result
    except UjinError:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        raise UjinError('Не удалось прочитать документ доступов Ujin') from None


def origin(value):
    parts = urllib.parse.urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise UjinError('Для Ujin нужен HTTPS-адрес без данных доступа в URL')
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, '', '', ''))


class SignalTable(HTMLParser):
    """Read only the panel's public signal table; never invoke its DB actions."""
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.cells = [], None, None, []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'tr':
            self.row, self.cells = {}, []
        if tag == 'td' and self.row is not None:
            self.cell = []
            if 'data-v' in attrs:
                self.row['name'] = attrs['data-v'].partition('|')[2]

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.cells.append(' '.join(' '.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            if self.row.get('name') and len(self.cells) >= 5:
                self.row.update(value=self.cells[1], management=self.cells[4], title=self.cells[0])
                self.rows.append(self.row)
            self.row = None


class UjinTransport:
    def __init__(self, packet, panel_url, timeout=12):
        self.packet = packet
        self.base = origin(packet['api_base'])
        self.panel = origin(panel_url)
        self.timeout = timeout
        self._token = None
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [('User-Agent', 'UjinFizteha/1.0')]
        self.panel_ready = False

    def _request(self, url, form=None, payload=None):
        headers = {}
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if payload is not None:
            data = json.dumps(payload).encode()
            headers['Content-Type'] = 'application/json'
        try:
            response = self.opener.open(urllib.request.Request(url, data=data, headers=headers), timeout=self.timeout)
            with response:
                text = response.read(4 * 1024 * 1024).decode('utf-8')
                return text, response.geturl()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                self._token, self.panel_ready = None, False
            raise UjinError(f'Ujin: HTTP {exc.code}') from None
        except (OSError, UnicodeError):
            raise UjinError('Сервис Ujin недоступен или не ответил вовремя') from None

    def _json(self, path, query=None, form=None, payload=None):
        url = self.base + path
        if query:
            url += '?' + urllib.parse.urlencode(query)
        text, _ = self._request(url, form, payload)
        try:
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError()
        except ValueError:
            raise UjinError('Ujin вернул ответ неизвестного формата') from None
        if result.get('error') not in (0, '0', False, None):
            # Remote messages/URLs can echo a token. Never expose them.
            self._token = None
            raise UjinError('Ujin отклонил запрос; проверьте права и параметры устройства')
        return result

    def authenticate(self):
        employee = self.packet['employee']
        if not self._token:
            auth = self._json('/api/auth/authenticate/', form={
                'login': employee['login'], 'password': employee['password'], 'app': employee.get('app', 'employee')})
            data = auth.get('data') or {}
            self._token = auth.get('token') or data.get('token') or (data.get('user') or {}).get('token')
            if not isinstance(self._token, str) or not self._token:
                raise UjinError('Ujin не выдал токен сотрудника')
        if not self.panel_ready:
            html, _ = self._request(self.panel + '/login')
            csrf = re.search(r'name="csrf"\s+value="([^"]+)"', html)
            if not csrf:
                raise UjinError('Форма входа панели изменилась; требуется обновление адаптера')
            html, url = self._request(self.panel + '/login', form={
                'csrf': csrf.group(1), 'user': employee['login'], 'pw': employee['password']})
            if urllib.parse.urlsplit(url).path == '/login' or '/logout' not in html:
                raise UjinError('Панель сигналов не приняла учётную запись employee')
            self.panel_ready = True

    def device_info(self, binding):
        return self._json('/api/bmsdevice/get-device-info/', query={
            'token': self._token, 'serialnumber': binding['sn'], 'mts': 1}).get('data') or {}

    def panel_signals(self, binding):
        if not binding.get('_panel_path'):
            html, url = self._request(self.panel + '/?' + urllib.parse.urlencode({'q': binding['sn']}))
            for row in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S):
                if str(binding['sn']) in row:
                    match = re.search(r'href="(/device/\d+)"', row)
                    if match:
                        binding['_panel_path'] = match.group(1)
                        break
            if not binding.get('_panel_path'):
                self.panel_ready = False
                raise UjinError('Выделенное устройство не найдено в панели сотрудника')
        html, url = self._request(self.panel + binding['_panel_path'])
        if urllib.parse.urlsplit(url).path == '/login':
            self.panel_ready = False
            raise UjinError('Сессия панели истекла; выполняется повторное подключение')
        table = SignalTable(); table.feed(html)
        return table.rows

    def publish(self, binding, rows):
        if not binding.get('model') or not binding.get('publish_class') or not binding.get('apartment_id'):
            raise UjinError('Не заполнены модель, класс публикации или квартира')
        return self._json('/api/import_device/group-update-device-signal/',
            query={'token': self._token, 'apartment_id': binding['apartment_id'], 'serialnumber': binding['sn']},
            payload={'data': [{'sn': binding['ext'], 's': name, 'v': value if value != 0 else 0.001,
                               'c': binding['publish_class']} for name, value in rows.items()]})


def numeric(value):
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise UjinError('Получено нечисловое значение сигнала Ujin') from None


class UjinIntegration:
    def __init__(self, home, packet_path=None, bindings_path=None, transport_factory=UjinTransport, state_path=None):
        self.home = home
        self.packet_path = packet_path or os.environ.get('UJIN_CREDENTIALS_FILE', '')
        self.bindings_path = bindings_path or os.environ.get('UJIN_BINDINGS_FILE', '')
        self.panel_url = origin(os.environ.get('UJIN_PANEL_URL', 'https://signal-panel.duckdns.org'))
        self.state_path = Path(state_path) if state_path else Path(__file__).parent / 'data/ujin-tasks.json'
        self.factory, self.transport = transport_factory, None
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.bindings = []
        self.seen = {}
        self._last_notice = None
        self._status = {'configured': bool(self.packet_path), 'state': 'idle', 'mode': 'off',
            'message': 'Подключение ещё не проверено' if self.packet_path else 'Укажите серверный файл доступов Ujin',
            'panel_url': self.panel_url, 'last_check': None, 'devices': [], 'published': 0, 'commands_applied': 0}
        try:
            self.seen = json.loads(self.state_path.read_text(encoding='utf-8'))
            if not isinstance(self.seen, dict): self.seen = {}
        except (OSError, ValueError):
            pass

    def status(self):
        with self.lock:
            return {**copy.deepcopy(self._status), 'running': bool(self.thread and self.thread.is_alive())}

    def _notice(self, failed):
        if self._last_notice == failed: return
        self._last_notice = failed
        self.home.add_event('error' if failed else 'integration_connected', source='ujin',
            message='Ujin: ошибка обмена, проверьте страницу подключения.' if failed else 'Подключение к Ujin проверено. Доступность команд показана на странице интеграции.')

    def _load(self):
        if not self.packet_path:
            raise UjinError('Не задан UJIN_CREDENTIALS_FILE на сервере')
        packet = read_packet(self.packet_path)
        overrides = {}
        if self.bindings_path:
            try:
                overrides = json.loads(Path(self.bindings_path).read_text(encoding='utf-8'))
                if not isinstance(overrides, dict): raise ValueError()
            except (OSError, ValueError):
                raise UjinError('Не удалось прочитать настройки сопоставления Ujin') from None
        bindings = []
        for entry in packet['devices']:
            if not all(entry.get(k) for k in ('family', 'sn', 'ext')):
                continue
            local_id = next((key for key, meta in self.home.metadata.items() if meta['family'] == entry['family']), None)
            override = overrides.get(entry['family'], {})
            if not isinstance(override, dict) or not isinstance(override.get('signals', {}), dict):
                raise UjinError('Неверный формат сопоставления сигналов Ujin')
            allowed = {'local_id', 'model', 'publish_class', 'signal_prefix', 'signals'}
            binding = {**entry, 'local_id': local_id, **{k: v for k, v in override.items() if k in allowed}}
            if binding.get('local_id') not in self.home.devices: binding['local_id'] = None
            binding.setdefault('signal_prefix', (binding.get('publish_class') or '') + '_')
            binding.setdefault('signals', {})
            bindings.append(binding)
        self.bindings = bindings
        self.transport = self.factory(packet, self.panel_url)

    def _task(self, binding, signal):
        name = signal.get('name') or signal.get('signal_name')
        state = signal.get('state') or {}
        task = signal.get('task', state.get('task'))
        readonly = state.get('readonly')
        writable = readonly in (False, 0, '0') or signal.get('management') in ('rw', 'w')
        if task is None or task == '' or readonly in (True, 1, '1') or not writable:
            return
        mapping = {v: k for k, v in binding['signals'].items()}
        short = mapping.get(name, name.removeprefix(binding['signal_prefix']))
        with self.home.lock:
            target = self.home.devices[binding['local_id']].signals.get(short)
            if not target or not target.writable:
                return
            value = numeric(task)
            if value == 0.001 and (target.layout and 0 in target.layout): value = 0
            stamp = str(signal.get('signal_task_dt') or signal.get('task_dt') or state.get('task_dt') or task)
            key = f"{binding['sn']}:{name}"
            if self.seen.get(key) == stamp: return
            if str(task) == str(state.get('value')): return
            self.home.request_command(binding['local_id'], short, value, require_confirmation=False)
            self.seen[key] = stamp
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.seen), encoding='utf-8'); temporary.replace(self.state_path)
        with self.lock: self._status['commands_applied'] += 1

    def cycle(self, mode='read'):
        """One explicit cycle; no device creation, dictionary writes, or foreign devices."""
        if not self.transport: self._load()
        self.transport.authenticate()
        devices = []
        for binding in self.bindings:
            if self.stop_event.is_set(): break
            local_id = binding['local_id']
            row = {'family': binding['family'], 'local_id': local_id,
                'name': self.home.metadata[local_id]['name'] if local_id else binding['family'],
                'model': binding.get('model', ''), 'publish_class': binding.get('publish_class', ''),
                'serial_hint': '…' + str(binding['sn'])[-6:],
                'panel_signals': 0, 'api_signals': 0, 'writable_signals': 0, 'verified': 0,
                'state': 'unmapped' if not local_id else 'connected', 'signals': []}
            try:
                info = self.transport.device_info(binding)
                meta = info.get('meta') or {}
                if str(meta.get('serialnumber')) != str(binding['sn']):
                    raise UjinError('Ujin не подтвердил идентификатор выделенного устройства')
                if mode == 'sync':
                    remote_model = meta.get('model') or {}
                    remote_class = meta.get('class') or {}
                    if remote_model.get('name') != binding.get('model') or remote_class.get('name') != binding.get('publish_class'):
                        raise UjinError('Модель или класс устройства изменились; обновите настройки сопоставления')
                panel = self.transport.panel_signals(binding)
                api_signals = [s for s in info.get('signals') or [] if s.get('name') != 'dt_create' and not (s.get('name') or '').startswith('meta_')]
                row.update(panel_signals=len(panel), api_signals=len(api_signals),
                    writable_signals=sum((s.get('state') or {}).get('readonly') in (False, 0, '0') for s in api_signals))
                row['signals'] = [{k: s[k] for k in ('name', 'value', 'management')} for s in panel
                    if not re.search(r'(^|_)(token|password|passwd|secret|cookie|login)($|_)', s['name'], re.I)]
                if local_id:
                    if mode == 'sync':
                        for signal in api_signals:
                            if self.stop_event.is_set(): break
                            self._task(binding, signal)
                    with self.home.lock:
                        local = self.home.devices[local_id].signals
                        rows = {binding['signals'].get(name, binding['signal_prefix'] + name): sig.value
                                for name, sig in local.items() if sig.publishable and name != 'fw' and isinstance(sig.value, (int, float))}
                    available = {s['name']: s for s in panel}
                    rows = {name: value for name, value in rows.items() if name in available}
                    if mode == 'sync' and rows and not self.stop_event.is_set():
                        self.transport.publish(binding, rows)
                        # error=0 alone does not prove delivery. Verify in the panel.
                        confirmed = {s['name']: s for s in self.transport.panel_signals(binding)}
                        for name, value in rows.items():
                            try:
                                actual = numeric(confirmed.get(name, {}).get('value'))
                                if abs(actual - (0.001 if value == 0 else value)) < 0.00001:
                                    row['verified'] += 1
                            except UjinError: pass
                        if row['verified'] != len(rows): row['state'] = 'unverified'
                        with self.lock: self._status['published'] += row['verified']
                    if not rows: row['state'] = 'no_signals'
                    elif not row['writable_signals'] and row['state'] == 'connected': row['state'] = 'read_only'
            except UjinError as exc:
                row.update(state='error', message=str(exc))
            devices.append(row)
            with self.lock: self._status['devices'] = copy.deepcopy(devices)
        errors = any(d['state'] in ('error', 'unverified') for d in devices)
        with self.lock:
            self._status.update(state='error' if errors else 'connected', devices=devices, last_check=time.time(),
                message='Есть ошибки обмена' if errors else 'Учётная запись employee подключена. Устройства прочитаны.')
        self._notice(errors)
        return self.status()

    def start(self, mode='read', once=False):
        if mode not in ('read', 'sync'): raise UjinError('Неизвестный режим Ujin')
        with self.lock:
            if self.thread and self.thread.is_alive(): raise UjinError('Обмен уже выполняется; сначала остановите его')
            if not self.packet_path: raise UjinError('Не задан UJIN_CREDENTIALS_FILE на сервере')
            self.stop_event.clear()
            # The packet and mappings may change during final platform checks.
            # Every new run reloads them rather than retaining an old session.
            self.transport, self.bindings = None, []
            self._status.update(state='connecting', mode=mode, message='Подключаемся к Ujin…')
            def work():
                try:
                    while not self.stop_event.is_set():
                        try: self.cycle(mode)
                        except Exception as exc:
                            message = str(exc) if isinstance(exc, UjinError) else 'Ошибка адаптера Ujin; проверьте настройки подключения'
                            with self.lock: self._status.update(state='error', message=message)
                            self._notice(True)
                        if once or self.stop_event.wait(15): break
                finally:
                    if self.stop_event.is_set():
                        with self.lock: self._status.update(state='stopped', mode='off', message='Обмен остановлен')
            self.thread = threading.Thread(target=work, daemon=True, name='ujin-sync')
            self.thread.start()
        return self.status()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            self._status.update(state='stopping' if self.thread and self.thread.is_alive() else 'stopped', mode='off', message='Останавливаем обмен…')
        return self.status()
