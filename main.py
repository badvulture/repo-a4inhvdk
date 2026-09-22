import asyncio
import logging
import re

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from config import config
from bot.db.base import init_db
from bot.handlers import (
    buy,
    circles,
    mirrors,
    partner,
    profile,
    start,
    subs,
    support,
    unknown,
    view_profiles,
)
from bot.handlers.admin import panel as admin_panel
from bot.locales.texts import t
from bot.middlewares.context import (
    ContextMiddleware,
    ForcedSubMiddleware,
    MenuResetMiddleware,
)
from bot.services import cryptopay
from bot.services import mirrors as mirrors_service
from bot.services import yookassa
from bot.services.mirror_manager import mirror_manager_service
from bot.services.startup_backup import send_startup_backup
from bot.services.telethon_cleaner import telethon_cleaner
from bot.services.mirrors import MirrorManager
from bot.services.premium_emoji import PremiumEmojiMiddleware

logging.basicConfig(level=logging.INFO)


def build_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(config.redis_url)
    dp = Dispatcher(storage=storage)
    dp.update.outer_middleware(ContextMiddleware())
    dp.update.outer_middleware(ForcedSubMiddleware())
    dp.message.middleware(MenuResetMiddleware())
    dp.include_routers(
        admin_panel.router,
        start.router,
        circles.router,
        profile.router,
        buy.router,
        subs.router,
        view_profiles.router,
        mirrors.router,
        partner.router,
        support.router,
        # catch-all: must stay the last router
        unknown.router,
    )
    return dp


MENU_COMMANDS = (
    "start", "circle", "profile", "buy", "free", "ref", "sub", "profiles",
    "mirrors", "partner", "promo", "info", "lang", "support", "cancel",
)


def _bilingual(key: str) -> str:
    ru = t("ru", key)
    # the emoji already leads the RU part, drop it from the EN part
    en = re.sub(r"^\W+", "", t("en", key))
    return f"{ru} | {en}"[:256]


async def set_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command=cmd, description=_bilingual(f"cmd_{cmd}"))
        for cmd in MENU_COMMANDS
    ]
    commands.append(BotCommand(command="s", description=_bilingual("cmd_terms")))
    await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    # drop the old per-language command list so everyone sees the bilingual menu
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats(), language_code="en")


async def main():
    await init_db()

    dp = build_dispatcher()
    mirrors_service.mirror_manager = MirrorManager(dp)
    await mirrors_service.mirror_manager.start_all()
    asyncio.create_task(mirrors_service.mirror_manager.cleaner_loop())
    # Bot API проверки зеркал: первое зеркало каждую минуту, все токены — раз в 20 мин
    asyncio.create_task(mirror_manager_service.validate_first_mirror_periodically())
    asyncio.create_task(mirror_manager_service.auto_token_checker())
    # Telethon-клинер: проверка зеркал с реальных аккаунтов
    if config.telethon_cleaner_enabled:
        asyncio.create_task(telethon_cleaner.start_scheduler())
    asyncio.create_task(yookassa.payment_watcher())
    asyncio.create_task(cryptopay.payment_watcher())

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=config.disable_link_preview,
        ),
    )
    if config.main_bot_premium:
        bot.session.middleware(PremiumEmojiMiddleware())
    mirrors_service.main_bot = bot
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    asyncio.create_task(send_startup_backup(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
