"""Умная плита: четыре конфорки, таймер и базовые защиты."""
from __future__ import annotations

from core import Device, Signal


class Stove(Device):
    model = "emul_stove"
    title = "Умная плита"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._residual_ticks = 0
        for index in range(1, 5):
            self.add_signal(Signal(f"burner_{index}", f"Конфорка {index}", "range", "rw",
                                   "capability", 0, "", 0, 9, zero_safe=True))
        self.add_signal(Signal("pot_present", "Посуда на плите", "switch", "rw",
                               "capability", 1, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("timer", "Таймер, с", "counter", "rw", "setting",
                               0, "с", 0, 7200, zero_safe=True))
        self.add_signal(Signal("child_lock", "Защита от детей", "switch", "rw",
                               "capability", 0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("residual_heat", "Остаточное тепло", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("boil_dry", "Сухой нагрев", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("overheat", "Перегрев", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("power_w", "Мощность", "graph", "r", "property", 0.0, "Вт"))
        self.add_signal(Signal("energy_kwh", "Энергия", "counter", "r", "property",
                               0.0, "кВт·ч"))

    def _burners(self):
        return [f"burner_{index}" for index in range(1, 5)]

    def on_command(self, name, value) -> None:
        if name == "child_lock" and int(value):
            for burner in self._burners():
                self.set_value(burner, 0)
            self.log(f"[{self.model}] защита от детей: конфорки выключены")
        elif name.startswith("burner_") and int(self.signals["child_lock"].value):
            self.set_value(name, 0)
            self.log(f"[{self.model}] конфорка заблокирована")
        elif name.startswith("burner_"):
            self.set_value(name, self.clamp(name, float(value)))
        elif name == "timer":
            self.set_value("timer", self.clamp("timer", float(value)))

    def tick(self, dt: int) -> None:
        levels = [int(self.signals[name].value) for name in self._burners()]
        total = sum(levels)
        if total and not int(self.signals["pot_present"].value):
            self.set_value("boil_dry", 1)
            for burner in self._burners():
                self.set_value(burner, 0)
            total = 0
            self.log(f"[{self.model}] сухой нагрев: конфорки выключены")

        if total >= 32:
            self.set_value("overheat", 1)
            for burner in self._burners():
                self.set_value(burner, 0)
            total = 0
            self.log(f"[{self.model}] перегрев: конфорки выключены")

        if total:
            self._residual_ticks = 30
            timer = int(self.signals["timer"].value)
            if timer > 0:
                timer = max(0, timer - dt)
                self.set_value("timer", timer)
                if timer == 0:
                    for burner in self._burners():
                        self.set_value(burner, 0)
                    total = 0

        power = total * 250.0
        self.set_value("power_w", round(power, 1))
        energy = self.signals["energy_kwh"].value + power * dt / 3600000.0
        self.set_value("energy_kwh", round(energy, 6))
        self.set_value("residual_heat", 1 if total or self._residual_ticks > 0 else 0)
        if self._residual_ticks > 0:
            self._residual_ticks -= dt
