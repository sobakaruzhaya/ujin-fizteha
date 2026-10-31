"""Photo cards, caption limits and Telegram file-id reuse."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / 'assets' / 'telegram'
TEMPLATES = Path(__file__).resolve().parent.parent / 'frontend/public/images/scenario-templates'
DEVICE_IMAGES = {
    'smart_plug_1': 'plug', 'light_1': 'lamp', 'thermostat_1': 'thermostat',
    'ventilation_1': 'ventilation', 'temp_sensor_1': 'temp_sensor', 'leak_1': 'leak',
    'hub_1': 'hub', 'fire_1': 'fire', 'counter_1': 'counter', 'tv_1': 'tv',
    'fridge_1': 'fridge', 'kettle_1': 'kettle', 'stove_1': 'stove',
    'oven_1': 'oven', 'intercom_1': 'intercom',
}
TEST_IMAGES = {
    'socket-overload': TEMPLATES / 'overload.jpg', 'network-overload': ASSETS / 'counter.jpg',
    'fire': TEMPLATES / 'fire.jpg', 'gas-leak': ASSETS / 'home.jpg',
    'water-leak': TEMPLATES / 'leak.jpg', 'high-co2': TEMPLATES / 'fresh-air.jpg',
    'dry-kettle': ASSETS / 'kettle.jpg', 'sensor-fault': ASSETS / 'thermostat.jpg',
}


def device_photo(device):
    return ASSETS / (DEVICE_IMAGES.get(device, 'home') + '.jpg')


def test_photo(key, emergency=True):
    return TEST_IMAGES.get(key, ASSETS / 'home.jpg') if emergency else device_photo(key)


def caption_parts(text):
    """Keep all information; long reports continue in regular text messages."""
    if len(text.encode('utf-16-le')) // 2 <= 1024:
        return text, ''
    first, separator, rest = text.partition('\n')
    if separator and len(first.encode('utf-16-le')) // 2 <= 1024:
        return first, rest
    units, index = 0, 0
    for index, char in enumerate(text):
        units += 2 if ord(char) > 0xffff else 1
        if units > 1000: break
    return text[:index], text[index:]


class PhotoMessages:
    def __init__(self, bot):
        self.bot = bot

    def render(self, ctx, text, rows=None, photo=None):
        caption, continuation = caption_parts(str(text))
        markup = json.dumps({'inline_keyboard': [] if continuation else rows or []}, ensure_ascii=False)
        if photo is None:
            # A settings prompt may retain the device photo from its callback.
            try:
                self.bot._api('editMessageCaption', {'chat_id': ctx.chat, 'message_id': ctx.message_id,
                    'caption': caption, 'reply_markup': markup})
            except RuntimeError:
                return False
        else:
            try: content = Path(photo).read_bytes()
            except OSError: return False
            fingerprint = hashlib.sha256(content).hexdigest()
            cached = self.bot.photo_ids.get(fingerprint)
            upload = (Path(photo).name, content)
            succeeded = False
            # An expired cached id is retried with a fresh upload.
            for source in ([cached, upload] if cached else [upload]):
                if ctx.message_id and ctx.media:
                    media = {'type': 'photo', 'media': source if isinstance(source, str) else 'attach://photo', 'caption': caption}
                    payload = {'chat_id': ctx.chat, 'message_id': ctx.message_id,
                               'media': json.dumps(media, ensure_ascii=False), 'reply_markup': markup}
                    if not isinstance(source, str): payload['photo'] = source
                    method = 'editMessageMedia'
                else:
                    method = 'sendPhoto'
                    payload = {'chat_id': ctx.chat, 'photo': source, 'caption': caption}
                    if rows and not continuation: payload['reply_markup'] = markup
                try:
                    response = self.bot._deliver(method, payload, ctx.chat)
                    result = response.get('result')
                    sizes = result.get('photo') if isinstance(result, dict) else None
                    if sizes and sizes[-1].get('file_id'):
                        with self.bot.state_lock:
                            if self.bot.photo_ids.get(fingerprint) != sizes[-1]['file_id']:
                                self.bot.photo_ids[fingerprint] = sizes[-1]['file_id']
                                self.bot.save_state()
                    succeeded = True
                    break
                except RuntimeError as exc:
                    if '403' in str(exc): raise
                    if isinstance(source, str):
                        with self.bot.state_lock:
                            self.bot.photo_ids.pop(fingerprint, None)
                            self.bot.save_state()
            if not succeeded: return False
        if continuation:
            self.bot._send(ctx.chat, continuation, rows)
        return True
