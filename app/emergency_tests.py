"""Fault injection into isolated real emulators and explicit test-bench rules."""
from __future__ import annotations

import copy
import operator
import time
import uuid


class Stand:
    def __init__(self, home):
        self.home = type(home)(tick_seconds=60)
        self.home.scenarios.clear()
        self.home.events.clear()
        self.checks, self.timeline, self.rules = [], [], []
        self.seconds = 0
        self.network = False
        self.trace = []
        self.watched = []
        self.phase = 'Подготовка стенда'

    def readings(self):
        readings = []
        for device, signal in self.watched:
            sig = self.home.devices[device].signals[signal]
            readings.append({'device': device, 'source': self.home.metadata[device]['name'],
                'signal': signal, 'title': sig.title, 'value': sig.value,
                'label': sig.layout.get(sig.value) if sig.layout else None,
                'discrete': bool(sig.layout), 'measure': sig.measure})
        return readings

    def capture(self, event=None, checkpoint=False):
        if self.watched:
            self.trace.append({'seconds': self.seconds, 'title': self.phase,
                'event': event, 'checkpoint': checkpoint, 'readings': self.readings()})

    def value(self, device, signal):
        return self.home.devices[device].signals[signal].value

    def command(self, device, signal, value):
        result = self.home.request_command(device, signal, value, require_confirmation=False)
        sig = self.home.devices[device].signals[signal]
        self.capture(f"{self.home.metadata[device]['name']}: {sig.title} → {sig.layout.get(value, value) if sig.layout else value}")
        return result

    def tick(self, count=1):
        for _ in range(count):
            self.home.step()
            if self.network:
                # Circuit input is a modelled measurement: Counter itself does
                # not aggregate appliances or provide an overcurrent breaker.
                power = sum(self.value(d, 'power_w') for d in CIRCUIT)
                if not self.value('counter_1', 'load_relay'):
                    power = 0
                self.home.devices['counter_1'].set_value('power_w', power)
                self.home._evaluate_scenarios()
            self.seconds += 1
            self.capture()

    def rule(self, name, device, signal, value, actions, comparison='=='):
        self.home.create_scenario({'name': name, 'enabled': True,
            'when': {'device': device, 'signal': signal, 'operator': comparison, 'value': value},
            'do': [{'device': d, 'signal': s, 'value': v} for d, s, v in actions]})
        self.rules.append(name)

    def expect(self, title, device, signal, expected, comparison='=='):
        actual = self.value(device, signal)
        sig = self.home.devices[device].signals[signal]
        self.checks.append({'title': title, 'device': device, 'signal': signal,
            'source': self.home.metadata[device]['name'], 'signal_title': sig.title, 'measure': sig.measure,
            'actual': actual, 'expected': expected, 'comparison': comparison,
            'passed': bool({'==': operator.eq, '>': operator.gt, '<': operator.lt}[comparison](actual, expected))})

    def snapshot(self, title, signals):
        self.watched = signals
        self.phase = title
        self.capture(checkpoint=True)
        self.timeline.append({'title': title, 'seconds': self.seconds,
            'frame': len(self.trace) - 1, 'readings': self.readings()})


CIRCUIT = ['smart_plug_1', 'stove_1', 'oven_1', 'kettle_1']
KITCHEN_OFF = [('smart_plug_1', 'power_switch', 0), ('oven_1', 'power', 0),
               ('kettle_1', 'power', 0)] + [('stove_1', f'burner_{i}', 0) for i in range(1, 5)]


def socket_overload(p):
    signals = [('smart_plug_1', s) for s in ['load_w', 'power_w', 'overload_alarm', 'power_switch', 'energy_kwh']]
    p.command('smart_plug_1', 'power_switch', 1); p.tick()
    p.snapshot('До события', signals)
    p.phase = 'Постепенно повышаем нагрузку'
    for load in (1200, 1500, 1800, 1950):
        p.command('smart_plug_1', 'load_w', load); p.tick()
    p.command('smart_plug_1', 'load_w', 2400)
    p.snapshot('Нагрузка 2400 Вт при лимите 2000 Вт', signals)
    p.tick()
    p.expect('Розетка обнаружила перегрузку', 'smart_plug_1', 'overload_alarm', 1)
    p.expect('Встроенная защита разомкнула реле', 'smart_plug_1', 'power_switch', 0)
    p.expect('Потребление прекратилось', 'smart_plug_1', 'power_w', 0)
    p.snapshot('Реакция защиты', signals)
    p.phase = 'Снижаем нагрузку и сбрасываем защиту'
    p.command('smart_plug_1', 'load_w', 900)
    p.command('smart_plug_1', 'reset_protection', 1)
    p.command('smart_plug_1', 'power_switch', 1); p.tick()
    p.expect('После снижения нагрузки и сброса питание восстановилось', 'smart_plug_1', 'power_w', 900)
    p.snapshot('После восстановления', signals)


