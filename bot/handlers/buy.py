import math
import secrets
import string
from urllib.parse import quote

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db.models import Payment, Purchase, Sponsor, SponsorReward, User
from bot.db.repo import get_setting
from bot.keyboards import smart_edit
from bot.locales.texts import btn_variants, t
from bot.services import cryptopay, yookassa
from bot.services import mirrors as mirrors_service
from bot.services.rates import format_crypto, rub_to_crypto, rub_to_usd

router = Router()

_CODE_ALPHABET = string.ascii_letters + string.digits


class BuyStates(StatesGroup):
    manual_screenshot = State()
    custom_amount = State()


MIN_CARD_RUB = 50


def custom_price_rub(coins: int) -> int:
    factor = 2.0 if coins < 150 else 1.5
    return max(1, math.ceil(coins * factor))


async def price_str(lang: str, rub: int) -> str:
    if lang == "en":
        return f"{await cryptopay.rub_to_usd_cb(rub)}$"
    return f"{rub} RUB"


RECEIPT_METHOD_LABELS = {
    "manual": "CryptoWallet 💶",
    "card": "Карта 💳",
    "sbp": "СБП 📱",
}


def buy_menu_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_buy_coins"), callback_data="buy:paid")
    kb.button(text=t(lang, "btn_free_coins"), callback_data="buy:free")
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("buy"))
@router.message(F.text.in_(btn_variants("btn_buy")))
async def buy_menu(message: Message, lang: str):
    await message.answer(t(lang, "buy_menu"), reply_markup=buy_menu_kb(lang))


@router.callback_query(F.data == "buy:menu")
async def buy_menu_cb(cb: CallbackQuery, lang: str, state: FSMContext):
    await state.clear()
    await smart_edit(cb.message, t(lang, "buy_menu"), reply_markup=buy_menu_kb(lang))
    await cb.answer()


@router.callback_query(F.data == "buy:paid")
async def buy_packs(cb: CallbackQuery, session: AsyncSession, lang: str):
    packs = await get_setting(session, "coin_packs")
    kb = InlineKeyboardBuilder()
    for coins, rub in packs.items():
        kb.button(
            text=t(lang, "pack_btn", coins=coins, price=await price_str(lang, int(rub))),
            callback_data=f"buy:pack:{coins}:{rub}",
        )
    kb.button(text=t(lang, "btn_custom_amount"), callback_data="buy:custom")
    kb.button(text=t(lang, "btn_back"), callback_data="buy:menu")
    kb.adjust(1)
    await smart_edit(cb.message, t(lang, "buy_packs"), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "buy:custom")
async def custom_amount_ask(cb: CallbackQuery, state: FSMContext, lang: str):
    await state.set_state(BuyStates.custom_amount)
    await smart_edit(cb.message, t(lang, "custom_amount_prompt"))
    await cb.answer()


@router.message(BuyStates.custom_amount)
async def custom_amount_input(message: Message, state: FSMContext, lang: str):
    try:
        coins = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(t(lang, "custom_amount_invalid"))
        return
    if coins < 10 or coins > 50000:
        await message.answer(t(lang, "custom_amount_invalid"))
        return
    await state.clear()
    rub = custom_price_rub(coins)
    text, kb = await _method_view(lang, coins, rub)
    await message.answer(text, reply_markup=kb)


async def _method_view(lang: str, coins: int | str, rub: int | str):
    coins, rub = int(coins), int(rub)
    kb = InlineKeyboardBuilder()
    if rub >= MIN_CARD_RUB:
        if config.pay_card_enabled:
            kb.button(text=t(lang, "btn_pay_card"), callback_data=f"buy:card:{coins}:{rub}")
        if config.pay_sbp_enabled and config.sbp_phone:
            kb.button(text=t(lang, "btn_pay_sbp"), callback_data=f"buy:sbp:{coins}:{rub}")
    if config.pay_crypto_enabled:
        kb.button(text=t(lang, "btn_pay_crypto"), callback_data=f"buy:crypto:{coins}:{rub}")
    if config.pay_stars_enabled:
        kb.button(text=t(lang, "btn_pay_stars"), callback_data=f"buy:stars:{coins}:{rub}")
    if config.pay_manual_enabled:
        kb.button(text=t(lang, "btn_pay_manual"), callback_data=f"buy:manual:{coins}:{rub}")
    kb.button(text=t(lang, "btn_back"), callback_data="buy:paid")
    kb.adjust(1)
    text = t(lang, "pay_method", coins=coins, price=await price_str(lang, rub))
    return text, kb.as_markup()


