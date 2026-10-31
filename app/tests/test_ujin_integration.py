import json
import tempfile
import unittest
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from app.control_api import ControlServer
from app.orchestrator import Orchestrator
from app.ujin_integration import UjinIntegration, UjinError, UjinTransport, SignalTable, read_packet


def packet():
    return {'api_base': 'https://api.example.test/api', 'employee': {'login': 'PRIVATE_LOGIN', 'password': 'PRIVATE_PASSWORD'},
        'devices': [{'family': 'light', 'sn': '123456789', 'ext': 'team_light', 'model': 'model_from_packet',
                     'publish_class': 'example', 'apartment_id': '99'}]}


class FakeTransport:
    def __init__(self, packet, panel):
        self.published = []
        self.remote = {'example_lamp': '0.001', 'example_brightness': '50'}
        self.tasks = []
        self.deliver = True

    def authenticate(self): pass
    def device_info(self, binding): return {'signals': self.tasks, 'meta': {'serialnumber': binding['sn'], 'model': {'name': binding['model']}, 'class': {'name': binding['publish_class']}}}
    def panel_signals(self, binding):
        return [{'name': k, 'value': v, 'management': 'r'} for k, v in self.remote.items()]
    def publish(self, binding, rows):
        self.published.append(rows.copy())
        if self.deliver: self.remote.update({k: str(v if v else 0.001) for k, v in rows.items()})
        return {'error': 0}


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'access.json'
        self.path.write_text(json.dumps(packet()), encoding='utf-8')
        self.home = Orchestrator()
        self.state_path = Path(self.directory.name) / 'tasks.json'
        self.bridge = UjinIntegration(self.home, self.path, transport_factory=FakeTransport, state_path=self.state_path)

    def test_zip_credentials_are_read_without_extraction(self):
        archive = Path(self.directory.name) / 'packet.zip'
        with zipfile.ZipFile(archive, 'w') as z: z.writestr('bundle/доступы.json', json.dumps(packet()))
        self.assertEqual(read_packet(archive)['employee']['password'], 'PRIVATE_PASSWORD')
        self.assertFalse((Path(self.directory.name) / 'bundle').exists())

    def test_read_only_authenticates_and_reports_real_capability_without_writes(self):
        result = self.bridge.cycle('read')
        self.assertEqual(result['state'], 'connected')
        self.assertEqual(result['devices'][0]['state'], 'read_only')
        self.assertEqual(result['devices'][0]['panel_signals'], 2)
        self.assertEqual(self.bridge.transport.published, [])
        public = json.dumps(result)
        self.assertNotIn('PRIVATE_LOGIN', public)
        self.assertNotIn('PRIVATE_PASSWORD', public)
        self.assertNotIn('123456789', public)
        self.bridge.transport.remote['example_token'] = 'PRIVATE_TOKEN'
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(self.bridge.cycle()))

    def test_publish_is_scoped_to_existing_signals_and_delivery_is_verified(self):
        result = self.bridge.cycle('sync')
        self.assertEqual(set(self.bridge.transport.published[0]), {'example_lamp', 'example_brightness'})
        self.assertEqual(result['devices'][0]['verified'], 2)
        self.assertEqual(result['published'], 2)
        self.bridge.transport.deliver = False
        self.home.request_command('light_1', 'brightness', 42, False)
        result = self.bridge.cycle('sync')
        self.assertEqual(result['devices'][0]['state'], 'unverified')
        self.assertEqual(result['devices'][0]['verified'], 1)

    def test_task_executes_once_and_dedup_survives_restart(self):
        self.bridge.cycle()
        self.bridge.transport.tasks = [{'name': 'example_lamp', 'task': '1', 'task_dt': 'epoch1', 'state': {'readonly': False, 'value': '0.001'}}]
        self.bridge.cycle('sync'); self.bridge.cycle('sync')
        self.assertEqual(self.bridge.status()['commands_applied'], 1)
        self.assertEqual(self.home.devices['light_1'].signals['lamp'].value, 1)
        restarted = UjinIntegration(self.home, self.path, transport_factory=FakeTransport, state_path=self.state_path)
        restarted.cycle()
        restarted.transport.tasks = self.bridge.transport.tasks
        restarted.cycle('sync')
        self.assertEqual(restarted.status()['commands_applied'], 0)
        self.bridge.transport.tasks[0].update(task='0.001', task_dt='epoch2')
        self.bridge.transport.tasks[0]['state']['value'] = '1'
        self.bridge.cycle('sync')
        self.assertEqual(self.home.devices['light_1'].signals['lamp'].value, 0)

    def test_read_only_or_unknown_tasks_never_control_local_devices(self):
        self.bridge.cycle()
        self.bridge.transport.tasks = [
            {'name': 'example_lamp', 'task': 1, 'state': {'readonly': True}},
            {'name': 'example_lamp', 'task': 1, 'state': {}},
            {'name': 'example_foreign', 'task': 1, 'state': {'readonly': False}}]
        self.bridge.cycle('sync')
        self.assertEqual(self.bridge.status()['commands_applied'], 0)
        self.assertEqual(self.home.devices['light_1'].signals['lamp'].value, 0)

    def test_wrong_remote_identity_or_model_prevents_publication(self):
        self.bridge.cycle()
        with patch.object(self.bridge.transport, 'device_info', return_value={'meta': {'serialnumber': 'FOREIGN'}}):
            result = self.bridge.cycle('sync')
        self.assertEqual(result['devices'][0]['state'], 'error')
        self.assertFalse(self.bridge.transport.published)
        with patch.object(self.bridge.transport, 'device_info', return_value={'meta': {'serialnumber': '123456789', 'model': {'name': 'other'}, 'class': {'name': 'example'}}}):
            result = self.bridge.cycle('sync')
        self.assertEqual(result['devices'][0]['state'], 'error')
        self.assertFalse(self.bridge.transport.published)

    def test_unmatched_family_and_device_never_publish(self):
        data = packet();data['devices'][0]['family'] = 'not_a_local_device'
        self.path.write_text(json.dumps(data), encoding='utf-8')
        result = self.bridge.cycle('sync')
        self.assertEqual(result['devices'][0]['state'], 'unmapped')
        self.assertFalse(self.bridge.transport.published)

    def test_panel_parser_reads_only_signal_values_not_csrf(self):
        p = SignalTable()
        p.feed('<table><tr><td>Lamp</td><td data-v="123|example_lamp">0.001</td><td>history</td><td>—</td><td>rw</td><td><input name="csrf" value="SECRET"></td></tr></table>')
        self.assertEqual(p.rows[0]['value'], '0.001')
        self.assertEqual(p.rows[0]['management'], 'rw')
        self.assertNotIn('SECRET', json.dumps(p.rows))

    def test_transport_supports_employee_token_shape_and_never_exposes_remote_errors(self):
        t = UjinTransport(packet(), 'https://panel.example.test')
        t.panel_ready = True
        with patch.object(t, '_json', return_value={'error': 0, 'data': {'user': {'token': 'SECRET_TOKEN'}}}): t.authenticate()
        self.assertEqual(t._token, 'SECRET_TOKEN')
        with patch.object(t, '_request', return_value=(json.dumps({'error': 1, 'message': 'SECRET_TOKEN PRIVATE_PASSWORD'}), '')):
            with self.assertRaises(UjinError) as context: t.device_info(packet()['devices'][0])
        self.assertNotIn('SECRET', str(context.exception))

    def test_group_protocol_uses_json_ext_guid_class_query_auth_and_wire_zero(self):
        t = UjinTransport(packet(), 'https://panel.example.test');t._token = 'SECRET_TOKEN'
        with patch.object(t, '_json', return_value={'error': 0}) as post:
            t.publish(packet()['devices'][0], {'example_lamp': 0})
        args, kwargs = post.call_args
        self.assertEqual(args[0], '/api/import_device/group-update-device-signal/')
        self.assertEqual(kwargs['query']['apartment_id'], '99')
        self.assertEqual(kwargs['payload']['data'], [{'sn': 'team_light', 's': 'example_lamp', 'v': 0.001, 'c': 'example'}])

    def test_control_api_status_and_background_actions(self):
        server = ControlServer(self.home, port=0, ujin=self.bridge)
        server.start()
        try:
            def request(body=None):
                data = json.dumps(body).encode() if body is not None else None
                req = urllib.request.Request(f'http://127.0.0.1:{server.port}/api/integrations/ujin', data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as r: return json.load(r)
            self.assertTrue(request()['configured'])
            request({'action': 'check'})
            self.bridge.thread.join(2)
            self.assertEqual(request()['state'], 'connected')
            self.assertFalse(request()['running'])
            request({'action': 'start', 'mode': 'read'})
            self.assertTrue(request()['running'])
            request({'action': 'stop'});self.bridge.thread.join(2)
            self.assertFalse(request()['running'])
            with self.assertRaises(urllib.error.HTTPError) as context: request({'action': 'start', 'mode': 'invalid'})
            self.assertEqual(context.exception.code, 400);context.exception.close()
        finally: server.stop()


if __name__ == '__main__': unittest.main()
