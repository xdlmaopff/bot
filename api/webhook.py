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
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://bot-pi-umber.vercel.app

ADMIN_CHAT_ID = -5270508762
CHANNEL_ID = -1003665236800
PROJECT_LINK = "https://t.me/+7IoWGj4ZCKs2NmRi"

CHECK_SUBSCRIPTION_BEFORE_FORM = True

if not TOKEN:
    raise ValueError("BOT_TOKEN not set in environment variables!")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set in environment variables!")

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
            "✅ Твоя анкета **принята**!\n\nС тобой скоро свяжутся по личным сообщениям.\nБудь на связи."
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


async def on_startup():
    webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url)
    logging.info(f"Webhook установлен: {webhook_url}")


async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook удалён")


# ──── Обработчики ─────────────────────────────────────────────────

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
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


@dp.callback_query(lambda c: c.data == "check_sub_again")
async def check_again(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        await callback.message.edit_text(
            WELCOME_TEXT,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Я подписался", callback_data="confirmed")]
            ])
        )
    else:
        await callback.answer("Подписка не найдена", show_alert=True)


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
        await message.answer("Нужны только цифры")
        return
    await state.update_data(age=message.text)
    await message.answer("Коротко об опыте (улица/спорт/силовики/другое)")
    await state.set_state(Form.experience)


@dp.message(Form.experience)
async def process_exp(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text.strip())
    await message.answer("Фото (по желанию). Если нет — пиши «нет»")
    await state.set_state(Form.photo)


@dp.message(Form.photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or f"id{user_id}"

    admin_text = (
        f"🆕 <b>НОВАЯ АНКЕТА</b>\n"
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
        current = callback.message.caption or callback.message.text or "🆕 НОВАЯ АНКЕТА\n\n"
        new_text = current + "\n✅ <b>Принят</b> (свяжутся вручную)"

        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")

        await notify_accepted(user_id)
        await callback.answer("Принято")
    except Exception as e:
        logging.error(f"Ошибка при принятии: {e}")
        await callback.answer("Ошибка", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("reject_"))
async def process_reject(callback: types.CallbackQuery):
    try:
        user_id = int(callback.data.split("_")[1])
        await send_rejection(user_id)

        current = callback.message.caption or callback.message.text or "🆕 НОВАЯ АНКЕТА\n\n"
        new_text = current + "\n❌ <b>Отказано</b>"

        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")

        await callback.answer("Отказано")
    except Exception as e:
        logging.error(f"Ошибка при отказе: {e}")
        await callback.answer("Ошибка", show_alert=True)


# ──── Самое важное для Vercel — глобальная переменная app ────────────────

app = web.Application()

webhook_handler = SimpleRequestHandler(
    dispatcher=dp,
    bot=bot,
)

webhook_handler.register(app, path=WEBHOOK_PATH)
setup_application(app, dp, bot=bot)

app.on_startup.append(lambda _: asyncio.create_task(on_startup()))
app.on_shutdown.append(lambda _: asyncio.create_task(on_shutdown()))