def network_overload(p):
    p.network = True
    p.rule('Отключение ввода при мощности выше 6000 Вт', 'counter_1', 'power_w', 6000,
           [('counter_1', 'load_relay', 0)] + KITCHEN_OFF, '>')
    signals = [('counter_1', 'power_w'), ('counter_1', 'load_relay'),
               ('stove_1', 'power_w'), ('oven_1', 'power_w'), ('kettle_1', 'power_w')]
    p.tick(); p.snapshot('До события', signals)
    p.phase = 'Поочерёдно включаем кухонную технику'
    p.command('smart_plug_1', 'power_switch', 1); p.tick()
    p.command('oven_1', 'power', 1); p.tick()
    p.command('kettle_1', 'power', 1); p.tick()
    p.command('stove_1', 'burner_1', 6); p.tick()
    p.command('stove_1', 'burner_2', 6)
    p.tick()
    p.expect('На вводе измерена суммарная перегрузка', 'counter_1', 'power_w', 6000, '>')
    p.expect('Правило стенда отключило вводное реле', 'counter_1', 'load_relay', 0)
    p.snapshot('Перегрузка: сработало правило стенда', signals)
    p.tick()
    p.expect('Мощность на вводе упала до нуля', 'counter_1', 'power_w', 0)
    for device, signal, value in KITCHEN_OFF:
        p.expect('Нагрузка отключена', device, signal, value)
    p.snapshot('Нагрузка отключена', signals)
    p.phase = 'Восстанавливаем ввод с нормальной нагрузкой'
    p.command('counter_1', 'load_relay', 1)
    p.command('smart_plug_1', 'power_switch', 1); p.tick()
    p.expect('После ручного включения нормальная нагрузка работает', 'counter_1', 'power_w', 900)
    p.snapshot('После восстановления', signals)


def fire(p):
    p.rule('Отключение техники при пожарной тревоге', 'fire_1', 'alarm', 1, KITCHEN_OFF)
    signals = [('fire_1', s) for s in ['smoke', 'alarm', 'duty', 'threshold']] + [('oven_1', 'power'), ('kettle_1', 'power')]
    p.command('oven_1', 'power', 1); p.command('kettle_1', 'power', 1)
    p.command('stove_1', 'burner_1', 5); p.tick()
    p.snapshot('До события', signals)
    p.phase = 'Повышаем задымление до порога тревоги'
    for smoke in (15, 30, 45, 55):
        p.home.devices['fire_1'].set_smoke(smoke); p.tick()
    p.home.devices['fire_1'].set_smoke(80); p.tick()
    p.expect('Датчик измерил задымление', 'fire_1', 'smoke', 80)
    p.expect('Пожарный датчик выдал тревогу', 'fire_1', 'alarm', 1)
    p.expect('Дежурный режим сменился тревогой', 'fire_1', 'duty', 0)
    for device, signal, value in KITCHEN_OFF:
        p.expect('Пожарное правило отключило технику', device, signal, value)
    p.snapshot('Пожарная тревога и отключение техники', signals)
    p.phase = 'Устраняем дым; тревога остаётся до сброса'
    p.home.devices['fire_1'].set_smoke(0); p.tick()
    p.expect('После рассеивания дыма тревога сохраняется до сброса', 'fire_1', 'alarm', 1)
    p.snapshot('Дым рассеялся, тревога зафиксирована', signals)
    p.command('fire_1', 'reset_alarm', 1); p.tick()
    p.expect('После сброса датчик вернулся в дежурный режим', 'fire_1', 'duty', 1)
    p.snapshot('После восстановления', signals)


