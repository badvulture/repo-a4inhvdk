from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy import select

from config import config
from bot.db.base import SessionMaker
from bot.db.models import Sponsor, User
from bot.locales.texts import btn_variants, t


class ContextMiddleware(BaseMiddleware):
    """Opens a DB session, upserts the user, injects lang/user/session."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        async with SessionMaker() as session:
            data["session"] = session
            user = None
            if tg_user and not tg_user.is_bot:
                user = (
                    await session.execute(select(User).where(User.tg_id == tg_user.id))
                ).scalar_one_or_none()
                if user is None:
                    from bot.db.repo import get_or_create_user

                    user, _ = await get_or_create_user(
                        session,
                        tg_user.id,
                        tg_user.username,
                        tg_user.full_name,
                        first_name=tg_user.first_name,
                    )
                elif (
                    tg_user.username != user.username
                    or tg_user.full_name != user.full_name
                    or tg_user.first_name != user.first_name
                ):
                    user.username = tg_user.username
                    user.full_name = tg_user.full_name
                    user.first_name = tg_user.first_name
                    await session.commit()
            data["user"] = user
            data["lang"] = user.lang if user else "ru"
            data["is_admin"] = bool(tg_user and tg_user.id in config.admin_ids)
            bot = data.get("bot")
            if user is not None and bot is not None and (
                user.last_bot_id != bot.id or not user.is_active
            ):
                user.last_bot_id = bot.id
                user.is_active = True
                await session.commit()
            if user is not None and user.is_banned and not data["is_admin"]:
                if isinstance(event, Update):
                    if event.callback_query is not None:
                        await event.callback_query.answer(
                            t(data["lang"], "banned"), show_alert=True
                        )
                    elif event.message is not None:
                        await event.message.answer(t(data["lang"], "banned"))
                return None
            return await handler(event, data)


MENU_KEYS = (
    "btn_next_circle", "btn_profile", "btn_buy", "btn_view_profiles",
    "btn_buy_sub", "btn_mirrors", "btn_lang",
)
MENU_TEXTS = {v for key in MENU_KEYS for v in btn_variants(key)}


class MenuResetMiddleware(BaseMiddleware):
    """Pressing a main-menu button always exits any FSM state (prevents 'stuck' input)."""

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]):
        if isinstance(event, Message) and event.text in MENU_TEXTS:
            state = data.get("state")
            if state is not None:
                await state.clear()
        return await handler(event, data)


class ForcedSubMiddleware(BaseMiddleware):
    """Blocks non-admins until they join all required sponsor channels."""

    async def __call__(self, handler, event: TelegramObject, data: dict[str, Any]):
        tg_user = data.get("event_from_user")
        if not tg_user or data.get("is_admin"):
            return await handler(event, data)

        msg = event.message if isinstance(event, Update) else (
            event if isinstance(event, Message) else None
        )
        cb = event.callback_query if isinstance(event, Update) else (
            event if isinstance(event, CallbackQuery) else None
        )

        # allow /start and language selection & sub-check callbacks
        if msg is not None and msg.text and msg.text.startswith("/start"):
            return await handler(event, data)
        if cb is not None and cb.data and (
            cb.data.startswith("lang:")
            or cb.data == "check_subs"
            or cb.data == "captcha:ok"
        ):
            return await handler(event, data)

        session = data["session"]
        sponsors = (
            (
                await session.execute(
                    select(Sponsor).where(Sponsor.is_active.is_(True), Sponsor.required.is_(True))
                )
            )
            .scalars()
            .all()
        )
        if not sponsors:
            return await handler(event, data)

        # membership is checked with the main bot: mirrors are usually
        # not admins of the sponsor channels
        from bot.services import mirrors as mirrors_service

        check_bot = mirrors_service.main_bot or data["bot"]
        missing = []
        for sp in sponsors:
            try:
                member = await check_bot.get_chat_member(sp.chat_id, tg_user.id)
                if member.status in ("left", "kicked"):
                    missing.append(sp)
            except Exception:
                continue
        if not missing:
            return await handler(event, data)

        from aiogram.utils.keyboard import InlineKeyboardBuilder

        lang = data.get("lang") or "ru"
        kb = InlineKeyboardBuilder()
        for sp in missing:
            kb.button(text=sp.title, url=sp.invite_link)
        kb.button(text=t(lang, "btn_check_subs"), callback_data="check_subs")
        kb.adjust(1)
        target = cb.message if cb is not None else msg
        if target is not None:
            await target.answer(t(lang, "forced_sub"), reply_markup=kb.as_markup())
        if cb is not None:
            await cb.answer()
        return None
