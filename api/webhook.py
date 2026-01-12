import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ────────────────────────────────────────────────
TOKEN = "8486942529:AAEEHucAbkLSrxeBM2DlGCZURAs0_H5MzXk"
ADMIN_CHAT_ID = -5270508762
CHANNEL_ID = -1003665236800
PROJECT_LINK = "https://t.me/+7IoWGj4ZCKs2NmRi"
CHECK_SUBSCRIPTION_BEFORE_FORM = True

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Form(StatesGroup):
    city = State()
    age = State()
    experience = State()
    photo = State()

WELCOME_TEXT = f"""Привет!
Это набор в проект «Могильное дело».
Задания: прессинг, разборки, поджоги, выносы, тяжёлые разговоры и т.п.
Оплата высокая (15–150к+ за задачу).

Сначала подпишись на канал:
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
            "✅ Твоя анкета **принята**!\n\n"
            "С тобой скоро свяжутся в личке.\n"
            "Будь на связи, не блокируй бота и не пропускай сообщения."
        )
    except:
        pass

async def send_rejection(user_id: int):
    try:
        await bot.send_message(
            user_id,
            "❌ По твоей анкете принято решение **отказать**.\n"
            "Спасибо за отклик."
        )
    except:
        pass

# ──── Handlers (все твои обработчики остаются без изменений) ───────
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    if await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Я подписался", callback_data="confirmed")]
        ])
        await message.answer(WELCOME_TEXT, reply_markup=kb, disable_web_page_preview=True)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться на канал", url=PROJECT_LINK)],
            [InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub_again")]
        ])
        await message.answer("❗ Сначала подпишись на канал", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "check_sub_again")
async def check_again(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Я подписался", callback_data="confirmed")]
        ])
        await callback.message.edit_text(WELCOME_TEXT, reply_markup=kb, disable_web_page_preview=True)
    else:
        await callback.answer("Подписка не найдена 😕", show_alert=True)

@dp.callback_query(lambda c: c.data == "confirmed")
async def confirmed(callback: types.CallbackQuery, state: FSMContext):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("Сначала подпишись на канал!", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Отлично! Заполняем анкету.\n\nГород?")
    await state.set_state(Form.city)
    await callback.answer()

@dp.message(Form.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("Возраст?")
    await state.set_state(Form.age)

@dp.message(Form.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Только цифры")
        return
    await state.update_data(age=message.text)
    await message.answer("Коротко опыт (улица / спорт / силовики / другое)")
    await state.set_state(Form.experience)

@dp.message(Form.experience)
async def process_exp(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())
    await message.answer("Фото (по желанию). Если нет — напиши «нет»")
    await state.set_state(Form.photo)

@dp.message(Form.photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or f"id{user_id}"

    admin_text = (
        f"<b>🆕 НОВАЯ АНКЕТА</b>\n"
        f"От: @{username}  [{user_id}]\n"
        f"Город: {data.get('city', '-')}\n"
        f"Возраст: {data.get('age', '-')}\n"
        f"Опыт: {data.get('experience', '-')}\n"
        f"Фото: {'есть' if message.photo else 'нет'}\n\n"
        f"Решение:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{user_id}"),
            InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject_{user_id}")
        ]
    ])

    if message.photo:
        await bot.send_photo(
            ADMIN_CHAT_ID,
            message.photo[-1].file_id,
            caption=admin_text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            ADMIN_CHAT_ID,
            admin_text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    await message.answer("Анкета отправлена на рассмотрение.\nОжидай решения.")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("accept_"))
async def process_accept(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[1])
        if callback.message.caption:
            new_caption = callback.message.caption + "\n\n✅ <b>Принят</b> (свяжутся вручную)"
            await callback.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="HTML")
        else:
            new_text = (callback.message.text or "🆕 НОВАЯ АНКЕТА") + "\n\n✅ <b>Принят</b> (свяжутся вручную)"
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
        await notify_accepted(user_id)
        await callback.answer("Принято")
    except Exception as e:
        logging.error(f"accept error: {e}")
        await callback.answer("Ошибка", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def process_reject(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[1])
        await send_rejection(user_id)
        if callback.message.caption:
            new_caption = callback.message.caption + "\n\n❌ <b>Отказано</b>"
            await callback.message.edit_caption(caption=new_caption, reply_markup=None, parse_mode="HTML")
        else:
            new_text = (callback.message.text or "🆕 НОВАЯ АНКЕТА") + "\n\n❌ <b>Отказано</b>"
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
        await callback.answer("Отказано")
    except Exception as e:
        logging.error(f"reject error: {e}")
        await callback.answer("Ошибка", show_alert=True)

# ──── Webhook + запуск ─────────────────────────────────────────────
async def on_startup(bot: Bot):
    webhook_path = "/webhook"
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}{webhook_path}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    logging.info(f"Webhook установлен: {webhook_url}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook удалён")

async def main():
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
    await site.start()

    await on_startup(bot)

    try:
        await asyncio.Event().wait()
    finally:
        await on_shutdown(bot)
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
