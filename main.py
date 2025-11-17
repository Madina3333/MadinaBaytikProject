import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base, User

# Загрузка переменных окружения (опционально, если файл .env существует)
load_dotenv()

# Настройки БД
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dataa.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Middleware для передачи сессии в хендлеры
class DBSessionMiddleware:
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


# Инициализация БД
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)




async def main():
    os.makedirs("photos", exist_ok=True)
    await init_db()

    # Получаем токен из переменных окружения или из .env файла
    bot_token = "8392047086:AAFzV8yBbHOqxxgkXuohjDUVEUQH03TWdh4"
    if not bot_token:
        raise ValueError(
            "BOT_TOKEN не установлен!\n"
            "Установите токен одним из способов:\n"
            "1. Создайте файл .env с содержимым: BOT_TOKEN=your_token_here\n"
            "2. Или установите переменную окружения: set BOT_TOKEN=your_token_here (Windows)\n"
            "3. Или экспортируйте переменную: export BOT_TOKEN=your_token_here (Linux/Mac)"
        )
    
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    await bot.set_my_commands([
        BotCommand(command="/start", description="Главное меню"),
        BotCommand(command="/next", description="Следующая анкета"),
        BotCommand(command="/matches", description="Мои матчи")
    ])

    dp = Dispatcher()
    dp.update.middleware(DBSessionMiddleware())

    from handlers import registration, swiping
    dp.include_router(registration.router)
    dp.include_router(swiping.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

