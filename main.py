import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models import Base  # твои модели

# === Настройка БД (всё в одном месте) ===
DATABASE_URL = "sqlite+aiosqlite:///./dating.db"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Асинхронная функция, которая создает все таблицы, описанные в моделях
async def init_db():
    # Открываем транзакцию на уровне подключения
    async with engine.begin() as conn:
        # Выполняем синхронную функцию создания таблиц (run_async оборачивает sync-код в async)
        await conn.run_sync(Base.metadata.create_all)


class DBSessionMiddleware():
    class DBSessionMiddleware:
        # Метод __cal__ вызывается при каждом обновлении от tg
        async def __cal__(self, handler, event, data):
            # Автоматически открываем сессию на время обработки запроса
            async with AsyncSessionLocal() as session:
                # Передаем сесию в контекст хендлера через словарь daata
                data["session"] = session
                # Вызываем сам хендлер (следующий шаг в цепочке)
                return await handler(event, data)


# Главная асинхронная функция
async def main():
    await init_db()
    bot = Bot(
        token="8392047086:AAFzV8yBbHOqxxgkXuohjDUVEUQH03TWdh4",
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)  # Включаем HTML - разметку по кмолчанию
    )
    # создаем диспетчер - центральный маршрутизатор событий
    dp = Dispatcher()
    # Подключаем middleware: теперь во всех хендлерах будет доступна сессия БД
    dp.update.middleware(DBSessionMiddleware())
    from handlers import registration, swiping
    # Регистрируем роутеры в диспетчере
    dp.include_router(registration.router)
    dp.include_router(swiping.router)

    # Запускаем бота в режиме long polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
