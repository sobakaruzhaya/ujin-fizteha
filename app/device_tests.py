"""Deterministic, isolated diagnostics using the real emulator command path."""
from __future__ import annotations

import copy
import operator
import time
import uuid

COMPARE = {'==': operator.eq, '>': operator.gt, '<': operator.lt}


class Probe:
    def __init__(self, home, device_id):
        self.home, self.id = home, device_id
        self.device = home.devices[device_id]
        self.checks = []

    def value(self, signal):
        return self.device.signals[signal].value

    def command(self, signal, value):
        self.home.request_command(self.id, signal, value, require_confirmation=False)

    def tick(self, count=1):
        for _ in range(count):
            self.device.step(1)

    def expect(self, title, signal, expected, comparison='=='):
        actual = self.value(signal)
        self.checks.append({'title': title, 'signal': signal, 'actual': actual,
                            'expected': expected, 'comparison': comparison,
                            'passed': bool(COMPARE[comparison](actual, expected))})

    def rejected(self, title, signal, value):
        try:
            self.command(signal, value)
        except (ValueError, PermissionError):
            rejected = True
        else:
            rejected = False
        self.checks.append({'title': title, 'signal': signal, 'actual': rejected,
                            'expected': True, 'comparison': '==', 'passed': rejected})


def plug(p):
    p.command('power_switch', 1); p.tick()
    p.expect('Розетка подаёт питание', 'power_w', 0, '>')
    p.command('load_w', 2400); p.tick()
    p.expect('Защита распознаёт перегрузку', 'overload_alarm', 1)
    p.expect('Питание отключено защитой', 'power_switch', 0)
    p.rejected('Повторное включение заблокировано', 'power_switch', 1)
    p.command('load_w', 900); p.command('reset_protection', 1)
    p.command('power_switch', 1); p.tick()
    p.expect('Работа восстанавливается после сброса', 'power_w', 900)


def light(p):
    p.command('brightness', 50); p.command('lamp', 1); p.tick()
    p.expect('Яркость применяется', 'brightness', 50)
    p.expect('Мощность зависит от яркости', 'power_w', 6.0)
    p.expect('Расход энергии учитывается', 'energy_kwh', 0, '>')
    p.command('lamp', 0); p.tick()
    p.expect('Выключенный свет не потребляет энергию', 'power_w', 0)


def thermostat(p):
    p.device.set_value('temperature', 18)
    p.command('mode', 1); p.command('target_temp', 23); p.tick()
    p.expect('Обогрев включается ниже цели', 'output', 1)
    p.expect('Температура повышается', 'temperature', 18, '>')
    p.command('mode', 0); before = p.value('temperature'); p.tick(5)
    p.expect('Выключение останавливает обогрев', 'output', 0)
    p.expect('Выключенный датчик не обновляется', 'temperature', before)


def ventilation(p):
    p.device.set_value('co2', 1200)
    p.command('fan_speed', 4); p.tick()
    p.expect('Регулировка включает ручной режим', 'mode', 2)
    p.expect('Заданная скорость сохраняется', 'fan_speed', 4)
    p.expect('Вентиляция снижает CO₂', 'co2', 1200, '<')
    p.command('mode', 0); before = p.value('co2'); p.tick(5)
    p.expect('Вентилятор остановлен', 'fan_speed', 0)
    p.expect('Выключенный датчик не обновляется', 'co2', before)
    p.device.set_value('co2', 1500); p.command('mode', 1); p.tick()
    p.expect('Автоматический режим реагирует на CO₂', 'fan_speed', 0, '>')


def temperature_sensor(p):
    p.device.set_temperature(22); p.command('calibration', 1.5); p.tick()
    p.expect('Калибровка корректирует показания', 'temperature', 23.5)
    p.device.set_battery(10); p.tick()
    p.expect('Низкий заряд обнаружен', 'low_battery', 1)
    p.device.set_fault(True)
    p.expect('Неисправность отображается', 'fault', 1)


