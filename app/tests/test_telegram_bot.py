import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from app.home_client import LocalHomeClient
from app.orchestrator import Orchestrator
from app.telegram_bot import TelegramBot


class FakeApi:
    def __init__(self):
        self.calls = []

    def __call__(self, method, payload=None):
        self.calls.append((method, dict(payload or {})))
        return {"ok": True, "result": []}

    def sent(self):
        return [dict(payload, text=payload.get('text', payload.get('caption', '')))
                for method, payload in self.calls if method in ('sendMessage', 'sendPhoto')]

    def last_text(self):
        return self.sent()[-1]["text"]


class TelegramBotTest(unittest.TestCase):
    def setUp(self):
        self.orchestrator = Orchestrator(tick_seconds=60)
        self.api = FakeApi()
        self.bot = TelegramBot(LocalHomeClient(self.orchestrator), token="test-token",
                               allowed_chat_ids="42,43", api=self.api)

    def tearDown(self):
        self.orchestrator.stop()

    def message(self, text, chat_id=42):
        self.bot.handle_update({"message": {"chat": {"id": chat_id}, "text": text}})

    def callback(self, data, callback_id="cb-1", chat_id=42):
        self.bot.handle_update({"callback_query": {
            "id": callback_id,
            "data": data,
            "message": {"chat": {"id": chat_id}},
        }})

    def test_unauthorized_chat_is_ignored(self):
        self.message("/status", chat_id=99)
        self.assertEqual(self.api.calls, [])

    def test_status_lists_all_devices(self):
        self.message("/status")
        text = self.api.last_text()
        for name in ("Умная розетка", "Основной свет", "Термостат", "Приточная вентиляция"):
            self.assertIn(name, text)

    def test_devices_keyboard(self):
        self.message("/devices")
        payload = self.api.sent()[-1]
        self.assertIn("Умная розетка", payload["reply_markup"])
        self.assertIn("Основной свет", payload["reply_markup"])

    def test_device_command_executes_immediately_like_the_web(self):
        self.callback("cmd:smart_plug_1:power_switch:1")
        text = self.api.last_text()
        self.assertIn("выполнена", self.api.last_text().lower())
        self.assertEqual(self.orchestrator.state()["devices"]["smart_plug_1"]["power_switch"], 1)

    def test_scenario_toggle(self):
        encoded = TelegramBot._encode_id("overload_protection")
        self.callback(f"sc:{encoded}:0")
        self.assertFalse(self.orchestrator.list_scenarios()[0]["enabled"])

    def test_demo_callback_runs_preset(self):
        self.callback("demo:co2")
        self.assertEqual(self.orchestrator.devices["ventilation_1"].signals["co2"].value, 1500)
        self.assertTrue(any(event["type"] == "demo_started" for event in self.orchestrator.events))

    def test_notifications_are_primed_and_not_duplicated(self):
        self.orchestrator.add_event("alarm", message="old alarm")
        self.bot._notify_events()
        self.assertEqual(self.api.sent(), [])

        self.orchestrator.add_event("alarm", message="new alarm")
        self.bot._notify_events()
        self.assertEqual(len(self.api.sent()), 2)
        self.assertIn("new alarm", self.api.last_text())

        self.bot._notify_events()
        self.assertEqual(len(self.api.sent()), 2)

    def test_events_and_health(self):
        self.orchestrator.add_event("test", message="hello")
        self.message("/events 5")
        self.assertIn("hello", self.api.last_text())
        self.message("/health")
        self.assertIn("ok", self.api.last_text())

    def test_layout_labels_work_with_http_string_keys(self):
        declaration = [{"name": "mode", "layout": {"0": "выкл", "3": "авто"}}]
        self.assertEqual(TelegramBot._layout_value(declaration, "mode", 3), "авто")
        self.assertEqual(TelegramBot._layout_value(declaration, "mode", 0), "выкл")

    def test_disabled_without_token_or_allowed_chats(self):
        self.assertFalse(TelegramBot(LocalHomeClient(self.orchestrator), token="",
                                     allowed_chat_ids="42", api=self.api).enabled)
        self.assertFalse(TelegramBot(LocalHomeClient(self.orchestrator), token="x",
                                     allowed_chat_ids="", api=self.api).enabled)


if __name__ == "__main__":
    unittest.main()
