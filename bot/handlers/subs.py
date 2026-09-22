from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Purchase, SubscriptionTier, User
from bot.db.repo import get_setting
from bot.keyboards import smart_edit
from bot.locales.texts import btn_variants, t

router = Router()

TIERS = {
    "a": ("sub_a_plus", SubscriptionTier.A_PLUS, "А+"),
    "app": ("sub_a_plus_plus", SubscriptionTier.A_PLUS_PLUS, "A++"),
    "premium": ("sub_premium", SubscriptionTier.PREMIUM, "⭐️ PREMIUM"),
}


@router.message(Command("sub"))
@router.message(F.text.in_(btn_variants("btn_buy_sub")))
async def subs_menu(message: Message, session: AsyncSession, lang: str):
    a = await get_setting(session, "sub_a_plus")
    app = await get_setting(session, "sub_a_plus_plus")
    p = await get_setting(session, "sub_premium")
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_sub_a", price=a["price"]), callback_data="sub:a")
    kb.button(text=t(lang, "btn_sub_app", price=app["price"]), callback_data="sub:app")
    kb.button(text=t(lang, "btn_sub_premium", price=p["price"]), callback_data="sub:premium")
    kb.adjust(1)
    await message.answer(
        t(
            lang,
            "subs_menu",
            a_limit=a["daily_limit"],
            a_days=a["days"],
            a_price=a["price"],
            app_days=app["days"],
            app_price=app["price"],
            p_price=p["price"],
        ),
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("sub:"))
async def buy_sub(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    key = cb.data.split(":")[1]
    if key not in TIERS:
        await cb.answer()
        return
    setting_key, tier, name = TIERS[key]
    cfg = await get_setting(session, setting_key)
    price = int(cfg["price"])
    if user.balance < price:
        await cb.answer(t(lang, "no_balance"), show_alert=True)
        return
    user.balance -= price
    user.subscription = tier
    days = int(cfg["days"])
    user.subscription_until = (datetime.utcnow() + timedelta(days=days)) if days else None
    session.add(
        Purchase(
            user_id=user.id,
            kind="subscription",
            description=f"Подписка {name}",
            amount_coins=price,
        )
    )
    await session.commit()
    await smart_edit(cb.message, t(lang, "sub_bought", tier=name))
    await cb.answer()
