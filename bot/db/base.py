from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.database_url, pool_pre_ping=True)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    from bot.db import models  # noqa: F401

    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for ddl in (
            "ALTER TABLE videos ADD COLUMN IF NOT EXISTS in_pool BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_partner BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_bot_id BIGINT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS author_photo_path VARCHAR(512)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS captcha_passed BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mirror_rewarded BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_code VARCHAR(16)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_code VARCHAR(16)",
            # existing users should not be asked to pick a language again
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS lang_chosen BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_credited BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_balance_rub DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_withdrawn_rub DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS partner_pending_rub DOUBLE PRECISION NOT NULL DEFAULT 0",
            "UPDATE users SET captcha_passed = TRUE WHERE captcha_passed = FALSE AND created_at < NOW() - INTERVAL '1 hour'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS free_view_used BOOLEAN NOT NULL DEFAULT FALSE",
            "ALTER TABLE sponsors ADD COLUMN IF NOT EXISTS kind VARCHAR(16) NOT NULL DEFAULT 'required'",
            "UPDATE sponsors SET kind = 'optional' WHERE required = FALSE AND kind = 'required'",
        ):
            await conn.execute(text(ddl))