def gas(p):
    from devices.gas import GasDetector
    p.home.devices['gas_test'] = GasDetector(serial='gas_test', logger=p.home._log)
    p.home.metadata['gas_test'] = {'name': 'Датчик газа · тестовая модель', 'room': 'Кухня', 'family': 'gas'}
    signals = [('gas_test', s) for s in ['concentration', 'threshold', 'alarm', 'siren']]
    p.tick(); p.snapshot('До события', signals)
    p.phase = 'Повышаем концентрацию газа'
    for concentration in (2, 5, 8):
        p.home.devices['gas_test'].set_concentration(concentration); p.tick()
    p.home.devices['gas_test'].set_concentration(25); p.tick()
    p.expect('Датчик измерил концентрацию газа', 'gas_test', 'concentration', 25)
    p.expect('Превышение порога вызвало тревогу', 'gas_test', 'alarm', 1)
    p.expect('Сирена включилась', 'gas_test', 'siren', 1)
    p.snapshot('Утечка газа: 25% НКПР при пороге 10%', signals)
    p.command('gas_test', 'reset_alarm', 1); p.tick()
    p.expect('Сброс не скрывает продолжающуюся утечку', 'gas_test', 'alarm', 1)
    p.phase = 'Устраняем газ; проверяем фиксацию тревоги'
    p.home.devices['gas_test'].set_concentration(0); p.tick()
    p.expect('Тревога сохраняется после исчезновения газа', 'gas_test', 'alarm', 1)
    p.snapshot('Газ рассеялся, тревога зафиксирована', signals)
    p.command('gas_test', 'reset_alarm', 1); p.tick()
    p.expect('После устранения утечки тревога сбрасывается', 'gas_test', 'alarm', 0)
    p.expect('После сброса сирена выключается', 'gas_test', 'siren', 0)
    p.snapshot('После восстановления', signals)


def water_leak(p):
    p.rule('Отключение розетки по сигналу хаба протечки', 'hub_1', 'leak', 1,
           [('smart_plug_1', 'power_switch', 0)])
    signals = [('leak_1', 'leak'), ('hub_1', 'leak'), ('hub_1', 'siren'), ('smart_plug_1', 'power_switch')]
    p.command('smart_plug_1', 'power_switch', 1); p.tick()
    p.snapshot('До события', signals)
    p.phase = 'Подаём воду на датчик и хаб'
    p.home.devices['leak_1'].set_wet(True)
    p.home.devices['hub_1'].sensor(1).set_wet(True); p.tick()
    p.expect('Контакт с водой обнаружен датчиком', 'leak_1', 'leak', 1)
    p.expect('Хаб получил сигнал от своего датчика', 'hub_1', 'leak', 1)
    p.expect('Сирена хаба включилась', 'hub_1', 'siren', 1)
    p.expect('Правило стенда отключило розетку', 'smart_plug_1', 'power_switch', 0)
    p.snapshot('Обнаружена протечка', signals)
    p.phase = 'Устраняем протечку'
    p.home.devices['leak_1'].set_wet(False)
    p.home.devices['hub_1'].sensor(1).set_wet(False); p.tick()
    p.expect('После высыхания датчик вернулся в норму', 'leak_1', 'leak', 0)
    p.expect('Сирена выключилась после высыхания', 'hub_1', 'siren', 0)
    p.expect('Питание само не возобновилось', 'smart_plug_1', 'power_switch', 0)
    p.snapshot('После устранения протечки', signals)


def high_co2(p):
    signals = [('ventilation_1', s) for s in ['co2', 'co2_target', 'fan_speed', 'mode']]
    p.command('ventilation_1', 'co2_target', 800)
    p.command('ventilation_1', 'mode', 1); p.tick()
    p.snapshot('До события', signals)
    p.phase = 'Повышаем CO₂; автоматика реагирует на показания'
    for concentration in (900, 1100, 1300):
        p.home.devices['ventilation_1'].set_value('co2', concentration)
        p.capture(); p.tick()
    p.home.devices['ventilation_1'].set_value('co2', 1500)
    p.snapshot('Повышение CO₂ до 1500 ppm', signals)
    p.tick()
    p.expect('Автоматика увеличила скорость вентилятора', 'ventilation_1', 'fan_speed', 3, '>')
    p.expect('Концентрация начала снижаться', 'ventilation_1', 'co2', 1500, '<')
    p.snapshot('Реакция автоматической вентиляции', signals)
    p.phase = 'Вентиляция очищает воздух'
    p.tick(20)
    p.expect('Вентиляция снизила CO₂ ниже 1000 ppm', 'ventilation_1', 'co2', 1000, '<')
    p.snapshot('После очистки воздуха', signals)


