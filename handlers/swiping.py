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
import asyncio
import logging

from utils.mistral import get_embedding, cosine_similarity

router = Router()
logger = logging.getLogger(__name__)


async def get_next_profile(session: AsyncSession, current_user_id: int):
    session.expire_all()

    current_user = await session.get(User, current_user_id)
    if not current_user:
        return None

    stmt = select(Swipes.target_id).where(Swipes.swiper_id == current_user_id)
    result = await session.execute(stmt)
    swiped_ids = {row[0] for row in result}
    swiped_ids.add(current_user_id)

    stmt = select(User).where(
        User.id.notin_(swiped_ids) if swiped_ids else User.id != current_user_id
    )
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())

    if not candidates:
        return None

    current_bio = (current_user.bio or "").strip()
    if not current_bio:
        return candidates[0]

    fallback_candidate = candidates[0]

    try:
        current_embedding = await get_embedding(current_bio)

        candidates_with_bio = [u for u in candidates if (u.bio or "").strip()]
        if not candidates_with_bio:
            return fallback_candidate

        bio_list = [(u, (u.bio or "").strip()) for u in candidates_with_bio]
        tasks = [get_embedding(bio) for _, bio in bio_list]
        embeddings = await asyncio.gather(*tasks, return_exceptions=True)

        similarities = []
        for (user, _), emb in zip(bio_list, embeddings):
            if isinstance(emb, Exception):
                logger.warning(f"Ошибка получения embedding для пользователя {user.id}: {emb}")
                continue
            sim = cosine_similarity(current_embedding, emb)
            similarities.append((sim, user))

        if similarities:
            similarities.sort(key=lambda x: x[0], reverse=True)
            return similarities[0][1]

        return fallback_candidate

    except Exception as e:
        logger.error(f"Ошибка при ранжировании через Mistral: {e}")
        return fallback_candidate


async def send_next_profile(bot: Bot, chat_id: int, user_id: int, session: AsyncSession):
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


async def send_like_notification(bot: Bot, target_user_id: int, liker_user: User, session: AsyncSession):
    stmt = select(Swipes).where(
        Swipes.swiper_id == target_user_id,
        Swipes.target_id == liker_user.id,
        Swipes.liked == True
    )
    result = await session.execute(stmt)
    already_liked = result.scalar_one_or_none()

    if not already_liked:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="❤️ Лайк в ответ", callback_data=f"like-back_{liker_user.id}"),
                InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip-like_{liker_user.id}")
            ]
        ])
        photo = FSInputFile(liker_user.photo_path)
        await bot.send_photo(
            chat_id=target_user_id,
            photo=photo,
            caption=f"❤️ <b>{liker_user.name}</b> лайкнул(-а) тебя!\n{liker_user.bio}",
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

    swipe1 = r1.scalar_one_or_none()
    swipe2 = r2.scalar_one_or_none()

    if swipe1 and swipe2:
        existing_match = await session.execute(
            select(Match).where(
                (Match.user1_id == min(user1_id, user2_id)) &
                (Match.user2_id == max(user1_id, user2_id))
            )
        )
        if existing_match.scalar_one_or_none():
            return True

        match = Match(
            user1_id=min(user1_id, user2_id),
            user2_id=max(user1_id, user2_id)
        )
        session.add(match)
        await session.commit()
        session.expire_all()

        user1 = await session.get(User, user1_id)
        user2 = await session.get(User, user2_id)

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
    elif swipe2 and not swipe1:
        liker_user = await session.get(User, user2_id)
        if liker_user:
            await send_like_notification(bot, user1_id, liker_user, session)
    elif swipe1 and not swipe2:
        liker_user = await session.get(User, user1_id)
        if liker_user:
            await send_like_notification(bot, user2_id, liker_user, session)

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
    await callback.answer()
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id
    chat_id = callback.message.chat.id

    existing_swipe = await session.execute(
        select(Swipes).where(
            Swipes.swiper_id == swiper_id,
            Swipes.target_id == target_id
        )
    )
    existing = existing_swipe.scalar_one_or_none()

    if existing:
        existing.liked = True
    else:
        swipe = Swipes(swiper_id=swiper_id, target_id=target_id, liked=True)
        session.add(swipe)

    await session.commit()
    session.expire_all()

    await check_match(session, swiper_id, target_id, callback.bot)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await send_next_profile(callback.bot, chat_id, swiper_id, session)


@router.callback_query(F.data.startswith("dislike_"))
async def handle_dislike(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id
    chat_id = callback.message.chat.id

    existing_swipe = await session.execute(
        select(Swipes).where(
            Swipes.swiper_id == swiper_id,
            Swipes.target_id == target_id
        )
    )
    existing = existing_swipe.scalar_one_or_none()

    if existing:
        existing.liked = False
    else:
        swipe = Swipes(swiper_id=swiper_id, target_id=target_id, liked=False)
        session.add(swipe)

    await session.commit()
    session.expire_all()

    try:
        await callback.message.delete()
    except Exception:
        pass

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


@router.message(F.text == "👥 Смотреть анкеты (/next)")
async def button_next(message: Message, session: AsyncSession):
    await show_next_profile(message, session)


@router.message(F.text == "💌 Мои матчи")
async def button_matches(message: Message, session: AsyncSession):
    await show_matches(message, session)


@router.callback_query(F.data.startswith("like-back_"))
async def handle_like_back(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id

    existing_swipe = await session.execute(
        select(Swipes).where(
            Swipes.swiper_id == swiper_id,
            Swipes.target_id == target_id
        )
    )
    existing = existing_swipe.scalar_one_or_none()

    if existing:
        if not existing.liked:
            existing.liked = True
    else:
        swipe = Swipes(swiper_id=swiper_id, target_id=target_id, liked=True)
        session.add(swipe)

    await session.commit()
    session.expire_all()

    await check_match(session, swiper_id, target_id, callback.bot)

    target_user = await session.get(User, target_id)
    await callback.message.edit_caption(
        caption=f"✅ Вы лайкнули <b>{target_user.name}</b> в ответ!",
        parse_mode="HTML",
        reply_markup=None
    )

    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("skip-like_"))
async def handle_skip_like(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass