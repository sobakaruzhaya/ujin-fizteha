import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from app.control_api import ControlServer
from app.home_client import HttpHomeClient, LocalHomeClient
from app.orchestrator import Orchestrator
from app.telegram_bot import TelegramBot
from app.run import telegram_check
from app.tests.test_telegram_bot import FakeApi


class TelegramUITest(unittest.TestCase):
    def setUp(self):
        self.home = Orchestrator()
        self.api = FakeApi()
        self.bot = TelegramBot(LocalHomeClient(self.home), token='FAKE_TOKEN', allowed_chat_ids='*', api=self.api)
        self.update_id = 0

    def message(self, text, chat=42, user=100):
        self.update_id += 1
        return self.bot.handle_update({'update_id':self.update_id,'message':{'chat':{'id':chat},'from':{'id':user},'text':text}})

    def buttons(self):
        return [b for row in json.loads(self.api.sent()[-1].get('reply_markup','{"inline_keyboard":[]}'))['inline_keyboard'] for b in row]

    def click(self, label, chat=42, user=100):
        button = next(b for b in self.buttons() if b['text']==label)
        self.update_id += 1
        update={'update_id':self.update_id,'callback_query':{'id':str(self.update_id),'from':{'id':user},'data':button['callback_data'],'message':{'chat':{'id':chat}}}}
        self.bot.handle_update(update)
        return update

    def test_open_access_dynamic_controls_for_new_devices_and_values(self):
        self.assertTrue(self.bot.enabled)
        self.message('/devices',chat=999)
        self.assertEqual(len(self.buttons()),16)
        self.click('Чайник · Кухня',chat=999)
        self.click('⚙️ Цель воды',chat=999) if any(b['text']=='⚙️ Цель воды' for b in self.buttons()) else self.click('⚙️ '+next(s['title'] for s in self.home.declarations()['kettle_1'] if s['name']=='target_temp'),chat=999)
        self.message('70',chat=999)
        self.assertEqual(self.home.devices['kettle_1'].signals['target_temp'].value,70)
        self.message('включи свет')
        self.assertEqual(self.home.devices['light_1'].signals['lamp'].value,1)
        self.message('яркость 45%')
        self.assertEqual(self.home.devices['light_1'].signals['brightness'].value,45)

    def condition(self):
        self.click('Умная розетка');self.click('Мощность');self.click('Больше');self.message('1000')

    def test_wizard_multi_action_save_edit_remove_and_no_early_side_effects(self):
        self.message('/newscenario');self.message('Telegram integration rule');self.condition()
        self.click('Основной свет');self.click('Свет');self.click('вкл')
        self.assertEqual(len(self.home.scenarios),1)
        self.click('➕ Добавить действие');self.click('Основной свет');self.click('Яркость');self.message('42')
        self.click('✅ Активировать после сохранения')
        before=copy.deepcopy(self.home.state()['devices'])
        self.click('🧪 Проверить на 30 секунд')
        self.assertEqual(self.home.state()['devices'],before)
        self.click('💾 Сохранить сценарий')
        rule=next(s for s in self.home.list_scenarios() if s['name']=='Telegram integration rule')
        self.assertFalse(rule['enabled'])
        self.assertEqual(rule['do'],[{'device':'light_1','signal':'lamp','value':1},{'device':'light_1','signal':'brightness','value':42}])
        self.click('🧩 Сценарии');self.click('⏸ Telegram integration rule');self.click('✏️ Изменить')
        self.click('🗑 Действие 2');self.click('💾 Сохранить сценарий')
        self.assertEqual(len(self.home.scenarios[rule['id']]['do']),1)
        self.click('🧩 Сценарии');self.click('⏸ Telegram integration rule');self.click('🗑 Удалить');self.click('🗑 Да, удалить')
        self.assertNotIn(rule['id'],self.home.scenarios)

    def test_template_cancel_does_not_save_and_names_do_not_overwrite(self):
        self.message('/templates');self.click('Защита от перегрузки')
        self.assertIn('Защита от перегрузки (2)',self.api.last_text())
        self.message('/cancel');self.assertEqual(len(self.home.scenarios),1)
        self.message('/templates');self.click('Киновечер');self.click('💾 Сохранить сценарий')
        self.assertEqual(len(self.home.scenarios),2)

    def test_template_photo_precedes_draft_and_failed_upload_keeps_wizard_available(self):
        self.message('/templates');self.click('Киновечер')
        photo=next(payload for method,payload in self.api.calls if method=='sendPhoto' and payload['photo'][0]=='cinema.jpg')
        self.assertEqual(photo['photo'][0],'cinema.jpg')
        self.assertTrue(photo['photo'][1].startswith(b'\xff\xd8'))
        self.assertIn('Киновечер',photo['caption'])
        original=self.bot._api_call
        def upload_fails(method,payload=None):
            if method=='sendPhoto': raise RuntimeError('Telegram unavailable')
            return original(method,payload)
        self.bot._api_call=upload_fails
        self.message('/templates');self.click('Киновечер')
        self.assertIn('💾 Сохранить сценарий',[b['text'] for b in self.buttons()])

    def test_group_drafts_and_buttons_are_bound_to_the_user(self):
        self.message('/newscenario');self.message('User one draft')
        stolen=self.buttons()[0]['callback_data']
        self.bot.handle_update({'callback_query':{'id':'stolen','from':{'id':200},'data':stolen,'message':{'chat':{'id':42}}}})
        self.assertIn('принадлежит другому',self.api.last_text())
        self.assertEqual(self.bot.sessions[('42','100')]['draft']['name'],'User one draft')
        self.message('/newscenario',user=200);self.message('User two draft',user=200)
        self.assertEqual(self.bot.sessions[('42','100')]['draft']['name'],'User one draft')
        self.assertEqual(self.bot.sessions[('42','200')]['draft']['name'],'User two draft')

    def test_bad_values_can_be_corrected_and_old_wizard_buttons_are_rejected(self):
        self.message('/device light_1');self.click('⚙️ Яркость');self.message('nan')
        self.assertIn('конечное число',self.api.last_text())
        self.message('99');self.assertEqual(self.home.devices['light_1'].signals['brightness'].value,99)
        self.message('/templates');self.click('Киновечер')
        stale=next(b['callback_data'] for b in self.buttons() if b['text']=='💾 Сохранить сценарий')
        self.click('✅ Активировать после сохранения')
        self.bot.handle_update({'callback_query':{'id':'old','from':{'id':100},'data':stale,'message':{'chat':{'id':42}}}})
        self.assertTrue(any('уже изменён' in m['text'] for m in self.api.sent()))
        self.assertEqual(len(self.home.scenarios),1)

    def test_tests_reports_and_device_diagnostics_use_real_isolated_engines(self):
        before=copy.deepcopy(self.home.state()['devices'])
        self.message('/tests');self.click('Пожар');self.click('▶️ Запустить тест')
        self.assertIn('Пройдено: 1 / 1',self.api.last_text())
        self.click('✅ Пожар');self.assertIn('Пожарная тревога',self.api.last_text())
        self.click('📎 JSON-отчёт')
        method,payload=self.api.calls[-1]
        self.assertEqual(method,'sendDocument');self.assertTrue(payload['document'][1].startswith(b'{'))
        self.assertEqual(before,self.home.state()['devices'])
        self.message('/diagnostics');self.click('▶️ Запустить все тесты')
        self.assertIn('Пройдено: 15 / 15',self.api.last_text())

    def test_subscriptions_and_offset_persist_without_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            self.bot=TelegramBot(LocalHomeClient(self.home),token='FAKE_TOKEN',allowed_chat_ids='*',api=self.api,state_path=path)
            self.message('/start',chat=-1001);self.bot.offset=25;self.bot.save_state()
            again=TelegramBot(LocalHomeClient(self.home),token='FAKE_TOKEN',allowed_chat_ids='*',api=self.api,state_path=path)
            self.assertIn('-1001',again.subscribers);self.assertEqual(again.offset,25)
            self.assertNotIn('FAKE_TOKEN',path.read_text())
            self.message('/notifications',chat=-1001);self.click('Выключить',chat=-1001)
            self.assertNotIn('-1001',self.bot.subscribers)

    def test_save_failure_keeps_draft_and_allows_retry(self):
        self.message('/templates');self.click('Киновечер')
        with patch.object(self.bot.client,'create_scenario',side_effect=RuntimeError('Не удалось сохранить')):
            self.click('💾 Сохранить сценарий')
        self.assertEqual(len(self.home.scenarios),1)
        self.assertIn('Киновечер',self.api.last_text())
        self.click('💾 Сохранить сценарий')
        self.assertEqual(len(self.home.scenarios),2)

    def test_disabled_subscription_survives_restart_for_fixed_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            self.bot=TelegramBot(LocalHomeClient(self.home),token='FAKE_TOKEN',allowed_chat_ids='42',api=self.api,state_path=path)
            self.message('/notifications');self.click('Выключить')
            again=TelegramBot(LocalHomeClient(self.home),token='FAKE_TOKEN',allowed_chat_ids='42',api=self.api,state_path=path)
            self.assertNotIn('42',again.subscribers)

    def test_callback_edits_the_original_menu_message(self):
        self.message('/start')
        button=next(b for b in self.buttons() if b['text']=='🔌 Устройства')
        self.bot.handle_update({'callback_query':{'id':'edit','from':{'id':100},'data':button['callback_data'],
            'message':{'message_id':321,'chat':{'id':42},'photo':[{'file_id':'home'}]}}})
        method,payload=self.api.calls[-1]
        self.assertEqual(method,'editMessageMedia')
        self.assertEqual(payload['message_id'],321)
        self.assertIn('Выберите устройство',json.loads(payload['media'])['caption'])

    def test_telegram_check_with_open_access_only_validates_identity(self):
        with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'FAKE_TOKEN','TELEGRAM_ALLOWED_CHAT_IDS':'*'}), \
                patch('app.run.telegram_api',return_value={'ok':True,'result':{'username':'fake_bot','id':1}}) as api, \
                patch('builtins.print'):
            self.assertEqual(telegram_check(),0)
            self.assertEqual(api.call_count,1)
            self.assertEqual(api.call_args.args[1],'getMe')

    def test_edited_and_duplicate_updates_do_not_reapply_commands(self):
        update={'update_id':100,'message':{'chat':{'id':42},'text':'/set light_1 brightness 50'}}
        self.assertTrue(self.bot.handle_update(update));count=len(self.home.events)
        self.assertFalse(self.bot.handle_update(update));self.assertEqual(len(self.home.events),count)
        self.assertFalse(self.bot.handle_update({'edited_message':{'chat':{'id':42},'text':'/reset'}}))

    def test_chunks_and_callback_data_fit_telegram_limits(self):
        self.bot._send(42,'🔥'*5000)
        self.assertTrue(all(len(m['text'].encode('utf-16-le'))//2<=3500 for m in self.api.sent()))
        self.message('/templates')
        self.assertTrue(all(len(b['callback_data'].encode())<=64 for b in self.buttons()))

    def test_remote_client_has_full_parity_including_ujin(self):
        server=ControlServer(self.home,port=0);server.start()
        try:
            client=HttpHomeClient(f'http://127.0.0.1:{server.port}')
            client.apply_command('light_1','brightness',35)
            self.assertEqual(self.home.devices['light_1'].signals['brightness'].value,35)
            self.assertEqual(len(client.templates()),8)
            self.assertEqual(len(client.test_catalog()['tests']),8)
            self.assertEqual(client.run_tests('gas-leak')['summary']['passed'],1)
            self.assertIn('configured',client.ujin_status())
        finally: server.stop()


if __name__=='__main__':unittest.main()
