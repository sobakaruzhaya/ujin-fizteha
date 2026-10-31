"""Telegram Bot API adapter without external dependencies.

The bot is a thin client of the same control plane as the web UI and MCP.
Device controls execute immediately like the web interface. Scenario drafts
are saved explicitly; destructive reset/delete operations have their own buttons.
"""
# ruff: noqa: BLE001 - the polling boundary must survive any Telegram/network error.
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from .home_client import ensure_client
    from .telegram_ui import TelegramUI, Context
    from .telegram_media import PhotoMessages, device_photo
except ImportError:  # script mode: python app/run.py
    from home_client import ensure_client
    from telegram_ui import TelegramUI, Context
    from telegram_media import PhotoMessages, device_photo

ICONS = {"plug": "🔌", "light": "💡", "climate": "🌡", "wind": "🌬"}
DEMO_LABELS = {
    "overload": "⚡ Перегрузка",
    "co2": "🌬 Высокий CO₂",
    "evening": "🌙 Вечерний режим",
}


class TelegramBot:

    def __init__(self, client, token=None, allowed_chat_ids=None, api=None, state_path=None):
        self.client = ensure_client(client)
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        prefix = self.token.partition(':')[0]
        self.bot_id = prefix if prefix.isdigit() else hashlib.sha256(self.token.encode()).hexdigest()[:16]
        raw = allowed_chat_ids if allowed_chat_ids is not None else os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
        self.allowed = {str(item.strip()) for item in raw.split(",") if item.strip()}
        self.allow_all = '*' in self.allowed
        self.allowed.discard('*')
        self.offset = 0
        self.running = False
        self._api_call = api or self._http_api
        self._notified_event_ids = set()
        self._notifications_primed = False
        self.sessions, self.actions, self.reports = {}, {}, {}
        self.photo_ids = {}
        self.subscribers = set(self.allowed)
        self.stop_event = threading.Event()
        self.state_lock = threading.RLock()
        self.delivery_lock = threading.RLock()
        self.last_delivery = {}
        self.state_path = Path(state_path) if state_path else (Path(__file__).parent / 'data/telegram-state.json' if api is None else None)
        self._seen_updates = set()
        self._previous_signals = {}
        self._pending_notifications = {}
        if self.state_path:
            try:
                saved = json.loads(self.state_path.read_text(encoding='utf-8'))
                if saved.get('bot_id') == self.bot_id:
                    self.offset = max(0, int(saved.get('offset', 0)))
                    self.subscribers = {str(c) for c in saved.get('subscribers', []) if self._authorized(c)}
                    photo_ids = saved.get('photos', {})
                    if isinstance(photo_ids, dict):
                        self.photo_ids = {str(k): v for k, v in photo_ids.items() if isinstance(v, str)}
            except (OSError, ValueError, TypeError): pass
        self.ui = TelegramUI(self)
        self.photos = PhotoMessages(self)

    @property
    def enabled(self):
        return bool(self.token and (self.allow_all or self.allowed))

    def save_state(self):
        if not self.state_path: return
        with self.state_lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'bot_id': self.bot_id, 'offset': self.offset, 'subscribers': sorted(self.subscribers), 'photos': self.photo_ids}), encoding='utf-8')
            temporary.replace(self.state_path)

    def button(self, *args, **kwargs): return self.ui.button(*args, **kwargs)
    def render(self, *args, **kwargs): return self.ui.render(*args, **kwargs)
    def send(self, *args, **kwargs): return self._send(*args, **kwargs)
    def home(self, ctx): return self.ui.home(ctx)
    def scenario_text(self, item): return self.ui.scenario_text(item)
    def scenario_photo(self, item): return self.ui.scenario_photo(item)
    def validate_value(self, signal, value): return self.ui.validate(signal, value)

    # ------------------------------------------------------------------ API
    def _http_api(self, method, payload=None, _retried=False):
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        fields = dict(payload or {})
        upload_field = 'photo' if 'photo' in fields else 'document'
        document = fields.get(upload_field)
        if isinstance(document, tuple): fields.pop(upload_field)
        else: document = None  # Existing file_id/URL values stay ordinary form fields.
        headers = {}
        if document:
            boundary = 'ujin' + secrets.token_hex(12)
            chunks = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
            filename, content = document
            content_type = 'image/jpeg' if upload_field == 'photo' else 'application/json'
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{upload_field}"; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'.encode() + content + b'\r\n')
            chunks.append(f'--{boundary}--\r\n'.encode())
            data = b''.join(chunks);headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
        else: data = urllib.parse.urlencode(fields).encode('utf-8')
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                result = json.loads(exc.read().decode("utf-8"))
            except ValueError:
                raise RuntimeError(f"Telegram HTTP {exc.code}") from None
        except (OSError, ValueError):
            raise RuntimeError('Telegram недоступен; соединение будет повторено') from None
        if not result.get("ok"):
            retry = (result.get('parameters') or {}).get('retry_after', 0)
            if not _retried and retry and retry <= 30 and not self.stop_event.wait(retry):
                return self._http_api(method, payload, _retried=True)
            raise RuntimeError('Telegram отклонил запрос: ' + str(result.get('error_code', 0)))
        return result

    def _api(self, method, payload=None):
        return self._api_call(method, payload)

    def _send(self, chat_id, text, keyboard=None):
        if len(str(text).encode('utf-16-le')) // 2 > 3500:
            chunks, current = [], ''
            for char in str(text):
                if len((current+char).encode('utf-16-le')) // 2 > 3500:
                    chunks.append(current);current = ''
                current += char
            chunks.append(current)
            for part in chunks[:-1]: self._send(chat_id, part)
            return self._send(chat_id, chunks[-1], keyboard)
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
        if keyboard:
            payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard},
                                                 ensure_ascii=False)
        return self._deliver('sendMessage', payload, chat_id)

    def _deliver(self, method, payload, chat_id):
        with self.delivery_lock:
            if self._api_call == self._http_api:
                delay = max(0, 0.35 - (time.monotonic() - self.last_delivery.get(str(chat_id), 0)))
                if delay: self.stop_event.wait(delay)
            result = self._api(method, payload)
            self.last_delivery[str(chat_id)] = time.monotonic()
            return result

    def _answer_callback(self, callback_id, text=None):
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            self._api("answerCallbackQuery", payload)
        except Exception as exc:
            print(f"telegram callback answer failed: {exc}", file=sys.stderr)

    def _authorized(self, chat_id):
        return self.allow_all or str(chat_id) in self.allowed

    # ------------------------------------------------------------ formatting
    @staticmethod
    def _layout_value(declaration, name, value):
        for signal in declaration:
            if signal.get("name") == name:
                layout = signal.get("layout") or {}
                try:
                    key = int(value)
                except (TypeError, ValueError):
                    return layout.get(value, value)
                if key in layout:
                    return layout[key]
                if str(key) in layout:  # JSON object keys arrive as strings over HTTP
                    return layout[str(key)]
                return layout.get(value, value)
        return value

    @staticmethod
    def _number(value):
        try:
            return f"{float(value):.3f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            return str(value)

    def _device_summary(self, device_id, data, declaration):
        if device_id == "smart_plug_1":
            state = "вкл" if data.get("power_switch") else "выкл"
            protection = "⚠️ сработала" if data.get("overload_alarm") else "нет"
            return (f"Реле: {state} · {self._number(data.get('power_w', 0))} Вт · "
                    f"{self._number(data.get('energy_kwh', 0))} кВт·ч · защита: {protection}")
        if device_id == "light_1":
            state = "вкл" if data.get("lamp") else "выкл"
            return (f"Свет: {state} · яркость: {self._number(data.get('brightness', 0))}% · "
                    f"{self._number(data.get('power_w', 0))} Вт")
        if device_id == "thermostat_1":
            mode = self._layout_value(declaration, "mode", data.get("mode", 0))
            return (f"{self._number(data.get('temperature', 0))} °C → "
                    f"{self._number(data.get('target_temp', 0))} °C · режим: {mode} · "
                    f"влажность: {self._number(data.get('humidity', 0))}%")
        if device_id == "ventilation_1":
            mode = self._layout_value(declaration, "mode", data.get("mode", 0))
            return (f"CO₂: {self._number(data.get('co2', 0))} ppm · "
                    f"PM2.5: {self._number(data.get('pm25', 0))} · режим: {mode} · "
                    f"скорость: {self._number(data.get('fan_speed', 0))}")
        return ' · '.join(f"{s['title']}: {self._number(data[s['name']])} {s.get('measure', '')}" for s in declaration if s['name'] in data and s['name'] in ('temperature','battery','power_w','alarm','water_level','call_state','fridge_temp'))

    def _status_text(self):
        state = self.client.state()
        declarations = self.client.declarations()
        devices = state.get("devices", {})
        metadata = state.get("metadata", {})
        lines = ["🏠 UjinFizteha", ""]
        for device_id, data in devices.items():
            meta = metadata.get(device_id, {})
            icon = ICONS.get(meta.get("icon"), "•")
            title = meta.get("name", device_id)
            room = meta.get("room", "")
            heading = f"{icon} {title}" + (f" · {room}" if room else "")
            lines.append(heading)
            lines.append("   " + self._device_summary(device_id, data,
                                                      declarations.get(device_id, [])))
            if device_id == "smart_plug_1" and data.get("overload_alarm"):
                lines.append("   ⚠️ Защита активна: сначала уменьшите нагрузку и сбросьте защиту")
            lines.append("")
        summary = state.get("summary", {})
        lines.append(f"Всего: {self._number(summary.get('power_w', 0))} Вт · "
                     f"{self._number(summary.get('energy_kwh', 0))} кВт·ч · "
                     f"сценариев активно: {summary.get('active_scenarios', 0)}")
        return "\n".join(lines)

    def _device_text(self, device_id):
        state = self.client.state()
        declarations = self.client.declarations()
        if device_id not in state.get("devices", {}):
            raise ValueError("Устройство не найдено")
        data = state["devices"][device_id]
        meta = state.get("metadata", {}).get(device_id, {})
        icon = ICONS.get(meta.get("icon"), "•")
        lines = [f"{icon} {meta.get('name', device_id)} · {meta.get('room', '')}", ""]
        declaration = declarations.get(device_id, [])
        for signal in declaration:
            name = signal.get("name")
            if name == "fw":
                continue
            value = data.get(name)
            if signal.get("layout"):
                value = self._layout_value(declaration, name, value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                value = self._number(value)
            measure = signal.get("measure", "")
            marker = "⚙️ " if signal.get("management") in ("rw", "w") else ""
            lines.append(f"{marker}{signal.get('title', name)}: {value} {measure}".rstrip())
        return "\n".join(lines)



    @staticmethod
    def _encode_id(value):
        return base64.urlsafe_b64encode(str(value).encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_id(value):
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding).decode("utf-8")





    # ------------------------------------------------------------ commands





    def _handle_callback(self, chat_id, callback):
        ctx = Context(str(chat_id), str(chat_id))
        parts = callback.get('data', '').split(':')
        if parts[0] == 'cmd' and len(parts) == 4:
            self.ui.apply(ctx, parts[1], parts[2], float(parts[3]))
        elif parts[0] == 'sc' and len(parts) == 3:
            self.client.toggle_scenario(self._decode_id(parts[1]), parts[2] == '1')
            self.ui.scenarios(ctx)
        elif parts[0] == 'demo' and len(parts) == 2:
            self.ui.dispatch(ctx, 'experiment', parts[1])
        elif parts[0] in ('status', 'devices', 'scenarios', 'demo', 'events', 'reset'):
            self.ui.dispatch(ctx, parts[0])
        elif parts[0] == 'dev' and len(parts) == 2:
            self.ui.device(ctx, parts[1])
        else:
            raise ValueError('Старое меню. /start — открыть новое')


    def handle_update(self, update):
        if 'edited_message' in update: return False
        callback = update.get("callback_query")
        message = (callback.get('message') if callback else update.get('message')) or {}
        if callback:
            chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
        else:
            chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None or not self._authorized(chat_id):
            return False
        update_id = update.get('update_id')
        if update_id is not None:
            if update_id in self._seen_updates: return False
            self._seen_updates.add(update_id)
            if len(self._seen_updates) > 2000: self._seen_updates = {update_id}
        user_id = ((callback or message).get('from') or {}).get('id', chat_id)
        ctx = Context(str(chat_id), str(user_id), message.get('message_id') if callback else None, bool(message.get('photo')))
        if callback:
            try:
                self._answer_callback(callback.get('id'))
                if callback.get('data','').startswith('b:'): self.ui.callback(ctx, callback['data'])
                else: self._handle_callback(chat_id, callback)
            except Exception as exc:
                error = 'Элемент уже удалён или недоступен' if isinstance(exc, StopIteration) else str(exc)
                if self.token: error = error.replace(self.token, '[скрыто]')
                self._send(chat_id, '❌ ' + error[:700] + '\n/cancel — отменить ввод')
                if self.sessions.get(ctx.actor, {}).get('kind') == 'scenario': self.ui.wizard.review(ctx)
            return True
        text = (message.get("text") or "").strip()
        if text:
            try: self.ui.message(ctx, text)
            except Exception as exc:
                error = str(exc).replace(self.token, '[скрыто]') if self.token else str(exc)
                self._send(chat_id, '❌ ' + error[:700] + '\nИсправьте ввод или отмените: /cancel')
            return True
        return False

    # --------------------------------------------------------- notifications
    def _notify_events(self):
        events = self.client.events(200)
        state = self.client.state()
        current = {(key, name): value for key, values in state['devices'].items() for name, value in values.items()
                   if name in ('alarm', 'fault', 'leak', 'overheat', 'dry_boil', 'boil_dry', 'low_battery', 'tamper')}
        if not self._notifications_primed:
            self._notified_event_ids = {event.get("id") for event in events if event.get("id")}
            self._notifications_primed = True
            self._previous_signals = current
            return
        fresh = []
        for event in events:
            event_id = event.get("id")
            if not event_id or event_id in self._notified_event_ids:
                continue
            self._notified_event_ids.add(event_id)
            if event.get('notification'):
                fresh.append(event)
            elif event.get("type") in {"alarm", "anomaly", "scenario_triggered", "error", "integration_connected",
                                     "device_started", "device_finished", "device_stopped"}:
                fresh.append(event)
            elif event.get('type') == 'command' and not event.get('notification_handled'):
                # Kettle power commands have one human-readable lifecycle event.
                # Other API/MCP commands must be delivered as well as scenario actions.
                if event.get('device') != 'kettle_1' or event.get('signal') != 'power':
                    fresh.append(event)
        declarations = None
        for (device, name), value in (current.items() if not state.get('notification_protocol') else []):
            if bool(value) != bool(self._previous_signals.get((device, name), 0)):
                if declarations is None: declarations = self.client.declarations()
                title = next((s['title'] for s in declarations.get(device, []) if s['name'] == name), name)
                fresh.append({'device':device,'message': f"{state['metadata'][device]['name']}: {title} — {'тревога / сбой' if value else 'состояние восстановлено'}"})
        self._previous_signals = current
        if len(self._notified_event_ids) > 1000:
            self._notified_event_ids = {event.get("id") for event in events[-100:]} | \
                set(list(self._notified_event_ids)[-500:])
        subscribers = {str(chat) for chat in tuple(self.subscribers) if self._authorized(chat)}
        for chat_id in tuple(self._pending_notifications):
            if chat_id not in subscribers: self._pending_notifications.pop(chat_id, None)
        for chat_id in subscribers:
            pending = self._pending_notifications.setdefault(chat_id, [])
            pending.extend(fresh)
            if not pending: continue
            batch = pending[:12]
            lines = []
            for event in batch:
                line = str(event.get('message') or event.get('type', 'Событие'))
                title = event.get('title')
                if title and title.casefold() not in line.casefold():
                    line = title + '\n' + line
                lines.append(line)
            message = '\n'.join(lines)
            try:
                devices={e.get('device') for e in batch if e.get('device')}
                self.ui.render(Context(chat_id,chat_id), '🔔 UjinFizteha\n' + message,
                    photo=device_photo(next(iter(devices))) if len(devices)==1 else device_photo(None))
                del pending[:len(batch)]
                print(f'telegram notification delivered: {len(batch)} events', file=sys.stderr, flush=True)
            except RuntimeError as exc:
                if '403' in str(exc):
                    with self.state_lock: self.subscribers.discard(chat_id);self.save_state()
                    self._pending_notifications.pop(chat_id, None)
                # Keep undelivered events for this subscriber; successful recipients
                # will not receive the batch again on the next poll.
                print('telegram alert delivery failed; queued for retry', file=sys.stderr)

    # --------------------------------------------------------------- runtime
    def run(self):
        if not self.enabled:
            print("Telegram bot disabled: set TELEGRAM_BOT_TOKEN and "
                  "TELEGRAM_ALLOWED_CHAT_IDS", file=sys.stderr)
            return
        self.running = True
        self.stop_event.clear()
        try:
            self._api("deleteWebhook")
            from_json = [{'command': command, 'description': description} for command, description in self.ui_commands()]
            self._api('setMyCommands', {'commands': json.dumps(from_json, ensure_ascii=False)})
        except Exception as exc:
            print(f"telegram deleteWebhook failed: {exc}", file=sys.stderr)
        backoff = 2
        def watch():
            while not self.stop_event.is_set():
                try: self._notify_events()
                except Exception: pass
                self.stop_event.wait(3)
        threading.Thread(target=watch, daemon=True, name='telegram-notifications').start()
        while self.running:
            try:
                result = self._api("getUpdates", {
                    "timeout": 15,
                    "offset": self.offset,
                    "allowed_updates": json.dumps(["message", "callback_query"]),
                })
                backoff = 2
                for update in result.get("result", []):
                    self.offset = max(self.offset, int(update.get("update_id", 0)) + 1)
                    self.save_state()
                    try:
                        self.handle_update(update)
                    except Exception as exc:
                        print(f"telegram update failed: {exc}", file=sys.stderr)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(f"telegram polling failed: {exc}", file=sys.stderr)
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 30)
        self.running = False

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.running = False
        self.stop_event.set()

    @staticmethod
    def ui_commands():
        try: from .telegram_ui import COMMANDS
        except ImportError: from telegram_ui import COMMANDS
        return COMMANDS
