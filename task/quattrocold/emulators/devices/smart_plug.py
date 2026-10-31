"""Smart Plug — розетка с измерением мощности и защитой Power Guardian."""
from __future__ import annotations

from core import Device, Signal


class SmartPlug(Device):
    model = "emul_smart_plug"
    title = "Умная розетка"

    def __init__(self, *args, load_w: float = 900.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = 0
        self._load_w = float(load_w)
        self._protected = False
        self.add_signal(Signal("power_switch", "Реле", "switch", "rw", "capability", 0,
                               layout={0: "выкл", 1: "вкл"}))
        self.add_signal(Signal("power_w", "Мощность", "graph", "r", "property", 0.0, "Вт"))
        self.add_signal(Signal("energy_kwh", "Энергия", "counter", "r", "property", 0.0, "кВт·ч"))
        self.add_signal(Signal("voltage", "Напряжение", "graph", "r", "property", 230.0, "В"))
        self.add_signal(Signal("current_a", "Ток", "graph", "r", "property", 0.0, "А"))
        self.add_signal(Signal("load_w", "Модель нагрузки", "range", "rw", "setting",
                               self._load_w, "Вт", 0, 3500))
        self.add_signal(Signal("power_limit_w", "Лимит мощности", "range", "rw", "setting",
                               2000.0, "Вт", 100, 3500))
        self.add_signal(Signal("auto_off_seconds", "Авто-выкл через", "counter", "rw", "setting",
                               0, "с", 0, 3600))
        self.add_signal(Signal("overload_alarm", "Защита", "list", "r", "property", 0,
                               layout={0: "нет", 1: "перегрузка"}))
        self.add_signal(Signal("anomaly", "Аномалия", "list", "r", "property", 0,
                               layout={0: "нет", 1: "обнаружена"}))
        self.add_signal(Signal("reset_protection", "Сбросить защиту", "button", "w",
                               "capability", 0))

    @property
    def protected(self) -> bool:
        return self._protected

    def on_command(self, name, value) -> None:
        if name == "power_switch":
            if int(value) and self._protected:
                self.set_value("power_switch", 0)
                self.log("[smart_plug] включение заблокировано защитой")
                return
            if int(value):
                timeout = int(self.signals["auto_off_seconds"].value)
                self._timer = timeout if timeout > 0 else 0
            else:
                self._timer = 0
        elif name == "load_w":
            self._load_w = float(self.clamp("load_w", float(value)))
        elif name == "power_limit_w":
            self.set_value("power_limit_w", self.clamp("power_limit_w", float(value)))
        elif name == "reset_protection" and int(value):
            self._protected = False
            self.set_value("overload_alarm", 0)
            self.set_value("anomaly", 0)
            self.set_value("reset_protection", 0)

    def trip(self, reason: str = "overload") -> None:
        self._protected = True
        self.set_value("power_switch", 0)
        self.set_value("overload_alarm", 1 if reason == "overload" else 0)
        self.set_value("anomaly", 1 if reason == "anomaly" else 0)
        self._timer = 0

    def tick(self, dt: int) -> None:
        on = int(self.signals["power_switch"].value) == 1 and not self._protected
        power = float(self.signals["load_w"].value) if on else 0.0
        self.set_value("power_w", round(power, 1))
        self.set_value("current_a", round(power / max(float(self.signals["voltage"].value), 1), 2))
        if on:
            energy = self.signals["energy_kwh"].value + power * dt / 3600000.0
            self.set_value("energy_kwh", round(energy, 6))
            if self._timer > 0:
                self._timer -= dt
                if self._timer <= 0:
                    self.set_value("power_switch", 0)
                    self.log("[smart_plug] авто-выключение по таймеру")
            if power > float(self.signals["power_limit_w"].value):
                self.trip("overload")
        else:
            self.set_value("overload_alarm", 1 if self._protected and self.signals["overload_alarm"].value else 0)

