# handlers/registration.py
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, any_state
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.photo import download_photo
from utils.mistral import extract_interests_from_bio

router = Router()


class Reg(StatesGroup):
    waiting_for_name = State()
    waiting_for_photo = State()
    waiting_for_bio = State()


@router.message(F.text == "/start")
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    user = await session.get(User, message.from_user.id)
    description = "👋 Добро пожаловать в бот знакомств!\n\n❤️ Лайкай анкеты и находи единомышленников."
    if user:
        text = description + "\n✅ Ты уже зарегистрирован!"
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔄 Изменить анкету")],
                [KeyboardButton(text="👥 Смотреть анкеты (/next)")],
                [KeyboardButton(text="💌 Мои матчи")],
            ],
            resize_keyboard=True
        )
        await message.answer(text, reply_markup=keyboard)
    else:
        text = description + "\n📝 Создай анкету, чтобы начать!"
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✍️ Создать анкету")]],
            resize_keyboard=True
        )
        await message.answer(text, reply_markup=keyboard)


@router.message(F.text == "✍️ Создать анкету")
async def start_registration(message: Message, state: FSMContext):
    await message.answer("Как тебя зовут?", reply_markup=None)
    await state.set_state(Reg.waiting_for_name)


@router.message(F.text == "🔄 Изменить анкету")
async def edit_profile(message: Message, state: FSMContext):
    await message.answer("Хорошо! Как тебя зовут?", reply_markup=None)
    await state.set_state(Reg.waiting_for_name)


@router.message(Reg.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Отлично! Теперь отправь своё фото.")
    await state.set_state(Reg.waiting_for_photo)


@router.message(Reg.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext, bot, session: AsyncSession):
    user_id = message.from_user.id
    telegram_username = message.from_user.username
    name = (await state.get_data()).get("name", "Аноним")

    try:
        photo_path = await download_photo(bot, message.photo[-1].file_id, user_id)
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
        await message.answer("❌ Не удалось сохранить фото. Попробуй другое.")
        return

    existing_user = await session.get(User, user_id)
    if existing_user:
        existing_user.name = name
        existing_user.username = telegram_username
        existing_user.photo_path = photo_path
        # bio и interests НЕ обнуляем!
    else:
        new_user = User(
            id=user_id,
            username=telegram_username,
            name=name,
            photo_path=photo_path,
            bio="",
            interests=None
        )
        session.add(new_user)
    await session.commit()
    await message.answer("📸 Фото сохранено! Напиши немного о себе (до 500 символов):")
    await state.set_state(Reg.waiting_for_bio)


@router.message(Reg.waiting_for_photo)
async def handle_not_photo(message: Message):
    await message.answer("📸 Пожалуйста, отправь именно фотографию.")


@router.message(Reg.waiting_for_bio)
async def process_bio(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    bio = message.text.strip()[:500]

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user:
        user.bio = bio
        print(f"🧠 Извлекаю интересы из bio: {bio[:30]}…")
        interests = await extract_interests_from_bio(bio)
        user.interests = interests or ""  # даже если None — сохраняем пустую строку
        await session.commit()

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔄 Изменить анкету")],
                [KeyboardButton(text="👥 Смотреть анкеты (/next)")],
                [KeyboardButton(text="💌 Мои матчи")],
            ],
            resize_keyboard=True
        )
        await message.answer("✅ Профиль обновлён! Напиши /next, чтобы смотреть анкеты.", reply_markup=keyboard)
    else:
        await message.answer("⚠️ Ошибка. Начни с /start.")
    await state.clear()


# Кнопки работают в любом состоянии FSM
@router.message(F.text == "👥 Смотреть анкеты (/next)", any_state)
async def view_profiles(message: Message, session: AsyncSession):
    from .swiping import show_next_profile
    await show_next_profile(message, session)


@router.message(F.text == "💌 Мои матчи", any_state)
async def view_matches(message: Message, session: AsyncSession):
    from .swiping import show_matches
    await show_matches(message, session)