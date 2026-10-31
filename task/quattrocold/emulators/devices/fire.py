"""Пожарный датчик (тип ИП 212/64 по fs_* моделям) — семейство «ПОЖС».

Свойства: задымлённость, дежурный режим, тампер, батарея, последняя связь;
возможность: самотест и сброс тревоги; настройка: порог срабатывания.
"""
from __future__ import annotations

from core import Device, Signal


class FireDetector(Device):
    model = "emul_fire_detector"
    title = "Пожарный датчик"

    def __init__(self, *args, threshold: int = 60, battery_drain: float = 0.005,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.battery_drain = float(battery_drain)
        self._smoke = 5
        self._latched = False
        self.add_signal(Signal("smoke", "Задымлённость", "graph", "r", "property",
                               5, "%", 0, 100))
        self.add_signal(Signal("alarm", "Пожар", "list", "r", "property", 0,
                               layout={0: "нет", 1: "ЕСТЬ"}, zero_safe=True))
        self.add_signal(Signal("duty", "Дежурный режим", "list", "r", "property", 1,
                               layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("tamper", "Вскрытие корпуса", "list", "r", "property", 0,
                               layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("battery", "Батарея", "graph", "r", "property", 100, "%", 0, 100))
        self.add_signal(Signal("low_battery", "Низкий заряд", "list", "r", "property", 0,
                               layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("last_seen", "Последняя связь", "counter", "r", "property", 0))
        self.add_signal(Signal("fault", "Неисправность", "list", "r", "property", 0,
                               layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("threshold", "Порог срабатывания", "counter", "rw",
                               "setting", threshold, "%", 10, 95))
        self.add_signal(Signal("self_test", "Самотест", "button", "w", "capability", 0))
        self.add_signal(Signal("reset_alarm", "Сбросить тревогу", "button", "w",
                               "capability", 0))

    def set_smoke(self, level: int) -> None:
        """Рука демо: подать дым (0..100)."""
        self._smoke = max(0, min(100, int(level)))

    def set_battery(self, value: float) -> None:
        self.set_value("battery", max(0.0, min(100.0, float(value))))

    def set_tamper(self, value: bool) -> None:
        self.set_value("tamper", 1 if value else 0)

    def set_fault(self, value: bool) -> None:
        self.set_value("fault", 1 if value else 0)

    def on_command(self, name, value) -> None:
        if name == "threshold":
            self.set_value("threshold", self.clamp("threshold", float(value)))
        elif name == "self_test" and int(value):
            healthy = not int(self.signals["fault"].value) and \
                not int(self.signals["low_battery"].value)
            self.log(f"[{self.model}] самотест: {'пройден' if healthy else 'ошибка'}")
            self.set_value("self_test", 0)
        elif name == "reset_alarm" and int(value):
            self._latched = False
            self.set_value("alarm", 0)
            self.set_value("reset_alarm", 0)
            self.log(f"[{self.model}] тревога сброшена")

    def tick(self, dt: int) -> None:
        self.set_value("smoke", self._smoke)
        threshold = int(self.signals["threshold"].value)
        if self._smoke >= threshold:
            self._latched = True
        alarm = self._latched or int(self.signals["tamper"].value) or \
            int(self.signals["fault"].value)
        self.set_value("alarm", 1 if alarm else 0)
        self.set_value("duty", 0 if alarm else 1)
        battery = float(self.signals["battery"].value) - self.battery_drain * dt
        self.set_value("battery", round(max(0.0, battery), 2))
        self.set_value("low_battery", 1 if self.signals["battery"].value <= 15 else 0)
        self.set_value("last_seen", self.tick_count)
        if self._smoke > 0:
            self._smoke = max(0, self._smoke - 1)
