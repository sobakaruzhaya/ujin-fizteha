"""Isolated gas detector model. Concentration is % LEL, not CO2 ppm."""
from core import Device, Signal


class GasDetector(Device):
    model = 'emul_gas_detector'
    title = 'Датчик газа (тестовая модель)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._concentration = 0.0
        self._latched = False
        self.add_signal(Signal('concentration', 'Концентрация газа', 'graph', 'r',
                               'property', 0.0, '% НКПР', 0, 100))
        self.add_signal(Signal('threshold', 'Порог тревоги', 'range', 'rw',
                               'setting', 10, '% НКПР', 1, 100))
        self.add_signal(Signal('alarm', 'Утечка газа', 'list', 'r', 'property', 0,
                               layout={0: 'Нет', 1: 'Тревога'}, zero_safe=True))
        self.add_signal(Signal('siren', 'Сирена', 'list', 'r', 'property', 0,
                               layout={0: 'Выключена', 1: 'Включена'}, zero_safe=True))
        self.add_signal(Signal('reset_alarm', 'Сброс тревоги', 'button', 'w', 'capability', 0))

    def set_concentration(self, value):
        self._concentration = float(self.clamp('concentration', value))

    def on_command(self, name, value):
        if name == 'reset_alarm' and value:
            # A reset cannot mask a continuing leak.
            if self._concentration < self.signals['threshold'].value:
                self._latched = False
            self.set_value('reset_alarm', 0)

    def tick(self, dt):
        self.set_value('concentration', self._concentration)
        if self._concentration >= self.signals['threshold'].value:
            self._latched = True
        self.set_value('alarm', int(self._latched))
        self.set_value('siren', int(self._latched))
