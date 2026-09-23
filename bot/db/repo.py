import html
import json
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Setting, User, Video, View

DEFAULT_SETTINGS: dict[str, object] = {
    # coin packs: coins -> price in RUB
    "coin_packs": {"10": 20, "50": 100, "200": 300, "500": 800, "1000": 1500},
    # subscriptions: tier -> {price (coins), days (0 = forever), daily_limit (0 = unlim)}
    "sub_a_plus": {"price": 199, "days": 7, "daily_limit": 100},
    "sub_a_plus_plus": {"price": 299, "days": 7, "daily_limit": 0},
    "sub_premium": {"price": 499, "days": 0, "daily_limit": 0},
    "view_price": 1,
    "start_balance": 5,
    "referral_reward": 2,
    "usd_rate": 0,  # 0 = fetch automatically
    "auto_delete_dislikes": 9999,  # dislikes to auto-hide a circle
    "mirror_reward": 10,  # coins for creating a mirror
    "min_withdraw_coins": 30,  # author withdrawal minimum (coins)
    "partner_min_withdraw_rub": 50,  # partner withdrawal minimum (RUB)
    "partner_reward_rub": 1,  # RUB per live referred user
    "coin_rub_buy": 2,  # 1 coin price when buying (RUB)
    "coin_rub_withdraw": 0.5,  # 1 coin rate when withdrawing (RUB)
    "recommend_every": 5,  # show a recommended sponsor every N viewed circles
}


async def get_setting(session: AsyncSession, key: str):
    row = await session.get(Setting, key)
    if row is None:
        return DEFAULT_SETTINGS.get(key)
    return json.loads(row.value)


async def set_setting(session: AsyncSession, key: str, value) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await session.commit()


def display_name(user: User) -> str:
    return html.escape(user.first_name or user.full_name or f"#{user.id}")


async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None = None,
    full_name: str | None = None,
    referrer_id: int | None = None,
    first_name: str | None = None,
) -> tuple[User, bool]:
    user = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    created = False
    if user is None:
        start_balance = await get_setting(session, "start_balance")
        user = User(
            tg_id=tg_id,
            username=username,
            first_name=first_name,
            full_name=full_name,
            balance=int(start_balance),
            referrer_id=referrer_id,
        )
        session.add(user)
        await session.commit()
        created = True
    elif (
        username != user.username
        or full_name != user.full_name
        or first_name != user.first_name
    ):
        user.username = username
        user.full_name = full_name
        user.first_name = first_name
        await session.commit()
    return user, created


async def reset_daily_if_needed(session: AsyncSession, user: User) -> None:
    today = date.today().isoformat()
    if user.viewed_today_date != today:
        user.viewed_today = 0
        user.viewed_today_date = today
        await session.commit()


async def random_video(session: AsyncSession, viewer_id: int | None = None) -> Video | None:
    """Random circle, preferring ones the viewer has not seen yet."""
    q = select(Video).where(Video.is_active.is_(True))
    if viewer_id is not None:
        seen = select(View.video_id).where(View.user_id == viewer_id)
        unseen = (
            await session.execute(
                q.where(Video.id.not_in(seen)).order_by(func.random()).limit(1)
            )
        ).scalar_one_or_none()
        if unseen is not None:
            return unseen
    return (
        await session.execute(q.order_by(func.random()).limit(1))
    ).scalar_one_or_none()


async def add_balance(session: AsyncSession, user_tg_id: int, amount: int) -> None:
    await session.execute(
        update(User).where(User.tg_id == user_tg_id).values(balance=User.balance + amount)
    )
    await session.commit()