def leak(p):
    p.device.set_wet(True); p.tick()
    p.expect('Вода вызывает тревогу', 'leak', 1)
    p.command('self_test', 1); p.tick()
    p.expect('Самотест возвращает сухое состояние', 'leak', 0)
    p.device.set_battery(10); p.tick()
    p.expect('Низкий заряд обнаружен', 'low_battery', 1)


def hub(p):
    p.device.sensor(1).set_wet(True); p.tick()
    p.expect('Хаб получает сигнал датчика', 'leak', 1)
    p.expect('Сирена включается при протечке', 'siren', 1)
    p.command('mute', 1); p.tick()
    p.expect('Сирену можно заглушить', 'siren', 0)
    p.expect('Тревога сохраняется без звука', 'leak', 1)
    p.device.sensor(2).set_online(False); p.tick()
    p.expect('Потеря связи с датчиком учитывается', 'sensors_online', 2)


def fire(p):
    p.device.set_smoke(80); p.tick()
    p.expect('Дым вызывает тревогу', 'alarm', 1)
    p.expect('Дежурный режим прекращается', 'duty', 0)
    p.device.set_smoke(0); p.tick()
    p.expect('Тревога сохраняется до сброса', 'alarm', 1)
    p.command('reset_alarm', 1); p.tick()
    p.expect('Сброс снимает тревогу', 'alarm', 0)
    p.expect('Датчик возвращается в дежурный режим', 'duty', 1)


def counter(p):
    before = p.value('total'); p.tick(3)
    p.expect('Показание счётчика увеличивается', 'total', before, '>')
    p.expect('Текущая мощность измеряется', 'power_w', 0, '>')
    p.command('load_relay', 0); before = p.value('total'); p.tick(3)
    p.expect('Реле отключает нагрузку', 'power_w', 0)
    p.expect('После отключения расход не растёт', 'total', before)


def tv(p):
    p.command('power', 1); p.tick()
    p.expect('Включённый телевизор потребляет энергию', 'power_w', 0, '>')
    p.command('volume', 65); p.expect('Громкость применяется', 'volume', 65)
    p.command('child_max_volume', 40); p.command('child_lock', 1); p.command('volume', 90)
    p.expect('Родительский контроль ограничивает громкость', 'volume', 40)
    p.command('power', 0); p.tick()
    p.expect('Выключение прекращает потребление', 'power_w', 0)


def fridge(p):
    p.device.set_value('fridge_temp', 8); p.tick()
    p.expect('Компрессор включается при нагреве камеры', 'compressor', 1)
    p.expect('Камера охлаждается', 'fridge_temp', 8, '<')
    p.device.set_door_open(True); p.tick(61)
    p.expect('Открытая дверь вызывает тревогу', 'alarm', 2)
    p.device.set_door_open(False); p.device.set_value('fridge_temp', 4)
    p.device.set_value('freezer_temp', -18); p.tick()
    p.expect('После закрытия двери тревога снимается', 'alarm', 0)


def kettle(p):
    p.command('target_temp', 40); p.command('power', 1); p.tick()
    p.expect('Вода нагревается', 'temperature', 20, '>')
    p.tick(10)
    p.expect('Достижение цели включает автоотключение', 'auto_off', 1)
    p.expect('Нагрев прекращается', 'power', 0)
    p.command('water_level', 0); p.command('power', 1)
    p.expect('Защита обнаруживает сухой ход', 'dry_boil', 1)
    p.expect('Без воды включение заблокировано', 'power', 0)


def stove(p):
    p.command('burner_1', 5); p.tick()
    p.expect('Конфорка нагревается', 'power_w', 1250)
    p.command('pot_present', 0); p.tick()
    p.expect('Отсутствие посуды распознаётся', 'boil_dry', 1)
    p.expect('Нагрев без посуды прекращается', 'power_w', 0)
    p.command('pot_present', 1); p.command('child_lock', 1); p.command('burner_1', 5); p.tick()
    p.expect('Защита от детей блокирует конфорку', 'burner_1', 0)


