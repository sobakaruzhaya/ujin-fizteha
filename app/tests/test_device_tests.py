import copy
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app.control_api import ControlServer
from app.device_tests import catalog, run, SUITES
from app.orchestrator import Orchestrator


class DiagnosticsTest(unittest.TestCase):
    def test_catalog_covers_every_current_device(self):
        home = Orchestrator()
        result = catalog(home)
        self.assertEqual(result['mode'], 'isolated')
        self.assertEqual({d['id'] for d in result['devices']}, set(home.devices))
        self.assertTrue(all(d['supported'] for d in result['devices']))

    def test_all_suites_exercise_real_devices_and_pass(self):
        result = run(Orchestrator())
        self.assertEqual(result['summary'], {'total': 15, 'passed': 15, 'failed': 0, 'unsupported': 0})
        self.assertTrue(all(len(d['checks']) >= 3 for d in result['results']))
        self.assertTrue(all('before' in d and 'after' in d for d in result['results']))

    def test_tests_leave_live_state_rules_events_timers_and_storage_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scenarios.json'
            home = Orchestrator(storage_path=path)
            home.toggle_scenario('overload_protection', False)
            home.request_command('light_1', 'offline_timeout', 4, False)
            home.request_command('light_1', 'lamp', 1, False)
            home.step()
            confirmation = home.request_command('tv_1', 'power', 1)
            before = copy.deepcopy((home.state()['devices'], home.scenarios, home.events, home.history, home.confirmations, home._edges, home.devices['light_1']._timer))
            saved = path.read_bytes()
            run(home)
            after = (home.state()['devices'], home.scenarios, home.events, home.history, home.confirmations, home._edges, home.devices['light_1']._timer)
            self.assertEqual(before, after)
            self.assertEqual(saved, path.read_bytes())
            self.assertIn(confirmation['confirmation_id'], home.confirmations)

    def test_a_broken_device_produces_a_failed_check(self):
        def broken(probe):
            probe.expect('Проверка неисправного реле', 'power_switch', 1)
        with patch.dict(SUITES, {'smart_plug': ('Поломка', broken)}):
            result = run(Orchestrator(), 'smart_plug_1')
        self.assertEqual(result['summary']['failed'], 1)
        self.assertFalse(result['results'][0]['checks'][0]['passed'])

    def test_unexpected_error_does_not_abort_other_devices(self):
        def broken(probe):
            raise RuntimeError('Diagnostic failure')
        with patch.dict(SUITES, {'smart_plug': ('Поломка', broken)}):
            report = run(Orchestrator())
        self.assertEqual(report['summary']['total'], 15)
        self.assertEqual(report['summary']['failed'], 1)
        self.assertEqual(report['summary']['passed'], 14)
        self.assertIn('Diagnostic failure', report['results'][0]['checks'][0]['error'])


class DiagnosticsApiTest(unittest.TestCase):
    def setUp(self):
        self.server = ControlServer(Orchestrator(), port=0)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def request(self, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f'http://127.0.0.1:{self.server.port}/api/device-tests', data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def test_catalog_single_and_all_runs(self):
        self.assertEqual(len(self.request()['devices']), 15)
        report = self.request({'device': 'kettle_1'})
        self.assertEqual(report['summary']['total'], 1)
        self.assertEqual(report['results'][0]['device'], 'kettle_1')
        self.assertEqual(self.request({})['summary']['passed'], 15)

    def test_invalid_device_and_body_are_rejected(self):
        for body in [{'device': 'missing'}, {'device': 1}, []]:
            with self.subTest(body=body), self.assertRaises(urllib.error.HTTPError) as exc:
                self.request(body)
            self.assertEqual(exc.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
