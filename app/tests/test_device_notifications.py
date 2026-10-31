import unittest

from app.home_client import LocalHomeClient
from app.orchestrator import Orchestrator
from app.telegram_bot import TelegramBot
from app.tests.test_telegram_bot import FakeApi


class DeviceNotificationsTest(unittest.TestCase):
    def new_home(self):
        home, api = Orchestrator(), FakeApi()
        bot = TelegramBot(LocalHomeClient(home), token='test-token', allowed_chat_ids='42', api=api)
        bot._notify_events()
        return home, api, bot

    @staticmethod
    def notices(home, device=None):
        return [e for e in home.events if e.get('notification') and (not device or e.get('device') == device)]

    def test_every_device_delivers_a_setting_or_operation_once_with_its_own_photo(self):
        actions = {
            'smart_plug_1': ('power_switch', 1), 'light_1': ('lamp', 1),
            'thermostat_1': ('mode', 1), 'ventilation_1': ('mode', 0),
            'temp_sensor_1': ('calibration', 1), 'leak_1': ('self_test', 1),
            'hub_1': ('mute', 1), 'fire_1': ('threshold', 65),
            'counter_1': ('load_relay', 0), 'tv_1': ('power', 1),
            'fridge_1': ('mode', 2), 'kettle_1': ('power', 1),
            'stove_1': ('burner_1', 2), 'oven_1': ('power', 1), 'intercom_1': ('volume', 40),
        }
        self.assertEqual(set(actions), set(Orchestrator().devices))
        for device, (signal, value) in actions.items():
            with self.subTest(device=device):
                home, api, bot = self.new_home()
                home.request_command(device, signal, value, require_confirmation=False)
                self.assertEqual(len(self.notices(home, device)), 1)
                bot._notify_events()
                self.assertEqual(len(api.sent()), 1)
                self.assertIn(home.metadata[device]['name'], api.last_text())
                self.assertEqual(api.calls[-1][0], 'sendPhoto')
                bot._notify_events()
                self.assertEqual(len(api.sent()), 1)

    def test_short_fire_alarm_and_recovery_are_delivered_between_bot_polls(self):
        home, api, bot = self.new_home()
        home.devices['fire_1'].set_smoke(80)
        home.step()
        home.devices['fire_1'].set_smoke(0)
        home.request_command('fire_1', 'reset_alarm', 1, False)
        home.step()
        bot._notify_events()
        text = api.last_text()
        self.assertEqual(text.count('Пожарная тревога'), 2)  # alert and its recovery
        self.assertIn('состояние восстановлено', text)
        alerts = self.notices(home, 'fire_1')
        self.assertEqual([e['type'] for e in alerts], ['alarm', 'device_recovered'])
        bot._notify_events()
        self.assertEqual(len(api.sent()), 1)

    def test_faults_battery_tamper_link_and_hub_sensors_have_recoveries(self):
        for device, signal, bad, good in [
            ('temp_sensor_1', 'fault', 1, 0), ('temp_sensor_1', 'low_battery', 1, 0),
            ('leak_1', 'tamper', 1, 0), ('hub_1', 'sensors_online', 1, 3),
            ('counter_1', 'online', 0, 1), ('counter_1', 'battery', 10, 90),
            ('fridge_1', 'alarm', 2, 0), ('oven_1', 'fault', 1, 0),
            ('stove_1', 'overheat', 1, 0), ('kettle_1', 'dry_boil', 1, 0),
        ]:
            with self.subTest(device=device, signal=signal):
                home, api, bot = self.new_home()
                for value in (bad, good):
                    home.devices[device].set_value(signal, value)
                    home._observe_state()
                notices = self.notices(home, device)
                self.assertEqual([e['type'] for e in notices], ['alarm', 'device_recovered'])
                bot._notify_events()
                self.assertIn('состояние восстановлено', api.last_text())
                self.assertEqual(len(api.sent()), 1)

    def test_co2_hysteresis_avoids_threshold_chatter(self):
        home, api, bot = self.new_home()
        for value in (1050, 995, 1005, 950, 901):
            home.devices['ventilation_1'].set_value('co2', value)
            home._observe_state()
        self.assertEqual(len(self.notices(home, 'ventilation_1')), 1)
        home.devices['ventilation_1'].set_value('co2', 900)
        home._observe_state()
        self.assertEqual([e['type'] for e in self.notices(home, 'ventilation_1')], ['alarm', 'device_recovered'])
        bot._notify_events()
        self.assertIn('Высокий уровень CO₂', api.last_text())

    def test_automatic_timers_are_events_without_manual_commands(self):
        for device, timer, switch in [
            ('light_1', 'offline_timeout', 'lamp'), ('tv_1', 'auto_off_seconds', 'power'),
            ('smart_plug_1', 'auto_off_seconds', 'power_switch'),
            ('oven_1', 'timer', 'power'), ('stove_1', 'timer', 'burner_1'),
        ]:
            with self.subTest(device=device):
                home, api, bot = self.new_home()
                for signal, value in ((timer, 1), (switch, 1)):
                    home.request_command(device, signal, value, False)
                bot._notify_events()
                home.step()
                finished = [e for e in self.notices(home, device) if e['type'] == 'device_finished']
                self.assertEqual(len(finished), 1)
                bot._notify_events()
                self.assertEqual(len(api.sent()), 2)

    def test_intercom_call_answer_door_and_hangup_report_observed_states(self):
        home, api, bot = self.new_home()
        home.devices['intercom_1'].ring()
        home._observe_state()
        home.request_command('intercom_1', 'answer', 1, False)
        home.request_command('intercom_1', 'unlock', 1, False)
        for _ in range(3): home.step()
        home.request_command('intercom_1', 'hangup', 1, False)
        titles = [e['title'] for e in self.notices(home, 'intercom_1')]
        self.assertEqual(titles, ['Звонок в дверь', 'Разговор начат', 'Дверь открыта', 'Дверь закрыта', 'Вызов завершён'])
        bot._notify_events()
        self.assertIn('Домофон', api.last_text())

    def test_temperature_completion_is_once_per_target_not_every_thermostat_cycle(self):
        home, api, bot = self.new_home()
        home.request_command('thermostat_1', 'mode', 1, False)
        for _ in range(100): home.step()
        finished = [e for e in self.notices(home, 'thermostat_1') if e['type'] == 'device_finished']
        self.assertEqual(len(finished), 1)

    def test_oven_preheat_is_not_reported_on_a_manual_stop(self):
        home, api, bot = self.new_home()
        home.request_command('oven_1', 'target_temp', 50, False)
        home.request_command('oven_1', 'power', 1, False)
        for _ in range(10): home.step()
        finished = [e for e in self.notices(home, 'oven_1') if e['title'] == 'Духовка прогрета']
        self.assertEqual(len(finished), 1)
        home.request_command('oven_1', 'power', 0, False)
        home.step()
        self.assertEqual(len([e for e in self.notices(home, 'oven_1') if e['title'] == 'Духовка прогрета']), 1)

    def test_measurements_dont_flood_and_reset_or_simulation_dont_replay_transitions(self):
        home, api, bot = self.new_home()
        home.request_command('thermostat_1', 'mode', 0, False)
        bot._notify_events()
        count = len(api.sent())
        for _ in range(100):
            home.step()
            bot._notify_events()
        self.assertEqual(len(api.sent()), count)
        before = list(home.events)
        home.simulate(10)
        self.assertEqual(home.events, before)
        home.reset()
        home._observe_state()
        self.assertEqual([e for e in home.events[len(before):] if e.get('notification')], [])


if __name__ == '__main__':
    unittest.main()
