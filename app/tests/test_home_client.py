import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from app.control_api import ControlServer
from app.home_client import HomeApiError, HttpHomeClient, LocalHomeClient, ensure_client
from app.orchestrator import Orchestrator


class HomeClientTest(unittest.TestCase):
    def setUp(self):
        self.orchestrator = Orchestrator(tick_seconds=60)
        self.server = ControlServer(self.orchestrator, port=0)
        self.server.start()
        self.base = f"http://127.0.0.1:{self.server.port}"
        self.client = HttpHomeClient(self.base, timeout=3)

    def tearDown(self):
        self.server.stop()
        self.orchestrator.stop()

    def test_read_endpoints(self):
        self.assertEqual(self.client.health(), {"status": "ok"})
        state = self.client.state()
        self.assertIn("smart_plug_1", state["devices"])
        self.assertIn("smart_plug_1", self.client.declarations())
        self.assertTrue(self.client.scenarios())
        self.assertIsInstance(self.client.history(10), list)

    def test_events_limit(self):
        for index in range(10):
            self.orchestrator.add_event("test", message=f"event {index}")
        events = self.client.events(4)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[-1]["message"], "event 9")

    def test_two_step_command(self):
        preview = self.client.request_command("smart_plug_1", "power_switch", 1)
        self.assertEqual(preview["status"], "confirmation_required")
        self.assertEqual(self.client.state()["devices"]["smart_plug_1"]["power_switch"], 0)
        result = self.client.confirm_command(preview["confirmation_id"])
        self.assertEqual(result["status"], "applied")
        self.assertEqual(self.client.state()["devices"]["smart_plug_1"]["power_switch"], 1)

    def test_scenario_lifecycle(self):
        created = self.client.create_scenario({
            "name": "Test rule",
            "when": {"device": "smart_plug_1", "signal": "power_w",
                     "operator": ">", "value": 100},
            "do": [{"device": "light_1", "signal": "lamp", "value": 1}],
        })
        self.assertFalse(self.client.toggle_scenario(created["id"], False)["enabled"])
        self.assertEqual(self.client.delete_scenario(created["id"])["status"], "deleted")
        self.assertNotIn(created["id"], {s["id"] for s in self.client.scenarios()})

    def test_demo_simulation_and_reset(self):
        self.assertEqual(self.client.experiment("overload")["status"], "started")
        self.assertIn("state", self.client.simulate(2))
        self.assertIn("devices", self.client.reset())

    def test_http_error_has_message(self):
        with self.assertRaises(HomeApiError) as context:
            self.client.request_command("missing", "power_switch", 1)
        self.assertIn("не найдены", str(context.exception))

    def test_local_adapter_accepts_orchestrator(self):
        local = ensure_client(self.orchestrator)
        self.assertIsInstance(local, LocalHomeClient)
        self.assertIn("devices", local.state())


if __name__ == "__main__":
    unittest.main()
