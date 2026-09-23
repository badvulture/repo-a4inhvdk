import secrets
import string
from urllib.parse import quote

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db.models import Payment, SponsorReward, User, Withdrawal
from bot.db.repo import get_setting
from bot.keyboards import main_menu, smart_edit
from bot.locales.texts import t
from bot.services import mirrors as mirrors_service

router = Router()

_CODE_ALPHABET = string.ascii_letters + string.digits


class PartnerStates(StatesGroup):
    withdraw = State()


def _gen_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


async def partner_view(session: AsyncSession, user: User, lang: str, bot: Bot):
    main_bot = mirrors_service.main_bot or bot
    me = await main_bot.get_me()
    link = f"https://t.me/{me.username}?start=p_{user.partner_code}"

    ref_ids = select(User.id).where(User.referrer_id == user.tg_id)
    count = (
        await session.execute(
            select(func.count(User.id)).where(User.referrer_id == user.tg_id)
        )
    ).scalar_one()
    donates = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount_rub), 0)).where(
                Payment.status == "paid", Payment.user_id.in_(ref_ids)
            )
        )
    ).scalar_one()
    views = (
        await session.execute(
            select(func.coalesce(func.sum(User.viewed_count), 0)).where(
                User.referrer_id == user.tg_id
            )
        )
    ).scalar_one()
    sponsor_subs = (
        await session.execute(
            select(func.count(SponsorReward.id)).where(
                SponsorReward.user_id.in_(ref_ids)
            )
        )
    ).scalar_one()
    reward_rub = float(await get_setting(session, "partner_reward_rub"))

    text = t(
        lang,
        "partner_info",
        link=link,
        count=count,
        balance=f"{user.partner_balance_rub:g}",
        withdrawn=f"{user.partner_withdrawn_rub:g}",
        pending=f"{user.partner_pending_rub:g}",
        donates=donates,
        views=views,
        sponsor_subs=sponsor_subs,
        reward=f"{reward_rub:g}",
    )
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(lang, "btn_share_ref"),
        url=f"https://t.me/share/url?url={quote(link, safe='')}",
    )
    kb.button(text=t(lang, "btn_partner_refresh"), callback_data="partner:refresh")
    kb.button(text=t(lang, "btn_partner_withdraw"), callback_data="partner:withdraw")
    kb.adjust(1, 2)
    return text, kb.as_markup()


@router.message(Command("partner"))
async def partner_cmd(message: Message, session: AsyncSession, user: User, lang: str, bot: Bot):
    if user.is_partner:
        text, kb = await partner_view(session, user, lang, bot)
        await message.answer(text, reply_markup=kb)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_partner_yes"), callback_data="partner:join")
    kb.button(text=t(lang, "btn_partner_no"), callback_data="partner:no")
    kb.adjust(2)
    await message.answer(t(lang, "partner_ask"), reply_markup=kb.as_markup())


@router.callback_query(F.data == "partner:join")
async def partner_join(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    user.is_partner = True
    if not user.partner_code:
        user.partner_code = _gen_code()
    await session.commit()
    text, kb = await partner_view(session, user, lang, cb.message.bot)
    await smart_edit(cb.message, t(lang, "partner_joined") + "\n\n" + text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "partner:no")
async def partner_no(cb: CallbackQuery, lang: str):
    await cb.message.delete()
    await cb.answer(t(lang, "cancelled"))


@router.callback_query(F.data == "partner:refresh")
async def partner_refresh(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    text, kb = await partner_view(session, user, lang, cb.message.bot)
    try:
        await smart_edit(cb.message, text, reply_markup=kb)
    except Exception:
        pass
    await cb.answer("🔄")


@router.callback_query(F.data == "partner:withdraw")
async def partner_withdraw_start(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, lang: str
):
    min_rub = int(await get_setting(session, "partner_min_withdraw_rub"))
    if user.partner_balance_rub < min_rub:
        await cb.answer(
            t(
                lang,
                "partner_withdraw_min",
                min_rub=min_rub,
                rub=f"{user.partner_balance_rub:g}",
            ),
            show_alert=True,
        )
        return
    await state.set_state(PartnerStates.withdraw)
    await cb.message.answer(
        t(lang, "partner_withdraw_prompt", rub=f"{user.partner_balance_rub:g}")
    )
    await cb.answer()


@router.message(PartnerStates.withdraw, F.text)
async def partner_withdraw(
    message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str, bot: Bot
):
    rub = int(user.partner_balance_rub)
    details = f"[PARTNER {rub} ₽] {message.text[:900]}"
    session.add(Withdrawal(user_id=user.id, amount=rub, details=details))
    user.partner_pending_rub += rub
    user.partner_balance_rub -= rub
    await session.commit()
    await state.clear()
    await message.answer(t(lang, "withdraw_sent"), reply_markup=main_menu(lang))
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"💸 Партнёрский вывод от @{user.username or user.tg_id}:\n{details}",
            )
        except Exception:
            pass
