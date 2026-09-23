"""Mirror manager: token validation, customization, backups and auto-checks.

Ported from the shop bot's mirror_manager.py; the mirrors themselves live in
Redis (bot/db/mirror_store.py) instead of a separate PostgreSQL table.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramUnauthorizedError,
)

from bot.db import mirror_store
from bot.db.mirror_store import MirrorRecord
from config import config

logger = logging.getLogger(__name__)

BACKUP_DIR = "storage/mirror_backups"
# Порог изменения в процентах, после которого создаётся новый бэкап
BACKUP_THRESHOLD_PERCENT = 25

# Ошибки токена, при которых зеркало удаляется
FATAL_ERRORS = ("unauthorized", "conflict", "webhook_active", "banned", "frozen")


class MirrorManagerService:
    """Валидация токенов зеркал, кастомизация ботов, бэкапы и авто-проверки."""

    def __init__(self):
        self._backup_lock = asyncio.Lock()

    # ============= ВСПОМОГАТЕЛЬНОЕ =============

    def _make_bot(self, token: str) -> Bot:
        if config.proxy_enabled and config.proxy_url:
            return Bot(token=token, session=AiohttpSession(proxy=config.proxy_url))
        return Bot(token=token)

    async def _close(self, bot: Bot | None) -> None:
        if bot is None:
            return
        try:
            await bot.session.close()
        except Exception:
            pass

    # ============= БЭКАПЫ =============

    async def _create_backup(self):
        """Создаёт резервную копию зеркал с проверкой изменений."""
        async with self._backup_lock:
            try:
                os.makedirs(BACKUP_DIR, exist_ok=True)
                mirrors = await mirror_store.active_mirrors()
                current_data = {
                    "mirror_bots": {
                        (m.bot_username or str(m.id)): {
                            "token": m.token,
                            "creator_id": m.owner_id,
                            "created_date": m.created_at,
                            "is_active": m.is_active,
                            "is_premium": m.is_premium,
                        }
                        for m in mirrors
                    },
                    "backup_created": datetime.now().isoformat(),
                }

                backups = sorted(
                    f
                    for f in os.listdir(BACKUP_DIR)
                    if f.startswith("mirrors_backup_") and f.endswith(".json")
                )

                if not backups:
                    path = os.path.join(
                        BACKUP_DIR,
                        f"mirrors_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    )
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(current_data, f, ensure_ascii=False, indent=2)
                    logger.info("📦 Создан первый бэкап зеркал: %s", path)
                    return

                latest_path = os.path.join(BACKUP_DIR, backups[-1])
                with open(latest_path, encoding="utf-8") as f:
                    latest_data = json.load(f)

                current_count = len(current_data["mirror_bots"])
                latest_count = len(latest_data.get("mirror_bots", {}))

                # Критическая ситуация: зеркал нет, а в бэкапе они есть
                if current_count == 0 and latest_count > 0:
                    logger.error(
                        "🚨 КРИТИЧНО: активных зеркал 0, а в бэкапе %s!", latest_count
                    )
                    path = os.path.join(
                        BACKUP_DIR,
                        f"mirrors_emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    )
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(current_data, f, ensure_ascii=False, indent=2)
                    logger.info("🚨 Создан аварийный бэкап: %s", path)
                    return

                if latest_count > 0:
                    change_percent = (
                        abs(current_count - latest_count) / latest_count * 100
                    )
                else:
                    change_percent = 100 if current_count > 0 else 0

                if change_percent >= BACKUP_THRESHOLD_PERCENT:
                    path = os.path.join(
                        BACKUP_DIR,
                        f"mirrors_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    )
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(current_data, f, ensure_ascii=False, indent=2)
                    logger.info(
                        "📦 Создан новый бэкап: %s (изменение: %.1f%%)",
                        path,
                        change_percent,
                    )
                    # Оставляем только последние 10 бэкапов
                    if len(backups) >= 10:
                        for old in backups[:-9]:
                            os.remove(os.path.join(BACKUP_DIR, old))
                else:
                    with open(latest_path, "w", encoding="utf-8") as f:
                        json.dump(current_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error("❌ Ошибка создания бэкапа зеркал: %s", e)

    # ============= КАСТОМИЗАЦИЯ БОТА =============

    async def set_bot_name(self, token: str, name: str | None = None) -> bool:
        """Меняет имя бота."""
        bot = None
        try:
            bot = self._make_bot(token)
            await bot.set_my_name(
                name=name or config.mirror_bot_name, language_code="ru"
            )
            return True
        except Exception as e:
            logger.error("❌ Ошибка смены имени: %s", e)
            return False
        finally:
            await self._close(bot)

    async def set_bot_description(
        self, token: str, description: str | None = None
    ) -> bool:
        """Меняет описание бота (поле 'What can this bot do?')."""
        bot = None
        try:
            bot = self._make_bot(token)
            await bot.set_my_description(
                description=description or config.mirror_bot_description,
                language_code="ru",
            )
            return True
        except Exception as e:
            logger.error("❌ Ошибка смены описания: %s", e)
            return False
        finally:
            await self._close(bot)

    async def customize_bot_fully(self, token: str) -> dict[str, bool]:
        """Полная кастомизация: имя и описание."""
        return {
            "name": await self.set_bot_name(token),
            "description": await self.set_bot_description(token),
        }

    # ============= ПРОВЕРКА ТОКЕНА (3 МЕТОДА) =============

    async def validate_token_with_detailed_errors(
        self, token: str
    ) -> tuple[bool, str | None, str | None]:
        """Проверяет токен: getMe, setMyDescription, getUpdates/webhook.

        Возвращает (валиден, username, тип_ошибки).
        Невалиден при Unauthorized, Frozen, Webhook, Moderation Ban.
        """
        test_bot = None
        try:
            test_bot = self._make_bot(token)

            # Метод 1: getMe
            bot_info = await test_bot.get_me()
            username = bot_info.username

            # Метод 2: setMyDescription (ловит frozen / ban модерацией)
            try:
                await test_bot.set_my_description(
                    description=config.mirror_bot_description, language_code="ru"
                )
            except TelegramBadRequest as e:
                error_str = str(e).upper()
                if "FROZEN_METHOD_INVALID" in error_str or "FROZEN" in error_str:
                    logger.error("Бот заморожен (по описанию): @%s", username)
                    return False, username, "frozen"
                if any(
                    x in error_str
                    for x in (
                        "UNAVAILABLE",
                        "BOT IS UNAVAILABLE",
                        "BOT WAS BLOCKED",
                        "НАРУШАЛ ПРАВИЛА",
                        "VIOLATED",
                        "BLOCKED",
                        "FORBIDDEN",
                        "THIS BOT IS UNAVAILABLE",
                    )
                ):
                    logger.error("Бот заблокирован модерацией (по описанию): @%s", username)
                    return False, username, "banned"
                if (
                    "webhook is active" in str(e).lower()
                    or "can't use getupdates" in str(e).lower()
                ):
                    logger.warning("Бот использует вебхук: @%s", username)
                    return False, username, "webhook_active"
                if "Conflict" in str(e) or "already running" in str(e).lower():
                    logger.warning("Бот уже запущен: @%s", username)
                    return True, username, "conflict"
                if "429" in str(e) or "Too Many Requests" in str(e):
                    logger.warning("Спам-блок: @%s", username)
                else:
                    logger.warning(
                        "Другая ошибка (set_my_description): @%s - %s", username, e
                    )

            # Метод 3: getWebhookInfo (активный вебхук ломает polling)
            try:
                info = await test_bot.get_webhook_info()
                if info.url:
                    logger.warning("У бота активен вебхук: @%s", username)
                    return False, username, "webhook_active"
            except TelegramBadRequest as e:
                error_str = str(e).upper()
                if "FROZEN" in error_str:
                    return False, username, "frozen"

            return True, username, None

        except TelegramUnauthorizedError:
            logger.error("Токен невалиден (Unauthorized): %s...", token[:10])
            return False, None, "unauthorized"
        except TelegramNetworkError as e:
            logger.warning("Сетевая ошибка: %s", e)
            return True, None, None
        except TelegramBadRequest as e:
            error_str = str(e).upper()
            if "FROZEN_METHOD_INVALID" in error_str or "FROZEN" in error_str:
                logger.error("Бот заморожен (outer): %s...", token[:10])
                return False, None, "frozen"
            if any(
                x in error_str
                for x in (
                    "UNAVAILABLE",
                    "BOT IS UNAVAILABLE",
                    "BOT WAS BLOCKED",
                    "НАРУШАЛ ПРАВИЛА",
                    "VIOLATED",
                    "BLOCKED",
                    "FORBIDDEN",
                )
            ):
                logger.error("Бот заблокирован модерацией (outer): %s...", token[:10])
                return False, None, "banned"
            if (
                "Conflict" in str(e)
                or "already running" in str(e).lower()
                or "terminated by other getUpdates request" in str(e)
            ):
                logger.warning("Конфликт: %s...", token[:10])
                return True, None, "conflict"
            logger.warning("BadRequest: %s", e)
            return True, None, None
        except Exception as e:
            error_str = str(e).upper()
            if "UNAUTHORIZED" in error_str:
                return False, None, "unauthorized"
            if any(
                x in error_str
                for x in (
                    "UNAVAILABLE",
                    "BOT IS UNAVAILABLE",
                    "BOT WAS BLOCKED",
                    "НАРУШАЛ ПРАВИЛА",
                    "VIOLATED",
                    "BLOCKED",
                    "FORBIDDEN",
                )
            ):
                logger.error(
                    "Бот заблокирован модерацией (внешний except): %s...", token[:10]
                )
                return False, None, "banned"
            if "FROZEN_METHOD_INVALID" in error_str or "FROZEN" in error_str:
                logger.error("Бот заморожен (внешний except): %s...", token[:10])
                return False, None, "frozen"
            if "WEBHOOK IS ACTIVE" in error_str:
                return False, None, "webhook_active"
            if "CONFLICT" in error_str or "already running" in str(e).lower():
                return True, None, "conflict"
            logger.warning("Другая ошибка: %s", e)
            return True, None, None
        finally:
            await self._close(test_bot)

    async def validate_token(self, token: str) -> tuple[bool, str | None]:
        """Проверяет валидность токена и возвращает username бота."""
        is_valid, username, _ = await self.validate_token_with_detailed_errors(token)
        return is_valid, username

    async def validate_mirror_token(self, bot_username: str) -> tuple[bool, str | None]:
        """Проверяет валидность токена конкретного зеркала."""
        mirror = await mirror_store.by_username(bot_username)
        if mirror is None:
            return False, "mirror_not_found"
        is_valid, _, error_type = await self.validate_token_with_detailed_errors(
            mirror.token
        )
        if not is_valid and error_type in FATAL_ERRORS:
            return False, error_type
        return is_valid, error_type

    async def validate_all_tokens(self) -> tuple[list[str], list[str]]:
        """Проверяет все токены на валидность. Возвращает (невалидные, [])."""
        invalid_mirrors: list[str] = []
        for m in await mirror_store.active_mirrors():
            is_valid, _, error_type = await self.validate_token_with_detailed_errors(
                m.token
            )
            if not is_valid and error_type in FATAL_ERRORS:
                invalid_mirrors.append(m.bot_username or str(m.id))
        return invalid_mirrors, []

    # ============= ЛИМИТЫ И УДАЛЕНИЕ =============

    async def user_has_mirror(self, user_id: int) -> bool:
        """Достиг ли пользователь лимита зеркал."""
        mirrors = await mirror_store.by_owner(user_id)
        return len(mirrors) >= config.max_mirrors_per_user

    async def get_first_mirror(self) -> MirrorRecord | None:
        """Возвращает ПЕРВОЕ активное зеркало (самое старое)."""
        mirrors = await mirror_store.active_mirrors()
        return mirrors[0] if mirrors else None

    async def get_random_mirror(self) -> MirrorRecord | None:
        """Возвращает случайное активное зеркало."""
        import random

        mirrors = await mirror_store.active_mirrors()
        return random.choice(mirrors) if mirrors else None

    async def get_mirror_count(self) -> int:
        return await mirror_store.count_active()

    async def rename_and_remove_mirror(self, mirror: MirrorRecord) -> bool:
        """Переименовывает бота через Bot API, затем удаляет зеркало."""
        if mirror.token:
            await self.set_bot_name(
                mirror.token, f"🤖NEW BOT: {config.backup_bot_url}"
            )
        try:
            await mirror_store.delete(mirror.id)
            await self._create_backup()
            logger.info("🚨 Полностью удалено зеркало @%s", mirror.bot_username)
            return True
        except Exception as e:
            logger.error("❌ Ошибка удаления @%s: %s", mirror.bot_username, e)
            return False

    async def deactivate_mirror(
        self, mirror: MirrorRecord, reason: str = "invalid_token"
    ) -> bool:
        """Удаляет зеркало (с переименованием) и пишет причину в лог."""
        logger.info("🚨 Удаление зеркала @%s: %s", mirror.bot_username, reason)
        return await self.rename_and_remove_mirror(mirror)

    # ============= АВТО-ПРОВЕРКИ =============

    async def validate_first_mirror_periodically(self, interval: int = 60):
        """Проверяет ПЕРВОЕ зеркало каждые 60 секунд. При невалидности — удаляет."""
        logger.info("🔄 Запущена периодическая проверка ПЕРВОГО зеркала (каждые %ss)", interval)
        while True:
            try:
                await asyncio.sleep(interval)
                mirror = await self.get_first_mirror()
                if mirror is None:
                    continue
                if not mirror.token:
                    logger.warning(
                        "🚨 У первого зеркала @%s нет токена - УДАЛЯЮ",
                        mirror.bot_username,
                    )
                    await self.deactivate_mirror(mirror, "first_mirror_no_token")
                    continue
                is_valid, _, error_type = await self.validate_token_with_detailed_errors(
                    mirror.token
                )
                if not is_valid:
                    logger.warning(
                        "🚨 Первое зеркало @%s невалидно (%s) - УДАЛЯЮ",
                        mirror.bot_username,
                        error_type,
                    )
                    await self.deactivate_mirror(
                        mirror, f"first_mirror_check_{error_type}"
                    )
            except Exception as e:
                logger.error("❌ Ошибка в ежеминутной проверке первого зеркала: %s", e)
                await asyncio.sleep(5)

    async def auto_token_checker(self, interval: int = 1200):
        """Автоматическая проверка всех токенов каждые 20 минут."""
        while True:
            try:
                await asyncio.sleep(interval)
                invalid_mirrors, _ = await self.validate_all_tokens()
                if invalid_mirrors:
                    logger.info(
                        "🚨 Найдено невалидных зеркал: %s", len(invalid_mirrors)
                    )
                    for username in invalid_mirrors:
                        mirror = await mirror_store.by_username(username)
                        if mirror is not None:
                            await self.deactivate_mirror(mirror, "auto_check_invalid")
                            logger.info("🗑️ Автоудалено зеркало @%s", username)
            except Exception as e:
                logger.error("❌ Ошибка в авто-проверке: %s", e)
                await asyncio.sleep(60)


# Глобальный экземпляр менеджера
mirror_manager_service = MirrorManagerService()
