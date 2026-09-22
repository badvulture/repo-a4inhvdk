import os
import uuid

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from bot.db.models import (
    PromoActivation,
    PromoCode,
    Purchase,
    SubscriptionTier,
    User,
    Video,
    VideoFileCache,
    Withdrawal,
)
from bot.db.repo import display_name, get_setting
from bot.keyboards import back_kb, main_menu, smart_edit
from bot.locales.texts import btn_variants, t
from bot.services.video import (
    MAIN_BOT_ID,
    MAX_DURATION,
    MAX_SIZE,
    detect_media,
    media_to_note,
    send_circle,
)

router = Router()


class ProfileStates(StatesGroup):
    upload = State()
    set_price = State()
    set_photo = State()
    set_description = State()
    withdraw = State()
    promo = State()


def profile_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_upload"), callback_data="pf:upload")
    kb.button(text=t(lang, "btn_my_circles"), callback_data="pf:my")
    kb.button(text=t(lang, "btn_author_profile"), callback_data="pf:author")
    kb.button(text=t(lang, "btn_my_purchases"), callback_data="pf:purchases")
    kb.button(text=t(lang, "btn_promo"), callback_data="pf:promo")
    kb.adjust(1)
    return kb.as_markup()


async def profile_text(session: AsyncSession, user: User, lang: str) -> str:
    uploaded, likes, dislikes = (
        await session.execute(
            select(
                func.count(Video.id),
                func.coalesce(func.sum(Video.likes), 0),
                func.coalesce(func.sum(Video.dislikes), 0),
            ).where(
                Video.owner_id == user.id,
                Video.is_active.is_(True),
                Video.in_pool.is_(False),
            )
        )
    ).one()
    return t(
        lang,
        "profile",
        tg_id=user.tg_id,
        uploaded=uploaded,
        likes=likes,
        dislikes=dislikes,
        viewed=user.viewed_count,
        balance=user.balance,
        sub=sub_label(lang, user),
    )


def sub_label(lang: str, user: User) -> str:
    if not user.has_active_subscription:
        return t(lang, "sub_none")
    names = {
        SubscriptionTier.A_PLUS: "А+",
        SubscriptionTier.A_PLUS_PLUS: "A++",
        SubscriptionTier.PREMIUM: "⭐️ PREMIUM",
    }
    name = names.get(user.subscription, "?")
    if user.subscription == SubscriptionTier.PREMIUM or not user.subscription_until:
        return f"{name} ({t(lang, 'sub_forever')})"
    return f"{name} ({t(lang, 'sub_until', date=user.subscription_until.strftime('%d.%m.%Y'))})"


@router.message(Command("profile"))
@router.message(F.text.in_(btn_variants("btn_profile")))
async def show_profile(message: Message, session: AsyncSession, user: User, lang: str):
    await message.answer(
        await profile_text(session, user, lang), reply_markup=profile_kb(lang)
    )


@router.callback_query(F.data == "pf:home")
async def profile_home(cb: CallbackQuery, session: AsyncSession, user: User, lang: str, state: FSMContext):
    await state.clear()
    await smart_edit(
        cb.message, await profile_text(session, user, lang), reply_markup=profile_kb(lang)
    )
    await cb.answer()


# ---------- upload ----------

