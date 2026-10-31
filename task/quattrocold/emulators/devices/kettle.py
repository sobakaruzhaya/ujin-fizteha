"""Умный чайник: нагрев, поддержание температуры и защита от сухого хода."""
from __future__ import annotations

from core import Device, Signal

MODES = {0: "Чай", 1: "Кофе", 2: "Кипячение"}
MODE_TEMPS = {0: 80.0, 1: 95.0, 2: 100.0}


class Kettle(Device):
    model = "emul_kettle"
    title = "Умный чайник"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._boils = 0
        self.add_signal(Signal("power", "Питание", "switch", "rw", "capability",
                               0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("temperature", "Температура", "graph", "r", "property",
                               20.0, "°C"))
        self.add_signal(Signal("target_temp", "Целевая температура", "range", "rw",
                               "setting", 100.0, "°C", 40, 100))
        self.add_signal(Signal("keep_warm", "Поддержание тепла", "switch", "rw",
                               "capability", 0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("water_level", "Уровень воды", "range", "rw", "setting",
                               80, "%", 0, 100, zero_safe=True))
        self.add_signal(Signal("mode", "Режим", "list", "rw", "capability", 0, layout=MODES,
                               zero_safe=True))
        self.add_signal(Signal("auto_off", "Авто-выключение", "list", "r", "property",
                               0, layout={0: "нет", 1: "сработало"}, zero_safe=True))
        self.add_signal(Signal("dry_boil", "Сухой ход", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("descale", "Нужна декальцинация", "list", "r", "property",
                               0, layout={0: "нет", 1: "да"}, zero_safe=True))
        self.add_signal(Signal("reset", "Сбросить защиту", "button", "w", "capability", 0))
        self.add_signal(Signal("power_w", "Мощность", "graph", "r", "property", 0.0, "Вт"))
        self.add_signal(Signal("energy_kwh", "Энергия", "counter", "r", "property",
                               0.0, "кВт·ч"))

    def set_water_level(self, value: float) -> None:
        self.set_value("water_level", max(0.0, min(100.0, float(value))))

    def on_command(self, name, value) -> None:
        if name == "water_level":
            self.set_value("water_level", self.clamp("water_level", float(value)))
        elif name == "target_temp":
            self.set_value("target_temp", self.clamp("target_temp", float(value)))
        elif name == "mode":
            mode = int(value)
            if mode in MODE_TEMPS:
                self.set_value("target_temp", MODE_TEMPS[mode])
        elif name == "power" and int(value):
            if float(self.signals["water_level"].value) <= 0:
                self.set_value("dry_boil", 1)
                self.set_value("power", 0)
                self.log(f"[{self.model}] сухой ход: нагрев заблокирован")
            else:
                self.set_value("power", 1)
        elif name == "power" and not int(value):
            self.set_value("power", 0)
        elif name == "reset" and int(value):
            self.set_value("dry_boil", 0)
            self.set_value("auto_off", 0)
            self.set_value("descale", 0)
            self.set_value("reset", 0)

    def tick(self, dt: int) -> None:
        power = int(self.signals["power"].value) == 1
        temperature = float(self.signals["temperature"].value)
        target = float(self.signals["target_temp"].value)
        water = float(self.signals["water_level"].value)

        if water <= 0 and power:
            self.set_value("dry_boil", 1)
            self.set_value("power", 0)
            power = False

        if power and not int(self.signals["dry_boil"].value):
            temperature = min(target, temperature + 3.0 * dt)
            self.set_value("temperature", round(temperature, 1))
            self.set_value("power_w", 1500.0)
            energy = self.signals["energy_kwh"].value + 1500.0 * dt / 3600000.0
            self.set_value("energy_kwh", round(energy, 6))
            if temperature >= target:
                self.set_value("power", 0)
                self.set_value("auto_off", 1)
                self._boils += 1
                if self._boils >= 20:
                    self.set_value("descale", 1)
        else:
            self.set_value("power_w", 0.0)
            if temperature > 20.0:
                self.set_value("temperature", round(max(20.0, temperature - 0.5 * dt), 1))

        if (int(self.signals["keep_warm"].value) and water > 0
                and not int(self.signals["dry_boil"].value)
                and temperature <= target - 2):
            self.set_value("power", 1)
            self.set_value("auto_off", 0)
