"""Telethon cleaner: checks mirror bots from real accounts and removes dead ones.

Ported from the shop bot's telethon_cleaner.py; the mirrors come from Redis
(bot/db/mirror_store.py) and all settings live in config.py.
"""

import asyncio
import logging
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import (
    AuthKeyInvalidError,
    AuthKeyUnregisteredError,
    PhoneNumberBannedError,
    SessionRevokedError,
    UserDeactivatedBanError,
)

from bot.db import mirror_store
from bot.db.mirror_store import MirrorRecord
from config import config

logger = logging.getLogger(__name__)
logging.getLogger("telethon").setLevel(logging.WARNING)

# Фразы, по которым видно забаненного бота
BANNED_PHRASES = (
    "violates the telegram terms of service",
    "couldn't be displayed",
    "can’t be displayed",
    "этот бот недоступен",
    "нарушал правила",
)


class TelethonCleaner:
    def __init__(self):
        self.sessions: list[str] = self._load_sessions()
        self.cooldown: dict[str, datetime] = {}
        # Счётчик жалоб в оперативной памяти: bot_username -> count
        self.complaints: dict[str, int] = {}

    # ============= СЕССИИ =============

    def _load_sessions(self) -> list[str]:
        sessions_dir = config.sessions_dir
        sessions: list[str] = []
        if not os.path.exists(sessions_dir):
            os.makedirs(sessions_dir, exist_ok=True)
            logger.warning("❌ Папка сессий создана: %s", sessions_dir)
            return sessions
        for file in os.listdir(sessions_dir):
            if file.endswith(".session"):
                sessions.append(os.path.join(sessions_dir, file))
        if not sessions:
            logger.error("❌ Нет сессий в %s", sessions_dir)
        return sessions

    def _is_cooldown(self, session_path: str) -> bool:
        if session_path not in self.cooldown:
            return False
        if datetime.now() > self.cooldown[session_path]:
            del self.cooldown[session_path]
            return False
        return True

    def _client(self, session_path: str) -> TelegramClient:
        proxy = config.proxy_tuple if config.proxy_enabled else None
        return TelegramClient(
            session_path, config.telethon_api_id, config.telethon_api_hash, proxy=proxy
        )

    # ============= ЗЕРКАЛА =============

    async def _load_mirrors(self) -> list[MirrorRecord]:
        try:
            mirrors = await mirror_store.active_mirrors()
            if not mirrors:
                logger.warning("⚠️ Нет активных зеркал")
            return mirrors
        except Exception as e:
            logger.error("❌ Ошибка загрузки зеркал: %s", e)
            return []

    async def _rename_bot_via_token(
        self, bot_username: str, token: str, new_name: str
    ) -> bool:
        if not token:
            return False
        try:
            url = f"https://api.telegram.org/bot{token}/setMyName"
            payload = {"name": new_name, "language_code": "ru"}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            return True
                        error_desc = data.get("description", "Unknown error")
                        if (
                            "FLOOD" not in error_desc
                            and "frozen" not in error_desc.lower()
                        ):
                            logger.error(
                                "❌ Ошибка API @%s: %s", bot_username, error_desc
                            )
                        return False
                    logger.error(
                        "❌ HTTP ошибка %s @%s", response.status, bot_username
                    )
                    return False
        except Exception as e:
            error_str = str(e).upper()
            if all(x not in error_str for x in ("UNAUTHORIZED", "FROZEN", "FLOOD")):
                logger.error("❌ Ошибка переименования @%s: %s", bot_username, e)
            return False

    async def _rename_and_remove_bot(self, mirror: MirrorRecord) -> bool:
        username = mirror.bot_username or str(mirror.id)
        if mirror.token:
            await self._rename_bot_via_token(
                username, mirror.token, f"🤖NEW BOT: {config.backup_bot_url}"
            )
        self.complaints.pop(username, None)
        return await self._remove_mirror(mirror)

    async def _remove_mirror(self, mirror: MirrorRecord) -> bool:
        try:
            from bot.services import mirrors as mirrors_service

            if mirrors_service.mirror_manager is not None:
                await mirrors_service.mirror_manager.stop_mirror(mirror.id)
            await mirror_store.delete(mirror.id)
            return True
        except Exception as e:
            logger.error("❌ Ошибка удаления зеркала: %s", e)
            return False

    # ============= ПРОВЕРКА БОТА =============

    async def _check_bot(self, bot_username: str, session_path: str) -> bool | None:
        """True — бот жив, False — забанен, None — проверить не удалось."""
        if self._is_cooldown(session_path):
            return None

        client = None
        try:
            client = self._client(session_path)
            await client.connect()
            if not await client.is_user_authorized():
                return None
            entity = await client.get_entity(bot_username)
            await client.send_message(entity, "/start")
            await asyncio.sleep(config.telethon_timeout_response)
            messages = await client.get_messages(entity, limit=1)
            if not messages:
                return True
            text = messages[0].text or ""
            if any(phrase in text.lower() for phrase in BANNED_PHRASES):
                logger.warning("🛑 Бан: @%s", bot_username)
                return False
            try:
                await client.delete_dialog(entity)
            except Exception:
                pass
            return True
        except FloodWaitError as e:
            logger.warning(
                "🌊 Флуд: %s ждать %sс", os.path.basename(session_path), e.seconds
            )
            self.cooldown[session_path] = datetime.now() + timedelta(seconds=e.seconds)
            return None
        except (
            SessionRevokedError,
            PhoneNumberBannedError,
            UserDeactivatedBanError,
            AuthKeyInvalidError,
            AuthKeyUnregisteredError,
        ):
            logger.warning("💀 Сессия умерла: %s", os.path.basename(session_path))
            try:
                if os.path.exists(session_path):
                    os.remove(session_path)
            except Exception:
                pass
            return None
        except Exception:
            return None
        finally:
            if client and client.is_connected():
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def _check_bot_with_retry(self, bot_username: str) -> bool:
        """Проверяет бота с повторными попытками.

        Если после MAX_RETRIES попыток проверить не удалось — считаем мёртвым.
        """
        if not self.sessions:
            logger.error("❌ Нет сессий для проверки @%s", bot_username)
            return True  # системная проблема, зеркало не трогаем

        retries = config.telethon_max_retries
        for attempt in range(retries):
            any_session_checked = False

            for session_path in self.sessions:
                if self._is_cooldown(session_path):
                    continue
                any_session_checked = True
                result = await self._check_bot(bot_username, session_path)
                if result is False:
                    return False
                if result is True:
                    return True

            if not any_session_checked:
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                    continue
                logger.warning(
                    "🚨 Все сессии в кулдауне после %s попыток для @%s - УДАЛЯЮ",
                    retries,
                    bot_username,
                )
                return False

            if attempt < retries - 1:
                await asyncio.sleep(2)

        logger.warning(
            "🚨 Не удалось проверить @%s после %s попыток - УДАЛЯЮ", bot_username, retries
        )
        return False

    # ============= ЧИСТКА СЕССИЙ =============

    async def _check_single_session(self, session_path: str) -> bool:
        client = None
        try:
            client = self._client(session_path)
            await client.connect()
            if not await client.is_user_authorized():
                return False
            await client.get_me()
            return True
        except Exception:
            return False
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def _rename_sessions_sequential(self):
        sessions_dir = config.sessions_dir
        session_files = list(Path(sessions_dir).glob("premium*.session"))

        numbers = []
        for f in session_files:
            match = re.search(r"premium(\d+)\.session", f.name)
            if match:
                numbers.append(int(match.group(1)))
        if not numbers:
            return
        numbers.sort()

        for new_index, old_num in enumerate(numbers, 1):
            old_name = f"premium{old_num}.session"
            new_name = f"premium{new_index}.session"
            old_path = os.path.join(sessions_dir, old_name)
            new_path = os.path.join(sessions_dir, new_name)
            if old_name != new_name and os.path.exists(old_path):
                os.rename(old_path, new_path)
                logger.info("🔄 Переименована сессия: %s → %s", old_name, new_name)

    async def cleanup_invalid_sessions(self):
        sessions_dir = config.sessions_dir
        if not os.path.exists(sessions_dir):
            os.makedirs(sessions_dir, exist_ok=True)
            return

        session_files = list(Path(sessions_dir).glob("premium*.session"))
        if not session_files:
            return

        alive, dead = [], []
        for session_file in session_files:
            session_path = str(session_file).replace(".session", "")
            if await self._check_single_session(session_path):
                alive.append(session_file)
            else:
                dead.append(session_file)

        for session_file in dead:
            try:
                os.remove(session_file)
                logger.info("🗑️ Удалена мёртвая сессия: %s", session_file.name)
            except Exception as e:
                logger.error("❌ Ошибка при удалении %s: %s", session_file.name, e)

        if alive:
            await self._rename_sessions_sequential()
            self.sessions = self._load_sessions()

        for json_file in Path(sessions_dir).glob("*.json"):
            if "premium" in str(json_file):
                try:
                    os.remove(json_file)
                except Exception:
                    pass

    # ============= ОСНОВНАЯ ЧИСТКА =============

    async def clean_once(self):
        mirrors = await self._load_mirrors()
        if not mirrors:
            return
        if not self.sessions:
            logger.error("❌ Нет сессий для проверки")
            return

        removed = 0
        for i, mirror in enumerate(mirrors):
            username = mirror.bot_username
            if not username:
                continue
            if not await self._check_bot_with_retry(username):
                if await self._rename_and_remove_bot(mirror):
                    removed += 1
            if i < len(mirrors) - 1:
                await asyncio.sleep(
                    random.uniform(*config.telethon_delay_between_checks)
                )

        if removed:
            logger.info("🗑️ Удалено зеркал: %s", removed)

    # ============= ЖАЛОБЫ =============

    async def add_complaint(self, bot_username: str) -> dict:
        """Добавляет жалобу на бота; при достижении порога зеркало удаляется."""
        mirror = await mirror_store.by_username(bot_username)
        if mirror is None or not mirror.is_active:
            return {"exists": False, "complaints": 0, "removed": False}

        current = self.complaints.get(bot_username, 0) + 1
        self.complaints[bot_username] = current
        logger.info(
            "📊 Жалоба на @%s: %s/%s", bot_username, current, config.complaint_threshold
        )

        if current >= config.complaint_threshold:
            logger.warning(
                "🚨 Бот @%s получил %s жалоб - УДАЛЯЮ!", bot_username, current
            )
            await self._rename_and_remove_bot(mirror)
            return {"exists": True, "complaints": current, "removed": True}

        return {"exists": True, "complaints": current, "removed": False}

    async def get_complaints(self, bot_username: str) -> int:
        return self.complaints.get(bot_username, 0)

    async def reset_complaints(self, bot_username: str):
        if bot_username in self.complaints:
            del self.complaints[bot_username]
            logger.info("🔄 Сброшен счётчик жалоб для @%s", bot_username)

    # ============= ПЛАНИРОВЩИК =============

    async def check_first_mirror_periodically(self, interval: int = 60):
        """Проверяет ПЕРВОЕ зеркало каждые 60 секунд через Telethon."""
        logger.info(
            "🔄 Запущена периодическая проверка ПЕРВОГО зеркала через Telethon (каждые %ss)",
            interval,
        )
        while True:
            try:
                await asyncio.sleep(interval)
                mirrors = await mirror_store.active_mirrors()
                if not mirrors:
                    continue
                mirror = mirrors[0]
                username = mirror.bot_username
                if not username:
                    continue
                if not await self._check_bot_with_retry(username):
                    logger.warning(
                        "🚨 Первое зеркало @%s невалидно (Telethon) - УДАЛЯЮ", username
                    )
                    await self._rename_and_remove_bot(mirror)
            except Exception as e:
                logger.error(
                    "❌ Ошибка в ежеминутной проверке первого зеркала (Telethon): %s", e
                )
                await asyncio.sleep(5)

    async def start_scheduler(self):
        logger.info("🧹 Запуск очистки нерабочих сессий...")
        await self.cleanup_invalid_sessions()
        logger.info("✅ Очистка сессий завершена")

        await asyncio.sleep(10)

        await asyncio.gather(
            self._main_check_loop(),
            self.check_first_mirror_periodically(),
        )

    async def _main_check_loop(self):
        """Основной цикл проверки всех ботов (каждые 2 часа)."""
        while True:
            try:
                await self.clean_once()
            except Exception as e:
                logger.error("❌ Ошибка в основной проверке: %s", e)
            await asyncio.sleep(config.telethon_check_interval)


telethon_cleaner = TelethonCleaner()
