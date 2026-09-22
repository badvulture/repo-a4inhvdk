import logging
import secrets

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    KeyboardButtonRequestManagedBot,
    ManagedBotUpdated,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db import mirror_store
from bot.db.models import User
from bot.db.repo import get_setting
from bot.keyboards import back_kb, main_menu, smart_edit
from bot.locales.texts import btn_variants, t
from bot.services import mirrors as mirrors_service

log = logging.getLogger(__name__)

router = Router()


class MirrorStates(StatesGroup):
    premium = State()


_USERNAME_WORDS = [
    "shop", "droog", "snook", "moon", "pixel", "nova", "frog", "zen",
    "byte", "cloud", "star", "echo", "luna", "vibe", "spark", "neo",
    "flux", "orbit", "mint", "fox", "wolf", "bear", "owl", "kit",
    "ring", "wave", "sky", "sun", "glow", "ace", "bolt", "dash",
    "ember", "frost", "gem", "hawk", "iris", "jade", "kite", "leaf",
]


def _gen_username() -> str:
    words = [secrets.choice(_USERNAME_WORDS) for _ in range(secrets.choice((2, 3)))]
    base = words[0] + "".join(w.capitalize() for w in words[1:])
    if len(base) < 8:
        base += f"{secrets.randbelow(100):02d}"
    return f"{base}_bot"


def _one_click_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[
            KeyboardButton(
                text=t(lang, "btn_create_bot_1click"),
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    request_id=1,
                    suggested_name="☀️CIRCLES",
                    suggested_username=_gen_username(),
                ),
            )
        ]],
    )


async def mirrors_kb_text(session: AsyncSession, user: User, lang: str):
    my = await mirror_store.by_owner(user.id)
    reward = int(await get_setting(session, "mirror_reward"))
    eligible = not user.mirror_rewarded and not my
    kb = InlineKeyboardBuilder()
    if eligible:
        kb.button(
            text=t(lang, "btn_add_mirror_reward", reward=reward), callback_data="mir:add"
        )
    else:
        kb.button(text=t(lang, "btn_add_mirror"), callback_data="mir:add")
    for m in my:
        kb.button(text=f"🗑 @{m.bot_username or m.id}", callback_data=f"mir:del:{m.id}")
    kb.adjust(1)
    return t(lang, "mirrors_menu", count=len(my), reward=reward), kb.as_markup()


@router.message(Command("mirrors"))
@router.message(F.text.in_(btn_variants("btn_mirrors")))
async def mirrors_menu(message: Message, session: AsyncSession, user: User, lang: str):
    text, kb = await mirrors_kb_text(session, user, lang)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "mir:menu")
async def mirrors_menu_cb(cb: CallbackQuery, session: AsyncSession, user: User, lang: str, state: FSMContext):
    await state.clear()
    text, kb = await mirrors_kb_text(session, user, lang)
    await smart_edit(cb.message, text, reply_markup=kb)
    await cb.message.answer(t(lang, "menu_restored"), reply_markup=main_menu(lang))
    await cb.answer()


@router.callback_query(F.data == "mir:add")
async def mirror_add(cb: CallbackQuery, session: AsyncSession, state: FSMContext, lang: str, user: User):
    if len(await mirror_store.by_owner(user.id)) >= config.max_mirrors_per_user:
        await smart_edit(
            cb.message,
            t(lang, "mirror_limit", max=config.max_mirrors_per_user),
            reply_markup=back_kb(lang, "mir:menu"),
        )
        await cb.answer()
        return
    reward = int(await get_setting(session, "mirror_reward"))
    await smart_edit(
        cb.message,
        t(lang, "mirror_1click_prompt", reward=reward),
        reply_markup=back_kb(lang, "mir:menu"),
    )
    await cb.answer()
    await cb.message.answer(
        t(lang, "mirror_1click_hint"),
        reply_markup=_one_click_kb(lang),
    )


async def _ask_premium(
    message: Message, state: FSMContext, lang: str, token: str, manager,
):
    existing = await mirror_store.by_token(token)
    if existing and existing.is_active and existing.id in manager.tasks:
        await message.answer(t(lang, "mirror_exists"))
        return

    await state.update_data(token=token)
    await state.set_state(MirrorStates.premium)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_mirror_premium"), callback_data="mir:prem:1")
    kb.button(text=t(lang, "btn_mirror_regular"), callback_data="mir:prem:0")
    kb.button(text=t(lang, "btn_back"), callback_data="mir:menu")
    kb.adjust(1)
    await message.answer(t(lang, "mirror_premium_prompt"), reply_markup=kb.as_markup())