@router.callback_query(F.data.startswith("buy:pack:"))
async def choose_method(cb: CallbackQuery, lang: str):
    _, _, coins, rub = cb.data.split(":")
    text, kb = await _method_view(lang, coins, rub)
    await smart_edit(cb.message, text, reply_markup=kb)
    await cb.answer()


# ---------- CryptoBot ----------

@router.callback_query(F.data.startswith("buy:crypto:"))
async def pay_crypto(cb: CallbackQuery, lang: str):
    _, _, coins, rub = cb.data.split(":")
    kb = InlineKeyboardBuilder()
    for symbol in ("USDT", "TON", "BTC", "ETH"):
        kb.button(text=symbol, callback_data=f"buy:cbc:{symbol}:{coins}:{rub}")
    kb.button(text=t(lang, "btn_cancel"), callback_data=f"buy:pack:{coins}:{rub}")
    kb.adjust(2, 2, 1)
    await smart_edit(
        cb.message, t(lang, "cryptobot_currency_choice"), reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("buy:cbc:"))
async def pay_crypto_currency(
    cb: CallbackQuery, session: AsyncSession, user: User, lang: str
):
    _, _, symbol, coins, rub = cb.data.split(":")
    amount = await rub_to_crypto(int(rub), symbol)
    if amount <= 0:
        await cb.answer(
            "❌ Не удалось получить курс" if lang == "ru" else "❌ Failed to get exchange rate",
            show_alert=True,
        )
        return
    invoice = await cryptopay.create_invoice_asset(
        amount, symbol, f"{coins} coins for {user.tg_id}"
    )
    payment = Payment(
        user_id=user.id, method="cryptobot", coins=int(coins), amount_rub=int(rub),
        external_id=str(invoice.invoice_id),
    )
    session.add(payment)
    await session.commit()
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_pay_cryptobot_go"), url=invoice.bot_invoice_url)
    kb.button(text=t(lang, "btn_cancel"), callback_data="buy:paid")
    kb.adjust(1)
    await smart_edit(
        cb.message,
        t(
            lang,
            "crypto_invoice",
            coins=coins,
            amount=format_crypto(amount, symbol),
            symbol=symbol,
        ),
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("buy:check:"))
async def check_crypto(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    payment = await session.get(Payment, int(cb.data.split(":")[2]))
    if payment is None or payment.user_id != user.id or payment.status == "paid":
        await cb.answer()
        return
    if await cryptopay.is_paid(int(payment.external_id)):
        payment.status = "paid"
        user.balance += payment.coins
        session.add(Purchase(user_id=user.id, kind="coins",
                             description=f"CryptoBot: +{payment.coins}", amount_coins=payment.coins))
        await session.commit()
        await smart_edit(cb.message, t(lang, "payment_success", coins=payment.coins))
        await cb.answer()
    else:
        await cb.answer(t(lang, "payment_not_found"), show_alert=True)


# ---------- card: YooKassa (automatic) or transfer + receipt ----------

@router.callback_query(F.data.startswith("buy:card:"))
async def pay_card(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, lang: str
):
    _, _, coins, rub = cb.data.split(":")
    if config.card_payment_method == "yookassa" and config.yookassa_enabled:
        payment_id, url = await yookassa.create_payment(
            float(rub),
            f"{coins} coins for {user.tg_id}",
            {"user_id": user.tg_id, "coins": coins},
        )
        if not payment_id or not url:
            await cb.answer(t(lang, "payment_create_error"), show_alert=True)
            return
        payment = Payment(
            user_id=user.id, method="yookassa", coins=int(coins), amount_rub=int(rub),
            external_id=payment_id,
        )
        session.add(payment)
        await session.commit()
        kb = InlineKeyboardBuilder()
        kb.button(text=t(lang, "btn_pay_card_link"), url=url)
        kb.button(text=t(lang, "btn_cancel"), callback_data="buy:paid")
        kb.adjust(1)
        await smart_edit(
            cb.message,
            t(lang, "card_auto", coins=coins, price=await price_str(lang, int(rub))),
            reply_markup=kb.as_markup(),
        )
        await cb.answer()
        return
    await _card_semi(cb, lang, coins, rub)


@router.callback_query(F.data.startswith("buy:cardm:"))
async def pay_card_semi(cb: CallbackQuery, lang: str):
    _, _, coins, rub = cb.data.split(":")
    await _card_semi(cb, lang, coins, rub)


async def _card_semi(cb: CallbackQuery, lang: str, coins: str, rub: str):
    await _show_receipt_method(
        cb,
        lang,
        method="card",
        coins=int(coins),
        rub=int(rub),
        text=t(
            lang,
            "card_manual",
            coins=coins,
            price=await price_str(lang, int(rub)),
            name=cb.from_user.full_name,
            card=config.card_number,
            bank=config.card_bank or "ЮMoney",
        ),
    )


@router.callback_query(F.data.startswith("buy:ycheck:"))
async def check_yookassa(cb: CallbackQuery, session: AsyncSession, user: User, lang: str):
    payment = await session.get(Payment, int(cb.data.split(":")[2]))
    if payment is None or payment.user_id != user.id:
        await cb.answer()
        return
    if payment.status == "paid" or await yookassa.check_payment(payment):
        await session.refresh(user)
        await smart_edit(cb.message, t(lang, "payment_success", coins=payment.coins))
        await cb.answer()
        return
    await cb.answer(t(lang, "payment_not_found"), show_alert=True)


# ---------- SBP transfer + receipt ----------

@router.callback_query(F.data.startswith("buy:sbp:"))
async def pay_sbp(cb: CallbackQuery, lang: str):
    _, _, coins, rub = cb.data.split(":")
    await _show_receipt_method(
        cb,
        lang,
        method="sbp",
        coins=int(coins),
        rub=int(rub),
        text=t(
            lang,
            "sbp_manual",
            coins=coins,
            price=await price_str(lang, int(rub)),
            name=cb.from_user.full_name,
            phone=config.sbp_phone,
            bank=config.sbp_bank or "ЮMoney",
        ),
    )


async def _show_receipt_method(
    cb: CallbackQuery, lang: str, method: str, coins: int, rub: int, text: str
):
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(lang, "btn_i_paid"), callback_data=f"buy:ipaid:{method}:{coins}:{rub}"
    )
    kb.button(text=t(lang, "btn_cancel"), callback_data=f"buy:pack:{coins}:{rub}")
    kb.adjust(1)
    await smart_edit(cb.message, text, reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("buy:ipaid:"))
