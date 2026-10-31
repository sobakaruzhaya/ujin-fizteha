"""Общий control plane для dashboard, Telegram и MCP."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from functools import cmp_to_key

EMU_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "task", "quattrocold", "emulators"))
if EMU_DIR not in sys.path:
    sys.path.insert(0, EMU_DIR)

from devices.smart_plug import SmartPlug  # noqa: E402


class Orchestrator:
    """Владелец состояния. Все команды проходят через него."""

    def __init__(self, tick_seconds: float = 1.0):
        self.lock = threading.RLock()
        self.device = SmartPlug(serial="smart_plug_1", logger=self._log)
        self.device.announce()
        self.scenarios = {}
        self.events = []
        self.confirmations = {}
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._last_values = self.state()["devices"]["smart_plug_1"]

        self.create_scenario({
            "id": "overload_protection",
            "name": "Защита от перегрузки",
            "enabled": True,
            "when": {"device": "smart_plug_1", "signal": "power_w", "operator": ">", "value": 2000},
            "do": [{"device": "smart_plug_1", "signal": "power_switch", "value": 0}],
        })

    def start(self):
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            with self.lock:
                self.device.step(1)
                self._evaluate_scenarios()
                self._observe_state()
            self._stop.wait(self.tick_seconds)

    def _log(self, message: str):
        self.add_event("log", message=message)

    def add_event(self, event_type: str, **payload):
        event = {"id": uuid.uuid4().hex[:10], "time": time.time(), "type": event_type, **payload}
        self.events.append(event)
        self.events = self.events[-200:]
        return event

    def _observe_state(self):
        current = self._device_state(self.device)
        previous = self._last_values
        if current.get("overload_alarm") == 1 and previous.get("overload_alarm") != 1:
            self.add_event("alarm", device="smart_plug_1", signal="overload_alarm",
                           value=1, message="Нагрузка отключена из-за превышения лимита")
        if current.get("power_switch") != previous.get("power_switch"):
            self.add_event("state_change", device="smart_plug_1", signal="power_switch",
                           value=current.get("power_switch"))
        self._last_values = current

    @staticmethod
    def _device_state(device):
        return {name: sig.value for name, sig in device.signals.items()}

    def state(self):
        with self.lock:
            return {"devices": {"smart_plug_1": self._device_state(self.device)},
                    "updated_at": time.time()}

    def declarations(self):
        return {"smart_plug_1": self.device.declaration()}

    def events_since(self, limit=50):
        with self.lock:
            return list(self.events[-max(1, min(int(limit), 200)):])

    def list_scenarios(self):
        with self.lock:
            return list(self.scenarios.values())

    def create_scenario(self, scenario):
        item = dict(scenario)
        item["id"] = str(item.get("id") or uuid.uuid4().hex[:8])
        item["enabled"] = bool(item.get("enabled", True))
        item.setdefault("do", [])
        with self.lock:
            self.scenarios[item["id"]] = item
            self.add_event("scenario_saved", scenario_id=item["id"], name=item.get("name", ""))
        return item

    def toggle_scenario(self, scenario_id, enabled=None):
        with self.lock:
            scenario = self.scenarios.get(str(scenario_id))
            if scenario is None:
                raise KeyError("unknown scenario")
            scenario["enabled"] = not scenario["enabled"] if enabled is None else bool(enabled)
            self.add_event("scenario_toggled", scenario_id=scenario["id"], enabled=scenario["enabled"])
            return scenario

    @staticmethod
    def _compare(left, operator, right):
        try:
            left, right = float(left), float(right)
        except (TypeError, ValueError):
            pass
        return {">": left > right, "<": left < right, ">=": left >= right,
                "<=": left <= right, "==": left == right, "!=": left != right}.get(operator, False)

    def _condition_true(self, condition):
        if condition.get("device") != "smart_plug_1":
            return False
        value = self._device_state(self.device).get(condition.get("signal"))
        return self._compare(value, condition.get("operator", "=="), condition.get("value"))

    def _evaluate_scenarios(self):
        for scenario in self.scenarios.values():
            if not scenario.get("enabled") or not self._condition_true(scenario.get("when", {})):
                scenario["_was_true"] = False
                continue
            if scenario.get("_was_true"):
                continue
            scenario["_was_true"] = True
            self.add_event("scenario_triggered", scenario_id=scenario["id"], name=scenario.get("name", ""))
            for action in scenario.get("do", []):
                self._apply_command(action["device"], action["signal"], action.get("value"), source="scenario")

    def _apply_command(self, device_id, signal, value, source="api"):
        if device_id != "smart_plug_1" or signal not in self.device.signals:
            raise KeyError("unknown device or signal")
        target = self.device.signals[signal]
        if not target.writable:
            raise PermissionError("signal is read-only")
        self.device.handle_recv({"recv": [{"command": "management", "id": device_id, signal: value}]})
        self.add_event("command", device=device_id, signal=signal, value=value, source=source)
        return {"device": device_id, "signal": signal, "value": value}

    def request_command(self, device_id, signal, value, require_confirmation=True):
        dangerous = signal in {"power_switch", "reset_protection", "power_limit_w", "load_w"}
        if require_confirmation and dangerous:
            token = uuid.uuid4().hex
            with self.lock:
                self.confirmations[token] = {"expires": time.time() + 60, "device": device_id,
                                             "signal": signal, "value": value}
            return {"status": "confirmation_required", "confirmation_id": token,
                    "expires_in": 60, "summary": f"{signal}={value} для {device_id}"}
        with self.lock:
            return {"status": "applied", **self._apply_command(device_id, signal, value)}

    def confirm_command(self, token):
        with self.lock:
            request = self.confirmations.pop(token, None)
            if not request or request["expires"] < time.time():
                raise PermissionError("confirmation expired")
            return {"status": "applied", **self._apply_command(request["device"], request["signal"], request["value"], "confirmation")}

    def reset(self):
        with self.lock:
            self.device._protected = False
            for name, value in (("power_switch", 0), ("overload_alarm", 0), ("anomaly", 0), ("energy_kwh", 0.0), ("load_w", 900.0)):
                self.device.set_value(name, value)
            for scenario in self.scenarios.values():
                scenario.pop("_was_true", None)
            self.events.clear()
            self.add_event("reset", message="Демо сброшено")
            self._last_values = self._device_state(self.device)
            return self.state()

    def simulate(self, seconds=10):
        with self.lock:
            snapshot = {n: s.value for n, s in self.device.signals.items()}
            protected = self.device._protected
            events_before = len(self.events)
            for _ in range(max(1, min(int(seconds), 120))):
                self.device.step(1)
                self._evaluate_scenarios()
            result = {"state": self.state(), "events": self.events[events_before:]}
            for name, value in snapshot.items():
                self.device.signals[name].value = value
            self.device._protected = protected
            self.events = self.events[:events_before]
            return result