@router.message(F.managed_bot_created)
async def mirror_managed_created(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, lang: str, bot: Bot,
):
    manager = mirrors_service.mirror_manager
    if manager is None:
        await message.answer(t(lang, "mirror_invalid"), reply_markup=main_menu(lang))
        return
    bot_user = message.managed_bot_created.bot_user
    try:
        token = await bot.get_managed_bot_token(user_id=bot_user.id)
    except Exception:
        await message.answer(
            t(lang, "mirror_token_fetch_failed"), reply_markup=main_menu(lang)
        )
        return
    await message.answer(
        t(lang, "mirror_bot_created", username=bot_user.username or bot_user.id),
        reply_markup=main_menu(lang),
    )
    if len(await mirror_store.by_owner(user.id)) >= config.max_mirrors_per_user:
        await message.answer(
            t(lang, "mirror_limit", max=config.max_mirrors_per_user)
        )
        return
    await _ask_premium(message, state, lang, token, manager)


@router.managed_bot()
async def mirror_managed_updated(event: ManagedBotUpdated, bot: Bot):
    manager = mirrors_service.mirror_manager
    mirror = await mirror_store.by_bot_id(event.bot_user.id)
    if mirror is None or manager is None:
        return
    try:
        token = await bot.get_managed_bot_token(user_id=event.bot_user.id)
    except Exception:
        log.exception("Failed to fetch managed bot token for %s", event.bot_user.id)
        return
    if token != mirror.token:
        await manager.stop_mirror(mirror.id)
        mirror.token = token
        await mirror_store.save(mirror)
        await manager.start_mirror(mirror)


@router.callback_query(MirrorStates.premium, F.data.startswith("mir:prem:"))
async def mirror_premium_choice(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, lang: str
):
    is_premium = cb.data.split(":")[2] == "1"
    data = await state.get_data()
    token = data.get("token")
    manager = mirrors_service.mirror_manager
    if not token or manager is None:
        await state.clear()
        await cb.answer()
        return

    my_mirrors = await mirror_store.by_owner(user.id)
    had_mirrors = bool(my_mirrors)
    existing = await mirror_store.by_token(token)
    if (existing is None or existing.owner_id != user.id) and len(my_mirrors) >= config.max_mirrors_per_user:
        await smart_edit(
            cb.message,
            t(lang, "mirror_limit", max=config.max_mirrors_per_user),
            reply_markup=back_kb(lang, "mir:menu"),
        )
        await cb.answer()
        return
    if existing:
        # re-activate a previously added/stopped mirror
        await manager.stop_mirror(existing.id)
        existing.owner_id = user.id
        existing.is_active = True
        existing.is_premium = is_premium
        mirror = await mirror_store.save(existing)
    else:
        mirror = await mirror_store.create(user.id, token, is_premium)

    username = await manager.start_mirror(mirror)
    if username is None:
        if existing is None:
            await mirror_store.delete(mirror.id)
        else:
            mirror.is_active = False
            await mirror_store.save(mirror)
        await smart_edit(cb.message, t(lang, "mirror_invalid"))
        await cb.answer()
        return
    mirror.bot_username = username
    await mirror_store.save(mirror)

    reward = int(await get_setting(session, "mirror_reward"))
    rewarded = (
        existing is None
        and reward
        and not user.mirror_rewarded
        and not had_mirrors
    )
    if rewarded:
        user.balance += reward
        user.mirror_rewarded = True
    await session.commit()
    await state.clear()
    text = t(lang, "mirror_created", username=username)
    if rewarded:
        text += "\n" + t(lang, "mirror_reward", reward=reward, balance=user.balance)
    await smart_edit(cb.message, text)
    await cb.answer()


@router.callback_query(F.data.startswith("mir:del:"))
async def mirror_delete(cb: CallbackQuery, session: AsyncSession, user: User, lang: str, is_admin: bool):
    mirror = await mirror_store.get(int(cb.data.split(":")[2]))
    if mirror is None or (mirror.owner_id != user.id and not is_admin):
        await cb.answer()
        return
    mirror.is_active = False
    await mirror_store.save(mirror)
    if mirrors_service.mirror_manager:
        await mirrors_service.mirror_manager.stop_mirror(mirror.id)
    await cb.answer(t(lang, "mirror_deleted"), show_alert=True)
    await cb.message.delete()
