#Импортируем Router — контейнер для хендлеров
from aiogram import Router

# Импортируем фильтры и типы событий
from aiogram.types import Message

# Импортируем FSM (Finite State Machine) для управления состояниями
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импортируем асинхронную сессию SQLAlchemy (будет передаваться через middleware)
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем модель User для работы с БД
from models import User

# Импортируем утилиту для скачивания фото
from ..utils.photo import download_photo


#Создаем роутер - он будет зарегестрирован в main.py
router = Router()
# Определяем состояния регистрации (пошаговый ввод данных)
class Reg(StatesGroup):
    waiting_for_name = State()    # Шаг 1: ожидаем имя
    waiting_for_photo = State()   # Шаг 2: ожидаем фото
    waiting_for_bio = State()     # Шаг 3: ожидаем описание


# Хендлер на команду /start
@router.message(lambda message: message.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    # Отправляем приветствие и просим имя
    await message.answer("👋 Привет! Как тебя зовут?")
    # Устанавливаем состояние: теперь бот ждёт имя
    await state.set_state(Reg.waiting_for_name)


# Хендлер для получения имени (работает ТОЛЬКО в состоянии waiting_for_name)
@router.message(Reg.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    # Сохраняем имя в данные FSM (временное хранилище)
    await state.update_data(name=message.text.strip())
    # Просим отправить фото
    await message.answer("Отлично! Теперь отправь своё фото.")
    # Переходим к следующему состоянию
    await state.set_state(Reg.waiting_for_photo)


# Хендлер для получения фото (работает ТОЛЬКО в состоянии waiting_for_photo)
@router.message(Reg.waiting_for_photo, lambda msg: msg.photo is not None)
async def process_photo(message: Message, state: FSMContext, bot, session: AsyncSession):
    # Берём самое большое фото из массива (Telegram присылает несколько размеров)
    photo = message.photo[-1]
    user_id = message.from_user.id

    # Получаем сохранённое ранее имя из FSM
    user_data = await state.get_data()
    name = user_data["name"]

    try:
        # Скачиваем фото и получаем локальный путь (например: "photos/123456789.jpg")
        photo_path = await download_photo(bot, photo.file_id, user_id)
    except Exception as e:
        await message.answer("❌ Не удалось сохранить фото. Попробуй другое.")
        return

    # Создаём объект пользователя и сохраняем в БД
    new_user = User(
        id=user_id,
        name=name,
        photo_path=photo_path,
        bio=""  # Временно пустое — заполним на следующем шаге
    )
    session.add(new_user)
    await session.commit()  # Сохраняем изменения

    # Сохраняем путь к фото в FSM (на случай, если bio не пройдёт)
    await state.update_data(photo_path=photo_path)

    # Просим описание
    await message.answer("📸 Фото сохранено! Напиши немного о себе (до 500 символов):")
    await state.set_state(Reg.waiting_for_bio)


# Хендлер для получения описания (работает ТОЛЬКО в состоянии waiting_for_bio)
@router.message(Reg.waiting_for_bio)
async def process_bio(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    # Ограничиваем описание 500 символами и убираем лишние пробелы
    bio = message.text.strip()[:500]

    # Находим пользователя в БД и обновляем bio
    existing_user = await session.get(User, user_id)
    if existing_user:
        existing_user.bio = bio
        await session.commit()
        await message.answer("✅ Профиль создан! Теперь ты можешь смотреть анкеты.")
    else:
        await message.answer("⚠️ Ошибка: пользователь не найден. Начни с /start.")

    # Завершаем FSM — очищаем состояние
    await state.clear()



