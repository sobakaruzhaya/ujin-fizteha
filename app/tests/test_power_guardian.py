import json
import os
import sys
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from app.control_api import ControlServer
from app.orchestrator import Orchestrator
from task.quattrocold.emulators.devices.smart_plug import SmartPlug


class SmartPlugTest(unittest.TestCase):
    def test_overload_trips_and_blocks_reenable(self):
        plug = SmartPlug(serial="1", load_w=2400)
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "power_limit_w": 2000}]})
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "power_switch": 1}]})
        plug.step()
        self.assertEqual(plug.signals["power_switch"].value, 0)
        self.assertEqual(plug.signals["overload_alarm"].value, 1)
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "power_switch": 1}]})
        self.assertEqual(plug.signals["power_switch"].value, 0)

    def test_reset_protection_allows_power(self):
        plug = SmartPlug(serial="1", load_w=2400)
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "power_switch": 1}]})
        plug.step()
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "reset_protection": 1}]})
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "load_w": 900}]})
        plug.handle_recv({"recv": [{"command": "management", "id": "1", "power_switch": 1}]})
        plug.step()
        self.assertEqual(plug.signals["power_switch"].value, 1)
        self.assertEqual(plug.signals["overload_alarm"].value, 0)


class OrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.o = Orchestrator(tick_seconds=60)

    def tearDown(self):
        self.o.stop()

    def test_dangerous_command_requires_confirmation(self):
        result = self.o.request_command("smart_plug_1", "power_switch", 1)
        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(self.o.state()["devices"]["smart_plug_1"]["power_switch"], 0)
        self.o.confirm_command(result["confirmation_id"])
        self.assertEqual(self.o.state()["devices"]["smart_plug_1"]["power_switch"], 1)

    def test_overload_scenario_creates_alarm(self):
        self.o.device.set_value("load_w", 2400)
        self.o.device.set_value("power_switch", 1)
        self.o.device.on_command("power_switch", 1)
        self.o.device.step()
        self.o._evaluate_scenarios()
        state = self.o.state()["devices"]["smart_plug_1"]
        self.assertEqual(state["overload_alarm"], 1)
        self.assertTrue(any(e["type"] == "scenario_triggered" for e in self.o.events))

    def test_simulation_restores_state(self):
        before = self.o.state()
        result = self.o.simulate(3)
        self.assertIn("state", result)
        self.assertEqual(before["devices"]["smart_plug_1"], self.o.state()["devices"]["smart_plug_1"])


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.o = Orchestrator(tick_seconds=60)
        self.server = ControlServer(self.o, port=0)
        self.server.start()
        self.base = f"http://127.0.0.1:{self.server.port}"

    def tearDown(self):
        self.server.stop()
        self.o.stop()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as response:
            return response.status, response.headers.get_content_type(), response.read()

    def post(self, path, payload=None):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload or {}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())

    def test_state_api(self):
        status, content_type, body = self.get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json")
        state = json.loads(body)
        self.assertIn("smart_plug_1", state["devices"])

    def test_health_api(self):
        status, _, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_config_api(self):
        status, _, body = self.get("/api/config")
        self.assertEqual(status, 200)
        config = json.loads(body)
        self.assertEqual(config["device_id"], "smart_plug_1")
        self.assertIn("phone", config["modes"])
        self.assertIn("tv", config["modes"])

    def test_static_frontend_files(self):
        status, content_type, body = self.get("/web/")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        html = body.decode("utf-8")
        self.assertIn("Power Guardian", html)

        status, content_type, body = self.get("/web/style.css")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/css")
        self.assertIn(b"--accent", body)

        status, content_type, body = self.get("/web/app.js")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/javascript")
        self.assertIn(b"/api/state", body)

    def test_unknown_static_file_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.get("/web/missing-file.js")
        self.assertEqual(context.exception.code, 404)
        context.exception.close()

    def test_path_traversal_is_rejected(self):
        for path in ("/web/../app/run.py", "/web/%2e%2e/app/run.py"):
            with self.assertRaises(urllib.error.HTTPError) as context:
                self.get(path)
            self.assertEqual(context.exception.code, 404)
            context.exception.close()

    def test_two_step_confirmation_api(self):
        status, preview = self.post("/api/commands/preview", {
            "device": "smart_plug_1", "signal": "power_switch", "value": 1})
        self.assertEqual(status, 200)
        self.assertEqual(preview["status"], "confirmation_required")
        self.assertEqual(self.o.state()["devices"]["smart_plug_1"]["power_switch"], 0)

        status, result = self.post(f"/api/commands/{preview['confirmation_id']}/confirm")
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(self.o.state()["devices"]["smart_plug_1"]["power_switch"], 1)

    def test_expired_confirmation_is_rejected(self):
        _, preview = self.post("/api/commands/preview", {
            "device": "smart_plug_1", "signal": "power_switch", "value": 1})
        token = preview["confirmation_id"]
        self.o.confirmations[token]["expires"] = 0

        with self.assertRaises(urllib.error.HTTPError) as context:
            self.post(f"/api/commands/{token}/confirm")
        self.assertEqual(context.exception.code, 400)
        payload = json.loads(context.exception.read())
        context.exception.close()
        self.assertIn("expired", payload["error"])
        self.assertEqual(self.o.state()["devices"]["smart_plug_1"]["power_switch"], 0)


class FrontendSmokeTest(unittest.TestCase):
    def setUp(self):
        web_dir = os.path.join(ROOT, "app", "web")
        with open(os.path.join(web_dir, "index.html"), encoding="utf-8") as source:
            self.html = source.read()
        with open(os.path.join(web_dir, "style.css"), encoding="utf-8") as source:
            self.css = source.read()
        with open(os.path.join(web_dir, "app.js"), encoding="utf-8") as source:
            self.js = source.read()

    def test_html_uses_live_api_and_assets(self):
        self.assertIn("/api/state", self.js)
        self.assertIn("/api/events", self.js)
        self.assertIn("/api/scenarios", self.js)
        self.assertIn("style.css", self.html)
        self.assertIn("app.js", self.html)

    def test_phone_and_tv_modes_are_present(self):
        self.assertIn("phone", self.html)
        self.assertIn("tv", self.html)
        self.assertIn("data-mode", self.html)
        self.assertIn('mode === "tv"', self.js)
        self.assertIn('[data-mode="tv"]', self.css)

    def test_controls_and_status_are_present(self):
        for element_id in ("demo-start", "demo-reset", "reset-protection",
                           "power-on", "power-off", "protection", "events", "scenarios"):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_confirmation_flow_is_used(self):
        self.assertIn("/api/commands/preview", self.js)
        self.assertIn("/confirm", self.js)


if __name__ == "__main__":
    unittest.main()
