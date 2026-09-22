import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db.models import Rating, Sponsor, SponsorHidden, SubscriptionTier, User, Video, View
from bot.db.repo import get_setting, random_video, reset_daily_if_needed
from bot.locales.texts import btn_variants, t
from bot.services.video import send_circle

router = Router()

_last_circle: dict[int, float] = {}


def circle_kb(lang: str, video: Video, balance: int | None = None, is_admin: bool = False):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"👍 {video.likes}", callback_data=f"rate:{video.id}:1")
    kb.button(text=f"👎 {video.dislikes}", callback_data=f"rate:{video.id}:-1")
    layout = [2]
    if not video.in_pool:
        kb.button(text=t(lang, "btn_view_author"), callback_data=f"vp:open:{video.owner_id}")
        layout.append(1)
    kb.button(text=t(lang, "btn_next"), callback_data="next_circle")
    layout.append(1)
    if is_admin:
        kb.button(text=t(lang, "btn_delete"), callback_data=f"adm:delvid:{video.id}")
        layout.append(1)
    kb.adjust(*layout)
    return kb.as_markup()


async def maybe_recommend(
    message: Message, session: AsyncSession, user: User, lang: str
) -> None:
    """Advertise one random 'recommend' sponsor every N viewed circles."""
    every = int(await get_setting(session, "recommend_every"))
    if not every or user.viewed_count % every != 0:
        return
    hidden = select(SponsorHidden.sponsor_id).where(SponsorHidden.user_id == user.id)
    sponsor = (
        await session.execute(
            select(Sponsor)
            .where(
                Sponsor.is_active.is_(True),
                Sponsor.kind == "recommend",
                Sponsor.id.not_in(hidden),
            )
            .order_by(func.random())
            .limit(1)
        )
    ).scalar_one_or_none()
    if sponsor is None:
        return
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_recommend_open"), url=sponsor.invite_link)
    kb.button(
        text=t(lang, "btn_recommend_hide"), callback_data=f"rec:hide:{sponsor.id}"
    )
    kb.adjust(1)
    await message.answer(
        t(lang, "recommend_channel", title=sponsor.title),
        reply_markup=kb.as_markup(),
    )


async def send_next_circle(
    message: Message, session: AsyncSession, user: User, lang: str
) -> str | None:
    """Sends a random circle. Returns a toast text for callback answer (or None)."""
    now = time.monotonic()
    if now - _last_circle.get(user.tg_id, 0) < 1.0:
        toast = t(lang, "too_fast")
        await message.answer(toast)
        return toast
    _last_circle[user.tg_id] = now

    await reset_daily_if_needed(session, user)

    video = await random_video(session, viewer_id=user.id)
    if video is None:
        await message.answer(t(lang, "no_videos"))
        return None

    free = user.has_active_subscription
    protect = True
    spent = 0
    free_toast = False
    if free:
        if user.subscription == SubscriptionTier.A_PLUS:
            limit_cfg = await get_setting(session, "sub_a_plus")
            if int(limit_cfg["daily_limit"]) and user.viewed_today >= int(
                limit_cfg["daily_limit"]
            ):
                await message.answer(t(lang, "daily_limit"))
                return None
        else:
            protect = False  # A++ / PREMIUM: forwarding & downloading allowed
    elif not user.free_view_used:
        # the very first watched circle is free
        user.free_view_used = True
        await session.commit()
        free = True
        free_toast = True

    if not free:
        price = int(await get_setting(session, "view_price"))
        res = await session.execute(
            text(
                "UPDATE users SET balance = balance - :price "
                "WHERE id = :id AND balance >= :price RETURNING balance"
            ),
            {"price": price, "id": user.id},
        )
        new_balance = res.scalar_one_or_none()
        await session.commit()
        if new_balance is None:
            await message.answer(t(lang, "no_balance"))
            return None
        user.balance = new_balance
        spent = price

    kb = circle_kb(lang, video, balance=user.balance, is_admin=user.tg_id in config.admin_ids)
    sent = await send_circle(
        message.bot,
        message.chat.id,
        video,
        session,
        protect=protect,
        reply_markup=kb,
        caption=t(
            lang,
            "circle_caption",
            seq=video.seq_no,
            author=video.owner_id,
            likes=video.likes,
            dislikes=video.dislikes,
            views=video.views + 1,
        ),
    )
    if sent is None:
        if spent:
            await session.execute(
                text("UPDATE users SET balance = balance + :price WHERE id = :id"),
                {"price": spent, "id": user.id},
            )
            await session.commit()
            user.balance += spent
        await message.answer(t(lang, "send_failed"))
        return None

    user.viewed_count += 1
    user.viewed_today += 1
    video.views += 1
    session.add(View(user_id=user.id, video_id=video.id))
    await session.commit()

    try:
        await maybe_recommend(message, session, user, lang)
    except Exception:
        pass

    if free_toast:
        toast = t(lang, "free_view_toast")
        await message.answer(toast)
        return toast
    if spent:
        toast = t(lang, "spent_toast", spent=spent, balance=user.balance)
        await message.answer(toast)
        return toast
    return None


@router.message(Command("circle"))
@router.message(F.text.in_(btn_variants("btn_next_circle")))
async def next_circle_msg(message: Message, session: AsyncSession, user: User, lang: str):
    await send_next_circle(message, session, user, lang)


@router.callback_query(F.data == "next_circle")
async def next_circle_cb(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    toast = await send_next_circle(cb.message, session, user, lang)
    try:
        await cb.answer(toast)
    except Exception:
        pass


@router.callback_query(F.data == "free_circle")
async def free_circle_cb(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    toast = await send_next_circle(cb.message, session, user, lang)
    try:
        await cb.answer(toast)
    except Exception:
        pass


@router.callback_query(F.data.startswith("rec:hide:"))
async def recommend_hide(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    sponsor_id = int(cb.data.split(":")[2])
    session.add(SponsorHidden(user_id=user.id, sponsor_id=sponsor_id))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer(t(lang, "recommend_hidden"))


@router.callback_query(F.data.startswith("rate:"))
async def rate_video(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    _, video_id, value = cb.data.split(":")
    video = await session.get(Video, int(video_id))
    if video is None:
        await cb.answer()
        return
    existing = (
        await session.execute(
            select(Rating).where(Rating.user_id == user.id, Rating.video_id == video.id)
        )
    ).scalar_one_or_none()
    if existing:
        await cb.answer(t(lang, "already_rated"), show_alert=True)
        return
    val = int(value)
    session.add(Rating(user_id=user.id, video_id=video.id, value=val))
    if val > 0:
        video.likes += 1
    else:
        video.dislikes += 1
        limit = int(await get_setting(session, "auto_delete_dislikes"))
        if limit and video.dislikes >= limit:
            video.is_active = False
    await session.commit()
    await cb.answer(t(lang, "rated"))
    try:
        await cb.message.edit_reply_markup(
            reply_markup=circle_kb(
                lang, video, balance=user.balance, is_admin=user.tg_id in config.admin_ids
            )
        )
    except Exception:
        pass
