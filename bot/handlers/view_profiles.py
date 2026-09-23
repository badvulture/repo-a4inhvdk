import os

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db.models import ProfileAccess, Purchase, User, Video
from bot.db.repo import display_name
from bot.locales.texts import btn_variants, t
from bot.services import mirrors as mirrors_service
from bot.services.video import send_circle

router = Router()

async def author_stats(session: AsyncSession, author_id: int):
    return (
        await session.execute(
            select(
                func.count(Video.id),
                func.coalesce(func.sum(Video.likes), 0),
                func.coalesce(func.sum(Video.dislikes), 0),
                func.coalesce(func.sum(Video.views), 0),
            ).where(
                Video.owner_id == author_id,
                Video.is_active.is_(True),
                Video.in_pool.is_(False),
            )
        )
    ).one()


async def author_buyers(session: AsyncSession, author_id: int) -> int:
    return (
        await session.execute(
            select(func.count(ProfileAccess.id)).where(
                ProfileAccess.author_id == author_id
            )
        )
    ).scalar_one()


async def ensure_photo_path(session: AsyncSession, author: User) -> str | None:
    """file_ids are bot-specific: photos set through a mirror can only be
    downloaded by that mirror, so try every running bot once and keep a
    local copy."""
    if author.author_photo_path and os.path.exists(author.author_photo_path):
        return author.author_photo_path
    if not author.author_photo:
        return None
    bots = []
    if mirrors_service.main_bot:
        bots.append(mirrors_service.main_bot)
    if mirrors_service.mirror_manager:
        bots.extend(mirrors_service.mirror_manager.bots.values())
    for b in bots:
        try:
            file = await b.get_file(author.author_photo)
            os.makedirs(config.storage_dir, exist_ok=True)
            path = os.path.join(
                config.storage_dir, f"avatar_{author.id}_{file.file_unique_id}.jpg"
            )
            await b.download_file(file.file_path, destination=path)
            author.author_photo_path = path
            await session.commit()
            return path
        except Exception:
            continue
    return None


async def random_author(session: AsyncSession, exclude_id: int | None = None) -> User | None:
    q = (
        select(User)
        .join(Video, Video.owner_id == User.id)
        .where(
            Video.is_active.is_(True),
            Video.in_pool.is_(False),
            # only complete profiles: photo + description + price
            User.author_photo.is_not(None),
            User.author_description.is_not(None),
            User.author_description != "",
            User.author_price > 0,
        )
        .group_by(User.id)
        .order_by(func.random())
        .limit(1)
    )
    if exclude_id is not None:
        author = (
            await session.execute(q.where(User.id != exclude_id))
        ).scalar_one_or_none()
        if author is not None:
            return author
    return (await session.execute(q)).scalar_one_or_none()


async def send_author_card(message: Message, session: AsyncSession, user: User, lang: str, author: User):
    count, likes, dislikes, _views = await author_stats(session, author.id)
    buyers = await author_buyers(session, author.id)
    has_access = author.id == user.id or (
        await session.execute(
            select(ProfileAccess).where(
                ProfileAccess.buyer_id == user.id, ProfileAccess.author_id == author.id
            )
        )
    ).scalar_one_or_none() is not None

    text = t(
        lang,
        "profile_card",
        id=author.id,
        name=display_name(author),
        description=author.author_description or t(lang, "no_description"),
        count=count,
        likes=likes,
        dislikes=dislikes,
        buyers=buyers,
        price=author.author_price,
    )
    if not has_access:
        text += "\n\n" + t(lang, "profile_card_hint")
    kb = InlineKeyboardBuilder()
    if has_access:
        kb.button(text=t(lang, "btn_open_profile"), callback_data=f"vp:videos:{author.id}")
    else:
        kb.button(
            text=t(lang, "btn_buy_access", price=author.author_price),
            callback_data=f"vp:buy:{author.id}",
        )
    kb.button(text=t(lang, "btn_next_profile"), callback_data=f"vp:next:{author.id}")
    kb.adjust(1)
    if author.author_photo:
        try:
            await message.answer_photo(
                author.author_photo, caption=text, reply_markup=kb.as_markup()
            )
            return
        except Exception:
            pass  # photo file_id belongs to another bot (mirror)
    path = await ensure_photo_path(session, author)
    if path:
        try:
            sent = await message.answer_photo(
                FSInputFile(path), caption=text, reply_markup=kb.as_markup()
            )
            if sent.photo:
                author.author_photo = sent.photo[-1].file_id
                await session.commit()
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=kb.as_markup())


