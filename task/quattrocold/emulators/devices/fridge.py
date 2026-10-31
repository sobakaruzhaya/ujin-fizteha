"""Умный холодильник: две камеры, компрессор, режимы и защита от открытой двери."""
from __future__ import annotations

from core import Device, Signal

MODES = {0: "Эко", 1: "Обычный", 2: "Супер"}


class Fridge(Device):
    model = "emul_fridge"
    title = "Умный холодильник"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._door_ticks = 0
        self._locked_mode = 1
        self.add_signal(Signal("fridge_temp", "Температура холодильника", "graph", "r",
                               "property", 4.0, "°C"))
        self.add_signal(Signal("freezer_temp", "Температура морозилки", "graph", "r",
                               "property", -18.0, "°C"))
        self.add_signal(Signal("target_fridge_temp", "Цель холодильника", "range", "rw",
                               "setting", 4.0, "°C", 1, 8))
        self.add_signal(Signal("target_freezer_temp", "Цель морозилки", "range", "rw",
                               "setting", -18.0, "°C", -24, -10))
        self.add_signal(Signal("door_open", "Дверь открыта", "list", "r", "property",
                               0, layout={0: "закрыта", 1: "открыта"}, zero_safe=True))
        self.add_signal(Signal("compressor", "Компрессор", "list", "r", "property",
                               0, layout={0: "выкл", 1: "работает"}, zero_safe=True))
        self.add_signal(Signal("mode", "Режим", "list", "rw", "capability", 1, layout=MODES,
                               zero_safe=True))
        self.add_signal(Signal("child_lock", "Защита от детей", "switch", "rw", "capability",
                               0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("power_w", "Мощность", "graph", "r", "property", 0.0, "Вт"))
        self.add_signal(Signal("energy_kwh", "Энергия", "counter", "r", "property",
                               0.0, "кВт·ч"))
        self.add_signal(Signal("alarm", "Тревога", "list", "r", "property", 0,
                               layout={0: "нет", 1: "температура", 2: "дверь"}, zero_safe=True))
        self.add_signal(Signal("fault", "Неисправность", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))

    def set_door_open(self, value: bool) -> None:
        self.set_value("door_open", 1 if value else 0)
        if not value:
            self._door_ticks = 0

    def set_fault(self, value: bool) -> None:
        self.set_value("fault", 1 if value else 0)

    def on_command(self, name, value) -> None:
        if name in {"target_fridge_temp", "target_freezer_temp"}:
            self.set_value(name, self.clamp(name, float(value)))
        elif name == "child_lock":
            if int(value):
                self._locked_mode = int(self.signals["mode"].value)
        elif name == "mode" and int(self.signals["child_lock"].value):
            self.set_value("mode", self._locked_mode)
            self.log(f"[{self.model}] смена режима заблокирована")

    def tick(self, dt: int) -> None:
        fridge = float(self.signals["fridge_temp"].value)
        freezer = float(self.signals["freezer_temp"].value)
        target_fridge = float(self.signals["target_fridge_temp"].value)
        target_freezer = float(self.signals["target_freezer_temp"].value)
        door = int(self.signals["door_open"].value) == 1
        mode = int(self.signals["mode"].value)
        fault = int(self.signals["fault"].value) == 1

        if door:
            self._door_ticks += dt
            fridge += 0.05 * dt
            freezer += 0.03 * dt
        else:
            self._door_ticks = 0

        compressor = mode == 2 or fridge > target_fridge + 0.5 or freezer > target_freezer + 1.0
        if compressor and not fault:
            fridge -= 0.08 * dt
            freezer -= 0.05 * dt
        if mode == 2:
            fridge -= 0.02 * dt
            freezer -= 0.02 * dt

        fridge = max(-5.0, min(15.0, fridge))
        freezer = max(-30.0, min(0.0, freezer))
        self.set_value("fridge_temp", round(fridge, 2))
        self.set_value("freezer_temp", round(freezer, 2))
        self.set_value("compressor", 1 if compressor and not fault else 0)

        power = 0.0 if not compressor or fault else (140.0 if mode == 2 else 95.0)
        self.set_value("power_w", round(power, 1))
        energy = self.signals["energy_kwh"].value + power * dt / 3600000.0
        self.set_value("energy_kwh", round(energy, 6))

        if fault:
            self.set_value("alarm", 0)
        elif self._door_ticks > 60:
            self.set_value("alarm", 2)
        elif fridge > target_fridge + 5 or freezer > target_freezer + 8:
            self.set_value("alarm", 1)
        else:
            self.set_value("alarm", 0)