def oven(p):
    p.command('power', 1); p.tick()
    p.expect('Духовка нагревается', 'temperature', 25, '>')
    p.expect('Предварительный нагрев включён', 'preheat', 1)
    p.device.set_door_open(True); p.tick()
    p.expect('Открытая дверь вызывает предупреждение', 'alarm', 1)
    p.expect('При открытой двери нагрев отключён', 'power_w', 0)
    p.device.set_door_open(False); p.command('timer', 2); p.tick(2)
    p.expect('Таймер отключает духовку', 'power', 0)


def intercom(p):
    p.command('unlock', 1)
    p.expect('Без вызова дверь не открывается', 'door_open', 0)
    p.device.ring(); p.tick()
    p.expect('Входящий вызов отображается', 'call_state', 1)
    p.command('answer', 1)
    p.expect('Можно ответить на вызов', 'call_state', 2)
    p.command('unlock', 1)
    p.expect('Во время разговора дверь открывается', 'door_open', 1)
    p.tick(3)
    p.expect('Дверь закрывается автоматически', 'door_open', 0)
    p.command('hangup', 1)
    p.expect('Разговор завершается', 'call_state', 0)


SUITES = {
    'smart_plug': ('Питание, перегрузка и восстановление', plug),
    'light': ('Яркость, мощность и выключение', light),
    'thermostat': ('Нагрев и остановка датчиков', thermostat),
    'ventilation': ('Скорость, очистка воздуха и автоматика', ventilation),
    'temp_sensor': ('Калибровка, батарея и неисправность', temperature_sensor),
    'leak': ('Протечка, самотест и батарея', leak),
    'hub': ('Сирена, отключение звука и связь', hub),
    'fire': ('Дым, фиксация тревоги и сброс', fire),
    'counter': ('Учёт расхода и отключение нагрузки', counter),
    'smart_tv': ('Питание, громкость и родительский контроль', tv),
    'fridge': ('Охлаждение и тревога открытой двери', fridge),
    'kettle': ('Нагрев, автоотключение и сухой ход', kettle),
    'stove': ('Конфорки, отсутствие посуды и блокировка', stove),
    'oven': ('Нагрев, открытая дверь и таймер', oven),
    'intercom': ('Вызов, разговор и открытие двери', intercom),
}


def catalog(home):
    with home.lock:
        return {'mode': 'isolated', 'devices': [
            {'id': key, **copy.deepcopy(meta), 'supported': meta['family'] in SUITES,
             'description': SUITES[meta['family']][0] if meta['family'] in SUITES else 'Проверка ещё не добавлена'}
            for key, meta in home.metadata.items() if key in home.devices]}


def run(home, device_id=None):
    devices = catalog(home)['devices']
    if device_id is not None:
        if not isinstance(device_id, str) or not any(d['id'] == device_id for d in devices):
            raise ValueError('Устройство для проверки не найдено')
        devices = [d for d in devices if d['id'] == device_id]
    results = []
    for item in devices:
        started = time.perf_counter()
        result = {'device': item['id'], 'name': item['name'], 'checks': [], 'status': 'unsupported'}
        suite = SUITES.get(item['family'])
        if suite:
            # No threads, persistent storage, live clients, or live scenarios.
            fixture = type(home)(tick_seconds=60)
            probe = Probe(fixture, item['id'])
            result['before'] = fixture._device_state(probe.device)
            try:
                suite[1](probe)
            except Exception as exc:
                probe.checks.append({'title': 'Выполнение проверки', 'passed': False,
                                     'error': f'{type(exc).__name__}: {exc}'})
            result['checks'] = probe.checks
            result['after'] = fixture._device_state(probe.device)
            result['status'] = 'passed' if probe.checks and all(c['passed'] for c in probe.checks) else 'failed'
        result['duration_ms'] = round((time.perf_counter() - started) * 1000, 2)
        results.append(result)
    return {'id': uuid.uuid4().hex, 'mode': 'isolated', 'finished_at': time.time(), 'results': results,
            'summary': {'total': len(results), 'passed': sum(r['status'] == 'passed' for r in results),
                        'failed': sum(r['status'] == 'failed' for r in results),
                        'unsupported': sum(r['status'] == 'unsupported' for r in results)}}
