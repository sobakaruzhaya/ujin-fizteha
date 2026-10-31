"""Telegram Bot API adapter без обязательной внешней библиотеки."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request


class TelegramBot:
    def __init__(self, orchestrator, token=None, allowed_chat_ids=None):
        self.orchestrator = orchestrator
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw = allowed_chat_ids if allowed_chat_ids is not None else os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
        self.allowed = {str(x.strip()) for x in raw.split(",") if x.strip()}
        self.offset = 0
        self.running = False
        self._notified_event_ids = set()

    @property
    def enabled(self):
        return bool(self.token and self.allowed)

    def _api(self, method, payload=None):
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = urllib.parse.urlencode(payload or {}).encode()
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=35) as response:
            return json.loads(response.read().decode())

    def _send(self, chat_id, text, keyboard=None):
        payload = {"chat_id": chat_id, "text": text}
        if keyboard:
            payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard}, ensure_ascii=False)
        return self._api("sendMessage", payload)

    def _authorized(self, chat_id):
        return str(chat_id) in self.allowed

    def _status_text(self):
        state = self.orchestrator.state()["devices"]["smart_plug_1"]
        return (f"🔌 Умная розетка\nРеле: {'вкл' if state['power_switch'] else 'выкл'}\n"
                f"Мощность: {state['power_w']} Вт\nЭнергия: {state['energy_kwh']} кВт·ч\n"
                f"Лимит: {state['power_limit_w']} Вт\nЗащита: {'сработала' if state['overload_alarm'] else 'нет'}")

    def handle_update(self, update):
        message = update.get("message") or {}
        callback = update.get("callback_query")
        chat_id = (message.get("chat") or {}).get("id") if message else (callback.get("message", {}).get("chat", {}).get("id") if callback else None)
        if chat_id is None or not self._authorized(chat_id):
            return
        if callback:
            data = callback.get("data", "")
            if data.startswith("confirm:"):
                try:
                    result = self.orchestrator.confirm_command(data.split(":", 1)[1])
                    self._send(chat_id, "✅ Команда выполнена\n" + json.dumps(result, ensure_ascii=False))
                except Exception as exc:
                    self._send(chat_id, f"❌ {exc}")
            elif data == "plug:off":
                result = self.orchestrator.request_command("smart_plug_1", "power_switch", 0)
                self._send(chat_id, "Подтвердите отключение розетки", [[{"text": "Подтвердить", "callback_data": "confirm:" + result["confirmation_id"]}]])
            self._api("answerCallbackQuery", {"callback_query_id": callback.get("id")})
            return
        text = (message.get("text") or "").strip()
        if text == "/status" or text == "/start":
            self._send(chat_id, self._status_text(), [[{"text": "Выключить розетку", "callback_data": "plug:off"}]])
        elif text == "/events":
            events = self.orchestrator.events_since(10)
            self._send(chat_id, "📋 События\n" + ("\n".join(e.get("message", e.get("type", "event")) for e in events) or "Нет событий"))
        elif text == "/scenarios":
            scenarios = self.orchestrator.list_scenarios()
            self._send(chat_id, "🧩 Сценарии\n" + "\n".join(f"{'✅' if s['enabled'] else '⏸'} {s['name']}" for s in scenarios))
        elif text == "/demo":
            self.orchestrator.reset()
            self.orchestrator.device.set_value("load_w", 2400.0)
            result = self.orchestrator.request_command("smart_plug_1", "power_switch", 1)
            self._send(chat_id, "Демо подготовлено. Подтвердите включение нагрузки", [[{"text": "Запустить", "callback_data": "confirm:" + result["confirmation_id"]}]])
        elif text == "/help":
            self._send(chat_id, "/status — состояние\n/events — события\n/scenarios — сценарии\n/demo — запустить демо")

    def run(self):
        if not self.enabled:
            return
        self.running = True
        while self.running:
            try:
                self._notify_events()
                result = self._api("getUpdates", {"timeout": 25, "offset": self.offset})
                for update in result.get("result", []):
                    self.offset = update["update_id"] + 1
                    self.handle_update(update)
            except Exception as exc:
                self.orchestrator.add_event("telegram_error", message=str(exc))
                time.sleep(2)

    def _notify_events(self):
        """Отправляет аварийные события разрешённым чатам один раз."""
        for event in self.orchestrator.events_since(50):
            event_id = event.get("id")
            if event_id in self._notified_event_ids:
                continue
            self._notified_event_ids.add(event_id)
            if event.get("type") not in {"alarm", "telegram_error"}:
                continue
            message = event.get("message", "Событие Power Guardian")
            for chat_id in self.allowed:
                self._send(chat_id, "⚠️ Power Guardian\n" + message)

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread

