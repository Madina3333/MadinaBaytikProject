# Telegram Dating Bot

Telegram бот для знакомств с функционалом свайпинга анкет (Tinder-like).

## Функциональность

- Регистрация пользователей с фото и описанием
- Просмотр анкет других пользователей
- Система лайков и дизлайков
- Уведомления о взаимных лайках (матчах)
- Просмотр списка матчей

## Технологии

- **aiogram 3.x** - асинхронный фреймворк для Telegram Bot API
- **SQLAlchemy** - ORM для работы с базой данных
- **aiosqlite** - асинхронный драйвер для SQLite

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd aiogramTelegramBot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте токен бота (один из способов):

   **Способ 1: Создайте файл `.env`** (рекомендуется):
   ```bash
   cp .env.example .env
   # Отредактируйте .env и укажите ваш токен
   ```

   **Способ 2: Установите переменную окружения:**
   ```bash
   # Windows (PowerShell)
   $env:BOT_TOKEN="your_telegram_bot_token_here"
   
   # Windows (CMD)
   set BOT_TOKEN=your_telegram_bot_token_here
   
   # Linux/Mac
   export BOT_TOKEN=your_telegram_bot_token_here
   ```

4. Запустите бота:
```bash
python main.py
```

## Структура проекта

```
.
├── main.py              # Точка входа, настройка бота
├── models.py            # Модели базы данных (User, Swipes, Match)
├── handlers/
│   ├── registration.py  # Обработка регистрации пользователей
│   └── swiping.py       # Обработка свайпинга и матчей
├── utils/
│   └── photo.py         # Утилиты для работы с фотографиями
└── photos/              # Директория для загруженных фото (не в git)

```

## Команды бота

- `/start` - Главное меню
- `/next` - Следующая анкета
- `/matches` - Мои матчи

## База данных

Бот использует SQLite базу данных. При первом запуске автоматически создаются необходимые таблицы:

- `users` - пользователи бота
- `swipes` - история свайпов (лайков/дизлайков)
- `matches` - взаимные лайки (матчи)

## Лицензия

MIT

