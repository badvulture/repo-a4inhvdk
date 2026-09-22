"""Startup backup: on bot launch, zip the config, user DB, videos and
mirrors tables and send them to the first admin."""

import asyncio
import logging
import os
import zipfile
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.types import FSInputFile

from config import config

log = logging.getLogger(__name__)

_BACKUP_DIR = "storage/backup"


def _pg_params() -> dict:
    url = urlparse(config.database_url.replace("+asyncpg", ""))
    return {
        "host": url.hostname or "localhost",
        "port": str(url.port or 5432),
        "user": url.username or "postgres",
        "password": url.password or "",
        "database": url.path.lstrip("/") or "postgres",
    }


async def _pg_dump(sql_path: str, table: str | None = None) -> str | None:
    """Run pg_dump; return None on success or the error text."""
    p = _pg_params()
    cmd = [
        "pg_dump",
        "-h", p["host"],
        "-p", p["port"],
        "-U", p["user"],
        "-d", p["database"],
        "-f", sql_path,
    ]
    if table:
        cmd += ["-t", table]
    env = os.environ.copy()
    env["PGPASSWORD"] = p["password"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0 and os.path.exists(sql_path):
            return None
        return stderr.decode(errors="replace")
    except Exception as e:  # noqa: BLE001
        return str(e)


async def _dump_zip(zip_path: str, arcname: str, table: str | None = None) -> str:
    sql_path = zip_path.replace(".zip", ".sql")
    error = await _pg_dump(sql_path, table)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        if error is None:
            zipf.write(sql_path, arcname)
        else:
            zipf.writestr("error.txt", f"pg_dump failed:\n{error}")
    if os.path.exists(sql_path):
        os.unlink(sql_path)
    return zip_path


async def send_startup_backup(bot: Bot) -> None:
    if not config.admin_ids:
        return
    admin_id = config.admin_ids[0]
    try:
        await bot.send_message(
            chat_id=admin_id,
            text="🤖 Бот успешно запущен!",
            disable_notification=True,
        )

        os.makedirs(_BACKUP_DIR, exist_ok=True)
        files: list[tuple[str, str]] = []

        # config
        config_zip = f"{_BACKUP_DIR}/config.zip"
        with zipfile.ZipFile(config_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists("config.py"):
                zipf.write("config.py", "config.py")
        files.append((config_zip, "📂 Текущий конфиг"))

        files.append((
            await _dump_zip(f"{_BACKUP_DIR}/users.zip", "users.sql", "users"),
            "📂 Таблица users",
        ))
        files.append((
            await _dump_zip(f"{_BACKUP_DIR}/videos.zip", "videos.sql", "videos"),
            "📂 Таблица videos",
        ))
        files.append((
            await _dump_zip(f"{_BACKUP_DIR}/mirrors.zip", "mirrors.sql", "mirrors"),
            "🪞 Таблица mirrors",
        ))
        files.append((
            await _dump_zip(f"{_BACKUP_DIR}/postgreSQL.zip", "postgres_dump.sql"),
            "🗄️ PostgreSQL дамп (вся БД)",
        ))

        try:
            for path, caption in files:
                if os.path.exists(path):
                    await bot.send_document(
                        chat_id=admin_id,
                        document=FSInputFile(path),
                        caption=caption,
                    )
        finally:
            for path, _ in files:
                if os.path.exists(path):
                    os.unlink(path)
    except Exception as e:  # noqa: BLE001
        log.error("Startup backup failed: %s", e)
