import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

import aiohttp
from sqlalchemy import select

from config import config
from bot.db.base import SessionMaker
from bot.db.models import Payment, Purchase, User
from bot.locales.texts import t

log = logging.getLogger(__name__)

API_URL = "https://api.yookassa.ru/v3/payments"


def _auth() -> aiohttp.BasicAuth:
    return aiohttp.BasicAuth(config.yookassa_shop_id, config.yookassa_secret_key)


async def create_payment(amount_rub: float, description: str, metadata: dict) -> tuple[str | None, str | None]:
    """Creates a YooKassa payment. Returns (payment_id, confirmation_url)."""
    body: dict = {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": config.yookassa_return_url},
        "capture": True,
        "description": description,
        "metadata": {k: str(v) for k, v in metadata.items()},
    }
    if config.yookassa_receipt_email:
        body["receipt"] = {
            "customer": {"email": config.yookassa_receipt_email},
            "items": [
                {
                    "description": description[:128],
                    "quantity": "1.00",
                    "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                    "vat_code": 1,
                }
            ],
        }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_URL,
                json=body,
                auth=_auth(),
                headers={
                    "Content-Type": "application/json",
                    "Idempotence-Key": str(uuid.uuid4()),
                },
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                result = await resp.json()
                if resp.status in (200, 201):
                    return result.get("id"), result.get("confirmation", {}).get(
                        "confirmation_url"
                    )
                log.error("YooKassa create error %s: %s", resp.status, result)
    except Exception:
        log.exception("YooKassa create request failed")
    return None, None


async def get_status(payment_id: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/{payment_id}",
                auth=_auth(),
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return None
                return (await resp.json()).get("status")
    except Exception:
        log.exception("YooKassa status request failed")
        return None


async def _credit(payment: Payment) -> None:
    """Credits coins for a paid YooKassa payment and notifies the buyer."""
    from bot.services import mirrors as mirrors_service

    async with SessionMaker() as session:
        fresh = await session.get(Payment, payment.id)
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
                    description=f"ЮKassa: +{fresh.coins}",
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
            log.warning("Cannot notify user %s about YooKassa payment", user.tg_id)


async def check_payment(payment: Payment) -> bool:
    """Polls one payment; credits coins when it is paid. Returns True when paid."""
    status = await get_status(payment.external_id)
    if status == "succeeded":
        await _credit(payment)
        return True
    if status in ("canceled", "cancelled"):
        async with SessionMaker() as session:
            fresh = await session.get(Payment, payment.id)
            if fresh and fresh.status == "pending":
                fresh.status = "rejected"
                await session.commit()
    return False


async def payment_watcher() -> None:
    """Background loop: credits paid YooKassa invoices, expires stale ones."""
    if not config.yookassa_enabled:
        log.info("YooKassa is not configured, watcher disabled")
        return
    ttl = timedelta(minutes=config.yookassa_payment_ttl_min)
    while True:
        try:
            async with SessionMaker() as session:
                pending = (
                    (
                        await session.execute(
                            select(Payment).where(
                                Payment.status == "pending",
                                Payment.method == "yookassa",
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
                await check_payment(payment)
        except Exception:
            log.exception("YooKassa watcher iteration failed")
        await asyncio.sleep(config.yookassa_poll_interval)
