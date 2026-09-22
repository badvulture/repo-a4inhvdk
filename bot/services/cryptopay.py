import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from aiocryptopay import AioCryptoPay, Networks
from sqlalchemy import select

from config import config
from bot.db.base import SessionMaker
from bot.db.models import Payment, Purchase, User
from bot.locales.texts import t

log = logging.getLogger(__name__)

crypto = AioCryptoPay(token=config.cryptobot_token, network=Networks.MAIN_NET)


async def create_invoice(usd_amount: float, description: str):
    return await crypto.create_invoice(
        amount=usd_amount, fiat="USD", currency_type="fiat", description=description
    )


_rate_cache: dict[str, float] = {"rate": 0.0, "ts": 0.0}


async def usd_rub_rate() -> float:
    """RUB per 1 USD by the CryptoBot USDT/RUB rate, cached for 5 min."""
    if _rate_cache["rate"] and time.time() - _rate_cache["ts"] < 300:
        return _rate_cache["rate"]
    try:
        rates = await crypto.get_exchange_rates()
        for r in rates:
            if r.source == "USDT" and r.target == "RUB":
                _rate_cache.update(rate=float(r.rate), ts=time.time())
                return _rate_cache["rate"]
    except Exception:
        log.warning("CryptoBot exchange rate fetch failed")
    return _rate_cache["rate"]


async def rub_to_usd_cb(rub: float) -> float:
    """RUB -> USD at the CryptoBot rate, CBR fallback."""
    from bot.services.rates import rub_to_usd

    rate = await usd_rub_rate()
    if rate > 0:
        return round(rub / rate, 2)
    return await rub_to_usd(rub)


async def create_invoice_asset(amount: float, asset: str, description: str):
    return await crypto.create_invoice(
        amount=amount, asset=asset, description=description
    )


async def is_paid(invoice_id: int) -> bool:
    invoices = await crypto.get_invoices(invoice_ids=invoice_id)
    inv = invoices if not isinstance(invoices, list) else invoices[0]
    return inv.status == "paid"


async def _credit(payment_id: int) -> None:
    """Credits coins for a paid CryptoBot invoice and notifies the buyer."""
    from bot.services import mirrors as mirrors_service

    async with SessionMaker() as session:
        fresh = await session.get(Payment, payment_id)
        if fresh is None or fresh.status != "pending":
            return
        user = await session.get(User, fresh.user_id)
        fresh.status = "paid"
        if user is not None:
            user.balance += fresh.coins
            session.add(
                Purchase(
                    user_id=user.id,
                    kind="coins",
                    description=f"CryptoBot: +{fresh.coins}",
                    amount_coins=fresh.coins,
                )
            )
        await session.commit()
        if user is None:
            return
        bot = mirrors_service.main_bot
        if bot is None:
            return
        try:
            await bot.send_message(
                user.tg_id, t(user.lang, "payment_success", coins=fresh.coins)
            )
        except Exception:
            log.warning("Cannot notify user %s about CryptoBot payment", user.tg_id)


async def payment_watcher() -> None:
    """Background loop: auto-credits paid CryptoBot invoices, expires stale ones."""
    if not config.pay_crypto_enabled or not config.cryptobot_token:
        log.info("CryptoBot is not configured, watcher disabled")
        return
    ttl = timedelta(hours=24)
    while True:
        try:
            async with SessionMaker() as session:
                pending = (
                    (
                        await session.execute(
                            select(Payment).where(
                                Payment.status == "pending",
                                Payment.method == "cryptobot",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            for payment in pending:
                created = payment.created_at
                if created is not None:
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - created > ttl:
                        async with SessionMaker() as session:
                            fresh = await session.get(Payment, payment.id)
                            if fresh and fresh.status == "pending":
                                fresh.status = "expired"
                                await session.commit()
                        continue
                try:
                    if await is_paid(int(payment.external_id)):
                        await _credit(payment.id)
                except Exception:
                    log.warning("CryptoBot invoice %s check failed", payment.external_id)
        except Exception:
            log.exception("CryptoBot watcher iteration failed")
        await asyncio.sleep(15)
