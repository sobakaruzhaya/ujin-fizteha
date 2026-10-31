import unittest

from app.home_client import LocalHomeClient
from app.orchestrator import Orchestrator
from app.telegram_bot import TelegramBot
from app.tests.test_telegram_bot import FakeApi


class KettleLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.home = Orchestrator()
        self.home.request_command('thermostat_1', 'mode', 0, False)
        self.client = LocalHomeClient(self.home)
        self.api = FakeApi()
        self.bot = TelegramBot(self.client, token='test-token', allowed_chat_ids='42,43', api=self.api)
        self.bot._notify_events()

    def sent_to(self, chat):
        return [p['text'] for p in self.api.sent() if str(p['chat_id']) == str(chat)]

    def start(self, target=40):
        self.client.apply_command('kettle_1', 'target_temp', target)
        request = self.client.request_command('kettle_1', 'power', 1)
        self.assertEqual(request['status'], 'confirmation_required')
        self.assertEqual(self.home.state()['devices']['kettle_1']['power'], 0)
        self.client.confirm_command(request['confirmation_id'])

    def finish(self):
        for _ in range(30):
            self.home.step()
            if not self.home.state()['devices']['kettle_1']['power']:
                return
        self.fail('Kettle did not finish heating')

    def test_mcp_command_and_finish_are_recorded_and_notified_even_between_polls(self):
        self.start()
        self.assertEqual(self.client.device('kettle_1')['state']['power'], 1)
        self.finish()
        state = self.client.device('kettle_1')['state']
        self.assertEqual((state['power'], state['auto_off'], state['power_w']), (0, 1, 0))
        # The entire cycle happened before Telegram's next polling iteration.
        self.bot._notify_events()
        for chat in (42, 43):
            text = '\n'.join(self.sent_to(chat))
            self.assertEqual(text.count('Чайник включён'), 1)
            self.assertEqual(text.count('вода нагрета до 40'), 1)
        count = len(self.api.sent())
        self.bot._notify_events()
        self.home.step()
        self.bot._notify_events()
        self.assertEqual(len(self.api.sent()), count)

    def test_reheat_clears_auto_off_and_manual_stop_is_not_reported_as_ready(self):
        self.start()
        self.finish()
        self.client.apply_command('kettle_1', 'target_temp', 80)
        self.client.apply_command('kettle_1', 'power', 1)
        self.assertEqual(self.client.device('kettle_1')['state']['auto_off'], 0)
        self.home.step()
        self.client.apply_command('kettle_1', 'power', 0)
        state = self.client.device('kettle_1')['state']
        self.assertEqual((state['auto_off'], state['power_w']), (0, 0))
        events = [e for e in self.home.events if e['type'] in ('device_started', 'device_finished', 'device_stopped')]
        self.assertEqual([e['type'] for e in events], ['device_started', 'device_finished', 'device_started', 'device_stopped'])

    def test_normal_api_commands_are_not_limited_to_scenario_notifications(self):
        self.client.apply_command('thermostat_1', 'target_temp', 25)
        self.bot._notify_events()
        self.assertTrue(any('Термостат' in text and '25' in text for text in self.sent_to(42)))

    def test_failed_subscriber_retries_without_repeating_successful_delivery(self):
        failing = True
        original = self.bot._api_call
        def flaky(method, payload=None):
            if failing and str((payload or {}).get('chat_id')) == '43':
                raise RuntimeError('Telegram 503')
            return original(method, payload)
        self.bot._api_call = flaky
        self.start()
        self.bot._notify_events()
        self.assertEqual(len(self.sent_to(42)), 1)
        self.assertEqual(self.sent_to(43), [])
        failing = False
        self.bot._notify_events()
        self.assertEqual(len(self.sent_to(42)), 1)
        self.assertEqual(len(self.sent_to(43)), 1)
        self.assertIn('Чайник включён', self.sent_to(43)[0])

    def test_keep_warm_cycles_do_not_spam_and_simulation_does_not_leak_events(self):
        self.client.apply_command('kettle_1', 'target_temp', 40)
        self.client.apply_command('kettle_1', 'keep_warm', 1)
        self.client.apply_command('kettle_1', 'power', 1)
        self.bot._notify_events()
        count = len(self.api.sent())
        for _ in range(30):
            self.home.step()
            self.bot._notify_events()
        self.assertEqual(len(self.api.sent()), count)
        before = list(self.home.events)
        self.home.simulate(10)
        self.assertEqual(self.home.events, before)


if __name__ == '__main__':
    unittest.main()