async def i_paid(cb: CallbackQuery, state: FSMContext, lang: str):
    _, _, method, coins, rub = cb.data.split(":")
    await state.set_state(BuyStates.manual_screenshot)
    await state.update_data(coins=int(coins), rub=int(rub), method=method)
    await smart_edit(cb.message, t(lang, "payment_photo_instruction"))
    await cb.answer()


# ---------- Telegram Stars ----------

@router.callback_query(F.data.startswith("buy:stars:"))
async def pay_stars(cb: CallbackQuery, lang: str):
    _, _, coins, rub = cb.data.split(":")
    usd = await rub_to_usd(int(rub))
    stars = max(1, math.ceil(usd / config.star_usd))
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(lang, "btn_pay_stars_go"), callback_data=f"buy:starsgo:{coins}:{rub}"
    )
    kb.button(text=t(lang, "btn_cancel"), callback_data=f"buy:pack:{coins}:{rub}")
    kb.adjust(1)
    await smart_edit(
        cb.message,
        t(lang, "stars_pay", coins=coins, price=await price_str(lang, int(rub)), stars=stars),
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("buy:starsgo:"))
async def pay_stars_go(cb: CallbackQuery, lang: str, bot: Bot):
    _, _, coins, rub = cb.data.split(":")
    usd = await rub_to_usd(int(rub))
    stars = max(1, math.ceil(usd / config.star_usd))
    await bot.send_invoice(
        chat_id=cb.message.chat.id,
        title=f"{coins} 🪙",
        description=t(lang, "pack_btn", coins=coins, price=await price_str(lang, int(rub))),
        payload=f"coins:{coins}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{coins} coins", amount=stars)],
    )
    await cb.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def stars_paid(message: Message, session: AsyncSession, user: User, lang: str):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("coins:"):
        coins = int(payload.split(":")[1])
        user.balance += coins
        session.add(Payment(user_id=user.id, method="stars", coins=coins, status="paid",
                            external_id=message.successful_payment.telegram_payment_charge_id))
        session.add(Purchase(user_id=user.id, kind="coins",
                             description=f"Stars: +{coins}", amount_coins=coins))
        await session.commit()
        await message.answer(t(lang, "payment_success", coins=coins))


