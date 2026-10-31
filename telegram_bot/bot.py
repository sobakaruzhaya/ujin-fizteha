import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from common.ujin_client import UjinSmartHomeClient

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ujin = UjinSmartHomeClient()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Панель управления умным домом Ujin\n\n"
        "Используйте команды:\n"
        "/devices — список устройств и управление\n"
        "/status — текущее состояние сети"
    )

@dp.message(Command("devices"))
async def cmd_devices(message: types.Message):
    try:
        devices = await ujin.get_devices()
        if not devices:
            await message.answer("Устройства не найдены.")
            return

        kb = []
        for dev in devices:
            dev_id = dev["id"]
            name = dev["name"]
            kb.append([
                InlineKeyboardButton(text=f"💡 {name} ON", callback_data=f"dev_on:{dev_id}"),
                InlineKeyboardButton(text=f"🔌 {name} OFF", callback_data=f"dev_off:{dev_id}")
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
        await message.answer("Выберите устройство для управления:", reply_markup=keyboard)
    except Exception as e:
        await message.answer(f"Ошибка получения списка: {e}")

@dp.callback_query(F.data.startswith("dev_"))
async def handle_device_control(callback: types.CallbackQuery):
    action, dev_id = callback.data.split(":")
    power = True if action == "dev_on" else False
    
    try:
        await ujin.set_device_state(dev_id, {"power": power})
        status_str = "включено" if power else "выключено"
        await callback.answer(f"Устройство {status_str}!")
    except Exception as e:
        await callback.answer(f"Ошибка: {e}", show_alert=True)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
