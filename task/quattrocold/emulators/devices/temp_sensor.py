"""Датчик температуры и влажности на батарее."""
from __future__ import annotations

from core import Device, Signal


class TempSensor(Device):
    model = "emul_temp_sensor"
    title = "Датчик температуры"

    def __init__(self, *args, start_temp: float = 22.0, start_humidity: float = 45.0,
                 ambient: float = 22.0, battery_drain: float = 0.01, **kwargs):
        super().__init__(*args, **kwargs)
        self.ambient = float(ambient)
        self.battery_drain = float(battery_drain)
        self._raw_temp = float(start_temp)
        self._humidity = float(start_humidity)
        self.add_signal(Signal("temperature", "Температура", "graph", "r", "property",
                               round(start_temp, 2), "°C"))
        self.add_signal(Signal("humidity", "Влажность", "graph", "r", "property",
                               round(start_humidity, 1), "%"))
        self.add_signal(Signal("battery", "Батарея", "graph", "r", "property",
                               100.0, "%", 0, 100))
        self.add_signal(Signal("low_battery", "Низкий заряд", "list", "r", "property",
                               0, layout={0: "нет", 1: "низкий"}, zero_safe=True))
        self.add_signal(Signal("tamper", "Вскрытие", "list", "r", "property",
                               0, layout={0: "закрыт", 1: "вскрыт"}, zero_safe=True))
        self.add_signal(Signal("fault", "Неисправность", "list", "r", "property",
                               0, layout={0: "нет", 1: "есть"}, zero_safe=True))
        self.add_signal(Signal("last_seen", "Последняя связь", "counter", "r", "property", 0))
        self.add_signal(Signal("report_interval", "Период отчёта, с", "counter", "rw",
                               "setting", 60, "с", 10, 3600))
        self.add_signal(Signal("calibration", "Калибровка", "range", "rw", "setting",
                               0.0, "°C", -5, 5, zero_safe=True))
        self.add_signal(Signal("target_temp", "Комфортная температура", "range", "rw",
                               "setting", 22.0, "°C", 5, 35))

    def set_temperature(self, value: float) -> None:
        self._raw_temp = float(value)

    def set_humidity(self, value: float) -> None:
        self._humidity = max(0.0, min(100.0, float(value)))

    def set_battery(self, value: float) -> None:
        self.set_value("battery", max(0.0, min(100.0, float(value))))

    def set_tamper(self, value: bool) -> None:
        self.set_value("tamper", 1 if value else 0)

    def set_fault(self, value: bool) -> None:
        self.set_value("fault", 1 if value else 0)

    def on_command(self, name, value) -> None:
        if name in {"report_interval", "calibration", "target_temp"}:
            self.set_value(name, self.clamp(name, float(value)))

    def tick(self, dt: int) -> None:
        # Датчик измеряет комнату; без внешнего воздействия температура
        # медленно тянется к ambient.
        self._raw_temp += (self.ambient - self._raw_temp) * 0.002 * dt
        self._humidity += (45.0 - self._humidity) * 0.001 * dt
        calibration = float(self.signals["calibration"].value)
        self.set_value("temperature", round(self._raw_temp + calibration, 2))
        self.set_value("humidity", round(self._humidity, 1))
        battery = float(self.signals["battery"].value) - self.battery_drain * dt
        self.set_value("battery", round(max(0.0, battery), 2))
        self.set_value("low_battery", 1 if self.signals["battery"].value <= 15 else 0)
        self.set_value("last_seen", self.tick_count)
