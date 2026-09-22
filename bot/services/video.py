import asyncio
import os
import uuid

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db.models import Video, VideoFileCache

MAX_SIZE = 20 * 1024 * 1024
MAX_DURATION = 60
NOTE_SIZE = 480
IMAGE_NOTE_SECONDS = 5
FFMPEG_TIMEOUT = 120

MAIN_BOT_ID = int(config.bot_token.split(":")[0])


def _note_path(video: Video) -> str | None:
    """Local file to use as the video-note source, if available."""
    if not video.local_path:
        return None
    candidate = video.local_path.rsplit(".", 1)[0] + "_note.mp4"
    if os.path.exists(candidate):
        return candidate
    if video.note_file_id == video.file_id and os.path.exists(video.local_path):
        return video.local_path  # original upload was already a video note
    if video.local_path.endswith("_note.mp4") and os.path.exists(video.local_path):
        return video.local_path  # uploads store the converted note as local_path
    return None


async def send_circle(
    bot: Bot,
    chat_id: int,
    video: Video,
    session: AsyncSession,
    protect: bool = True,
    reply_markup: InlineKeyboardMarkup | None = None,
    caption: str | None = None,
) -> Message | None:
    """Send a circle with any bot: file_ids are bot-specific, so mirrors
    upload from the local file once and cache their own file_id.
    Circles are always sent as video notes; returns None on failure."""
    if bot.id == MAIN_BOT_ID:
        note_id, cache = video.note_file_id, None
    else:
        cache = (
            await session.execute(
                select(VideoFileCache).where(
                    VideoFileCache.video_id == video.id, VideoFileCache.bot_id == bot.id
                )
            )
        ).scalar_one_or_none()
        note_id = cache.note_file_id if cache else None

    if note_id:
        try:
            sent = await bot.send_video_note(
                chat_id, note_id, protect_content=protect, reply_markup=reply_markup
            )
        except Exception:
            sent = None
        if sent is not None:
            return sent

    # fall back to uploading the local note file, converting on the fly if needed
    src = _note_path(video)
    if src is None and video.local_path and os.path.exists(video.local_path):
        src = await to_square_note(video.local_path)
    sent = None
    if src:
        try:
            sent = await bot.send_video_note(
                chat_id, FSInputFile(src), protect_content=protect, reply_markup=reply_markup
            )
        except Exception:
            sent = None
    if sent is None or not sent.video_note:
        return None

    if bot.id == MAIN_BOT_ID:
        video.note_file_id = sent.video_note.file_id
    else:
        if cache is None:
            cache = VideoFileCache(video_id=video.id, bot_id=bot.id)
            session.add(cache)
        cache.note_file_id = sent.video_note.file_id
    await session.commit()
    return sent


async def download_video(bot: Bot, file_id: str, ext: str = ".mp4") -> str:
    os.makedirs(config.storage_dir, exist_ok=True)
    path = os.path.join(config.storage_dir, f"{uuid.uuid4().hex}{ext}")
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=path)
    return path


def detect_media(message: Message):
    """Returns (media, kind) where kind is 'note' | 'video' | 'image'.
    Documents are only accepted for video/* and image/* mime types."""
    if message.video_note:
        return message.video_note, "note"
    if message.video:
        return message.video, "video"
    if message.animation:
        return message.animation, "video"
    if message.photo:
        return message.photo[-1], "image"
    if message.document:
        mime = message.document.mime_type or ""
        if mime.startswith("video/"):
            return message.document, "video"
        if mime.startswith("image/"):
            return message.document, "image"
    return None, None


async def media_to_note(bot: Bot, message: Message) -> tuple[str, int] | None:
    """Download the message media and convert it to a square video note.
    Returns (note_path, duration) or None on failure / unsupported media."""
    media, kind = detect_media(message)
    if media is None or kind is None:
        return None
    local_path = await download_video(bot, media.file_id)
    if kind == "note":
        return local_path, media.duration or 0
    if kind == "image":
        note_path = await to_square_note_from_image(local_path)
        duration = IMAGE_NOTE_SECONDS
    else:
        note_path = await to_square_note(local_path)
        duration = media.duration or 0
    # the downloaded source is no longer needed — keep only the note
    try:
        os.remove(local_path)
    except OSError:
        pass
    if note_path is None:
        return None
    return note_path, duration


async def to_square_note(src_path: str) -> str | None:
    """Crop/scale a video to a square so Telegram accepts it as a video note."""
    dst = src_path.rsplit(".", 1)[0] + "_note.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-vf",
        f"crop='min(iw,ih)':'min(iw,ih)',scale={NOTE_SIZE}:{NOTE_SIZE}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "26",
        "-c:a", "aac", "-b:a", "96k",
        "-t", str(MAX_DURATION),
        dst,
    ]
    return await _run_ffmpeg(cmd, dst)


async def _run_ffmpeg(cmd: list[str], dst: str) -> str | None:
    """Run ffmpeg with a bounded timeout; returns dst on success else None."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=FFMPEG_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        try:
            os.remove(dst)
        except OSError:
            pass
        return None
    if proc.returncode != 0 or not os.path.exists(dst):
        return None
    return dst


async def to_square_note_from_image(src_path: str) -> str | None:
    """Turn a still image into a 5-second square video note (silent audio)."""
    dst = src_path.rsplit(".", 1)[0] + "_note.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", src_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(IMAGE_NOTE_SECONDS),
        "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        dst,
    ]
    return await _run_ffmpeg(cmd, dst)
