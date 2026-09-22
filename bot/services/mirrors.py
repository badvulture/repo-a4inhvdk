import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from bot.db import mirror_store
from bot.db.mirror_store import MirrorRecord
from bot.services.premium_emoji import PremiumEmojiMiddleware

log = logging.getLogger(__name__)


class MirrorManager:
    """Runs mirror bots as polling tasks inside the main process (Redis-backed).

    All mirrors share the single main Dispatcher (routers can only be attached
    to one dispatcher), each mirror gets its own polling task.
    """

    def __init__(self, dp: Dispatcher):
        self.dp = dp
        self.tasks: dict[int, asyncio.Task] = {}
        self.bots: dict[int, Bot] = {}

    def bots_by_id(self) -> dict[int, Bot]:
        return {b.id: b for b in self.bots.values()}

    async def start_mirror(self, mirror: MirrorRecord) -> str | None:
        """Validate the token, spawn polling. Returns bot username or None."""
        try:
            bot = Bot(
                token=mirror.token,
                default=DefaultBotProperties(
                    parse_mode=ParseMode.HTML,
                    link_preview_is_disabled=config.disable_link_preview,
                ),
            )
            if mirror.is_premium:
                bot.session.middleware(PremiumEmojiMiddleware())
        except Exception:
            return None
        try:
            me = await bot.get_me()
        except Exception:
            await bot.session.close()
            return None
        task = asyncio.create_task(self._poll(bot, mirror.id))
        self.tasks[mirror.id] = task
        self.bots[mirror.id] = bot
        return me.username

    async def _poll(self, bot: Bot, mirror_id: int):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await self.dp._polling(bot, mirror_id=mirror_id)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Mirror %s polling crashed", mirror_id)
        finally:
            await bot.session.close()

    async def stop_mirror(self, mirror_id: int):
        task = self.tasks.pop(mirror_id, None)
        self.bots.pop(mirror_id, None)
        if task:
            task.cancel()

    async def token_status(self, token: str) -> str:
        """Returns 'ok', 'unauthorized', 'frozen', 'banned' or 'webhook_active'.

        Uses the full three-step check from MirrorManagerService.
        """
        from bot.services.mirror_manager import mirror_manager_service

        is_valid, _, error_type = (
            await mirror_manager_service.validate_token_with_detailed_errors(token)
        )
        if is_valid:
            return "ok"
        return error_type or "unauthorized"

    async def clean_invalid(self) -> list[str]:
        """Deactivates mirrors with dead tokens. Returns removed usernames."""
        removed: list[str] = []
        for m in await mirror_store.active_mirrors():
            status = await self.token_status(m.token)
            if status != "ok":
                m.is_active = False
                await mirror_store.save(m)
                removed.append(f"@{m.bot_username} ({status})")
                await self.stop_mirror(m.id)
                log.warning("Mirror @%s deactivated: %s", m.bot_username, status)
            await asyncio.sleep(0.3)
        return removed

    async def first_mirror_loop(self, interval: int = 60):
        """Every 60s validates the oldest active mirror; deactivates it on any error."""
        while True:
            await asyncio.sleep(interval)
            try:
                mirrors = await mirror_store.active_mirrors()
                if not mirrors:
                    continue
                m = mirrors[0]
                status = await self.token_status(m.token)
                if status != "ok":
                    m.is_active = False
                    await mirror_store.save(m)
                    await self.stop_mirror(m.id)
                    log.warning(
                        "First mirror @%s deactivated by 60s check: %s",
                        m.bot_username,
                        status,
                    )
            except Exception:
                log.exception("First-mirror check failed")

    async def cleaner_loop(self, interval: int = 7200):
        while True:
            try:
                await self.clean_invalid()
            except Exception:
                log.exception("Mirror cleaner failed")
            await asyncio.sleep(interval)

    async def start_all(self):
        await mirror_store.migrate_from_postgres()
        for m in await mirror_store.active_mirrors():
            username = await self.start_mirror(m)
            if username is None:
                log.warning("Mirror %s has an invalid token, skipping", m.id)
            elif username != m.bot_username:
                m.bot_username = username
                await mirror_store.save(m)


mirror_manager: MirrorManager | None = None
main_bot: Bot | None = None