# ---------- manual (screenshot to admin) ----------

@router.callback_query(F.data.startswith("buy:manual:"))
async def pay_manual(cb: CallbackQuery, lang: str):
    _, _, coins, rub = cb.data.split(":")
    rub_i = int(rub)
    usdt = format_crypto(await rub_to_crypto(rub_i, "USDT"), "USDT")
    ton = format_crypto(await rub_to_crypto(rub_i, "TON"), "TON")
    btc = format_crypto(await rub_to_crypto(rub_i, "BTC"), "BTC")
    eth = format_crypto(await rub_to_crypto(rub_i, "ETH"), "ETH")
    text = t(
        lang,
        "crypto_wallets",
        price=await price_str(lang, rub_i),
        usdt_ton_wallet=config.crypto_wallet_usdt_ton or "—",
        btc_wallet=config.crypto_wallet_btc or "—",
        eth_wallet=config.crypto_wallet_eth or "—",
        usdt=usdt,
        ton=ton,
        btc=btc,
        eth=eth,
    )
    await _show_receipt_method(
        cb, lang, method="manual", coins=int(coins), rub=int(rub), text=text
    )


@router.message(BuyStates.manual_screenshot, F.photo | F.document)
async def manual_screenshot(
    message: Message, state: FSMContext, session: AsyncSession, user: User, lang: str, bot: Bot
):
    data = await state.get_data()
    method = data.get("method", "manual")
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    payment = Payment(
        user_id=user.id, method=method, coins=data["coins"], amount_rub=data["rub"],
        screenshot_file_id=file_id,
    )
    session.add(payment)
    await session.commit()
    await state.clear()
    await message.answer(t(lang, "manual_sent"))
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=f"adm:pay:ok:{payment.id}")
    kb.button(text="❌ Отклонить", callback_data=f"adm:pay:no:{payment.id}")
    main_bot = mirrors_service.main_bot or bot
    caption = (
        f"<b>💰 Подтвердите покупку #{payment.id}.</b>\n\n"
        f"👤 Пользователь: @{user.username or user.tg_id} "
        f"{user.full_name or ''} ({user.tg_id})\n"
        f"📦 Товар: {data['coins']} 🪙\n"
        f"💰 Сумма: <b>{data['rub']} RUB</b>\n"
        f"💳 Способ оплаты: {RECEIPT_METHOD_LABELS.get(method, method)}\n\n"
        f"<b>Подтвердить выдачу товара?</b>"
    )
    for admin_id in config.admin_ids:
        try:
            await main_bot.send_photo(
                admin_id, file_id, caption=caption, reply_markup=kb.as_markup()
            )
        except Exception:
            try:
                await main_bot.send_message(admin_id, caption, reply_markup=kb.as_markup())
            except Exception:
                pass


# ---------- free: referral & sponsors ----------

