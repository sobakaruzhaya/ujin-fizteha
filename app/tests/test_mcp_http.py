import asyncio
import copy
import socket
import threading
import time
import unittest

from app.tests.test_mcp_server import HAS_MCP, payload
from app.control_api import ControlServer
from app.home_client import HttpHomeClient
from app.orchestrator import Orchestrator


@unittest.skipUnless(HAS_MCP, 'MCP SDK is not installed')
class McpHttpTest(unittest.TestCase):
    def test_real_client_discovers_and_operates_on_the_shared_api(self):
        import uvicorn
        from mcp import Client
        from app.mcp_server import build_server
        home = Orchestrator()
        control = ControlServer(home, port=0)
        control.start()
        server = build_server(HttpHomeClient(f'http://127.0.0.1:{control.port}'))
        app = server.streamable_http_app(json_response=True, stateless_http=True)
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        config = uvicorn.Config(app, log_level='error', lifespan='on')
        http = uvicorn.Server(config)
        thread = threading.Thread(target=lambda: asyncio.run(http.serve(sockets=[sock])), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not http.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(http.started)
            async def exercise():
                async with Client(f'http://127.0.0.1:{port}/mcp') as client:
                    names = {t.name for t in (await client.list_tools()).tools}
                    self.assertIn('run_emergency_tests', names)
                    self.assertIn('manage_ujin_integration', names)
                    health = payload(await client.call_tool('get_health'))
                    self.assertEqual(health, {'status': 'ok', 'transport': 'http'})
                    rule = payload(await client.call_tool('create_scenario_from_template', {'template_key': 'cinema', 'enabled': False}))
                    self.assertIn(rule['id'], home.scenarios)
                    self.assertFalse(home.scenarios[rule['id']]['enabled'])
                    preview = payload(await client.call_tool('request_device_command', {'device': 'light_1', 'signal': 'lamp', 'value': 1}))
                    self.assertEqual(preview['status'], 'confirmation_required')
                    self.assertEqual(home.state()['devices']['light_1']['lamp'], 0)
                    applied = payload(await client.call_tool('confirm_device_command', {'confirmation_id': preview['confirmation_id']}))
                    self.assertEqual(applied['status'], 'applied')
                    self.assertEqual(home.state()['devices']['light_1']['lamp'], 1)
                    before = copy.deepcopy(home.state()['devices'])
                    report = payload(await client.call_tool('run_emergency_tests', {'case_id': 'gas-leak', 'include_trace': True}))
                    self.assertEqual(report['summary']['passed'], 1)
                    self.assertTrue(report['results'][0]['trace'])
                    self.assertEqual(home.state()['devices'], before)
                    resource = await client.read_resource('home://scenario-templates')
                    self.assertIn('Киновечер', resource.contents[0].text)
            asyncio.run(exercise())
        finally:
            http.should_exit = True
            thread.join(5)
            control.stop()
            sock.close()
        self.assertFalse(thread.is_alive())


if __name__ == '__main__': unittest.main()