@router.callback_query(F.data == "pf:upload")
async def upload_start(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(ProfileStates.upload)
    await smart_edit(cb.message, t(lang, "upload_prompt"), reply_markup=back_kb(lang, "pf:home"))
    await cb.answer()


@router.message(
    ProfileStates.upload, F.video | F.video_note | F.animation | F.photo | F.document
)
async def upload_video(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    lang: str,
    bot: Bot,
):
    media, kind = detect_media(message)
    if media is None or kind is None:
        await message.answer(t(lang, "unsupported_media"))
        return
    if kind != "image" and media.duration and media.duration > MAX_DURATION:
        await message.answer(t(lang, "upload_too_long"))
        return
    if media.file_size and media.file_size > MAX_SIZE:
        await message.answer(t(lang, "upload_too_big"))
        return

    status = await message.answer(t(lang, "upload_processing"))
    note_file_id = None
    local_path = None
    try:
        result = await media_to_note(bot, message)
        if result is None:
            await status.edit_text(t(lang, "convert_failed"))
            return
        local_path, duration = result
        if kind == "note":
            note_file_id = media.file_id
        else:
            # send the note back as the confirmation preview and keep its file_id
            sent = await bot.send_video_note(message.chat.id, FSInputFile(local_path))
            note_file_id = sent.video_note.file_id
    except Exception:
        pass

    if note_file_id is None:
        await status.edit_text(t(lang, "convert_failed"))
        return

    seq = (
        await session.execute(
            select(func.coalesce(func.max(Video.seq_no), 0)).where(Video.owner_id == user.id)
        )
    ).scalar_one() + 1
    video = Video(
        owner_id=user.id,
        seq_no=seq,
        file_id=media.file_id,
        note_file_id=note_file_id,
        local_path=local_path,
        duration=duration,
    )
    session.add(video)
    await session.flush()
    if bot.id != MAIN_BOT_ID:
        # the upload came through a mirror: these file_ids belong to that bot
        session.add(
            VideoFileCache(
                video_id=video.id,
                bot_id=bot.id,
                note_file_id=note_file_id,
                file_id=media.file_id,
            )
        )
    await session.commit()
    await state.clear()
    await status.edit_text(t(lang, "upload_done", seq=seq))


@router.message(ProfileStates.upload)
async def upload_wrong_type(message: Message, lang: str):
    await message.answer(t(lang, "upload_prompt"), reply_markup=back_kb(lang, "pf:home"))


# ---------- my circles ----------

@router.callback_query(F.data == "pf:my")
async def my_circles(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    await cb.answer()
    videos = (
        (
            await session.execute(
                select(Video)
                .where(
                    Video.owner_id == user.id,
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
        await cb.message.answer(t(lang, "my_circles_empty"))
        return
    for v in videos:
        kb = InlineKeyboardBuilder()
        kb.button(text=t(lang, "btn_delete"), callback_data=f"pf:del:{v.id}")
        await send_circle(cb.message.bot, cb.message.chat.id, v, session)
        await cb.message.answer(
            t(lang, "my_circle_caption", seq=v.seq_no, likes=v.likes, dislikes=v.dislikes, views=v.views),
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("pf:del:"))
async def delete_circle(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    video = await session.get(Video, int(cb.data.split(":")[2]))
    if video and video.owner_id == user.id:
        video.is_active = False
        await session.commit()
    await cb.answer(t(lang, "deleted"))
    await cb.message.delete()


# ---------- promo code ----------

@router.callback_query(F.data == "pf:promo")
async def promo_start(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(ProfileStates.promo)
    await smart_edit(cb.message, t(lang, "promo_prompt"), reply_markup=back_kb(lang, "pf:home"))
    await cb.answer()


@router.message(Command("promo"))
async def promo_cmd(message: Message, state: FSMContext, lang: str):
    await state.set_state(ProfileStates.promo)
    await message.answer(t(lang, "promo_prompt"), reply_markup=back_kb(lang, "pf:home"))


@router.message(ProfileStates.promo, F.text)
async def promo_enter(
    message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str
):
    code = message.text.strip()
    promo = (
        await session.execute(
            select(PromoCode).where(
                func.lower(PromoCode.code) == code.lower(), PromoCode.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if promo is None or (promo.max_uses and promo.used_count >= promo.max_uses):
        await message.answer(t(lang, "promo_invalid"), reply_markup=back_kb(lang, "pf:home"))
        return
    session.add(PromoActivation(promo_id=promo.id, user_id=user.id))
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        await message.answer(t(lang, "promo_used"), reply_markup=back_kb(lang, "pf:home"))
        return
    promo.used_count += 1
    rewards = []
    if promo.coins:
        user.balance += promo.coins
        rewards.append(f"+{promo.coins} \U0001fa99")
    if promo.sub_tier:
        user.subscription = SubscriptionTier(promo.sub_tier)
        user.subscription_until = (
            datetime.utcnow() + timedelta(days=promo.sub_days) if promo.sub_days else None
        )
        rewards.append(sub_label(lang, user))
    await session.commit()
    await state.clear()
    await message.answer(
        t(lang, "promo_success", rewards=", ".join(rewards)), reply_markup=main_menu(lang)
    )


# ---------- author profile ----------

def author_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_set_price"), callback_data="pf:price")
    kb.button(text=t(lang, "btn_set_photo"), callback_data="pf:photo")
    kb.button(text=t(lang, "btn_set_description"), callback_data="pf:desc")
    kb.button(text=t(lang, "btn_withdraw"), callback_data="pf:withdraw")
    kb.button(text=t(lang, "btn_back"), callback_data="pf:home")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def author_info_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_author_agree"), callback_data="pf:authorcfg")
    kb.button(text=t(lang, "btn_back"), callback_data="pf:home")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "pf:author")
async def author_info(cb: CallbackQuery, lang: str):
    await smart_edit(cb.message, t(lang, "author_info"), reply_markup=author_info_kb(lang))
    await cb.answer()


@router.message(Command("info"))
async def author_info_cmd(message: Message, lang: str):
    await message.answer(t(lang, "author_info"), reply_markup=author_info_kb(lang))


@router.callback_query(F.data == "pf:authorcfg")
async def author_profile(cb: CallbackQuery, user: User, lang: str):
    text = t(
        lang,
        "author_profile",
        description=user.author_description or t(lang, "no_description"),
        price=user.author_price,
        earned=user.author_earned,
    )
    await smart_edit(cb.message, text, reply_markup=author_kb(lang))
    await cb.answer()


@router.callback_query(F.data.in_({"pf:price", "pf:photo", "pf:desc", "pf:withdraw"}))
async def author_edit_start(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, lang: str
):
    mapping = {
        "pf:price": (ProfileStates.set_price, "set_price_prompt"),
        "pf:photo": (ProfileStates.set_photo, "set_photo_prompt"),
        "pf:desc": (ProfileStates.set_description, "set_description_prompt"),
        "pf:withdraw": (ProfileStates.withdraw, "withdraw_prompt"),
    }
    if cb.data == "pf:withdraw":
        min_coins = int(await get_setting(session, "min_withdraw_coins"))
        if user.author_earned < min_coins:
            await cb.answer(
                t(lang, "withdraw_min", min=min_coins, earned=user.author_earned),
                show_alert=True,
            )
            return
    st, prompt = mapping[cb.data]
    await state.set_state(st)
    await smart_edit(cb.message, t(lang, prompt), reply_markup=back_kb(lang, "pf:authorcfg"))
    await cb.answer()


@router.message(ProfileStates.set_price, F.text)
async def set_price(message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str):
    try:
        price = max(0, int(message.text.strip()))
    except ValueError:
        await message.answer(t(lang, "set_price_prompt"))
        return
    user.author_price = price
    await session.commit()
    await state.clear()
    await message.answer(t(lang, "saved"))


@router.message(ProfileStates.set_photo, F.photo)
async def set_photo(
    message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str, bot: Bot
):
    file_id = message.photo[-1].file_id
    user.author_photo = file_id
    # keep a local copy: file_ids are bot-specific and photos set via a
    # mirror can not be sent by the main bot (and vice versa)
    try:
        os.makedirs(config.storage_dir, exist_ok=True)
        path = os.path.join(config.storage_dir, f"avatar_{uuid.uuid4().hex}.jpg")
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=path)
        user.author_photo_path = path
    except Exception:
        pass
    await session.commit()
    await state.clear()
    await message.answer(t(lang, "saved"))


@router.message(ProfileStates.set_description, F.text)
async def set_description(message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str):
    user.author_description = message.text[:500]
    await session.commit()
    await state.clear()
    await message.answer(t(lang, "saved"))


@router.message(ProfileStates.withdraw, F.text)
async def withdraw(
    message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str, bot: Bot
):
    session.add(Withdrawal(user_id=user.id, amount=user.author_earned, details=message.text[:1000]))
    await session.commit()
    await state.clear()
    await message.answer(t(lang, "withdraw_sent"), reply_markup=main_menu(lang))
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"💸 Заявка на вывод от @{user.username or user.tg_id} "
                f"(заработано {user.author_earned} 🪙):\n{message.text[:1000]}",
            )
        except Exception:
            pass


# ---------- purchases ----------

@router.callback_query(F.data == "pf:purchases")
async def my_purchases(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    await cb.answer()
    purchases = (
        (
            await session.execute(
                select(Purchase)
                .where(Purchase.user_id == user.id)
                .order_by(Purchase.created_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    if not purchases:
        text = t(lang, "purchases_empty")
    else:
        text = t(lang, "purchases_title") + "\n\n" + "\n".join(
            f"• {p.created_at.strftime('%d.%m.%Y %H:%M')} — {p.description} ({p.amount_coins} 🪙)"
            for p in purchases
        )
    kb = InlineKeyboardBuilder()
    author_ids: list[int] = []
    for p in purchases:
        if p.kind == "profile" and p.target_user_id and p.target_user_id not in author_ids:
            author_ids.append(p.target_user_id)
    authors = {}
    if author_ids:
        authors = {
            a.id: a
            for a in (
                await session.execute(select(User).where(User.id.in_(author_ids[:20])))
            ).scalars()
        }
    for author_id in author_ids[:20]:
        author = authors.get(author_id)
        name = display_name(author) if author else f"#{author_id}"
        kb.button(
            text=t(lang, "btn_purchased_author", name=name),
            callback_data=f"vp:videos:{author_id}",
        )
    kb.button(text=t(lang, "btn_back"), callback_data="pf:home")
    kb.adjust(1)
    if author_ids:
        text += "\n\n" + t(lang, "purchases_hint")
    await smart_edit(cb.message, text, reply_markup=kb.as_markup())
