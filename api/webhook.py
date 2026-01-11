import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.exceptions import TelegramBadRequest

# ────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")  # берём из переменных окружения Vercel
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://твой-проект.vercel.app/webhook

ADMIN_CHAT_ID = -5270508762
CHANNEL_ID = -1003665236800
PROJECT_LINK = "https://t.me/+7IoWGj4ZCKs2NmRi"

CHECK_SUBSCRIPTION_BEFORE_FORM = True

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)
# ────────────────────────────────────────────────


class Form(StatesGroup):
    city = State()
    age = State()
    experience = State()
    photo = State()


WELCOME_TEXT = f"""Привет!  
Это проект Могильное дело.
Задания: избиения, поджоги и т.п.
Оплата высокая.

Сначала нужно быть подписанным на канал:

🔗 {PROJECT_LINK}

После подписки жми кнопку ниже ↓"""


async def is_subscribed(user_id: int) -> bool:
    if not CHECK_SUBSCRIPTION_BEFORE_FORM:
        return True
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except TelegramBadRequest:
        return False


async def notify_accepted(user_id: int):
    try:
        await bot.send_message(
            user_id,
            "✅ Твоя анкета **принята**!\n\nС тобой скоро свяжутся по личным сообщениям."
        )
    except Exception:
        pass


async def send_rejection(user_id: int):
    try:
        await bot.send_message(
            user_id,
            "❌ К сожалению, по данной анкете принято решение **отказать**.\nСпасибо за отклик!"
        )
    except Exception:
        pass


# ──── Обработчики (почти как раньше, но без polling) ───────────────────────

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    # ... (весь код start без изменений)
    if await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Я подписался", callback_data="confirmed")]
        ])
        await message.answer(WELCOME_TEXT, reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться на канал", url=PROJECT_LINK)],
            [InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub_again")]
        ])
        await message.answer("❗ Сначала подпишись на канал", reply_markup=kb)


# Все остальные обработчики (check_again, confirmed, process_city, process_age, process_exp, process_photo)
# копируй из предыдущей версии без изменений!


# Решения админов (accept/reject) — тоже без изменений, только убедись, что они есть


async def on_startup():
    await bot.set_webhook(url=WEBHOOK_URL + WEBHOOK_PATH)


async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)


def main():
    app = web.Application()

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )

    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(lambda _: asyncio.create_task(on_startup()))
    app.on_shutdown.append(lambda _: asyncio.create_task(on_shutdown()))

    return app


if __name__ == "__main__":
    web.run_app(main(), host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
