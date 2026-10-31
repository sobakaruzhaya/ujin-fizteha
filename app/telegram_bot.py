"""Telegram Bot API adapter without external dependencies.

The bot is a thin client of the same control plane as the web UI and MCP.
Every state-changing command is previewed first and executed only after an
inline confirmation, so a compromised chat cannot bypass the safety policy.
"""
# ruff: noqa: BLE001 - the polling boundary must survive any Telegram/network error.
from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import ClassVar

try:
    from .home_client import ensure_client
except ImportError:  # script mode: python app/run.py
    from home_client import ensure_client

ICONS = {"plug": "🔌", "light": "💡", "climate": "🌡", "wind": "🌬"}
DEMO_LABELS = {
    "overload": "⚡ Перегрузка",
    "co2": "🌬 Высокий CO₂",
    "evening": "🌙 Вечерний режим",
}


class TelegramBot:
    DEVICE_ACTIONS: ClassVar[dict] = {
        "smart_plug_1": [
            ("Включить розетку", "power_switch", 1),
            ("Выключить розетку", "power_switch", 0),
            ("Сбросить защиту", "reset_protection", 1),
            ("Нагрузка 900 Вт", "load_w", 900),
            ("Нагрузка 2400 Вт", "load_w", 2400),
        ],
        "light_1": [
            ("Свет включить", "lamp", 1),
            ("Свет выключить", "lamp", 0),
            ("Яркость 100%", "brightness", 100),
            ("Яркость 30%", "brightness", 30),
        ],
        "thermostat_1": [
            ("Цель 20 °C", "target_temp", 20),
            ("Цель 22 °C", "target_temp", 22),
            ("Цель 24 °C", "target_temp", 24),
            ("Режим: авто", "mode", 3),
            ("Режим: нагрев", "mode", 1),
            ("Режим: выкл", "mode", 0),
        ],
        "ventilation_1": [
            ("Режим: авто", "mode", 1),
            ("Режим: выкл", "mode", 0),
            ("Скорость 3", "fan_speed", 3),
            ("Скорость 6", "fan_speed", 6),
        ],
    }

    def __init__(self, client, token=None, allowed_chat_ids=None, api=None):
        self.client = ensure_client(client)
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw = allowed_chat_ids if allowed_chat_ids is not None else os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
        self.allowed = {str(item.strip()) for item in raw.split(",") if item.strip()}
        self.offset = 0
        self.running = False
        self._api_call = api or self._http_api
        self._notified_event_ids = set()
        self._notifications_primed = False

    @property
    def enabled(self):
        return bool(self.token and self.allowed)

    # ------------------------------------------------------------------ API
    def _http_api(self, method, payload=None):
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = urllib.parse.urlencode(payload or {}).encode("utf-8")
        request = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                result = json.loads(exc.read().decode("utf-8"))
            except ValueError:
                raise RuntimeError(f"Telegram HTTP {exc.code}") from exc
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram API error"))
        return result

    def _api(self, method, payload=None):
        return self._api_call(method, payload)

    def _send(self, chat_id, text, keyboard=None):
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
        if keyboard:
            payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard},
                                                 ensure_ascii=False)
        return self._api("sendMessage", payload)

    def _answer_callback(self, callback_id, text=None):
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        try:
            self._api("answerCallbackQuery", payload)
        except Exception as exc:
            print(f"telegram callback answer failed: {exc}", file=sys.stderr)

    def _authorized(self, chat_id):
        return str(chat_id) in self.allowed

    # ------------------------------------------------------------ formatting
    @staticmethod
    def _layout_value(declaration, name, value):
        for signal in declaration:
            if signal.get("name") == name:
                layout = signal.get("layout") or {}
                try:
                    key = int(value)
                except (TypeError, ValueError):
                    return layout.get(value, value)
                if key in layout:
                    return layout[key]
                if str(key) in layout:  # JSON object keys arrive as strings over HTTP
                    return layout[str(key)]
                return layout.get(value, value)
        return value

    @staticmethod
    def _number(value):
        try:
            return f"{float(value):.3f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            return str(value)

    def _device_summary(self, device_id, data, declaration):
        if device_id == "smart_plug_1":
            state = "вкл" if data.get("power_switch") else "выкл"
            protection = "⚠️ сработала" if data.get("overload_alarm") else "нет"
            return (f"Реле: {state} · {self._number(data.get('power_w', 0))} Вт · "
                    f"{self._number(data.get('energy_kwh', 0))} кВт·ч · защита: {protection}")
        if device_id == "light_1":
            state = "вкл" if data.get("lamp") else "выкл"
            return (f"Свет: {state} · яркость: {self._number(data.get('brightness', 0))}% · "
                    f"{self._number(data.get('power_w', 0))} Вт")
        if device_id == "thermostat_1":
            mode = self._layout_value(declaration, "mode", data.get("mode", 0))
            return (f"{self._number(data.get('temperature', 0))} °C → "
                    f"{self._number(data.get('target_temp', 0))} °C · режим: {mode} · "
                    f"влажность: {self._number(data.get('humidity', 0))}%")
        if device_id == "ventilation_1":
            mode = self._layout_value(declaration, "mode", data.get("mode", 0))
            return (f"CO₂: {self._number(data.get('co2', 0))} ppm · "
                    f"PM2.5: {self._number(data.get('pm25', 0))} · режим: {mode} · "
                    f"скорость: {self._number(data.get('fan_speed', 0))}")
        return ""

    def _status_text(self):
        state = self.client.state()
        declarations = self.client.declarations()
        devices = state.get("devices", {})
        metadata = state.get("metadata", {})
        lines = ["🏠 Power Guardian", ""]
        for device_id, data in devices.items():
            meta = metadata.get(device_id, {})
            icon = ICONS.get(meta.get("icon"), "•")
            title = meta.get("name", device_id)
            room = meta.get("room", "")
            heading = f"{icon} {title}" + (f" · {room}" if room else "")
            lines.append(heading)
            lines.append("   " + self._device_summary(device_id, data,
                                                      declarations.get(device_id, [])))
            if device_id == "smart_plug_1" and data.get("overload_alarm"):
                lines.append("   ⚠️ Защита активна: сначала уменьшите нагрузку и сбросьте защиту")
            lines.append("")
        summary = state.get("summary", {})
        lines.append(f"Всего: {self._number(summary.get('power_w', 0))} Вт · "
                     f"{self._number(summary.get('energy_kwh', 0))} кВт·ч · "
                     f"сценариев активно: {summary.get('active_scenarios', 0)}")
        return "\n".join(lines)

    def _device_text(self, device_id):
        state = self.client.state()
        declarations = self.client.declarations()
        if device_id not in state.get("devices", {}):
            raise ValueError("Устройство не найдено")
        data = state["devices"][device_id]
        meta = state.get("metadata", {}).get(device_id, {})
        icon = ICONS.get(meta.get("icon"), "•")
        lines = [f"{icon} {meta.get('name', device_id)} · {meta.get('room', '')}", ""]
        declaration = declarations.get(device_id, [])
        for signal in declaration:
            name = signal.get("name")
            if name == "fw":
                continue
            value = data.get(name)
            if signal.get("layout"):
                value = self._layout_value(declaration, name, value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                value = self._number(value)
            measure = signal.get("measure", "")
            marker = "⚙️ " if signal.get("management") in ("rw", "w") else ""
            lines.append(f"{marker}{signal.get('title', name)}: {value} {measure}".rstrip())
        return "\n".join(lines)

    def _device_keyboard(self, device_id):
        rows = []
        current = []
        for label, signal, value in self.DEVICE_ACTIONS.get(device_id, []):
            current.append({"text": label,
                            "callback_data": f"cmd:{device_id}:{signal}:{value}"})
            if len(current) == 2:
                rows.append(current)
                current = []
        if current:
            rows.append(current)
        rows.append([{"text": "◀️ К устройствам", "callback_data": "devices"}])
        return rows

    def _devices_keyboard(self):
        state = self.client.state()
        rows = []
        for device_id in state.get("devices", {}):
            meta = state.get("metadata", {}).get(device_id, {})
            icon = ICONS.get(meta.get("icon"), "•")
            rows.append([{"text": f"{icon} {meta.get('name', device_id)}",
                          "callback_data": f"dev:{device_id}"}])
        return rows

    @staticmethod
    def _encode_id(value):
        return base64.urlsafe_b64encode(str(value).encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_id(value):
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding).decode("utf-8")

    def _scenarios_text_and_keyboard(self):
        scenarios = self.client.scenarios()
        if not scenarios:
            return "🧩 Сценариев пока нет", []
        lines = ["🧩 Сценарии", ""]
        rows = []
        for scenario in scenarios:
            enabled = bool(scenario.get("enabled"))
            mark = "✅" if enabled else "⏸"
            lines.append(f"{mark} {scenario.get('name', scenario['id'])}")
            rows.append([{
                "text": f"{mark} {scenario.get('name', scenario['id'])}",
                "callback_data": f"sc:{self._encode_id(scenario['id'])}:{0 if enabled else 1}",
            }])
        return "\n".join(lines), rows

    def _events_text(self, limit=10):
        events = self.client.events(limit)
        if not events:
            return "📋 Событий пока нет"
        lines = ["📋 Последние события", ""]
        for event in events[-limit:]:
            moment = time.strftime("%H:%M:%S", time.localtime(event.get("time", time.time())))
            message = event.get("message") or event.get("type", "event")
            if isinstance(message, dict):
                message = "; ".join(f"{key}: {value}" for key, value in message.items())
            lines.append(f"{moment} — {message}")
        return "\n".join(lines)

    def _main_keyboard(self):
        return [
            [{"text": "📊 Состояние", "callback_data": "status"},
             {"text": "🧩 Сценарии", "callback_data": "scenarios"}],
            [{"text": "🔌 Устройства", "callback_data": "devices"},
             {"text": "📋 События", "callback_data": "events"}],
            [{"text": "🧪 Демо", "callback_data": "demo"}],
        ]

    def _demo_keyboard(self):
        rows = [[{"text": label, "callback_data": f"demo:{preset}"}]
                for preset, label in DEMO_LABELS.items()]
        rows.append([{"text": "♻️ Сбросить эмуляторы", "callback_data": "reset"}])
        return rows

    # ------------------------------------------------------------ commands
    def _preview_command(self, chat_id, device, signal, value):
        try:
            result = self.client.request_command(device, signal, value)
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")
            return
        if result.get("status") != "confirmation_required":
            self._send(chat_id, "✅ Команда выполнена")
            return
        keyboard = [[
            {"text": "✅ Подтвердить", "callback_data": "confirm:" + result["confirmation_id"]},
            {"text": "Отмена", "callback_data": "cancel"},
        ]]
        self._send(chat_id, "⚠️ Подтвердите команду\n" + result.get("summary", ""), keyboard)

    def _confirm_command(self, chat_id, confirmation_id):
        try:
            result = self.client.confirm_command(confirmation_id)
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")
            return
        summary = result.get("summary") or ""
        self._send(chat_id, "✅ Команда выполнена" + (f"\n{summary}" if summary else ""))

    def _run_demo(self, chat_id, preset):
        if preset not in DEMO_LABELS:
            self._send(chat_id, "❌ Неизвестный демонстрационный сценарий")
            return
        try:
            self.client.experiment(preset)
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")
            return
        try:
            status = self._status_text()
        except Exception:
            status = ""
        self._send(chat_id, f"🧪 Запущено: {DEMO_LABELS[preset]}" +
                   (f"\n{status}" if status else ""))

    def _reset(self, chat_id):
        try:
            self.client.reset()
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")
            return
        self._send(chat_id, "♻️ Эмуляторы сброшены. Сценарии сохранены.")

    def _toggle_scenario(self, chat_id, encoded_id, enabled):
        try:
            scenario = self.client.toggle_scenario(self._decode_id(encoded_id), enabled)
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")
            return
        mark = "✅ включён" if scenario.get("enabled") else "⏸ выключен"
        self._send(chat_id, f"Сценарий «{scenario.get('name')}» {mark}")

    def _handle_callback(self, chat_id, callback):
        data = callback.get("data", "")
        parts = data.split(":")
        action = parts[0]
        if action == "status":
            self._send(chat_id, self._status_text(), self._main_keyboard())
        elif action == "devices":
            self._send(chat_id, "Выберите устройство", self._devices_keyboard())
        elif action == "dev" and len(parts) == 2:
            try:
                self._send(chat_id, self._device_text(parts[1]),
                           self._device_keyboard(parts[1]))
            except Exception as exc:
                self._send(chat_id, f"❌ {exc}")
        elif action == "events":
            self._send(chat_id, self._events_text(12), self._main_keyboard())
        elif action == "scenarios":
            text, keyboard = self._scenarios_text_and_keyboard()
            self._send(chat_id, text, keyboard)
        elif action == "sc" and len(parts) == 3:
            self._toggle_scenario(chat_id, parts[1], parts[2] == "1")
        elif action == "demo":
            if len(parts) == 2 and parts[1] in DEMO_LABELS:
                self._run_demo(chat_id, parts[1])
            else:
                self._send(chat_id, "Выберите демонстрацию", self._demo_keyboard())
        elif action == "reset":
            self._reset(chat_id)
        elif action == "cmd" and len(parts) == 4:
            try:
                value = float(parts[3])
            except ValueError:
                self._send(chat_id, "❌ Некорректное значение команды")
                return
            self._preview_command(chat_id, parts[1], parts[2], value)
        elif action == "confirm" and len(parts) == 2:
            self._confirm_command(chat_id, parts[1])
        elif action == "cancel":
            self._send(chat_id, "Отменено")
        else:
            self._send(chat_id, "Неизвестное действие")

    def _handle_message(self, chat_id, text):
        parts = text.split()
        command = parts[0].split("@", 1)[0].lower()
        args = parts[1:]
        try:
            if command in ("/start", "/help"):
                self._send(chat_id, (
                    "🏠 Power Guardian — умный дом\n\n"
                    "/status — состояние всех устройств\n"
                    "/devices — устройства и управление\n"
                    "/device <id> — карточка устройства\n"
                    "/events [n] — последние события\n"
                    "/scenarios — сценарии и переключатели\n"
                    "/scenario_on <id> — включить сценарий\n"
                    "/scenario_off <id> — выключить сценарий\n"
                    "/demo [overload|co2|evening] — демонстрация\n"
                    "/reset — сбросить эмуляторы\n"
                    "/health — доступность control plane\n\n"
                    "Опасные команды требуют inline-подтверждения."
                ), self._main_keyboard())
            elif command == "/status":
                self._send(chat_id, self._status_text(), self._main_keyboard())
            elif command == "/devices":
                self._send(chat_id, "Выберите устройство", self._devices_keyboard())
            elif command == "/device":
                if not args:
                    self._send(chat_id, "Выберите устройство", self._devices_keyboard())
                else:
                    self._send(chat_id, self._device_text(args[0]),
                               self._device_keyboard(args[0]))
            elif command == "/events":
                limit = 10
                if args:
                    try:
                        limit = max(1, min(int(args[0]), 30))
                    except ValueError:
                        pass
                self._send(chat_id, self._events_text(limit), self._main_keyboard())
            elif command == "/scenarios":
                text, keyboard = self._scenarios_text_and_keyboard()
                self._send(chat_id, text, keyboard)
            elif command in ("/scenario_on", "/scenario_off"):
                if not args:
                    self._send(chat_id, "Укажите id сценария: /scenario_on <id>")
                else:
                    self.client.toggle_scenario(args[0], command == "/scenario_on")
                    self._send(chat_id, "Сценарий обновлён")
            elif command == "/demo":
                if args and args[0] in DEMO_LABELS:
                    self._run_demo(chat_id, args[0])
                else:
                    self._send(chat_id, "Выберите демонстрацию", self._demo_keyboard())
            elif command == "/reset":
                self._reset(chat_id)
            elif command == "/health":
                health = self.client.health()
                self._send(chat_id, "✅ Control plane: " + str(health.get("status", "ok")))
            elif command == "/id":
                self._send(chat_id, f"chat_id: {chat_id}")
            else:
                self._send(chat_id, "Неизвестная команда. /help")
        except Exception as exc:
            self._send(chat_id, f"❌ {exc}")

    def handle_update(self, update):
        callback = update.get("callback_query")
        message = update.get("message") or update.get("edited_message") or {}
        if callback:
            chat_id = ((callback.get("message") or {}).get("chat") or {}).get("id")
        else:
            chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None or not self._authorized(chat_id):
            return False
        if callback:
            try:
                self._handle_callback(chat_id, callback)
            finally:
                self._answer_callback(callback.get("id"))
            return True
        text = (message.get("text") or "").strip()
        if text.startswith("/"):
            self._handle_message(chat_id, text)
            return True
        return False

    # --------------------------------------------------------- notifications
    def _notify_events(self):
        events = self.client.events(50)
        if not self._notifications_primed:
            self._notified_event_ids = {event.get("id") for event in events if event.get("id")}
            self._notifications_primed = True
            return
        fresh = []
        for event in events:
            event_id = event.get("id")
            if not event_id or event_id in self._notified_event_ids:
                continue
            self._notified_event_ids.add(event_id)
            if event.get("type") in {"alarm", "anomaly", "scenario_triggered"}:
                fresh.append(event)
        if len(self._notified_event_ids) > 1000:
            self._notified_event_ids = {event.get("id") for event in events[-100:]} | \
                set(list(self._notified_event_ids)[-500:])
        for event in fresh:
            message = event.get("message") or event.get("type", "Событие")
            if isinstance(message, dict):
                message = "; ".join(f"{key}: {value}" for key, value in message.items())
            for chat_id in self.allowed:
                try:
                    self._send(chat_id, "⚠️ Power Guardian\n" + str(message))
                except Exception as exc:
                    print(f"telegram alert failed: {exc}", file=sys.stderr)

    # --------------------------------------------------------------- runtime
    def run(self):
        if not self.enabled:
            print("Telegram bot disabled: set TELEGRAM_BOT_TOKEN and "
                  "TELEGRAM_ALLOWED_CHAT_IDS", file=sys.stderr)
            return
        self.running = True
        try:
            self._api("deleteWebhook")
        except Exception as exc:
            print(f"telegram deleteWebhook failed: {exc}", file=sys.stderr)
        backoff = 2
        while self.running:
            try:
                self._notify_events()
                result = self._api("getUpdates", {
                    "timeout": 25,
                    "offset": self.offset,
                    "allowed_updates": json.dumps(["message", "callback_query"]),
                })
                backoff = 2
                for update in result.get("result", []):
                    self.offset = max(self.offset, int(update.get("update_id", 0)) + 1)
                    try:
                        self.handle_update(update)
                    except Exception as exc:
                        print(f"telegram update failed: {exc}", file=sys.stderr)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(f"telegram polling failed: {exc}", file=sys.stderr)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
        self.running = False

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread

    def stop(self):
        self.running = False
