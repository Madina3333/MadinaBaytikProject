# handlers/swiping.py
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, any_state  # ← any_state — это объект, не аргумент!
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, Swipes, Match
import asyncio
import os
import random
import logging

from utils.mistral import jaccard_similarity

router = Router()
logger = logging.getLogger(__name__)


async def get_next_profile(session, current_user_id: int):
    session.expire_all()
    current_user = await session.get(User, current_user_id)
    if not current_user:
        print("❌ Текущий пользователь не найден")
        return None

    swiped_result = await session.execute(
        select(Swipes.target_id).where(Swipes.swiper_id == current_user_id)
    )
    swiped_ids = {row[0] for row in swiped_result}
    swiped_ids.add(current_user_id)

    candidates_result = await session.execute(
        select(User).where(User.id.notin_(swiped_ids))
    )
    candidates = [u for u in candidates_result.scalars().all() if u.interests]

    if not candidates:
        # Fallback: все кандидаты (даже без интересов)
        candidates_result = await session.execute(
            select(User).where(User.id.notin_(swiped_ids))
        )
        candidates = list(candidates_result.scalars().all())
        if candidates:
            fallback = random.choice(candidates)
            print(f"🎲 Fallback (нет интересов): выбран {fallback.name} (ID={fallback.id})")
            return fallback
        return None

    # Ранжируем по Жаккару
    if current_user.interests:
        similarities = []
        for candidate in candidates:
            if candidate.interests:
                score = jaccard_similarity(current_user.interests, candidate.interests)
                similarities.append((score, candidate))
                print(f"   → {candidate.name} (ID={candidate.id}): интересы = '{candidate.interests}', схожесть = {score:.3f}")

        if similarities:
            similarities.sort(key=lambda x: x[0], reverse=True)
            best = similarities[0][1]
            print(f"🎯 Выбран по интересам: {best.name} (ID={best.id}) | схожесть = {similarities[0][0]:.3f}")
            return best

    # Fallback на случайный выбор
    fallback = random.choice(candidates)
    print(f"🔀 Fallback: выбран {fallback.name} (ID={fallback.id})")
    return fallback


