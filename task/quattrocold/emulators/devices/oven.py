"""Умная духовка: режимы, предварительный нагрев, таймер и защита."""
from __future__ import annotations

from core import Device, Signal

MODES = {0: "Верх", 1: "Низ", 2: "Конвекция", 3: "Гриль"}


class Oven(Device):
    model = "emul_oven"
    title = "Умная духовка"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._residual_ticks = 0
        self.add_signal(Signal("power", "Питание", "switch", "rw", "capability",
                               0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("temperature", "Температура", "graph", "r", "property",
                               25.0, "°C"))
        self.add_signal(Signal("target_temp", "Целевая температура", "range", "rw",
                               "setting", 180.0, "°C", 50, 250))
        self.add_signal(Signal("mode", "Режим", "list", "rw", "capability", 2, layout=MODES,
                               zero_safe=True))
        self.add_signal(Signal("timer", "Таймер, с", "counter", "rw", "setting",
                               0, "с", 0, 7200, zero_safe=True))
        self.add_signal(Signal("door_open", "Дверь открыта", "list", "r", "property",
                               0, layout={0: "закрыта", 1: "открыта"}, zero_safe=True))
        self.add_signal(Signal("preheat", "Предварительный нагрев", "list", "r", "property",
                               0, layout={0: "готово", 1: "нагрев"}, zero_safe=True))
        self.add_signal(Signal("child_lock", "Защита от детей", "switch", "rw",
                               "capability", 0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("residual_heat", "Остаточное тепло", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("alarm", "Тревога", "list", "r", "property", 0,
                               layout={0: "нет", 1: "дверь", 2: "перегрев"}, zero_safe=True))
        self.add_signal(Signal("fault", "Неисправность", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("power_w", "Мощность", "graph", "r", "property", 0.0, "Вт"))
        self.add_signal(Signal("energy_kwh", "Энергия", "counter", "r", "property",
                               0.0, "кВт·ч"))

    def set_door_open(self, value: bool) -> None:
        self.set_value("door_open", 1 if value else 0)

    def set_fault(self, value: bool) -> None:
        self.set_value("fault", 1 if value else 0)

    def on_command(self, name, value) -> None:
        if name in {"target_temp", "timer"}:
            self.set_value(name, self.clamp(name, float(value)))
        elif name == "power" and int(value) and int(self.signals["child_lock"].value):
            self.set_value("power", 0)
            self.log(f"[{self.model}] включение заблокировано защитой от детей")

    def tick(self, dt: int) -> None:
        power = int(self.signals["power"].value) == 1
        temperature = float(self.signals["temperature"].value)
        target = float(self.signals["target_temp"].value)
        door = int(self.signals["door_open"].value) == 1
        fault = int(self.signals["fault"].value) == 1

        if door and power:
            self.set_value("alarm", 1)
            self.set_value("power_w", 0.0)
            temperature = max(20.0, temperature - 0.5 * dt)
        elif power and not fault:
            self.set_value("alarm", 0)
            if temperature < target:
                temperature = min(target, temperature + 5.0 * dt)
                self.set_value("power_w", 1800.0)
                self.set_value("preheat", 1)
                energy = self.signals["energy_kwh"].value + 1800.0 * dt / 3600000.0
                self.set_value("energy_kwh", round(energy, 6))
            else:
                self.set_value("power_w", 0.0)
                self.set_value("preheat", 0)
            if temperature > target + 10:
                self.set_value("alarm", 2)
                self.set_value("power", 0)
                self.set_value("power_w", 0.0)
                power = False
        else:
            self.set_value("power_w", 0.0)
            self.set_value("preheat", 0)
            temperature = max(20.0, temperature - 0.3 * dt)

        if not power:
            self.set_value("preheat", 0)
        self.set_value("temperature", round(temperature, 1))
        self.set_value("residual_heat", 1 if power or self._residual_ticks > 0 else 0)
        if power:
            self._residual_ticks = 60
        elif self._residual_ticks > 0:
            self._residual_ticks -= dt

        timer = int(self.signals["timer"].value)
        if power and timer > 0:
            timer = max(0, timer - dt)
            self.set_value("timer", timer)
            if timer == 0:
                self.set_value("power", 0)
                self.set_value("power_w", 0.0)
                self.log(f"[{self.model}] таймер: нагрев завершён")
