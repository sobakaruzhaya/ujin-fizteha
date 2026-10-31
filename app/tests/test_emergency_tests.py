import copy
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app.orchestrator import Orchestrator
from app.control_api import ControlServer
from app.emergency_tests import run
from devices.gas import GasDetector


class EmergencyTestsTest(unittest.TestCase):
    def test_every_emergency_passes_with_observed_sensor_history(self):
        report = run(Orchestrator())
        self.assertEqual(report['summary'], {'total': 8, 'passed': 8, 'failed': 0})
        self.assertTrue(all(len(r['timeline']) >= 3 for r in report['results']))
        self.assertTrue(all(len(r['checks']) >= 3 for r in report['results']))
        cases = {r['id']: r for r in report['results']}
        network = cases['network-overload']
        self.assertEqual(network['timeline'][1]['readings'][0]['value'], 7200)
        self.assertEqual(network['timeline'][2]['readings'][0]['value'], 0)
        self.assertTrue(network['rules'])
        self.assertFalse(cases['socket-overload']['rules'])
        self.assertFalse(cases['gas-leak']['rules'])
        self.assertTrue(any(e['type'] == 'scenario_triggered' for e in cases['fire']['events']))

    def test_a_sensor_that_does_not_detect_smoke_fails_the_fire_test(self):
        from devices.fire import FireDetector
        with patch.object(FireDetector, 'set_smoke', lambda self, value: None):
            result = run(Orchestrator(), 'fire')['results'][0]
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(any(c['signal'] == 'alarm' and not c['passed'] for c in result['checks']))

    def test_recorded_frames_show_rising_load_actual_trip_and_recovery(self):
        result = run(Orchestrator(), 'socket-overload')['results'][0]
        def series(signal):
            return [next(r['value'] for r in f['readings'] if r['signal'] == signal) for f in result['trace']]
        load, relay, power = series('load_w'), series('power_switch'), series('power_w')
        self.assertEqual(sorted(set(load)), [900, 1200, 1500, 1800, 1950, 2400])
        self.assertTrue(any(r == 0 and p == 0 for r, p in zip(relay, power)))
        self.assertEqual(power[-1], 900)
        energy = series('energy_kwh')
        self.assertGreater(energy[-1], energy[0])
        self.assertEqual(energy, sorted(energy))
        self.assertEqual(result['visualization']['threshold']['value'], 2000)

    def test_trace_preserves_checkpoints_and_sensor_thresholds_without_invented_reactions(self):
        for result in run(Orchestrator())['results']:
            with self.subTest(case=result['id']):
                frames = result['trace']
                self.assertGreater(len(frames), len(result['timeline']))
                self.assertEqual([f['seconds'] for f in frames], sorted(f['seconds'] for f in frames))
                for stage in result['timeline']:
                    self.assertEqual(frames[stage['frame']]['readings'], stage['readings'])
        from devices.fire import FireDetector
        with patch.object(FireDetector, 'set_smoke', lambda self, value: None):
            result = run(Orchestrator(), 'fire')['results'][0]
        self.assertFalse(any(r['value'] for f in result['trace'] for r in f['readings'] if r['signal'] == 'alarm'))

    def test_missing_automation_is_reported_as_failed_not_as_a_successful_shutdown(self):
        with patch.object(Orchestrator, '_evaluate_scenarios', lambda self: None):
            result = run(Orchestrator(), 'fire')['results'][0]
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(any(c['device'] == 'oven_1' and not c['passed'] for c in result['checks']))

    def test_live_state_history_rules_and_storage_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scenarios.json'
            home = Orchestrator(storage_path=path)
            home.toggle_scenario('overload_protection', False)
            home.request_command('light_1', 'offline_timeout', 40, False)
            home.request_command('light_1', 'lamp', 1, False)
            home.step()
            home.request_command('tv_1', 'power', 1)
            def state():
                return copy.deepcopy((home.state()['devices'], home.scenarios, home.events,
                    home.history, home.confirmations, home._edges,
                    {k: d.tick_count for k, d in home.devices.items()}, home.devices['light_1']._timer))
            before, saved = state(), path.read_bytes()
            run(home)
            self.assertEqual(state(), before)
            self.assertEqual(path.read_bytes(), saved)
            self.assertNotIn('gas_test', home.devices)


class GasDetectorTest(unittest.TestCase):
    def test_threshold_latching_and_reset_do_not_hide_an_active_leak(self):
        device = GasDetector(logger=lambda _: None)
        device.set_concentration(9.9); device.step(1)
        self.assertEqual(device.signals['alarm'].value, 0)
        device.set_concentration(10); device.step(1)
        self.assertEqual(device.signals['alarm'].value, 1)
        device.on_command('reset_alarm', 1); device.step(1)
        self.assertEqual(device.signals['siren'].value, 1)
        device.set_concentration(0); device.step(1)
        self.assertEqual(device.signals['alarm'].value, 1)
        device.on_command('reset_alarm', 1); device.step(1)
        self.assertEqual(device.signals['alarm'].value, 0)
        self.assertEqual(device.signals['siren'].value, 0)


class EmergencyApiTest(unittest.TestCase):
    def setUp(self):
        self.server = ControlServer(Orchestrator(), port=0)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def request(self, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f'http://127.0.0.1:{self.server.port}/api/emergency-tests', data=data,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def test_catalog_individual_and_batch_reports(self):
        items = self.request()['tests']
        self.assertEqual(len(items), 8)
        self.assertIn('тестовая модель', next(c for c in items if c['id'] == 'gas-leak')['note'])
        report = self.request({'case': 'gas-leak'})
        self.assertEqual(report['results'][0]['id'], 'gas-leak')
        self.assertEqual(report['summary']['passed'], 1)
        self.assertEqual(self.request({})['summary']['passed'], 8)

    def test_invalid_case_and_request_shape_are_rejected(self):
        for body in [{'case': 'missing'}, {'case': 12}, []]:
            with self.subTest(body=body), self.assertRaises(urllib.error.HTTPError) as context:
                self.request(body)
            self.assertEqual(context.exception.code, 400)
            context.exception.close()


if __name__ == '__main__':
    unittest.main()
