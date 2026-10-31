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
        self.assertTrue({'get_scenario', 'update_scenario', 'list_scenario_templates', 'create_scenario_from_template',
            'list_emergency_tests', 'run_emergency_tests', 'list_device_diagnostics', 'run_device_diagnostics',
            'get_ujin_status', 'manage_ujin_integration', 'describe_api'}.issubset(names))

    def test_templates_and_update_tools_use_the_same_scenario_store(self):
        self.assertEqual(len(call(self.server, 'list_scenario_templates')), 8)
        created = call(self.server, 'create_scenario_from_template', {'template_key': 'cinema', 'enabled': False})
        self.assertFalse(created['enabled'])
        self.assertEqual(call(self.server, 'get_scenario', {'scenario_id': created['id']}), created)
        created['name'] = 'Updated from MCP'
        result = call(self.server, 'update_scenario', {'scenario_id': created['id'], 'scenario': created})
        self.assertEqual(result['name'], 'Updated from MCP')

    def test_isolated_test_tools_can_return_recorded_trace(self):
        import copy
        before = copy.deepcopy(self.orchestrator.state()['devices'])
        self.assertEqual(len(call(self.server, 'list_emergency_tests')['tests']), 8)
        report = call(self.server, 'run_emergency_tests', {'case_id': 'socket-overload', 'include_trace': True})
        self.assertEqual(report['summary']['passed'], 1)
        self.assertTrue(report['results'][0]['trace'])
        concise = call(self.server, 'run_emergency_tests', {'case_id': 'gas-leak'})
        self.assertNotIn('trace', concise['results'][0])
        self.assertEqual(len(call(self.server, 'list_device_diagnostics')['devices']), 15)
        self.assertEqual(call(self.server, 'run_device_diagnostics', {'device': 'light_1'})['summary']['passed'], 1)
        self.assertEqual(before, self.orchestrator.state()['devices'])

    def test_ujin_and_resources_work_through_the_shared_http_api(self):
        from app.control_api import ControlServer
        from app.home_client import HttpHomeClient
        from app.mcp_server import build_server
        control = ControlServer(self.orchestrator, port=0)
        control.start()
        try:
            server = build_server(HttpHomeClient(f'http://127.0.0.1:{control.port}'))
            self.assertIn('configured', call(server, 'get_ujin_status'))
            self.assertFalse(call(server, 'manage_ujin_integration', {'action': 'stop'})['running'])
            self.assertEqual(call(server, 'describe_api')['name'], 'UjinFizteha')
            uris = {str(resource.uri) for resource in asyncio.run(server.list_resources())}
            self.assertTrue({'home://scenario-templates', 'home://tests/emergency', 'home://integrations/ujin', 'home://api'}.issubset(uris))
        finally: control.stop()

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