def free_menu_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_ref"), callback_data="free:ref")
    kb.button(text=t(lang, "btn_sponsors"), callback_data="free:sponsors")
    kb.button(text=t(lang, "btn_back"), callback_data="buy:menu")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "buy:free")
async def free_menu(cb: CallbackQuery, lang: str):
    await smart_edit(cb.message, t(lang, "free_menu"), reply_markup=free_menu_kb(lang))
    await cb.answer()


@router.message(Command("free"))
async def free_menu_cmd(message: Message, lang: str):
    await message.answer(t(lang, "free_menu"), reply_markup=free_menu_kb(lang))


def gen_ref_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


async def _ref_view(session: AsyncSession, user: User, lang: str, bot: Bot):
    me = await bot.get_me()
    if not user.ref_code:
        user.ref_code = gen_ref_code()
        await session.commit()
    link = f"https://t.me/{me.username}?start=ref_{user.ref_code}"
    count = (
        await session.execute(
            select(func.count(User.id)).where(User.referrer_id == user.tg_id)
        )
    ).scalar_one()
    reward = int(await get_setting(session, "referral_reward"))
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(lang, "btn_share_ref"),
        url=f"https://t.me/share/url?url={quote(link, safe='')}",
    )
    kb.button(text=t(lang, "btn_back"), callback_data="buy:free")
    kb.adjust(1)
    return t(lang, "ref_text", reward=reward, link=link, count=count), kb.as_markup()


@router.callback_query(F.data == "free:ref")
async def ref_link(cb: CallbackQuery, session: AsyncSession, user: User, lang: str, bot: Bot):
    text, kb = await _ref_view(session, user, lang, bot)
    await smart_edit(cb.message, text, reply_markup=kb)
    await cb.answer()


@router.message(Command("ref"))
async def ref_link_cmd(message: Message, session: AsyncSession, user: User, lang: str, bot: Bot):
    text, kb = await _ref_view(session, user, lang, bot)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "free:sponsors")
async def sponsors_list(cb: CallbackQuery, session: AsyncSession, lang: str):
    sponsors = (
        (
            await session.execute(
                select(Sponsor).where(
                    Sponsor.is_active.is_(True), Sponsor.kind != "recommend"
                )
            )
        )
        .scalars()
        .all()
    )
    if not sponsors:
        await cb.answer(t(lang, "sponsors_empty"), show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    for sp in sponsors:
        kb.button(text=sp.title, url=sp.invite_link)
    kb.button(text=t(lang, "btn_check_subs"), callback_data="free:check")
    kb.button(text=t(lang, "btn_back"), callback_data="buy:free")
    kb.adjust(1)
    await smart_edit(cb.message, t(lang, "sponsors_text"), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "free:check")
async def sponsors_check(cb: CallbackQuery, session: AsyncSession, user: User, lang: str, bot: Bot):
    sponsors = (
        (
            await session.execute(
                select(Sponsor).where(
                    Sponsor.is_active.is_(True), Sponsor.kind != "recommend"
                )
            )
        )
        .scalars()
        .all()
    )
    earned = 0
    all_subscribed = True
    check_bot = mirrors_service.main_bot or bot
    for sp in sponsors:
        try:
            member = await check_bot.get_chat_member(sp.chat_id, user.tg_id)
            subscribed = member.status not in ("left", "kicked")
        except Exception:
            subscribed = False
        if not subscribed:
            all_subscribed = False
            continue
        already = (
            await session.execute(
                select(SponsorReward).where(
                    SponsorReward.user_id == user.id, SponsorReward.sponsor_id == sp.id
                )
            )
        ).scalar_one_or_none()
        if already is None:
            session.add(SponsorReward(user_id=user.id, sponsor_id=sp.id))
            user.balance += sp.reward_coins
            earned += sp.reward_coins
    await session.commit()
    if earned:
        await smart_edit(cb.message, t(lang, "sponsors_reward", coins=earned))
        await cb.answer()
    elif not all_subscribed:
        await cb.answer(t(lang, "sponsors_not_all"), show_alert=True)
    else:
        await cb.answer("✅")
