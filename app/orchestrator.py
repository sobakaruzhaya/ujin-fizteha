"""Shared home runtime for web, Telegram and MCP clients."""
from __future__ import annotations

import copy
import json
import math
import operator
import os
from pathlib import Path
import sys
import threading
import time
import uuid

EMU_DIR = str(Path(__file__).resolve().parent.parent / 'task/quattrocold/emulators')
if EMU_DIR not in sys.path:
    sys.path.insert(0, EMU_DIR)
from devices.smart_plug import SmartPlug
from devices.light import Light
from devices.thermostat import Thermostat
from devices.ventilation import Ventilation

OPERATORS = {'>': operator.gt, '<': operator.lt, '>=': operator.ge,
             '<=': operator.le, '==': operator.eq, '!=': operator.ne}


class Orchestrator:
    def __init__(self, tick_seconds=1.0, storage_path=None):
        self.lock = threading.RLock()
        self.events, self.history, self.confirmations = [], [], {}
        self.scenarios = {}
        self._edges = {}
        self.tick_seconds = tick_seconds
        self.storage_path = Path(storage_path) if storage_path else None
        self._stop = threading.Event()
        self._thread = None
        self._make_devices()
        self.scenarios = {'overload_protection': {
            'id': 'overload_protection', 'name': 'Защита от перегрузки', 'enabled': True,
            'when': {'device': 'smart_plug_1', 'signal': 'power_w', 'operator': '>', 'value': 2000},
            'do': [{'device': 'smart_plug_1', 'signal': 'power_switch', 'value': 0}]}}
        if self.storage_path and self.storage_path.exists():
            try:
                saved = json.loads(self.storage_path.read_text(encoding='utf-8'))
                for item in saved:
                    self._validate_scenario(item)
                self.scenarios = {s['id']: s for s in saved}
            except (ValueError, KeyError, TypeError, OSError):
                self.add_event('error', message='Не удалось прочитать сохранённые сценарии. Загружены стандартные.')
        self._last_values = self._device_state(self.device)

    def _make_devices(self):
        self.devices = {
            'smart_plug_1': SmartPlug(serial='smart_plug_1', logger=self._log),
            'light_1': Light(serial='light_1', logger=self._log),
            'thermostat_1': Thermostat(serial='thermostat_1', logger=self._log),
            'ventilation_1': Ventilation(serial='ventilation_1', logger=self._log)}
        self.device = self.devices['smart_plug_1']  # compatibility with Telegram/MCP
        self.metadata = {
            'smart_plug_1': {'name': 'Умная розетка', 'room': 'Кухня', 'family': 'smart_plug', 'icon': 'plug'},
            'light_1': {'name': 'Основной свет', 'room': 'Гостиная', 'family': 'light', 'icon': 'light'},
            'thermostat_1': {'name': 'Термостат', 'room': 'Гостиная', 'family': 'thermostat', 'icon': 'climate'},
            'ventilation_1': {'name': 'Приточная вентиляция', 'room': 'Спальня', 'family': 'ventilation', 'icon': 'wind'}}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while not self._stop.wait(self.tick_seconds):
            self.step()

    def step(self):
        with self.lock:
            for device in self.devices.values():
                device.step(1)
            self._evaluate_scenarios()
            self._observe_state()
            self.history.append({'time': time.time(), 'power_w': self.total_power(),
                                 'co2': self.devices['ventilation_1'].signals['co2'].value})
            self.history = self.history[-300:]

    def _log(self, message):
        self.add_event('log', message=message)

    def add_event(self, event_type, **payload):
        with self.lock:
            event = {'id': uuid.uuid4().hex[:10], 'time': time.time(), 'type': event_type, **payload}
            self.events.append(event)
            self.events = self.events[-200:]
            return copy.deepcopy(event)

    def _observe_state(self):
        if not self.device.signals['power_switch'].value:
            self.device.set_value('power_w', 0.0)
            self.device.set_value('current_a', 0.0)
        current = self._device_state(self.device)
        if current['overload_alarm'] == 1 and self._last_values['overload_alarm'] != 1:
            self.add_event('alarm', device='smart_plug_1', message='Розетка отключена: превышен лимит мощности. Уменьшите нагрузку перед сбросом защиты.')
        if current['power_switch'] != self._last_values['power_switch']:
            self.add_event('state_change', device='smart_plug_1', signal='power_switch', value=current['power_switch'])
        self._last_values = current

    @staticmethod
    def _device_state(device):
        return {name: sig.value for name, sig in device.signals.items()}

    def total_power(self):
        return round(sum(float(d.signals['power_w'].value) for d in self.devices.values() if 'power_w' in d.signals), 1)

    def state(self):
        with self.lock:
            return {'devices': {key: self._device_state(d) for key, d in self.devices.items()},
                    'metadata': copy.deepcopy(self.metadata), 'updated_at': time.time(),
                    'mode': 'emulation', 'summary': {'power_w': self.total_power(),
                    'energy_kwh': round(sum(d.signals['energy_kwh'].value for d in self.devices.values() if 'energy_kwh' in d.signals), 6),
                    'active_scenarios': sum(s['enabled'] for s in self.scenarios.values())}}

    def declarations(self):
        with self.lock:
            return {key: d.declaration() for key, d in self.devices.items()}

    def events_since(self, limit=50):
        with self.lock:
            return copy.deepcopy(self.events[-max(1, min(int(limit), 200)):])

    def list_scenarios(self):
        with self.lock:
            return copy.deepcopy(list(self.scenarios.values()))

    def _save(self):
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.storage_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(list(self.scenarios.values()), ensure_ascii=False), encoding='utf-8')
            temporary.replace(self.storage_path)

    def _validate_command(self, device_id, signal, value):
        if device_id not in self.devices or signal not in self.devices[device_id].signals:
            raise ValueError('Устройство или сигнал не найдены')
        target = self.devices[device_id].signals[signal]
        if not target.writable:
            raise ValueError('Сигнал доступен только для чтения')
        self._number(value)
        if target.minimum is not None and value < target.minimum or target.maximum is not None and value > target.maximum:
            raise ValueError('Значение вне допустимого диапазона')
        if target.layout and value not in target.layout:
            raise ValueError('Недопустимый режим')
        if target.control == 'button' and value != 1:
            raise ValueError('Кнопка принимает значение 1')

    @staticmethod
    def _number(value):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError('Ожидается конечное число')

    def _validate_scenario(self, item):
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Введите название сценария')
        if not isinstance(item.get('enabled', True), bool):
            raise ValueError('enabled должен быть логическим значением')
        when = item.get('when', {})
        if not isinstance(when, dict) or when.get('device') not in self.devices or when.get('signal') not in self.devices[when['device']].signals:
            raise ValueError('Выберите сигнал условия')
        if when.get('operator') not in OPERATORS:
            raise ValueError('Неизвестный оператор сравнения')
        self._number(when.get('value'))
        if not isinstance(item.get('do'), list) or not item['do']:
            raise ValueError('Добавьте действие')
        for action in item['do']:
            self._validate_command(action.get('device'), action.get('signal'), action.get('value'))

    def create_scenario(self, scenario):
        with self.lock:
            self._validate_scenario(scenario)
            key = str(scenario.get('id') or uuid.uuid4().hex[:8])
            item = {'id': key, 'name': scenario['name'].strip()[:120], 'enabled': scenario.get('enabled', True),
                    'when': copy.deepcopy(scenario['when']), 'do': copy.deepcopy(scenario['do'])}
            self.scenarios[key] = item
            self._edges.pop(key, None)
            self._save()
            self.add_event('scenario_saved', name=item['name'], message='Сохранён сценарий «' + item['name'] + '»')
            return copy.deepcopy(item)

    def toggle_scenario(self, scenario_id, enabled=None):
        with self.lock:
            if scenario_id not in self.scenarios:
                raise ValueError('Сценарий не найден')
            if enabled is not None and not isinstance(enabled, bool):
                raise ValueError('enabled должен быть логическим значением')
            s = self.scenarios[scenario_id]
            s['enabled'] = not s['enabled'] if enabled is None else enabled
            self._edges.pop(scenario_id, None)
            self._save()
            self.add_event('scenario_toggled', message=('Включён' if s['enabled'] else 'Отключён') + ' сценарий «' + s['name'] + '»')
            return copy.deepcopy(s)

    def delete_scenario(self, scenario_id):
        with self.lock:
            if scenario_id not in self.scenarios:
                raise ValueError('Сценарий не найден')
            s = self.scenarios.pop(scenario_id)
            self._edges.pop(scenario_id, None)
            self._save()
            self.add_event('scenario_deleted', message='Удалён сценарий «' + s['name'] + '»')
            return {'status': 'deleted'}

    @staticmethod
    def _compare(left, op, right):
        return OPERATORS[op](left, right)

    def _evaluate_scenarios(self):
        for key, s in self.scenarios.items():
            w = s['when']
            matched = s['enabled'] and self._compare(self.devices[w['device']].signals[w['signal']].value, w['operator'], w['value'])
            if matched and not self._edges.get(key):
                self.add_event('scenario_triggered', scenario_id=key, message='Сработал сценарий «' + s['name'] + '»')
                for a in s['do']:
                    try:
                        self._apply_command(a['device'], a['signal'], a['value'], source='scenario')
                    except (ValueError, PermissionError) as exc:
                        self.add_event('error', message=str(exc))
            self._edges[key] = matched

    def _apply_command(self, device_id, signal, value, source='api'):
        self._validate_command(device_id, signal, value)
        d = self.devices[device_id]
        if device_id == 'smart_plug_1' and signal == 'power_switch' and value and d.protected:
            raise PermissionError('Сначала уменьшите нагрузку и сбросьте защиту')
        if device_id == 'smart_plug_1' and signal == 'reset_protection' and d.signals['load_w'].value > d.signals['power_limit_w'].value:
            raise PermissionError('Сначала уменьшите нагрузку ниже лимита')
        d.set_value(signal, value)
        d.on_command(signal, value)
        self.add_event('command', device=device_id, signal=signal, value=value, source=source,
                       message=f"{self.metadata[device_id]['name']}: {d.signals[signal].title} → {value}")
        return {'device': device_id, 'signal': signal, 'value': d.signals[signal].value}

    def request_command(self, device_id, signal, value, require_confirmation=True):
        with self.lock:
            self._validate_command(device_id, signal, value)
            if require_confirmation:
                now = time.time()
                self.confirmations = {k: v for k, v in self.confirmations.items() if v['expires'] > now}
                token = uuid.uuid4().hex
                self.confirmations[token] = {'expires': now + 60, 'device': device_id, 'signal': signal, 'value': value}
                return {'status': 'confirmation_required', 'confirmation_id': token, 'expires_in': 60,
                        'summary': f"{self.metadata[device_id]['name']}: {self.devices[device_id].signals[signal].title} → {value}"}
            return {'status': 'applied', **self._apply_command(device_id, signal, value)}

    def confirm_command(self, token):
        with self.lock:
            req = self.confirmations.pop(token, None)
            if not req or req['expires'] < time.time():
                raise PermissionError('confirmation expired — запросите команду повторно')
            return {'status': 'applied', **self._apply_command(req['device'], req['signal'], req['value'], 'confirmation')}

    def reset(self):
        with self.lock:
            self._make_devices()
            self.confirmations.clear()
            self._edges.clear()
            self.history.clear()
            self._last_values = self._device_state(self.device)
            self.add_event('reset', message='Состояние эмуляторов сброшено. Сценарии сохранены.')
            return self.state()

    def experiment(self, preset):
        with self.lock:
            if preset == 'overload':
                if self.device.protected:
                    raise ValueError('Сбросьте лабораторию перед повторным запуском')
                self.device.set_value('load_w', 2400)
                self._apply_command('smart_plug_1', 'power_switch', 1, 'lab')
            elif preset == 'co2':
                self.devices['ventilation_1'].set_value('co2', 1500)
                self._apply_command('ventilation_1', 'mode', 1, 'lab')
            elif preset == 'evening':
                self._apply_command('light_1', 'lamp', 1, 'lab')
                self._apply_command('light_1', 'brightness', 35, 'lab')
                self._apply_command('thermostat_1', 'target_temp', 23, 'lab')
            else:
                raise ValueError('Неизвестный эксперимент')
            self.add_event('demo_started', message={'overload': 'Тест перегрузки: нагрузка 2400 Вт', 'co2': 'Тест воздуха: CO₂ 1500 ppm', 'evening': 'Вечер: приглушённый свет и температура 23 °C'}[preset])
            return {'status': 'started'}

    def simulate(self, seconds=10, scenario=None):
        """Run an isolated clone; no live timers, logs, edges or clients are touched."""
        with self.lock:
            clone = Orchestrator()
            clone.devices = copy.deepcopy(self.devices, {id(self): clone})
            for d in clone.devices.values():
                d.client = None
                d.log = clone._log
            clone.device = clone.devices['smart_plug_1']
            clone.scenarios = copy.deepcopy(self.scenarios)
            if scenario is not None:
                clone._validate_scenario(scenario)
                item = copy.deepcopy(scenario)
                item['id'] = str(item.get('id') or 'preview')
                clone.scenarios[item['id']] = item
            clone._last_values = self._device_state(clone.device)
            for _ in range(max(1, min(int(seconds), 120))):
                clone.step()
            return {'state': clone.state(), 'events': clone.events_since(200), 'history': clone.history}
