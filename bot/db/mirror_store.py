"""Mirror bots live in Redis; the main data stays in PostgreSQL."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from redis.asyncio import Redis

from config import config

log = logging.getLogger(__name__)

KEY_PREFIX = "mirror:"
KEY_INDEX = "mirrors:ids"
KEY_SEQ = "mirrors:seq"
KEY_MIGRATED = "mirrors:migrated"

_redis: Redis | None = None


def redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(config.mirrors_redis_url, decode_responses=True)
    return _redis


@dataclass
class MirrorRecord:
    id: int
    owner_id: int
    token: str
    bot_username: str | None = None
    is_premium: bool = False
    is_active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def created(self) -> datetime:
        try:
            return datetime.fromisoformat(self.created_at)
        except ValueError:
            return datetime.now(timezone.utc)


def _key(mirror_id: int) -> str:
    return f"{KEY_PREFIX}{mirror_id}"


async def save(mirror: MirrorRecord) -> MirrorRecord:
    await redis().set(_key(mirror.id), json.dumps(asdict(mirror)))
    await redis().sadd(KEY_INDEX, mirror.id)
    return mirror


async def create(owner_id: int, token: str, is_premium: bool) -> MirrorRecord:
    mirror_id = int(await redis().incr(KEY_SEQ))
    return await save(
        MirrorRecord(id=mirror_id, owner_id=owner_id, token=token, is_premium=is_premium)
    )


async def get(mirror_id: int) -> MirrorRecord | None:
    raw = await redis().get(_key(mirror_id))
    if raw is None:
        return None
    return MirrorRecord(**json.loads(raw))


async def delete(mirror_id: int) -> None:
    await redis().delete(_key(mirror_id))
    await redis().srem(KEY_INDEX, mirror_id)


async def all_mirrors() -> list[MirrorRecord]:
    ids = await redis().smembers(KEY_INDEX)
    mirrors = []
    for mirror_id in ids:
        mirror = await get(int(mirror_id))
        if mirror is not None:
            mirrors.append(mirror)
    return sorted(mirrors, key=lambda m: m.created)


async def active_mirrors() -> list[MirrorRecord]:
    return [m for m in await all_mirrors() if m.is_active]


async def by_owner(owner_id: int, only_active: bool = True) -> list[MirrorRecord]:
    return [
        m
        for m in await all_mirrors()
        if m.owner_id == owner_id and (m.is_active or not only_active)
    ]


async def by_token(token: str) -> MirrorRecord | None:
    for mirror in await all_mirrors():
        if mirror.token == token:
            return mirror
    return None


async def by_bot_id(bot_id: int) -> MirrorRecord | None:
    for mirror in await all_mirrors():
        if mirror.token.startswith(f"{bot_id}:"):
            return mirror
    return None


async def by_username(username: str) -> MirrorRecord | None:
    wanted = username.lstrip("@").lower()
    for mirror in await all_mirrors():
        if (mirror.bot_username or "").lower() == wanted:
            return mirror
    return None


async def count_active() -> int:
    return len(await active_mirrors())


async def migrate_from_postgres() -> int:
    """One-time import of mirrors that were stored in PostgreSQL."""
    if await redis().get(KEY_MIGRATED):
        return 0
    from sqlalchemy import select

    from bot.db.base import SessionMaker
    from bot.db.models import Mirror

    imported = 0
    try:
        async with SessionMaker() as session:
            rows = (await session.execute(select(Mirror))).scalars().all()
            for row in rows:
                if await by_token(row.token):
                    continue
                mirror_id = int(await redis().incr(KEY_SEQ))
                await save(
                    MirrorRecord(
                        id=mirror_id,
                        owner_id=row.owner_id,
                        token=row.token,
                        bot_username=row.bot_username,
                        is_premium=row.is_premium,
                        is_active=row.is_active,
                        created_at=(row.created_at or datetime.now(timezone.utc)).isoformat(),
                    )
                )
                imported += 1
    except Exception:
        log.exception("Mirror migration from PostgreSQL failed")
        return imported
    await redis().set(KEY_MIGRATED, "1")
    if imported:
        log.info("Imported %s mirrors from PostgreSQL into Redis", imported)
    return imported
