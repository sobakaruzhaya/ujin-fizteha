import json
import os
import sys
import unittest
import tempfile
import copy
import re
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
    def test_climate_off_stops_actuators_and_freezes_sensor_readings(self):
        o = Orchestrator()
        o.devices['ventilation_1'].set_value('co2', 1200)
        o.step()
        self.assertGreater(o.state()['devices']['ventilation_1']['fan_speed'], 0)
        o.request_command('ventilation_1', 'mode', 0, False)
        self.assertEqual(o.state()['devices']['ventilation_1']['fan_speed'], 0)
        self.assertEqual(o.state()['devices']['ventilation_1']['heat_pct'], 0)
        co2 = o.state()['devices']['ventilation_1']['co2']
        measurements = {s: o.state()['devices']['ventilation_1'][s] for s in ['co2', 'pm25', 'supply_temp']}
        for _ in range(5):
            o.step()
        self.assertEqual({s: o.state()['devices']['ventilation_1'][s] for s in measurements}, measurements)
        self.assertEqual(o.state()['devices']['ventilation_1']['fan_speed'], 0)
        thermostat = o.devices['thermostat_1']
        thermostat.set_value('temperature', 18)
        o.step()
        self.assertEqual(o.state()['devices']['thermostat_1']['output'], 1)
        o.request_command('thermostat_1', 'mode', 0, False)
        temperature = o.state()['devices']['thermostat_1']['temperature']
        for _ in range(5):
            o.step()
        self.assertEqual(o.state()['devices']['thermostat_1']['mode'], 0)
        self.assertEqual(o.state()['devices']['thermostat_1']['output'], 0)
        self.assertEqual(o.state()['devices']['thermostat_1']['temperature'], temperature)
        o.request_command('ventilation_1', 'mode', 1, False)
        o.request_command('thermostat_1', 'mode', 3, False)
        o.step()
        self.assertLess(o.state()['devices']['ventilation_1']['co2'], co2)
        self.assertNotEqual(o.state()['devices']['thermostat_1']['temperature'], temperature)

    def test_setting_fan_speed_switches_to_manual_mode(self):
        o = Orchestrator()
        o.request_command('ventilation_1', 'fan_speed', 5, False)
        o.step()
        self.assertEqual(o.state()['devices']['ventilation_1']['mode'], 2)
        self.assertEqual(o.state()['devices']['ventilation_1']['fan_speed'], 5)

    def test_ventilation_restores_manual_speed_after_off(self):
        o = Orchestrator()
        for signal, value in [('mode', 2), ('fan_speed', 4), ('mode', 0)]:
            o.request_command('ventilation_1', signal, value, False)
        o.step()
        self.assertEqual(o.state()['devices']['ventilation_1']['fan_speed'], 0)
        o.request_command('ventilation_1', 'mode', 2, False)
        o.step()
        self.assertEqual(o.state()['devices']['ventilation_1']['fan_speed'], 4)

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

    def test_home_device_inventory(self):
        expected = {
            'smart_plug_1', 'light_1', 'thermostat_1', 'ventilation_1',
            'temp_sensor_1', 'leak_1', 'hub_1', 'fire_1', 'counter_1',
            'tv_1', 'fridge_1', 'kettle_1', 'stove_1', 'oven_1', 'intercom_1'}
        state = self.o.state()
        self.assertTrue(expected.issubset(state['devices']))
        self.assertTrue(expected.issubset(state['metadata']))
        declarations = self.o.declarations()
        self.assertIn('fridge_temp', {s['name'] for s in declarations['fridge_1']})
        self.assertIn('call_state', {s['name'] for s in declarations['intercom_1']})

    def test_commands_route_to_new_devices(self):
        self.o.request_command('tv_1', 'power', 1, False)
        self.o.request_command('kettle_1', 'target_temp', 70, False)
        state = self.o.state()['devices']
        self.assertEqual(state['tv_1']['power'], 1)
        self.assertEqual(state['kettle_1']['target_temp'], 70)

    def test_comfort_demo_uses_temp_sensor(self):
        self.o.experiment('comfort')
        self.o.step()
        state = self.o.state()['devices']
        self.assertLess(state['temp_sensor_1']['temperature'], 21)
        self.assertEqual(state['thermostat_1']['mode'], 1)
        self.assertEqual(state['thermostat_1']['target_temp'], 23)
        self.assertEqual(state['thermostat_1']['output'], 1)

    def test_leak_demo_sounds_hub_and_cuts_load(self):
        self.o.request_command('smart_plug_1', 'power_switch', 1, False)
        self.o.experiment('leak')
        self.o.step()
        state = self.o.state()['devices']
        self.assertEqual(state['hub_1']['leak'], 1)
        self.assertEqual(state['hub_1']['siren'], 1)
        self.assertEqual(state['smart_plug_1']['power_switch'], 0)

    def test_fire_demo_raises_alarm(self):
        self.o.experiment('fire')
        self.o.step()
        self.assertEqual(self.o.state()['devices']['fire_1']['alarm'], 1)

    def test_intercom_demo_rings_and_turns_on_light(self):
        self.o.experiment('intercom')
        self.o.step()
        state = self.o.state()['devices']
        self.assertEqual(state['intercom_1']['call_state'], 1)
        self.assertEqual(state['light_1']['lamp'], 1)

    def test_cross_device_rule_and_single_edge(self):
        self.o.create_scenario({'name': 'Свежий воздух', 'when': {
            'device': 'ventilation_1', 'signal': 'co2', 'operator': '>', 'value': 1000},
            'do': [{'device': 'light_1', 'signal': 'lamp', 'value': 1}]})
        self.o.experiment('co2')
        self.o.step()
        self.assertEqual(self.o.devices['light_1'].signals['lamp'].value, 1)
        self.o.step()
        self.assertEqual(len([e for e in self.o.events if e['type'] == 'scenario_triggered']), 1)

    def test_invalid_rule_cannot_break_loop(self):
        for value in (float('nan'), '1000', None):
            with self.assertRaises(ValueError):
                self.o.create_scenario({'name': 'Broken', 'when': {
                    'device': 'smart_plug_1', 'signal': 'power_w', 'operator': '>', 'value': value},
                    'do': [{'device': 'light_1', 'signal': 'lamp', 'value': 1}]})
        self.o.step()

    def test_simulation_preserves_internal_timers_edges_and_events(self):
        self.o.request_command('light_1', 'offline_timeout', 10, False)
        self.o.request_command('light_1', 'lamp', 1, False)
        before = (self.o.devices['light_1']._timer, self.o.device.tick_count,
                  copy.deepcopy(self.o.events), copy.deepcopy(self.o._edges))
        self.o.simulate(30)
        after = (self.o.devices['light_1']._timer, self.o.device.tick_count,
                 self.o.events, self.o._edges)
        self.assertEqual(before, after)
        self.assertEqual(self.o.devices['light_1'].signals['lamp'].value, 1)

    def test_persistent_scenario_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'scenarios.json')
            first = Orchestrator(storage_path=path)
            first.toggle_scenario('overload_protection', False)
            second = Orchestrator(storage_path=path)
            self.assertFalse(second.list_scenarios()[0]['enabled'])
            second.delete_scenario('overload_protection')
            self.assertEqual(Orchestrator(storage_path=path).list_scenarios(), [])


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
        if not os.path.isfile(os.path.join(ROOT, 'app', 'web', 'dist', 'index.html')):
            self.skipTest('Run npm run build to test the production frontend')
        status, content_type, body = self.get("/web/")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html")
        html = body.decode("utf-8")
        self.assertIn("UjinFizteha", html)

        stylesheet = re.search(r'href="([^"]+\.css)"', html).group(1)
        javascript = re.search(r'src="([^"]+\.js)"', html).group(1)
        status, content_type, body = self.get(stylesheet)
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/css")
        self.assertIn(b"--accent", body)

        status, content_type, body = self.get(javascript)
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


if __name__ == "__main__":
    unittest.main()