async def send_next_profile(bot: Bot, chat_id: int, user_id: int, session: AsyncSession):
    profile = await get_next_profile(session, user_id)
    if not profile:
        await bot.send_message(chat_id, "🚫 Больше анкет нет. Загляни позже!")
        return

    if not os.path.exists(profile.photo_path):
        logger.warning(f"Фото отсутствует: {profile.photo_path}, пропускаем")
        await send_next_profile(bot, chat_id, user_id, session)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{profile.id}")],
        [InlineKeyboardButton(text="🚫 Не лайк", callback_data=f"dislike_{profile.id}")]
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
            [InlineKeyboardButton(text="❤️ Лайк в ответ", callback_data=f"like-back_{liker_user.id}")],
            [InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip-like_{liker_user.id}")]
        ])
        if os.path.exists(liker_user.photo_path):
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

    stmt1 = select(Swipes).where(Swipes.swiper_id == user1_id, Swipes.target_id == user2_id, Swipes.liked == True)
    stmt2 = select(Swipes).where(Swipes.swiper_id == user2_id, Swipes.target_id == user1_id, Swipes.liked == True)
    r1 = await session.execute(stmt1)
    r2 = await session.execute(stmt2)
    swipe1 = r1.scalar_one_or_none()
    swipe2 = r2.scalar_one_or_none()

    if swipe1 and swipe2:
        # Проверяем, не создан ли матч
        match_exists = await session.execute(
            select(Match).where(
                (Match.user1_id == min(user1_id, user2_id)) &
                (Match.user2_id == max(user1_id, user2_id))
            )
        )
        if not match_exists.scalar_one_or_none():
            match = Match(user1_id=min(user1_id, user2_id), user2_id=max(user1_id, user2_id))
            session.add(match)
            await session.commit()

            user1 = await session.get(User, user1_id)
            user2 = await session.get(User, user2_id)
            if user1 and user2:
                link2 = f"@{user2.username}" if user2.username else f"tg://user?id={user2.id}"
                link1 = f"@{user1.username}" if user1.username else f"tg://user?id={user1.id}"

                if os.path.exists(user2.photo_path):
                    await bot.send_photo(
                        user1_id,
                        photo=FSInputFile(user2.photo_path),
                        caption=f"💌 У вас взаимный лайк с <b>{user2.name}</b>!\n{user2.bio}\n\nНаписать: {link2}",
                        parse_mode="HTML"
                    )
                if os.path.exists(user1.photo_path):
                    await bot.send_photo(
                        user2_id,
                        photo=FSInputFile(user1.photo_path),
                        caption=f"💌 У вас взаимный лайк с <b>{user1.name}</b>!\n{user1.bio}\n\nНаписать: {link1}",
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


@router.message(F.text == "/next", StateFilter("*"))
async def show_next_profile(message: Message, session: AsyncSession):
    await send_next_profile(message.bot, message.chat.id, message.from_user.id, session)


@router.callback_query(F.data.startswith("like_"))
async def handle_like(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id

    existing = await session.execute(
        select(Swipes).where(Swipes.swiper_id == swiper_id, Swipes.target_id == target_id)
    )
    swipe = existing.scalar_one_or_none()

    if swipe:
        swipe.liked = True
    else:
        session.add(Swipes(swiper_id=swiper_id, target_id=target_id, liked=True))
    await session.commit()

    # ✅ Вызываем напрямую — без импорта!
    await check_match(session, swiper_id, target_id, callback.bot)

    try:
        await callback.message.delete()
    except:
        pass
    await send_next_profile(callback.bot, callback.message.chat.id, swiper_id, session)


@router.callback_query(F.data.startswith("dislike_"))
async def handle_dislike(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id

    existing = await session.execute(
        select(Swipes).where(Swipes.swiper_id == swiper_id, Swipes.target_id == target_id)
    )
    swipe = existing.scalar_one_or_none()

    if swipe:
        swipe.liked = False
    else:
        session.add(Swipes(swiper_id=swiper_id, target_id=target_id, liked=False))
    await session.commit()

    try:
        await callback.message.delete()
    except:
        pass
    await send_next_profile(callback.bot, callback.message.chat.id, swiper_id, session)


@router.message(F.text == "/matches", StateFilter("*"))
async def show_matches(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    stmt = select(Match).where((Match.user1_id == user_id) | (Match.user2_id == user_id))
    result = await session.execute(stmt)
    matches = result.scalars().all()

    if not matches:
        await message.answer("💌 У тебя пока нет матчей.")
        return

    for match in matches:
        partner_id = match.user2_id if match.user1_id == user_id else match.user1_id
        partner = await session.get(User, partner_id)
        if partner and os.path.exists(partner.photo_path):
            link = f"@{partner.username}" if partner.username else f"tg://user?id={partner.id}"
            await message.answer_photo(
                FSInputFile(partner.photo_path),
                caption=f"💌 Матч с: <b>{partner.name}</b>\n{partner.bio}\n\nНаписать: {link}",
                parse_mode="HTML"
            )


@router.message(F.text == "👥 Смотреть анкеты (/next)", StateFilter("*"))
async def button_next(message: Message, session: AsyncSession):
    await show_next_profile(message, session)


@router.message(F.text == "💌 Мои матчи", StateFilter("*"))
async def button_matches(message: Message, session: AsyncSession):
    await show_matches(message, session)


@router.callback_query(F.data.startswith("like-back_"))
async def handle_like_back(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    target_id = int(callback.data.split("_")[1])
    swiper_id = callback.from_user.id

    existing = await session.execute(
        select(Swipes).where(Swipes.swiper_id == swiper_id, Swipes.target_id == target_id)
    )
    swipe = existing.scalar_one_or_none()

    if swipe:
        swipe.liked = True
    else:
        session.add(Swipes(swiper_id=swiper_id, target_id=target_id, liked=True))
    await session.commit()

    await check_match(session, swiper_id, target_id, callback.bot)

    await callback.message.edit_caption(caption="✅ Лайк отправлен!", reply_markup=None)
    try:
        await callback.message.delete()
    except:
        pass


@router.callback_query(F.data.startswith("skip-like_"))
async def handle_skip_like(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except:
        pass