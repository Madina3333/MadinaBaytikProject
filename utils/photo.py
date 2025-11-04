# utils/photo.py

import os
import aiohttp

# Папка для хранения фотографий пользователей
PHOTO_DIR = "photos"

# Создаём папку при импорте модуля (если её нет)
os.makedirs(PHOTO_DIR, exist_ok=True)


async def download_photo(bot, file_id: str, user_id: int) -> str:
    """
    Скачивает фото из Telegram по file_id и сохраняет его локально.

    Аргументы:
        bot — экземпляр Bot из aiogram (нужен для получения file_path и токена)
        file_id — строка, полученная от Telegram при отправке фото
        user_id — ID пользователя в Telegram (используется как имя файла)

    Возвращает:
        str — путь к сохранённому файлу, например: "photos/123456789.jpg"

    Выбрасывает исключение, если скачать не удалось.
    """
    # Запрашиваем у Telegram информацию о файле (в т.ч. file_path)
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path  # путь на серверах Telegram, например: "photos/AbC123.jpg"

    # Формируем локальный путь: photos/{user_id}.jpg
    local_filename = f"{user_id}.jpg"
    local_path = os.path.join(PHOTO_DIR, local_filename)

    # Строим полный URL для скачивания
    url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"

    # Асинхронно скачиваем файл
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                # Записываем содержимое в файл
                with open(local_path, "wb") as f:
                    f.write(await response.read())
            else:
                # Если ошибка — выбрасываем исключение
                raise Exception(f"Не удалось скачать фото. Код ответа: {response.status}")

    # Возвращаем относительный путь к файлу
    return local_path