@router.message(Command("profiles"))
@router.message(F.text.in_(btn_variants("btn_view_profiles")))
async def view_profiles(message: Message, session: AsyncSession, user: User, lang: str):
    author = await random_author(session)
    if author is None:
        await message.answer(t(lang, "no_authors"))
        return
    await send_author_card(message, session, user, lang, author)


@router.callback_query(F.data.startswith("vp:next:"))
async def next_profile(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    author = await random_author(session, exclude_id=int(cb.data.split(":")[2]))
    await cb.answer()
    if author is None:
        await cb.message.answer(t(lang, "no_authors"))
        return
    await send_author_card(cb.message, session, user, lang, author)


@router.callback_query(F.data.startswith("vp:open:"))
async def open_author(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    author = await session.get(User, int(cb.data.split(":")[2]))
    await cb.answer()
    if author:
        await send_author_card(cb.message, session, user, lang, author)


@router.callback_query(F.data.startswith("vp:buy:"))
async def buy_access(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    author = await session.get(User, int(cb.data.split(":")[2]))
    if author is None:
        await cb.answer()
        return
    existing = (
        await session.execute(
            select(ProfileAccess).where(
                ProfileAccess.buyer_id == user.id, ProfileAccess.author_id == author.id
            )
        )
    ).scalar_one_or_none()
    if existing:
        await cb.answer(t(lang, "access_already"), show_alert=True)
        return
    if user.balance < author.author_price:
        await cb.answer(t(lang, "no_balance"), show_alert=True)
        return
    user.balance -= author.author_price
    author.author_earned += author.author_price
    session.add(ProfileAccess(buyer_id=user.id, author_id=author.id))
    session.add(
        Purchase(
            user_id=user.id,
            kind="profile",
            description=f"Доступ к профилю #{author.id}",
            amount_coins=author.author_price,
            target_user_id=author.id,
        )
    )
    await session.commit()
    await cb.message.answer(t(lang, "access_bought"))
    await cb.answer()
    await send_author_videos(cb.message, session, lang, author.id)


async def send_author_videos(message: Message, session: AsyncSession, lang: str, author_id: int):
    videos = (
        (
            await session.execute(
                select(Video)
                .where(
                    Video.owner_id == author_id,
                    Video.is_active.is_(True),
                    Video.in_pool.is_(False),
                )
                .order_by(Video.seq_no)
            )
        )
        .scalars()
        .all()
    )
    if not videos:
        await message.answer(t(lang, "author_no_videos"))
        return
    for v in videos:
        kb = InlineKeyboardBuilder()
        kb.button(text=f"👍 {v.likes}", callback_data=f"rate:{v.id}:1")
        kb.button(text=f"👎 {v.dislikes}", callback_data=f"rate:{v.id}:-1")
        kb.adjust(2)
        await send_circle(
            message.bot, message.chat.id, v, session, reply_markup=kb.as_markup()
        )


@router.callback_query(F.data.startswith("vp:videos:"))
async def open_videos(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    author_id = int(cb.data.split(":")[2])
    author = await session.get(User, author_id)
    if author is None:
        await cb.answer()
        return
    has_access = author.id == user.id or (
        await session.execute(
            select(ProfileAccess).where(
                ProfileAccess.buyer_id == user.id, ProfileAccess.author_id == author.id
            )
        )
    ).scalar_one_or_none() is not None
    await cb.answer()
    if has_access:
        await send_author_videos(cb.message, session, lang, author_id)
