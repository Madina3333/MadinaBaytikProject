from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, Swipes, Match

router = Router()


async def get_next_profile(session: AsyncSession, current_user_id: int):
    # Очищаем кэш сессии, чтобы видеть последние изменения после commit
    session.expire_all()
    
    # Получаем все ID пользователей, которых уже свайпнули
    stmt = select(Swipes.target_id).where(Swipes.swiper_id == current_user_id)
    result = await session.execute(stmt)
    swiped_ids = {row[0] for row in result}
    swiped_ids.add(current_user_id)  # не показывать себя
    
    # Выбираем пользователя, которого еще не свайпнули
    # Используем NOT IN для исключения всех просмотренных
    stmt = select(User).where(
        User.id.notin_(swiped_ids) if swiped_ids else User.id != current_user_id
    ).limit(1)
    result = await session.execute(stmt)
    return result.scalars().first()


async def send_next_profile(bot: Bot, chat_id: int, user_id: int, session: AsyncSession):
    """Вспомогательная функция для отправки следующей анкеты"""
    profile = await get_next_profile(session, user_id)
    if not profile:
        await bot.send_message(chat_id, "🚫 Больше анкет нет. Загляни позже!")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{profile.id}"),
            InlineKeyboardButton(text="🚫 Не лайк", callback_data=f"dislike_{profile.id}")
        ]
    ])
    photo = FSInputFile(profile.photo_path)
    await bot.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=f"<b>{profile.name}</b>\n{profile.bio}",
        reply_markup=kb,
        parse_mode="HTML"
    )


async def check_match(session: AsyncSession, user1_id: int, user2_id: int, bot: Bot) -> bool:
    if user1_id == user2_id:
        return False

    stmt1 = select(Swipes).where(
        Swipes.swiper_id == user1_id,
        Swipes.target_id == user2_id,
        Swipes.liked == True
    )
    stmt2 = select(Swipes).where(
        Swipes.swiper_id == user2_id,
        Swipes.target_id == user1_id,
        Swipes.liked == True
    )
    r1 = await session.execute(stmt1)
    r2 = await session.execute(stmt2)

    if r1.scalar() and r2.scalar():
        match = Match(
            user1_id=min(user1_id, user2_id),
            user2_id=max(user1_id, user2_id)
        )
        session.add(match)
        await session.commit()
        session.expire_all()  # Обновляем сессию после commit

        user1 = await session.get(User, user1_id)
        user2 = await session.get(User, user2_id)

        # Отправляем анкету собеседника без кнопок
        photo2 = FSInputFile(user2.photo_path)
        link1 = f"@{user2.username}" if user2.username else f"tg://user?id={user2.id}"
        await bot.send_photo(
            user1_id,
            photo=photo2,
            caption=f"💌 У вас взаимный лайк с <b>{user2.name}</b>!\n{user2.bio}\n\nНаписать: {link1}",
            parse_mode="HTML"
        )

        photo1 = FSInputFile(user1.photo_path)
        link2 = f"@{user1.username}" if user1.username else f"tg://user?id={user1.id}"
        await bot.send_photo(
            user2_id,
            photo=photo1,
            caption=f"💌 У вас взаимный лайк с <b>{user1.name}</b>!\n{user1.bio}\n\nНаписать: {link2}",
            parse_mode="HTML"
        )
        return True
    return False


@router.message(F.text == "/next")
async def show_next_profile(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    profile = await get_next_profile(session, user_id)
    if not profile:
        await message.answer("🚫 Больше анкет нет. Загляни позже!")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{profile.id}"),
            InlineKeyboardButton(text="🚫 Не лайк", callback_data=f"dislike_{profile.id}")
        ]
    ])
    photo = FSInputFile(profile.photo_path)
    await message.answer_photo(
        photo=photo,
        caption=f"<b>{profile.name}</b>\n{profile.bio}",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("like_"))
async def handle_like(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()  # Подтверждаем обработку callback
    
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # Проверяем, не существует ли уже свайп
    existing_swipe = await session.execute(
        select(Swipes).where(
            Swipes.swiper_id == swiper_id,
            Swipes.target_id == target_id
        )
    )
    existing = existing_swipe.scalar_one_or_none()
    
    if existing:
        # Обновляем существующий свайп
        existing.liked = True
    else:
        # Создаем новый свайп
        swipe = Swipes(swiper_id=swiper_id, target_id=target_id, liked=True)
        session.add(swipe)
    
    await session.commit()
    # Обновляем сессию, чтобы изменения были видны в следующем запросе
    session.expire_all()

    # Проверяем матч
    await check_match(session, swiper_id, target_id, callback.bot)

    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass  # Игнорируем ошибки при удалении
    
    # Отправляем следующую анкету
    await send_next_profile(callback.bot, chat_id, swiper_id, session)


@router.callback_query(F.data.startswith("dislike_"))
async def handle_dislike(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()  # Подтверждаем обработку callback
    
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # Проверяем, не существует ли уже свайп
    existing_swipe = await session.execute(
        select(Swipes).where(
            Swipes.swiper_id == swiper_id,
            Swipes.target_id == target_id
        )
    )
    existing = existing_swipe.scalar_one_or_none()
    
    if existing:
        # Обновляем существующий свайп
        existing.liked = False
    else:
        # Создаем новый свайп
        swipe = Swipes(swiper_id=swiper_id, target_id=target_id, liked=False)
        session.add(swipe)
    
    await session.commit()
    # Обновляем сессию, чтобы изменения были видны в следующем запросе
    session.expire_all()

    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass  # Игнорируем ошибки при удалении
    
    # Отправляем следующую анкету
    await send_next_profile(callback.bot, chat_id, swiper_id, session)


@router.message(F.text == "/matches")
async def show_matches(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    stmt = select(Match).where(
        (Match.user1_id == user_id) | (Match.user2_id == user_id)
    )
    result = await session.execute(stmt)
    matches = result.scalars().all()

    if not matches:
        await message.answer("💌 У тебя пока нет матчей.")
        return

    for match in matches:
        partner_id = match.user2_id if match.user1_id == user_id else match.user1_id
        partner = await session.get(User, partner_id)
        if partner:
            photo = FSInputFile(partner.photo_path)
            link = f"@{partner.username}" if partner.username else f"tg://user?id={partner.id}"
            await message.answer_photo(
                photo=photo,
                caption=f"💌 Матч с: <b>{partner.name}</b>\n{partner.bio}\n\nНаписать: {link}",
                parse_mode="HTML"
            )
        else:
            await message.answer(f"💌 Матч с пользователем {partner_id} (анкета удалена)")


# Кнопки из меню
@router.message(F.text == "👥 Смотреть анкеты (/next)")
async def button_next(message: Message, session: AsyncSession):
    await show_next_profile(message, session)

@router.message(F.text == "💌 Мои матчи")
async def button_matches(message: Message, session: AsyncSession):
    await show_matches(message, session)