"""Умный телевизор: базовое управление, источники, приложения и авто-выключение."""
from __future__ import annotations

from core import Device, Signal

SOURCES = {0: "ТВ", 1: "HDMI 1", 2: "HDMI 2", 3: "Приложение"}
APPS = {0: "Нет", 1: "YouTube", 2: "Netflix", 3: "Кинопоиск"}
PLAYBACK = {0: "Стоп", 1: "Играет", 2: "Пауза"}


class SmartTV(Device):
    model = "emul_smart_tv"
    title = "Умный телевизор"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = 0
        self._locked_source = 0
        self._locked_app = 0
        self.add_signal(Signal("power", "Питание", "switch", "rw", "capability",
                               0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("volume", "Громкость", "range", "rw", "capability",
                               30, "%", 0, 100))
        self.add_signal(Signal("mute", "Без звука", "switch", "rw", "capability",
                               0, layout={0: "нет", 1: "да"}, zero_safe=True))
        self.add_signal(Signal("source", "Источник", "list", "rw", "capability",
                               0, layout=SOURCES, zero_safe=True))
        self.add_signal(Signal("app", "Приложение", "list", "rw", "capability",
                               0, layout=APPS, zero_safe=True))
        self.add_signal(Signal("playback", "Воспроизведение", "list", "rw", "capability",
                               0, layout=PLAYBACK, zero_safe=True))
        self.add_signal(Signal("brightness", "Яркость", "range", "rw", "capability",
                               80, "%", 1, 100))
        self.add_signal(Signal("child_lock", "Родительский контроль", "switch", "rw",
                               "capability", 0, layout={0: "выкл", 1: "вкл"}, zero_safe=True))
        self.add_signal(Signal("child_max_volume", "Предел громкости", "range", "rw",
                               "setting", 40, "%", 0, 100, zero_safe=True))
        self.add_signal(Signal("auto_off_seconds", "Авто-выкл через", "counter", "rw",
                               "setting", 0, "с", 0, 3600, zero_safe=True))
        self.add_signal(Signal("power_w", "Мощность", "graph", "r", "property", 0.0, "Вт"))
        self.add_signal(Signal("energy_kwh", "Энергия", "counter", "r", "property",
                               0.0, "кВт·ч"))
        self.add_signal(Signal("fault", "Неисправность", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))

    def on_command(self, name, value) -> None:
        if name == "power":
            if int(value):
                timeout = int(self.signals["auto_off_seconds"].value)
                self._timer = timeout if timeout > 0 else 0
            else:
                self._timer = 0
                self.set_value("playback", 0)
        elif name == "volume":
            volume = self.clamp("volume", float(value))
            if int(self.signals["child_lock"].value):
                volume = min(volume, float(self.signals["child_max_volume"].value))
            self.set_value("volume", volume)
        elif name == "brightness":
            self.set_value("brightness", self.clamp("brightness", float(value)))
        elif name == "child_lock":
            if int(value):
                self._locked_source = int(self.signals["source"].value)
                self._locked_app = int(self.signals["app"].value)
                self.set_value("volume", min(
                    float(self.signals["volume"].value),
                    float(self.signals["child_max_volume"].value)))
        elif name == "child_max_volume":
            self.set_value("child_max_volume",
                           self.clamp("child_max_volume", float(value)))
        elif name in {"source", "app"} and int(self.signals["child_lock"].value):
            self.set_value("source", self._locked_source)
            self.set_value("app", self._locked_app)
            self.log(f"[{self.model}] смена источника заблокирована")

    def tick(self, dt: int) -> None:
        on = int(self.signals["power"].value) == 1
        if not on:
            self.set_value("power_w", 0.0)
            return
        power = 60.0 + float(self.signals["brightness"].value) * 0.6
        self.set_value("power_w", round(power, 1))
        energy = self.signals["energy_kwh"].value + power * dt / 3600000.0
        self.set_value("energy_kwh", round(energy, 6))
        if self._timer > 0:
            self._timer -= dt
            if self._timer <= 0:
                self.set_value("power", 0)
                self.set_value("playback", 0)
                self.log(f"[{self.model}] авто-выключение по таймеру")
