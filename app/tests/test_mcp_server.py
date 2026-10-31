import asyncio
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from app.home_client import LocalHomeClient
from app.orchestrator import Orchestrator

try:
    import mcp  # noqa: F401
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


def payload(result):
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    values = []
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            values.append(json.loads(text))
        except ValueError:
            values.append(text)
    if len(values) == 1:
        return values[0]
    return values


def call(server, name, arguments=None):
    return payload(asyncio.run(server.call_tool(name, arguments or {})))


@unittest.skipUnless(HAS_MCP, "MCP SDK is not installed")
class McpServerTest(unittest.TestCase):
    def setUp(self):
        self.orchestrator = Orchestrator(tick_seconds=60)
        self.server = __import__("app.mcp_server", fromlist=["build_server"]).build_server(
            LocalHomeClient(self.orchestrator))

    def tearDown(self):
        self.orchestrator.stop()

    def test_tools_are_registered(self):
        names = {tool.name for tool in asyncio.run(self.server.list_tools())}
        expected = {"get_home_state", "list_devices", "get_device_state",
                    "get_recent_events", "analyze_energy", "list_scenarios",
                    "create_scenario", "toggle_scenario", "delete_scenario",
                    "simulate_scenario", "request_device_command",
                    "confirm_device_command", "run_demo", "reset_home", "get_health"}
        self.assertTrue(expected.issubset(names))

    def test_get_home_state_and_devices(self):
        state = call(self.server, "get_home_state")
        self.assertIn("smart_plug_1", state["devices"])
        devices = call(self.server, "list_devices")
        self.assertEqual(len(devices), 15)
        self.assertTrue(all(item["declaration"] for item in devices))

    def test_two_step_command_flow(self):
        preview = call(self.server, "request_device_command", {
            "device": "smart_plug_1", "signal": "power_switch", "value": 1})
        self.assertEqual(preview["status"], "confirmation_required")
        result = call(self.server, "confirm_device_command", {
            "confirmation_id": preview["confirmation_id"]})
        self.assertEqual(result["status"], "applied")

    def test_scenario_tools(self):
        created = call(self.server, "create_scenario", {"scenario": {
            "name": "MCP rule",
            "when": {"device": "smart_plug_1", "signal": "power_w",
                     "operator": ">", "value": 100},
            "do": [{"device": "light_1", "signal": "lamp", "value": 1}],
        }})
        toggled = call(self.server, "toggle_scenario", {
            "scenario_id": created["id"], "enabled": False})
        self.assertFalse(toggled["enabled"])
        deleted = call(self.server, "delete_scenario", {
            "scenario_id": created["id"]})
        self.assertEqual(deleted["status"], "deleted")

    def test_simulation_does_not_change_live_state(self):
        before = self.orchestrator.state()["devices"]["smart_plug_1"]
        result = call(self.server, "simulate_scenario", {"seconds": 2})
        self.assertIn("state", result)
        self.assertEqual(before, self.orchestrator.state()["devices"]["smart_plug_1"])

    def test_energy_analysis(self):
        result = call(self.server, "analyze_energy")
        self.assertIn("total_power_w", result)
        self.assertEqual(len(result["devices"]), 8)
        self.assertEqual(result['total_power_w'], self.orchestrator.state()['summary']['power_w'])


if __name__ == "__main__":
    unittest.main()
