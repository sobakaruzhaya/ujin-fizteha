import io
import json
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

from app.home_client import LocalHomeClient
from app.orchestrator import Orchestrator
from app.telegram_bot import TelegramBot
from app.telegram_media import ASSETS, DEVICE_IMAGES, caption_parts, device_photo
from app.telegram_ui import Context
from app.tests.test_telegram_bot import FakeApi


class PhotoApi(FakeApi):
    def __call__(self, method, payload=None):
        super().__call__(method, payload)
        if method in ('sendPhoto', 'editMessageMedia'):
            return {'ok': True, 'result': {'message_id': 19, 'photo': [{'file_id': 'reusable-photo-id'}]}}
        return {'ok': True, 'result': []}


class TelegramMediaTest(unittest.TestCase):
    def setUp(self):
        self.api = PhotoApi()
        self.home = Orchestrator()
        self.bot = TelegramBot(LocalHomeClient(self.home), token='fake-token', allowed_chat_ids='*', api=self.api)
        self.ctx = Context('42', '42')

    def test_all_fifteen_devices_have_valid_local_jpeg_uploads(self):
        self.assertEqual(set(DEVICE_IMAGES), set(self.home.devices))
        for device in self.home.devices:
            with self.subTest(device=device):
                self.bot.ui.device(self.ctx, device)
                method, payload = self.api.calls[-1]
                self.assertEqual(method, 'sendPhoto')
                self.assertTrue(payload['photo'][1].startswith(b'\xff\xd8'))
                self.assertLess(len(payload['photo'][1]), 10 * 1024 * 1024)
                self.assertIn('inline_keyboard', json.loads(payload['reply_markup']))

    def test_existing_photo_is_edited_and_reuses_the_uploaded_file_id(self):
        self.bot.ui.device(self.ctx, 'light_1')
        first = self.api.calls[-1][1]
        self.assertIsInstance(first['photo'], tuple)
        self.bot.ui.device(Context('42', '42', 19, True), 'light_1')
        method, payload = self.api.calls[-1]
        self.assertEqual(method, 'editMessageMedia')
        self.assertEqual(json.loads(payload['media'])['media'], 'reusable-photo-id')
        self.assertNotIn('photo', payload)
        self.assertEqual(payload['message_id'], 19)

    def test_settings_prompt_edits_caption_instead_of_editing_photo_as_text(self):
        self.bot.ui.field(Context('42', '42', 19, True), 'light_1', 'brightness')
        method, payload = self.api.calls[-1]
        self.assertEqual(method, 'editMessageCaption')
        self.assertIn('Введите число', payload['caption'])
        self.assertEqual(self.bot.sessions[('42', '42')]['signal'], 'brightness')

    def test_long_emoji_report_preserves_all_text_and_keeps_controls_on_last_message(self):
        text = 'Результаты теста\n' + '🔥 Проверка показаний\n' * 350
        rows = [[{'text': 'Отчёт', 'callback_data': 'report'}]]
        self.bot.ui.render(self.ctx, text, rows, photo=ASSETS/'fire.jpg')
        photo = self.api.calls[0][1]
        self.assertLessEqual(len(photo['caption'].encode('utf-16-le')) // 2, 1024)
        tails = [payload for method, payload in self.api.calls if method == 'sendMessage']
        self.assertEqual(photo['caption'] + '\n' + ''.join(p['text'] for p in tails), text)
        self.assertTrue(all(len(p['text'].encode('utf-16-le')) // 2 <= 3500 for p in tails))
        self.assertNotIn('reply_markup', photo)
        self.assertIn('reply_markup', tails[-1])
        self.assertTrue(all('reply_markup' not in p for p in tails[:-1]))
        caption, tail = caption_parts('🔥' * 1000)
        self.assertEqual(caption + tail, '🔥' * 1000)
        self.assertLessEqual(len(caption.encode('utf-16-le')) // 2, 1024)

    def test_unavailable_photo_falls_back_to_working_text_controls(self):
        original = self.bot._api_call
        def unavailable(method, payload=None):
            if method == 'sendPhoto': raise RuntimeError('Telegram 400')
            return original(method, payload)
        self.bot._api_call = unavailable
        self.bot.ui.home(self.ctx)
        self.assertEqual(self.api.calls[-1][0], 'sendMessage')
        self.assertIn('Устройства', self.api.calls[-1][1]['reply_markup'])

    def test_expired_file_id_is_reuploaded_and_cache_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'state.json'
            self.bot.state_path = path
            self.bot.ui.device(self.ctx, 'light_1')
            self.assertTrue(self.bot.photo_ids)
            again = TelegramBot(LocalHomeClient(self.home), token='fake-token', allowed_chat_ids='*', api=self.api, state_path=path)
            self.assertEqual(again.photo_ids, self.bot.photo_ids)
            original = self.bot._api_call
            def expired(method, payload=None):
                if method == 'sendPhoto' and isinstance(payload.get('photo'), str):
                    self.api.calls.append((method, payload.copy()))
                    raise RuntimeError('Telegram 400')
                return original(method, payload)
            self.bot._api_call = expired
            before = len(self.api.calls)
            self.bot.ui.device(self.ctx, 'light_1')
            attempts = self.api.calls[before:]
            self.assertIsInstance(attempts[0][1]['photo'], str)
            self.assertIsInstance(attempts[1][1]['photo'], tuple)
            self.assertNotIn('fake-token', path.read_text())

    def test_binary_media_and_cached_id_are_encoded_in_the_right_bot_api_format(self):
        captured = []
        def urlopen(request, timeout=None):
            captured.append(request)
            return io.BytesIO(b'{"ok":true,"result":{}}')
        photo = ('lamp.jpg', device_photo('light_1').read_bytes())
        media = json.dumps({'type': 'photo', 'media': 'attach://photo', 'caption': 'Основной свет'})
        with patch('urllib.request.urlopen', side_effect=urlopen):
            self.bot._http_api('editMessageMedia', {'chat_id': '42', 'message_id': 19, 'media': media, 'photo': photo})
            self.bot._http_api('sendPhoto', {'chat_id': '42', 'photo': 'existing-id', 'caption': 'Свет'})
        request = captured[0]
        content_type = request.get_header('Content-type')
        parsed = BytesParser(policy=policy.default).parsebytes(
            ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + request.data)
        parts = {part.get_param('name', header='Content-Disposition'): part for part in parsed.iter_parts()}
        self.assertEqual(parts['photo'].get_content_type(), 'image/jpeg')
        self.assertEqual(parts['photo'].get_payload(decode=True), photo[1])
        self.assertEqual(json.loads(parts['media'].get_payload(decode=True))['media'], 'attach://photo')
        self.assertEqual(parse_qs(captured[1].data.decode())['photo'], ['existing-id'])


if __name__ == '__main__': unittest.main()