def dry_kettle(p):
    signals = [('kettle_1', s) for s in ['water_level', 'dry_boil', 'power', 'power_w']]
    p.tick(); p.snapshot('До события', signals)
    p.phase = 'Сливаем воду и пробуем включить нагрев'
    p.command('kettle_1', 'water_level', 0)
    p.command('kettle_1', 'power', 1); p.tick()
    p.expect('Защита обнаружила отсутствие воды', 'kettle_1', 'dry_boil', 1)
    p.expect('Нагрев заблокирован', 'kettle_1', 'power', 0)
    p.expect('Потребление отсутствует', 'kettle_1', 'power_w', 0)
    p.snapshot('Попытка нагрева без воды', signals)
    p.phase = 'Доливаем воду и сбрасываем защиту'
    p.command('kettle_1', 'water_level', 80); p.command('kettle_1', 'reset', 1)
    p.command('kettle_1', 'power', 1); p.tick()
    p.expect('С водой нагрев возобновился', 'kettle_1', 'power_w', 0, '>')
    p.expect('Ошибка сухого хода сброшена', 'kettle_1', 'dry_boil', 0)
    p.snapshot('После восстановления', signals)


def sensor_fault(p):
    signals = [('thermostat_1', s) for s in ['temperature', 'fault', 'output', 'mode']]
    p.home.devices['thermostat_1'].set_value('temperature', 18)
    p.command('thermostat_1', 'target_temp', 23); p.command('thermostat_1', 'mode', 1); p.tick()
    p.snapshot('До события: обогрев', signals)
    p.phase = 'Имитируем неисправность температурного датчика'
    p.home.devices['thermostat_1'].set_fault(True)
    before = p.value('thermostat_1', 'temperature'); p.tick(3)
    p.expect('Неисправность датчика отображается', 'thermostat_1', 'fault', 1)
    p.expect('Обогрев прекращён при потере данных', 'thermostat_1', 'output', 0)
    p.expect('Ошибочные измерения не генерируются', 'thermostat_1', 'temperature', before)
    p.snapshot('Датчик неисправен, обогрев остановлен', signals)
    p.phase = 'Восстанавливаем датчик'
    p.home.devices['thermostat_1'].set_fault(False); p.tick()
    p.expect('После восстановления датчика обогрев возобновился', 'thermostat_1', 'output', 1)
    p.snapshot('После восстановления', signals)


CASES = {
    'socket-overload': {'name': 'Перегрузка розетки', 'category': 'Электросеть', 'image': 'plug',
        'description': 'Нагрузка 2400 Вт при лимите розетки 2000 Вт.',
        'expected': 'Тревога перегрузки, отключение реле и восстановление после сброса.',
        'mechanism': 'Встроенная защита розетки', 'run': socket_overload},
    'network-overload': {'name': 'Перегрузка сети', 'category': 'Электросеть', 'image': 'counter',
        'description': 'Одновременная работа розетки, плиты, духовки и чайника: 7200 Вт на вводе кухни.',
        'expected': 'Измерение нагрузки и отключение ввода при превышении 6000 Вт.',
        'mechanism': 'Модель ввода + тестовое правило отключения', 'run': network_overload},
    'fire': {'name': 'Пожар', 'category': 'Безопасность', 'image': 'fire',
        'description': 'Задымление 80% при пороге пожарного датчика 60%.',
        'expected': 'Пожарная тревога, отключение кухонной техники; тревога сохраняется до сброса.',
        'mechanism': 'Пожарный датчик + тестовое правило отключения', 'run': fire},
    'gas-leak': {'name': 'Утечка газа', 'category': 'Безопасность', 'image': None,
        'description': 'Концентрация газа 25% НКПР при пороге тревоги 10%.',
        'expected': 'Тревога и сирена. Сброс заблокирован, пока концентрация выше порога.',
        'mechanism': 'Тестовая модель датчика газа',
        'note': 'В текущем доме датчика газа нет. Здесь проверяется отдельная тестовая модель; CO₂ не используется как датчик газа.', 'run': gas},
    'water-leak': {'name': 'Протечка воды', 'category': 'Безопасность', 'image': 'leak',
        'description': 'Вода попадает на отдельный датчик протечки и первый датчик хаба.',
        'expected': 'Датчики обнаруживают воду, хаб включает сирену, правило отключает розетку.',
        'mechanism': 'Датчики протечки + тестовое правило отключения', 'run': water_leak},
    'high-co2': {'name': 'Высокий уровень CO₂', 'category': 'Воздух', 'image': 'ventilation',
        'description': 'Рост CO₂ до 1500 ppm при целевом уровне 800 ppm.',
        'expected': 'Вентиляция увеличивает скорость и снижает CO₂ ниже 1000 ppm.',
        'mechanism': 'Встроенная автоматика вентиляции', 'run': high_co2},
    'dry-kettle': {'name': 'Чайник без воды', 'category': 'Защита техники', 'image': 'kettle',
        'description': 'Попытка включить нагрев при уровне воды 0%.',
        'expected': 'Сигнал сухого хода, блокировка нагрева и нулевая мощность.',
        'mechanism': 'Встроенная защита чайника', 'run': dry_kettle},
    'sensor-fault': {'name': 'Отказ датчика температуры', 'category': 'Защита техники', 'image': 'thermostat',
        'description': 'Неисправность датчика термостата во время обогрева.',
        'expected': 'Ошибка датчика, остановка нагрева и прекращение измерений.',
        'mechanism': 'Встроенная защита термостата', 'run': sensor_fault},
}

