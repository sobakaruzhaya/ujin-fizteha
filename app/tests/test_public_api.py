import copy
import json
import unittest
import urllib.error
import urllib.request

from app.control_api import ControlServer
from app.home_client import HttpHomeClient
from app.orchestrator import Orchestrator


class PublicApiTest(unittest.TestCase):
    def setUp(self):
        self.home = Orchestrator()
        self.server = ControlServer(self.home, port=0)
        self.server.start()
        self.base = f'http://127.0.0.1:{self.server.port}'
        self.client = HttpHomeClient(self.base)

    def tearDown(self):
        self.server.stop()

    def request(self, path, body=None, method=None):
        req = urllib.request.Request(self.base + path, method=method,
            data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as reply:
            return reply.status, json.load(reply)

    def test_discovery_openapi_docs_and_reference_integrity(self):
        self.assertEqual(self.request('/api')[1]['name'], 'UjinFizteha')
        schema = self.request('/api/openapi.json')[1]
        self.assertEqual(schema['openapi'], '3.1.0')
        operations = [op for methods in schema['paths'].values() for op in methods.values()]
        self.assertEqual(len({op['operationId'] for op in operations}), len(operations))
        def check(node):
            if isinstance(node, dict):
                if '$ref' in node:
                    self.assertIn(node['$ref'].split('/')[-1], schema['components']['schemas'])
                for value in node.values(): check(value)
            elif isinstance(node, list):
                for value in node: check(value)
        check(schema)
        with urllib.request.urlopen(self.base + '/api/docs') as reply:
            self.assertIn('text/html', reply.headers['Content-Type'])
            self.assertIn(b'/api/openapi.json', reply.read())
        req = urllib.request.Request(self.base + '/api/openapi.json', method='HEAD')
        with urllib.request.urlopen(req) as reply:
            self.assertEqual(reply.status, 200)
            self.assertGreater(int(reply.headers['Content-Length']), 100)
            self.assertEqual(reply.read(), b'')

    def test_single_device_statistics_and_immediate_command_share_the_home(self):
        result = self.client.device('light_1')
        self.assertEqual(result['metadata']['name'], 'Основной свет')
        self.assertTrue(result['declaration'])
        self.request('/api/commands', {'device': 'light_1', 'signal': 'lamp', 'value': 1})
        self.assertEqual(self.home.state()['devices']['light_1']['lamp'], 1)
        self.home.step()
        self.assertEqual(self.client.statistics()['total_power_w'], self.home.state()['summary']['power_w'])

    def test_template_scenario_read_update_delete_and_name_collision(self):
        first = self.client.create_from_template('cinema', enabled=False)
        self.assertFalse(first['enabled'])
        second = self.client.create_from_template('cinema')
        self.assertEqual(second['name'], 'Киновечер (2)')
        self.assertEqual(self.client.scenario(first['id']), first)
        first['do'][0]['value'] = 35
        updated = self.client.update_scenario(first['id'], first)
        self.assertEqual(updated['do'][0]['value'], 35)
        custom = self.client.create_scenario({**first, 'id': 'правило-света'})
        self.assertEqual(self.client.scenario(custom['id'])['id'], 'правило-света')
        self.client.delete_scenario(custom['id'])
        self.assertEqual(self.client.delete_scenario(first['id'])['status'], 'deleted')
        self.assertEqual(len(self.client.scenarios()), 2)

    def test_errors_are_json_and_invalid_requests_do_not_modify_state(self):
        before = copy.deepcopy(self.home.state()['devices'])
        for path, body, method, code in [
            ('/api/devices/absent', None, 'GET', 404),
            ('/api/scenarios/absent', None, 'GET', 404),
            ('/api/scenarios/absent', {}, 'PUT', 404),
            ('/api/scenario-templates/absent/apply', {}, 'POST', 404),
            ('/api/commands', [], 'POST', 400),
            ('/api/commands', {'device': 'light_1', 'signal': 'brightness', 'value': 101}, 'POST', 400),
            ('/api/scenario-templates/cinema/apply', {'enabled': 'false'}, 'POST', 400),
        ]:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(path, body, method)
            with caught.exception as reply:
                self.assertEqual(reply.code, code)
                self.assertIn('error', json.load(reply))
        self.assertEqual(before, self.home.state()['devices'])

    def test_emergency_api_exposes_trace_without_touching_live_devices(self):
        before = copy.deepcopy((self.home.state()['devices'], self.home.events, self.home.scenarios))
        result = self.client.run_tests('socket-overload')['results'][0]
        self.assertEqual(result['status'], 'passed')
        self.assertGreater(len(result['trace']), len(result['timeline']))
        self.assertEqual(before, (self.home.state()['devices'], self.home.events, self.home.scenarios))


if __name__ == '__main__': unittest.main()
