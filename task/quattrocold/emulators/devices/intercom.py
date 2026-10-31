"""Умный домофон: вызов, разговор, открытие двери и базовые защиты."""
from __future__ import annotations

from core import Device, Signal

CALL_STATES = {0: "Ожидание", 1: "Вызов", 2: "Разговор"}


class Intercom(Device):
    model = "emul_intercom"
    title = "Умный домофон"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auto_timer = 0
        self._door_timer = 0
        self.add_signal(Signal("call_state", "Состояние вызова", "list", "r", "property",
                               0, layout=CALL_STATES, zero_safe=True))
        self.add_signal(Signal("answer", "Ответить", "button", "w", "capability", 0))
        self.add_signal(Signal("hangup", "Завершить", "button", "w", "capability", 0))
        self.add_signal(Signal("unlock", "Открыть дверь", "button", "w", "capability", 0))
        self.add_signal(Signal("door_open", "Дверь открыта", "list", "r", "property",
                               0, layout={0: "закрыта", 1: "открыта"}, zero_safe=True))
        self.add_signal(Signal("mute", "Без звука", "switch", "rw", "capability",
                               0, layout={0: "нет", 1: "да"}, zero_safe=True))
        self.add_signal(Signal("volume", "Громкость", "range", "rw", "capability",
                               50, "%", 0, 100))
        self.add_signal(Signal("last_call", "Последний вызов", "counter", "r", "property", 0))
        self.add_signal(Signal("tamper", "Вскрытие", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("failed_attempts", "Неудачные попытки", "counter", "r",
                               "property", 0))
        self.add_signal(Signal("auto_hangup_seconds", "Авто-завершение, с", "counter", "rw",
                               "setting", 30, "с", 5, 120))

    def ring(self) -> None:
        self.set_value("call_state", 1)
        self.set_value("last_call", self.signals["last_call"].value + 1)
        self._auto_timer = int(self.signals["auto_hangup_seconds"].value)

    def set_tamper(self, value: bool) -> None:
        self.set_value("tamper", 1 if value else 0)

    def on_command(self, name, value) -> None:
        if name == "answer" and int(value):
            if int(self.signals["call_state"].value) == 1:
                self.set_value("call_state", 2)
                self._auto_timer = int(self.signals["auto_hangup_seconds"].value)
            self.set_value("answer", 0)
        elif name == "hangup" and int(value):
            self.set_value("call_state", 0)
            self._auto_timer = 0
            self.set_value("hangup", 0)
        elif name == "unlock" and int(value):
            if int(self.signals["call_state"].value) in (1, 2) and not int(self.signals["tamper"].value):
                self.set_value("door_open", 1)
                self._door_timer = 3
            else:
                self.set_value("failed_attempts", self.signals["failed_attempts"].value + 1)
            self.set_value("unlock", 0)
        elif name == "volume":
            self.set_value("volume", self.clamp("volume", float(value)))
        elif name == "auto_hangup_seconds":
            self.set_value("auto_hangup_seconds", self.clamp("auto_hangup_seconds", float(value)))

    def tick(self, dt: int) -> None:
        if int(self.signals["call_state"].value) in (1, 2):
            if self._auto_timer > 0:
                self._auto_timer -= dt
                if self._auto_timer <= 0:
                    self.set_value("call_state", 0)
                    self.log(f"[{self.model}] авто-завершение вызова")
        if self._door_timer > 0:
            self._door_timer -= dt
            if self._door_timer <= 0:
                self.set_value("door_open", 0)