# Plot configuration describes actual signals and test-bench rule thresholds.
VISUALIZATIONS = {
    'socket-overload': {'primary': ['smart_plug_1', 'load_w'], 'secondary': ['smart_plug_1', 'power_w'],
        'threshold': {'value': 2000, 'title': 'Лимит розетки'}},
    'network-overload': {'primary': ['counter_1', 'power_w'],
        'threshold': {'value': 6000, 'title': 'Порог отключения ввода'}},
    'fire': {'primary': ['fire_1', 'smoke'], 'threshold': {'value': 60, 'title': 'Порог тревоги'}},
    'gas-leak': {'primary': ['gas_test', 'concentration'], 'threshold': {'value': 10, 'title': 'Порог тревоги'}},
    'water-leak': {'primary': ['leak_1', 'leak']},
    'high-co2': {'primary': ['ventilation_1', 'co2'], 'threshold': {'value': 800, 'title': 'Целевой CO₂', 'target': True}},
    'dry-kettle': {'primary': ['kettle_1', 'water_level']},
    'sensor-fault': {'primary': ['thermostat_1', 'temperature']},
}


def catalog(home):
    return {'mode': 'isolated', 'tests': [
        {'id': key, **{k: v for k, v in item.items() if k != 'run'}, 'supported': True}
        for key, item in CASES.items()]}


def run(home, case_id=None):
    if case_id is not None and (not isinstance(case_id, str) or case_id not in CASES):
        raise ValueError('Аварийный тест не найден')
    results = []
    for key in ([case_id] if case_id is not None else CASES):
        item = CASES[key]
        started = time.perf_counter()
        p = Stand(home)
        try:
            item['run'](p)
        except Exception as exc:
            p.checks.append({'title': 'Выполнение теста', 'passed': False,
                             'error': f'{type(exc).__name__}: {exc}'})
        results.append({'id': key, 'name': item['name'], 'checks': p.checks,
            'status': 'passed' if p.checks and all(c['passed'] for c in p.checks) else 'failed',
            'timeline': p.timeline, 'rules': p.rules, 'mechanism': item['mechanism'],
            'trace': p.trace, 'visualization': copy.deepcopy(VISUALIZATIONS[key]),
            'events': copy.deepcopy([e for e in p.home.events if e['type'] in ('alarm', 'scenario_triggered', 'command')]),
            'simulated_seconds': p.seconds, 'duration_ms': round((time.perf_counter() - started) * 1000, 2)})
    return {'id': uuid.uuid4().hex, 'mode': 'isolated', 'finished_at': time.time(), 'results': results,
        'summary': {'total': len(results), 'passed': sum(r['status'] == 'passed' for r in results),
                    'failed': sum(r['status'] == 'failed' for r in results)}}
