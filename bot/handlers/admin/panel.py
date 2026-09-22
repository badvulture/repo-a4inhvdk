import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    LabeledPrice,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from bot.db import mirror_store
from bot.db.models import (
    Mirror,
    Payment,
    ProfileAccess,
    PromoActivation,
    PromoCode,
    Purchase,
    Rating,
    Sponsor,
    SponsorHidden,
    SponsorReward,
    SubscriptionTier,
    User,
    Video,
    VideoFileCache,
    View,
    Withdrawal,
)
from bot.db.repo import DEFAULT_SETTINGS, get_setting, set_setting
from bot.keyboards import cancel_kb
from bot.locales.texts import t
from bot.services import cryptopay
from bot.services import mirrors as mirrors_service
from bot.services.video import (
    MAX_DURATION,
    MAX_SIZE,
    detect_media,
    download_video,
    media_to_note,
)

router = Router()


class AdminStates(StatesGroup):
    broadcast_message = State()
    broadcast_buttons = State()
    grant = State()
    setting_value = State()
    sponsor_add = State()
    sponsor_reward = State()
    promo_add = State()
    ban = State()
    decline_reason = State()
    give_sub = State()
    pool_upload = State()


def panel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm:stats")
    kb.button(text="📣 Рассылка", callback_data="adm:broadcast")
    kb.button(text="💰 Начислить баланс", callback_data="adm:grant")
    kb.button(text="🎫 Выдать подписку", callback_data="adm:givesub")
    kb.button(text="🔒 Бан / разбан", callback_data="adm:ban")
    kb.button(text="🏷 Промокоды", callback_data="adm:promo")
    kb.button(text="📤 Загрузить в общий пул", callback_data="adm:pool")
    kb.button(text="🧾 Ожидают пополнения", callback_data="adm:payments")
    kb.button(text="💸 Заявки на вывод", callback_data="adm:withdrawals")
    kb.button(text="💲 Цены и настройки", callback_data="adm:settings")
    kb.button(text="📢 Спонсоры", callback_data="adm:sponsors")
    kb.button(text="🤖 Зеркала", callback_data="adm:mirrors")
    kb.button(text="🧪 Тест-оплата", callback_data="adm:testpay")
    kb.adjust(1)
    return kb.as_markup()


@router.message(Command("admin"))
async def admin_panel(message: Message, is_admin: bool):
    if not is_admin:
        return
    await message.answer("🛠 Админ-панель", reply_markup=panel_kb())


# ---------- quick commands ----------

@router.message(Command("give"))
async def give_cmd(message: Message, session: AsyncSession, is_admin: bool, bot: Bot):
    if not is_admin:
        return
    try:
        _, tg_id_s, amount_s = message.text.split()
        tg_id, amount = int(tg_id_s), int(amount_s)
    except ValueError:
        await message.answer("Формат: <code>/give tg_id сумма</code>")
        return
    target = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.")
        return
    target.balance += amount
    await session.commit()
    await message.answer(f"✅ Баланс @{target.username or tg_id}: {target.balance} 🪙 ({amount:+})")
    try:
        await bot.send_message(tg_id, f"💰 Админ изменил твой баланс: {amount:+} 🪙")
    except Exception:
        pass


@router.message(Command("vip"))
async def vip_cmd(message: Message, session: AsyncSession, is_admin: bool, bot: Bot):
    if not is_admin:
        return
    parts = message.text.split()
    try:
        tg_id = int(parts[1])
        tier = TIER_ALIASES[parts[2].lower()] if len(parts) >= 3 else SubscriptionTier.PREMIUM
        days = int(parts[3]) if len(parts) >= 4 else 0
    except (ValueError, KeyError, IndexError):
        await message.answer(
            "Формат: <code>/vip tg_id [тир] [дни]</code>\n"
            "Тир: a+ / a++ / premium / none (по умолчанию premium), дни 0 = навсегда"
        )
        return
    target = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.")
        return
    target.subscription = tier
    target.subscription_until = (
        (datetime.utcnow() + timedelta(days=days)) if days and tier != SubscriptionTier.NONE else None
    )
    await session.commit()
    await message.answer(f"✅ Подписка @{target.username or tg_id}: {tier.value}")
    try:
        await bot.send_message(tg_id, f"🎫 Админ выдал тебе подписку: {tier.value}")
    except Exception:
        pass


@router.message(Command("mirrors_list"))
async def mirrors_list_cmd(message: Message, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    mirrors = await mirror_store.all_mirrors()
    if not mirrors:
        await message.answer("Зеркал нет.")
        return
    lines = []
    for m in mirrors:
        owner = await session.get(User, m.owner_id)
        owner_label = f"@{owner.username or '-'} ({owner.tg_id})" if owner else "?"
        lines.append(
            f"@{m.bot_username or '?'} | владелец: {owner_label} | "
            f"{'активно' if m.is_active else 'выключено'} | "
            f"{m.created.strftime('%d.%m.%Y %H:%M')}"
        )
    content = "\n".join(lines)
    await message.answer_document(
        BufferedInputFile(content.encode(), filename="mirrors.txt"),
        caption=f"🤖 Зеркал всего: {len(mirrors)}",
    )


@router.message(Command("mirrors_clean"))
async def mirrors_clean_cmd(message: Message, is_admin: bool):
    if not is_admin:
        return
    status = await message.answer("🔄 Проверяю токены зеркал...")
    manager = mirrors_service.mirror_manager
    if manager is None:
        await status.edit_text("Менеджер зеркал не запущен.")
        return
    removed = await manager.clean_invalid()
    if removed:
        await status.edit_text("🗑 Удалены невалидные зеркала:\n" + "\n".join(removed))
    else:
        await status.edit_text("✅ Все зеркала валидны.")


@router.message(Command("delcircle"))
async def del_video_cmd(message: Message, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    try:
        video_id = int(message.text.split()[1])
    except (ValueError, IndexError):
        await message.answer("Формат: <code>/delcircle id_кружка</code>")
        return
    video = await session.get(Video, video_id)
    if video is None:
        await message.answer("Кружок не найден.")
        return
    video.is_active = False
    await session.commit()
    await message.answer(f"🗑 Кружок #{video_id} удалён.")


@router.message(Command("del"))
async def del_user_cmd(message: Message, command: CommandObject, session: AsyncSession, is_admin: bool):
    """Полное удаление пользователя: /del @username или /del 123456789."""
    if not is_admin:
        return
    if not command.args:
        await message.answer(
            "❌ Использование: /del ID_или_username\n"
            "Пример: /del 123456789 или /del @username"
        )
        return
    ident = command.args.strip().lstrip("@")
    if ident.isdigit():
        cond = User.tg_id == int(ident)
    else:
        cond = func.lower(User.username) == ident.lower()
    target = (await session.execute(select(User).where(cond))).scalar_one_or_none()
    if target is None:
        await message.answer("❌ Пользователь не найден")
        return
    if target.tg_id in config.admin_ids:
        await message.answer("❌ Нельзя удалить администратора!")
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ ДА, УДАЛИТЬ ПОЛНОСТЬЮ", callback_data=f"adm:deluser:{target.id}")
    kb.button(text="❌ ОТМЕНА", callback_data="adm:deluser:cancel")
    kb.adjust(1)
    await message.answer(
        "⚠️ <b>ВНИМАНИЕ! НЕОБРАТИМОЕ ДЕЙСТВИЕ!</b>\n\n"
        "Вы собираетесь полностью удалить пользователя из БД:\n"
        f"👤 <b>@{target.username or 'без юзернейма'}</b> (ID: <code>{target.tg_id}</code>)\n"
        f"📛 Имя: {target.full_name or 'не указано'}\n"
        f"💰 Баланс: {target.balance} 🪙\n"
        f"🎫 Подписка: {target.subscription.value}\n\n"
        "<b>Будут удалены ВСЕ данные:</b>\n"
        "• Баланс и платежи\n"
        "• Кружки и оценки\n"
        "• Покупки и доступы\n"
        "• Рефералы и партнёрка\n"
        "• ВСЕ остальные данные\n\n"
        "<b>ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!</b>",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("adm:deluser:"))
async def del_user_confirm(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    arg = cb.data.split(":")[2]
    if arg == "cancel":
        await cb.message.edit_text("✅ Удаление отменено")
        await cb.answer()
        return
    target = await session.get(User, int(arg))
    if target is None:
        await cb.message.edit_text("❌ Пользователь уже удалён.")
        await cb.answer()
        return
    if target.tg_id in config.admin_ids:
        await cb.message.edit_text("❌ Нельзя удалить администратора!")
        await cb.answer()
        return
    uid = target.id
    tg_id, username = target.tg_id, target.username
    video_ids = select(Video.id).where(Video.owner_id == uid)
    await session.execute(delete(VideoFileCache).where(VideoFileCache.video_id.in_(video_ids)))
    await session.execute(delete(Rating).where(Rating.video_id.in_(video_ids)))
    await session.execute(delete(View).where(View.video_id.in_(video_ids)))
    await session.execute(delete(Rating).where(Rating.user_id == uid))
    await session.execute(delete(View).where(View.user_id == uid))
    await session.execute(delete(Video).where(Video.owner_id == uid))
    await session.execute(
        delete(Purchase).where(
            (Purchase.user_id == uid) | (Purchase.target_user_id == uid)
        )
    )
    await session.execute(
        delete(ProfileAccess).where(
            (ProfileAccess.buyer_id == uid) | (ProfileAccess.author_id == uid)
        )
    )
    await session.execute(delete(Payment).where(Payment.user_id == uid))
    await session.execute(delete(Withdrawal).where(Withdrawal.user_id == uid))
    await session.execute(delete(SponsorReward).where(SponsorReward.user_id == uid))
    await session.execute(delete(SponsorHidden).where(SponsorHidden.user_id == uid))
    await session.execute(delete(PromoActivation).where(PromoActivation.user_id == uid))
    await session.execute(delete(Mirror).where(Mirror.owner_id == uid))
    for m in await mirror_store.by_owner(uid, only_active=False):
        await mirror_store.delete(m.id)
    await session.execute(delete(User).where(User.id == uid))
    await session.commit()
    await cb.message.edit_text(
        f"✅ <b>Пользователь @{username or 'без юзернейма'} (ID: {tg_id}) "
        "полностью удалён из БД.</b>\n\n"
        "Все данные пользователя стёрты без возможности восстановления."
    )
    await cb.answer()


@router.message(Command("give_all"))
async def give_all_cmd(message: Message, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    parts = message.text.split()
    try:
        amount = int(parts[1])
    except (ValueError, IndexError):
        await message.answer("Формат: <code>/give_all сумма [active]</code>")
        return
    only_active = len(parts) >= 3 and parts[2].lower() == "active"
    q = update(User).values(balance=User.balance + amount)
    if only_active:
        q = q.where(User.is_active.is_(True))
    res = await session.execute(q)
    await session.commit()
    await message.answer(
        f"✅ Начислено {amount:+} 🪙 "
        f"{'активным' if only_active else 'всем'} ({res.rowcount} польз.)"
    )


@router.message(Command("ban"))
async def ban_cmd(message: Message, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    try:
        tg_id = int(message.text.split()[1])
    except (ValueError, IndexError):
        await message.answer("Формат: <code>/ban tg_id</code>")
        return
    target = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.")
        return
    target.is_banned = not target.is_banned
    await session.commit()
    await message.answer(
        f"{'🔒 Забанен' if target.is_banned else '🔓 Разбанен'} @{target.username or tg_id}"
    )


@router.message(Command("msg"))
async def msg_cmd(message: Message, is_admin: bool, bot: Bot, command: CommandObject):
    if not is_admin:
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: <code>/msg tg_id текст</code>")
        return
    try:
        tg_id = int(parts[0])
    except ValueError:
        await message.answer("Формат: <code>/msg tg_id текст</code>")
        return
    try:
        await bot.send_message(tg_id, parts[1])
        await message.answer("✅ Отправлено")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("info"))
async def info_cmd(message: Message, session: AsyncSession, is_admin: bool, command: CommandObject):
    if not is_admin or not command.args:
        raise SkipHandler  # обычный /info для пользователей
    arg = command.args.strip()
    if arg.startswith("@"):
        q = select(User).where(func.lower(User.username) == arg[1:].lower())
    else:
        try:
            q = select(User).where(User.tg_id == int(arg))
        except ValueError:
            await message.answer("Формат: <code>/info tg_id</code> или <code>/info @username</code>")
            return
    target = (await session.execute(q)).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.")
        return
    uploaded = (
        await session.execute(
            select(func.count(Video.id)).where(Video.owner_id == target.id)
        )
    ).scalar_one()
    refs = (
        await session.execute(
            select(func.count(User.id)).where(User.referrer_id == target.tg_id)
        )
    ).scalar_one()
    await message.answer(
        f"👤 <b>@{target.username or '-'}</b> (<code>{target.tg_id}</code>)\n"
        f"Имя: {target.full_name or '-'}\n"
        f"Язык: {target.lang}\n"
        f"Баланс: {target.balance} 🪙\n"
        f"Подписка: {target.subscription.value}\n"
        f"Загружено кружков: {uploaded}\n"
        f"Просмотрено: {target.viewed_count}\n"
        f"Заработано автором: {target.author_earned} 🪙\n"
        f"Рефералов: {refs}\n"
        f"Партнёр: {'да' if target.is_partner else 'нет'} "
        f"(баланс {target.partner_balance_rub:g} ₽)\n"
        f"Активен: {'да' if target.is_active else 'нет'}\n"
        f"Бан: {'да' if target.is_banned else 'нет'}\n"
        f"Регистрация: {target.created_at.strftime('%d.%m.%Y %H:%M') if target.created_at else '-'}"
    )


@router.message(Command("stop_mirror"))
async def stop_mirror_cmd(message: Message, session: AsyncSession, is_admin: bool, command: CommandObject):
    if not is_admin:
        return
    if not command.args:
        await message.answer("Формат: <code>/stop_mirror username</code>")
        return
    username = command.args.strip().lstrip("@")
    mirror = await mirror_store.by_username(username)
    if mirror is None:
        await message.answer("Зеркало не найдено.")
        return
    mirror.is_active = False
    await mirror_store.save(mirror)
    manager = mirrors_service.mirror_manager
    if manager:
        try:
            await manager.stop_mirror(mirror.id)
        except Exception:
            pass
    await message.answer(f"🛑 Зеркало @{username} остановлено.")


@router.message(Command("manual"))
async def manual_cmd(message: Message, is_admin: bool):
    if not is_admin:
        return
    await message.answer(
        "<b>👨‍💻 АДМИН-КОМАНДЫ</b>\n\n"
        "/admin — админ-панель\n"
        "/manual — этот список\n\n"
        "<b>💰 Баланс</b>\n"
        "/give tg_id сумма — выдать монеты\n"
        "/give_all сумма [active] — выдать всем / только активным\n\n"
        "<b>👑 Подписки</b>\n"
        "/vip tg_id [тир] [дни] — выдать подписку\n\n"
        "<b>📨 Сообщения</b>\n"
        "/msg tg_id текст — написать пользователю\n"
        "Рассылка — через /admin → 📣\n\n"
        "<b>🚫 Пользователи</b>\n"
        "/ban tg_id — бан/разбан\n"
        "/info tg_id | @username — инфо о пользователе\n\n"
        "<b>🪞 Зеркала</b>\n"
        "/mirrors_list — список зеркал\n"
        "/mirrors_clean — проверить и удалить невалидные\n"
        "/stop_mirror username — остановить зеркало\n\n"
        "<b>🎬 Видео</b>\n"
        "/del id — удалить кружок\n"
        "/reset_circles — удалить все кружки из БД\n"
        "Общий пул — через /admin → 📤"
    )


@router.message(Command("reset_circles"))
async def reset_circles_cmd(message: Message, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    total = (await session.execute(select(func.count(Video.id)))).scalar_one()
    if not total:
        await message.answer("Кружков в БД нет.")
        return
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🗑 Удалить все ({total})", callback_data="adm:resetcircles")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(1)
    await message.answer(
        f"⚠️ Будут удалены все кружки ({total}) вместе с оценками и просмотрами. Продолжить?",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "adm:resetcircles")
async def reset_circles(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    total = (await session.execute(select(func.count(Video.id)))).scalar_one()
    paths = (
        (await session.execute(select(Video.local_path).where(Video.local_path.is_not(None))))
        .scalars()
        .all()
    )
    for table in (Rating, View, VideoFileCache):
        await session.execute(delete(table))
    await session.execute(delete(Video))
    await session.execute(update(User).values(author_earned=0, viewed_count=0, viewed_today=0))
    await session.commit()
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass
    await cb.answer()
    await cb.message.edit_text(f"🗑 Удалено кружков: {total}")


@router.callback_query(F.data.startswith("adm:delvid:"))
async def del_video_button(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    video = await session.get(Video, int(cb.data.split(":")[2]))
    if video:
        video.is_active = False
        await session.commit()
    await cb.answer("🗑 Кружок удалён")
    try:
        await cb.message.delete()
    except Exception:
        pass


# ---------- upload to common pool ----------

@router.callback_query(F.data == "adm:pool")
async def pool_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.pool_upload)
    await cb.message.answer(
        "📤 Отправляй видео/кружки (до 60 сек, до 20 МБ) — они попадут в общий пул "
        "и не будут привязаны к профилю. Можно несколько подряд.",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(
    AdminStates.pool_upload,
    F.video | F.video_note | F.animation | F.photo | F.document,
)
async def pool_upload(
    message: Message, session: AsyncSession, is_admin: bool, user: User, bot: Bot
):
    if not is_admin:
        return
    media, kind = detect_media(message)
    if media is None or kind is None:
        await message.answer("❌ Поддерживаются только видео, GIF и фото.")
        return
    if kind != "image" and media.duration and media.duration > MAX_DURATION:
        await message.answer("❌ Видео длиннее 60 секунд.")
        return
    if media.file_size and media.file_size > MAX_SIZE:
        await message.answer("❌ Файл больше 20 МБ.")
        return
    status = await message.answer("⏳ Обрабатываю...")
    note_file_id = None
    local_path = None
    try:
        result = await media_to_note(bot, message)
        if result is None:
            await status.edit_text("❌ Не удалось сделать кружок из этого файла.")
            return
        local_path, duration = result
        if kind == "note":
            note_file_id = media.file_id
        else:
            sent = await bot.send_video_note(message.chat.id, FSInputFile(local_path))
            note_file_id = sent.video_note.file_id
    except Exception:
        pass
    if note_file_id is None:
        await status.edit_text("❌ Не удалось сделать кружок из этого файла.")
        return
    # pool circles are owned by a random regular user, not by the admin
    owner = (
        await session.execute(
            select(User)
            .where(User.tg_id.not_in(config.admin_ids), User.is_banned.is_(False))
            .order_by(func.random())
            .limit(1)
        )
    ).scalar_one_or_none() or user
    seq = (
        await session.execute(
            select(func.coalesce(func.max(Video.seq_no), 0)).where(
                Video.owner_id == owner.id
            )
        )
    ).scalar_one() + 1
    video = Video(
        owner_id=owner.id,
        seq_no=seq,
        file_id=media.file_id,
        note_file_id=note_file_id,
        local_path=local_path,
        duration=duration,
        in_pool=True,
    )
    session.add(video)
    await session.commit()
    await status.edit_text(
        f"✅ Кружок #{video.id} добавлен в общий пул (владелец #{owner.id}). "
        "Отправь ещё или нажми «Отмена»."
    )


# ---------- stats ----------

@router.callback_query(F.data == "adm:stats")
async def stats(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async def _count(col=User.id, *conds):
        return (
            await session.execute(select(func.count(col)).where(*conds))
        ).scalar_one()

    async def _sum(col, *conds):
        return (
            await session.execute(select(func.coalesce(func.sum(col), 0)).where(*conds))
        ).scalar_one()

    # users
    users_total = await _count()
    users_day = await _count(User.id, User.created_at >= day_ago)
    users_week = await _count(User.id, User.created_at >= week_ago)
    users_active = await _count(User.id, User.is_active.is_(True))
    users_banned = await _count(User.id, User.is_banned.is_(True))
    subs_active = await _count(User.id, User.subscription != SubscriptionTier.NONE)
    subs_a = await _count(User.id, User.subscription == SubscriptionTier.A_PLUS)
    subs_app = await _count(User.id, User.subscription == SubscriptionTier.A_PLUS_PLUS)
    subs_prem = await _count(User.id, User.subscription == SubscriptionTier.PREMIUM)

    # coins
    paid = Payment.status == "paid"
    coins_today = await _sum(Payment.coins, paid, Payment.created_at >= today_start)
    coins_yest = await _sum(
        Payment.coins, paid, Payment.created_at >= yesterday_start,
        Payment.created_at < today_start,
    )
    coins_week = await _sum(Payment.coins, paid, Payment.created_at >= week_ago)
    coins_month = await _sum(Payment.coins, paid, Payment.created_at >= month_ago)
    coins_all = await _sum(Payment.coins, paid)
    rub_all = await _sum(Payment.amount_rub, paid)
    balance_all = await _sum(User.balance)

    # content
    videos_total = await _count(Video.id)
    videos_active = await _count(Video.id, Video.is_active.is_(True))
    authors = (
        await session.execute(
            select(func.count(func.distinct(Video.owner_id))).where(
                Video.is_active.is_(True)
            )
        )
    ).scalar_one()
    views_total = await _count(View.id)
    views_day = await _count(View.id, View.created_at >= day_ago)
    likes = await _count(Rating.id, Rating.value == 1)
    dislikes = await _count(Rating.id, Rating.value == -1)
    access_count = await _count(ProfileAccess.id)
    access_coins = await _sum(Purchase.amount_coins, Purchase.kind == "profile")

    # referrals
    refs_day = await _count(
        User.id, User.referrer_id.is_not(None), User.created_at >= day_ago
    )
    refs_total = await _count(User.id, User.referrer_id.is_not(None))
    ref_reward = int(await get_setting(session, "referral_reward"))

    # withdrawals
    wd_pending = await _count(Withdrawal.id, Withdrawal.status == "pending")
    wd_pending_sum = await _sum(Withdrawal.amount, Withdrawal.status == "pending")
    wd_done = await _count(Withdrawal.id, Withdrawal.status == "paid")

    # promos
    promos_total = await _count(PromoCode.id)
    promos_active = await _count(PromoCode.id, PromoCode.is_active.is_(True))
    promos_used = await _count(PromoActivation.id)

    # sponsors
    sp_req = await _count(Sponsor.id, Sponsor.is_active.is_(True), Sponsor.kind == "required")
    sp_opt = await _count(Sponsor.id, Sponsor.is_active.is_(True), Sponsor.kind == "optional")
    sp_rec = await _count(Sponsor.id, Sponsor.is_active.is_(True), Sponsor.kind == "recommend")
    sp_rewards = await _count(SponsorReward.id)
    sp_hidden = await _count(SponsorHidden.id)

    # mirrors & partners
    mirrors_active = await mirror_store.count_active()
    mirrors_total = len(await mirror_store.all_mirrors())
    partners = await _count(User.id, User.is_partner.is_(True))
    partner_balance = await _sum(User.partner_balance_rub)

    await cb.message.answer(
        "📊 Статистика\n\n"
        "👥 <b>Пользователи</b>\n"
        f"Всего: {users_total} (24ч: +{users_day}, 7д: +{users_week})\n"
        f"✅ Активных: {users_active} | 🚫 Забанено: {users_banned}\n"
        f"🎫 Подписок: {subs_active} (А+: {subs_a}, A++: {subs_app}, PREMIUM: {subs_prem})\n\n"
        "💰 <b>Монеты</b>\n"
        f"Продано сегодня: {coins_today} 🪙 | вчера: {coins_yest} 🪙\n"
        f"7 дней: {coins_week} 🪙 | 30 дней: {coins_month} 🪙\n"
        f"Всё время: {coins_all} 🪙 (~{rub_all} ₽)\n"
        f"🏦 Общий баланс юзеров: {balance_all} 🪙\n\n"
        "🎬 <b>Контент</b>\n"
        f"Кружков: {videos_total} (активных {videos_active}) | авторов: {authors}\n"
        f"Просмотров: {views_total} (24ч: {views_day})\n"
        f"Оценок: 👍 {likes} 👎 {dislikes}\n"
        f"Покупок доступа: {access_count} ({access_coins} 🪙)\n\n"
        "👫 <b>Рефералы</b>\n"
        f"Приглашено за 24ч: {refs_day} (+{refs_day * ref_reward} 🪙 рефоводам)\n"
        f"Всего рефералов: {refs_total}\n\n"
        "💸 <b>Выводы</b>\n"
        f"Активных заявок: {wd_pending} на {wd_pending_sum} 🪙 | выполнено: {wd_done}\n\n"
        "🎟 <b>Промокоды</b>\n"
        f"Всего: {promos_total} | активных: {promos_active} | активаций: {promos_used}\n\n"
        "📢 <b>Спонсоры</b>\n"
        f"ОП: {sp_req} | необязательных: {sp_opt} | рекомендаций: {sp_rec}\n"
        f"Наград за подписку выдано: {sp_rewards} | скрытий рекомендаций: {sp_hidden}\n\n"
        "🤖 <b>Зеркала и партнёры</b>\n"
        f"Зеркал активных: {mirrors_active} (всего {mirrors_total})\n"
        f"🤝 Партнёров: {partners} (баланс {partner_balance} ₽)"
    )
    await cb.answer()


# ---------- broadcast ----------

CALLBACK_WHITELIST = {
    "free_circle": "Следующий кружок (первый бесплатно)",
    "next_circle": "Следующий кружок",
    "buy:menu": "Приобрести монеты",
    "buy:free": "Бесплатные монеты",
    "pf:home": "Профиль",
    "pf:upload": "Загрузить кружок",
    "mir:menu": "Зеркала",
    "free:ref": "Реферальная ссылка",
    "free:sponsors": "Спонсоры",
    "partner:join": "Партнёрская программа",
}

BUTTONS_PROMPT = (
    "Теперь отправь кнопки к сообщению.\n"
    "Каждая строка — один ряд кнопок; несколько кнопок в ряду разделяй <code>||</code>.\n"
    "Формат кнопки: <code>Текст | https://ссылка</code> или <code>Текст | callback:имя</code>\n\n"
    "Пример:\n"
    "<code>🎁 1 кружок бесплатно | callback:free_circle || 📢 Канал | https://t.me/channel</code>\n\n"
    "Доступные callback:\n"
    + "\n".join(f"<code>{name}</code> — {desc}" for name, desc in CALLBACK_WHITELIST.items())
    + "\n\nИли отправь <code>-</code> чтобы разослать без кнопок."
)

MEDIA_EXT = {
    "photo": ".jpg",
    "video": ".mp4",
    "animation": ".mp4",
    "audio": ".mp3",
    "voice": ".ogg",
    "video_note": ".mp4",
    "sticker": ".webp",
}


def parse_buttons(text: str):
    """Parse the admin's button markup text. Returns an InlineKeyboardMarkup,
    None for "-" (no buttons), raises ValueError with a precise RU message."""
    text = text.strip()
    if text == "-":
        return None
    rows = []
    total = 0
    for n, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        row = []
        for chunk in line.split("||"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "|" not in chunk:
                raise ValueError(
                    f"Строка {n}: нет разделителя «|» — формат «Текст | ссылка»"
                )
            label, target = (p.strip() for p in chunk.split("|", 1))
            if not label:
                raise ValueError(f"Строка {n}: пустой текст кнопки")
            if target.lower().startswith("callback:"):
                name = target[len("callback:"):].strip()
                if name not in CALLBACK_WHITELIST:
                    raise ValueError(
                        f"Строка {n}: неизвестный callback «{name}». "
                        f"Доступные: {', '.join(CALLBACK_WHITELIST)}"
                    )
                if len(name.encode()) > 64:
                    raise ValueError(f"Строка {n}: callback «{name}» длиннее 64 байт")
                row.append(InlineKeyboardButton(text=label, callback_data=name))
            else:
                if not target.startswith(("http://", "https://", "tg://")):
                    raise ValueError(
                        f"Строка {n}: «{target}» — ссылка должна начинаться с https://"
                    )
                row.append(InlineKeyboardButton(text=label, url=target))
            total += 1
            if total > 100:
                raise ValueError("Слишком много кнопок (максимум 100)")
        if not row:
            continue
        if len(row) > 8:
            raise ValueError(f"Строка {n}: больше 8 кнопок в ряду")
        rows.append(row)
    if not rows:
        raise ValueError("Нет ни одной кнопки — отправь <code>-</code> без кнопок.")
    kb = InlineKeyboardBuilder()
    for row in rows:
        kb.row(*row)
    return kb.as_markup()


def _broadcast_media(message: Message):
    """Returns (media_type, file_id, file_name) or (None, None, None)."""
    for kind in ("photo", "video", "animation", "audio", "voice", "document", "video_note", "sticker"):
        media = getattr(message, kind)
        if media:
            file_id = media[-1].file_id if kind == "photo" else media.file_id
            name = getattr(media, "file_name", None)
            return kind, file_id, name
    return None, None, None


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.broadcast_message)
    await cb.message.answer(
        "Отправь сообщение для рассылки — текст, фото, видео, GIF, музыка, "
        "голосовое, документ, стикер, видео-кружок (будет отправлено как есть):",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.broadcast_message)
async def broadcast_message(message: Message, state: FSMContext, is_admin: bool):
    if not is_admin:
        return
    media_type, media_file_id, media_name = _broadcast_media(message)
    text_html = message.html_text if (message.text or message.caption) else None
    if not text_html and not media_file_id:
        await message.answer("❌ Это сообщение нельзя разослать. Отправь текст или медиа.")
        return
    await state.update_data(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text_html=text_html,
        media_type=media_type,
        media_file_id=media_file_id,
        media_name=media_name,
    )
    await state.set_state(AdminStates.broadcast_buttons)
    await message.answer(BUTTONS_PROMPT)


async def _send_via_mirror(target: Bot, tg_id: int, data: dict, media_path: str | None, markup):
    media_type = data.get("media_type")
    text_html = data.get("text_html")
    if media_type and media_path:
        f = FSInputFile(media_path)
        if media_type == "photo":
            await target.send_photo(tg_id, f, caption=text_html, reply_markup=markup)
        elif media_type == "video":
            await target.send_video(tg_id, f, caption=text_html, reply_markup=markup)
        elif media_type == "animation":
            await target.send_animation(tg_id, f, caption=text_html, reply_markup=markup)
        elif media_type == "audio":
            await target.send_audio(tg_id, f, caption=text_html, reply_markup=markup)
        elif media_type == "voice":
            await target.send_voice(tg_id, f, caption=text_html, reply_markup=markup)
        elif media_type == "document":
            await target.send_document(tg_id, f, caption=text_html, reply_markup=markup)
        elif media_type == "video_note":
            await target.send_video_note(tg_id, f, reply_markup=None if text_html else markup)
            if text_html:
                await target.send_message(tg_id, text_html, reply_markup=markup)
        elif media_type == "sticker":
            await target.send_sticker(tg_id, f, reply_markup=None if text_html else markup)
            if text_html:
                await target.send_message(tg_id, text_html, reply_markup=markup)
        else:
            await target.send_document(tg_id, f, caption=text_html, reply_markup=markup)
    elif text_html:
        await target.send_message(tg_id, text_html, reply_markup=markup)
    else:
        raise ValueError("nothing to send")


@router.message(AdminStates.broadcast_buttons, F.text)
async def broadcast_send(
    message: Message, state: FSMContext, session: AsyncSession, is_admin: bool, bot: Bot
):
    if not is_admin:
        return
    try:
        markup = parse_buttons(message.text)
    except ValueError as e:
        await message.answer(
            f"❌ {e}\n\nИсправь и отправь кнопки ещё раз, или <code>-</code> без кнопок."
        )
        return
    data = await state.get_data()
    await state.clear()

    # preview for the admin first — abort if the message can't be reproduced
    try:
        await bot.copy_message(
            message.chat.id, data["chat_id"], data["message_id"], reply_markup=markup
        )
    except Exception as e:
        await message.answer(f"❌ Превью не удалось: {e}")
        return

    users = (
        await session.execute(
            select(User.tg_id, User.last_bot_id).where(User.is_banned.is_(False))
        )
    ).all()

    # deliver through the bot each user actually talks to (main bot or mirror)
    manager = mirrors_service.mirror_manager
    bots_by_id = manager.bots_by_id() if manager else {}
    main_b = mirrors_service.main_bot or bot

    media_type = data.get("media_type")
    media_path = None
    if media_type and data.get("media_file_id"):
        ext = MEDIA_EXT.get(media_type)
        if media_type == "document" and data.get("media_name"):
            ext = os.path.splitext(data["media_name"])[1] or ".bin"
        ext = ext or ".bin"
        try:
            media_path = await download_video(bot, data["media_file_id"], ext)
        except Exception:
            media_path = None

    sent = failed = 0
    failed_ids: list[int] = []
    status = await message.answer(f"Рассылаю {len(users)} пользователям...")
    for tg_id, last_bot_id in users:
        target = bots_by_id.get(last_bot_id) or main_b
        try:
            if target.id == bot.id:
                await target.copy_message(
                    tg_id, data["chat_id"], data["message_id"], reply_markup=markup
                )
            else:
                await _send_via_mirror(target, tg_id, data, media_path, markup)
            sent += 1
        except Exception:
            failed += 1
            failed_ids.append(tg_id)
        await asyncio.sleep(0.05)
    if failed_ids:
        await session.execute(
            update(User).where(User.tg_id.in_(failed_ids)).values(is_active=False)
        )
        await session.commit()
    await status.edit_text(f"📣 Рассылка завершена.\nДоставлено: {sent}\nОшибок: {failed} (помечены неактивными)")


@router.message(AdminStates.broadcast_buttons)
async def broadcast_buttons_wrong(message: Message, is_admin: bool):
    if not is_admin:
        return
    await message.answer("❌ Нужен текст с кнопками или «-».")


# ---------- grant balance ----------

@router.callback_query(F.data == "adm:grant")
async def grant_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.grant)
    await cb.message.answer(
        "Отправь: <code>tg_id сумма</code> (сумма может быть отрицательной)",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.grant, F.text)
async def grant(message: Message, state: FSMContext, session: AsyncSession, is_admin: bool, bot: Bot):
    if not is_admin:
        return
    try:
        tg_id_s, amount_s = message.text.split()
        tg_id, amount = int(tg_id_s), int(amount_s)
    except ValueError:
        await message.answer(
            "Формат: <code>tg_id сумма</code>", reply_markup=cancel_kb("ru")
        )
        return
    target = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.", reply_markup=cancel_kb("ru"))
        return
    target.balance += amount
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Баланс @{target.username or tg_id}: {target.balance} 🪙")
    try:
        await bot.send_message(tg_id, f"💰 Админ изменил твой баланс: {amount:+} 🪙")
    except Exception:
        pass


# ---------- give subscription ----------

TIER_ALIASES = {
    "a+": SubscriptionTier.A_PLUS,
    "a++": SubscriptionTier.A_PLUS_PLUS,
    "premium": SubscriptionTier.PREMIUM,
    "none": SubscriptionTier.NONE,
}


@router.callback_query(F.data == "adm:givesub")
async def give_sub_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.give_sub)
    await cb.message.answer(
        "Отправь: <code>tg_id тир дни</code>\n"
        "Тир: <code>a+</code> / <code>a++</code> / <code>premium</code> / <code>none</code> (снять)\n"
        "Дни: 0 = навсегда\n"
        "Например: <code>123456 a++ 7</code>",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.give_sub, F.text)
async def give_sub(
    message: Message, state: FSMContext, session: AsyncSession, is_admin: bool, bot: Bot
):
    if not is_admin:
        return
    try:
        tg_id_s, tier_s, days_s = message.text.split()
        tg_id, days = int(tg_id_s), int(days_s)
        tier = TIER_ALIASES[tier_s.lower()]
    except (ValueError, KeyError):
        await message.answer("Формат: <code>tg_id тир дни</code>", reply_markup=cancel_kb("ru"))
        return
    target = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.", reply_markup=cancel_kb("ru"))
        return
    target.subscription = tier
    target.subscription_until = (
        (datetime.utcnow() + timedelta(days=days)) if days and tier != SubscriptionTier.NONE else None
    )
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Подписка @{target.username or tg_id}: {tier.value}")
    try:
        await bot.send_message(tg_id, f"🎫 Админ выдал тебе подписку: {tier.value}")
    except Exception:
        pass


# ---------- ban / unban ----------

@router.callback_query(F.data == "adm:ban")
async def ban_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.ban)
    await cb.message.answer(
        "Отправь <code>tg_id</code> — статус бана переключится (бан ↔ разбан).",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.ban, F.text)
async def ban_toggle(
    message: Message, state: FSMContext, session: AsyncSession, is_admin: bool, bot: Bot
):
    if not is_admin:
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Формат: <code>tg_id</code>", reply_markup=cancel_kb("ru"))
        return
    target = (
        await session.execute(select(User).where(User.tg_id == tg_id))
    ).scalar_one_or_none()
    if target is None:
        await message.answer("Пользователь не найден.", reply_markup=cancel_kb("ru"))
        return
    target.is_banned = not target.is_banned
    await session.execute(
        update(Video)
        .where(Video.owner_id == target.id)
        .values(is_active=not target.is_banned)
    )
    await session.commit()
    await state.clear()
    status = "🔒 забанен" if target.is_banned else "🔓 разбанен"
    await message.answer(f"✅ @{target.username or tg_id} {status}.")
    if not target.is_banned:
        try:
            await bot.send_message(tg_id, "🔓 Тебя разбанили. Добро пожаловать обратно!")
        except Exception:
            pass


# ---------- promo codes ----------

@router.callback_query(F.data == "adm:promo")
async def promo_menu(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    promos = (
        (await session.execute(select(PromoCode).where(PromoCode.is_active.is_(True))))
        .scalars()
        .all()
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Создать промокод", callback_data="adm:promo:add")
    lines = []
    for p in promos:
        reward = []
        if p.coins:
            reward.append(f"{p.coins} 🪙")
        if p.sub_tier:
            reward.append(f"{p.sub_tier} ({p.sub_days or '∞'} дн)")
        lines.append(
            f"<code>{p.code}</code> — {', '.join(reward) or '—'} — {p.used_count}/{p.max_uses or '∞'}"
        )
        kb.button(text=f"🗑 {p.code}", callback_data=f"adm:promo:del:{p.id}")
    kb.adjust(1)
    await cb.message.answer(
        "🏷 <b>Промокоды</b>\n\n" + ("\n".join(lines) or "Пока нет промокодов."),
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:promo:add")
async def promo_add_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.promo_add)
    await cb.message.answer(
        "Отправь: <code>КОД монеты активации [тир дни]</code>\n"
        "Активации: 0 = безлимит. Тир (необяз.): a+ / a++ / premium, дни 0 = навсегда\n\n"
        "Примеры:\n"
        "<code>BONUS50 50 100</code> — 50 🪙, 100 активаций\n"
        "<code>VIP 0 5 premium 0</code> — PREMIUM навсегда, 5 активаций\n\n"
        "❌ Отмена - /cancel",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.promo_add, F.text)
async def promo_add(message: Message, state: FSMContext, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    parts = message.text.split()
    try:
        code, coins, max_uses = parts[0], int(parts[1]), int(parts[2])
        tier = None
        days = 0
        if len(parts) >= 4:
            tier = TIER_ALIASES[parts[3].lower()].value
            days = int(parts[4]) if len(parts) >= 5 else 0
    except (ValueError, KeyError, IndexError):
        await message.answer(
            "❌ Неверный формат. Пример: <code>BONUS50 50 100</code>",
            reply_markup=cancel_kb("ru"),
        )
        return
    existing = (
        await session.execute(select(PromoCode).where(func.lower(PromoCode.code) == code.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        await message.answer("❌ Такой промокод уже есть.", reply_markup=cancel_kb("ru"))
        return
    session.add(
        PromoCode(code=code, coins=coins, max_uses=max_uses, sub_tier=tier, sub_days=days)
    )
    await session.commit()
    await state.clear()
    await message.answer(f"✅ Промокод <code>{code}</code> создан.")


@router.callback_query(F.data.startswith("adm:promo:del:"))
async def promo_delete(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    promo = await session.get(PromoCode, int(cb.data.split(":")[3]))
    if promo:
        promo.is_active = False
        await session.commit()
    await cb.answer("Удалено")
    await cb.message.delete()


# ---------- pending payments ----------

# semi-automatic methods: the user sends a receipt, an admin confirms it
RECEIPT_METHODS = ("manual", "card", "sbp")
METHOD_LABELS = {
    "manual": "CryptoWallet 💶",
    "card": "Карта 💳",
    "sbp": "СБП 📱",
}


@router.callback_query(F.data == "adm:payments")
async def pending_payments(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    payments = (
        (
            await session.execute(
                select(Payment).where(
                    Payment.status == "pending",
                    Payment.method.in_(RECEIPT_METHODS),
                    Payment.screenshot_file_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    await cb.answer()
    if not payments:
        await cb.message.answer("Нет ожидающих пополнений.")
        return
    for p in payments:
        user = await session.get(User, p.user_id)
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Подтвердить", callback_data=f"adm:pay:ok:{p.id}")
        kb.button(text="❌ Отклонить", callback_data=f"adm:pay:no:{p.id}")
        caption = (
            f"<b>💰 Подтвердите покупку #{p.id}.</b>\n\n"
            f"👤 Пользователь: @{user.username or user.tg_id} "
            f"{user.full_name or ''} ({user.tg_id})\n"
            f"📦 Товар: {p.coins} 🪙\n"
            f"💰 Сумма: <b>{p.amount_rub} RUB</b>\n"
            f"💳 Способ оплаты: {METHOD_LABELS.get(p.method, p.method)}\n\n"
            f"<b>Подтвердить выдачу товара?</b>"
        )
        if p.screenshot_file_id:
            await cb.message.answer_photo(p.screenshot_file_id, caption=caption, reply_markup=kb.as_markup())
        else:
            await cb.message.answer(caption, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("adm:pay:"))
async def payment_decision(
    cb: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    is_admin: bool,
    bot: Bot,
):
    if not is_admin:
        await cb.answer()
        return
    _, _, decision, pid = cb.data.split(":")
    payment = await session.get(Payment, int(pid))
    if payment is None or payment.status != "pending":
        await cb.answer("Уже обработано.")
        return
    user = await session.get(User, payment.user_id)
    if decision == "ok":
        payment.status = "paid"
        user.balance += payment.coins
        session.add(
            Purchase(
                user_id=user.id,
                kind="coins",
                description=f"Оплата скрином: +{payment.coins}",
                amount_coins=payment.coins,
            )
        )
        await session.commit()
        try:
            await bot.send_message(user.tg_id, t(user.lang, "manual_approved", coins=payment.coins))
        except Exception:
            pass
        admin_text = (
            f"<b>💰 Новая покупка (полуавтоматическая).</b>\n\n"
            f"<b>👤 Пользователь @{user.username or user.tg_id} "
            f"{user.full_name or ''}, (ID: {user.tg_id}) купил продукт: "
            f"{payment.coins} 🪙 за {payment.amount_rub} RUB</b>\n\n"
            f"<b>💵 Способ оплаты: {METHOD_LABELS.get(payment.method, payment.method)}</b>"
        )
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception:
                pass
        await cb.answer("✅ Подтверждено")
    elif decision == "no":
        kb = InlineKeyboardBuilder()
        kb.button(text="📝 Указать причину", callback_data=f"adm:pay:reason:{pid}")
        kb.button(text="⏭️ Пропустить", callback_data=f"adm:pay:skip:{pid}")
        await cb.message.answer(
            "❌ Выберите способ отклонения оплаты:", reply_markup=kb.as_markup()
        )
        await cb.answer()
        return
    elif decision == "reason":
        await state.set_state(AdminStates.decline_reason)
        await state.update_data(decline_payment_id=int(pid))
        await cb.message.answer("📝 Введите причину отклонения оплаты:")
        await cb.answer()
        return
    else:  # skip -> decline without a reason
        payment.status = "rejected"
        await session.commit()
        try:
            await bot.send_message(user.tg_id, t(user.lang, "manual_rejected"))
        except Exception:
            pass
        await cb.answer("❌ Отклонено")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.message(AdminStates.decline_reason, F.text)
async def decline_reason_input(
    message: Message, state: FSMContext, session: AsyncSession, is_admin: bool, bot: Bot
):
    if not is_admin:
        return
    data = await state.get_data()
    await state.clear()
    payment = await session.get(Payment, int(data["decline_payment_id"]))
    if payment is None or payment.status != "pending":
        await message.answer("Уже обработано.")
        return
    payment.status = "rejected"
    user = await session.get(User, payment.user_id)
    await session.commit()
    try:
        await bot.send_message(
            user.tg_id,
            t(user.lang, "manual_rejected_reason", reason=message.text.strip()[:500]),
        )
    except Exception:
        pass
    await message.answer("✅ Оплата отклонена с указанной причиной.")


# ---------- withdrawals ----------

@router.callback_query(F.data == "adm:withdrawals")
async def withdrawals(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    rows = (
        (await session.execute(select(Withdrawal).where(Withdrawal.status == "pending")))
        .scalars()
        .all()
    )
    await cb.answer()
    if not rows:
        await cb.message.answer("Нет заявок на вывод.")
        return
    for w in rows:
        user = await session.get(User, w.user_id)
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Выплачено", callback_data=f"adm:wd:ok:{w.id}")
        kb.button(text="❌ Отклонить", callback_data=f"adm:wd:no:{w.id}")
        await cb.message.answer(
            f"💸 Вывод #{w.id} — @{user.username or user.tg_id}\n"
            f"Заработано: {user.author_earned} 🪙\n{w.details}",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(F.data.startswith("adm:wd:"))
async def withdrawal_decision(cb: CallbackQuery, session: AsyncSession, is_admin: bool, bot: Bot):
    if not is_admin:
        await cb.answer()
        return
    _, _, decision, wid = cb.data.split(":")
    w = await session.get(Withdrawal, int(wid))
    if w is None or w.status != "pending":
        await cb.answer("Уже обработано.")
        return
    user = await session.get(User, w.user_id)
    is_partner_wd = w.details.startswith("[PARTNER")
    if decision == "ok":
        w.status = "paid"
        if is_partner_wd:
            user.partner_withdrawn_rub += w.amount
            user.partner_pending_rub = max(0, user.partner_pending_rub - w.amount)
        else:
            user.author_earned = 0
        msg = "✅ Твоя заявка на вывод выплачена!"
    else:
        w.status = "rejected"
        if is_partner_wd:
            user.partner_balance_rub += w.amount
            user.partner_pending_rub = max(0, user.partner_pending_rub - w.amount)
        msg = "❌ Заявка на вывод отклонена."
    await session.commit()
    try:
        await bot.send_message(user.tg_id, msg)
    except Exception:
        pass
    await cb.answer("Готово")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ---------- settings / prices ----------

@router.callback_query(F.data == "adm:settings")
async def settings_menu(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    lines = []
    for key in DEFAULT_SETTINGS:
        value = await get_setting(session, key)
        lines.append(f"<code>{key}</code> = <code>{json.dumps(value, ensure_ascii=False)}</code>")
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data="adm:set")
    await cb.message.answer(
        "💲 Настройки:\n\n" + "\n".join(lines) +
        "\n\ncoin_packs — пакеты монет {монеты: цена ₽}\n"
        "sub_* — подписки {price, days (0=навсегда), daily_limit (0=безлимит)}\n"
        "view_price — цена просмотра кружка\n"
        "start_balance — баланс на старте\n"
        "referral_reward — награда за реферала\n"
        "recommend_every — 📢 Рекомендация каждые N кружков",
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data == "adm:set")
async def setting_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.setting_value)
    await cb.message.answer(
        "Отправь: <code>ключ значение_в_JSON</code>\n"
        "Например: <code>view_price 2</code> или "
        "<code>coin_packs {\"10\": 20, \"50\": 100}</code>",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.setting_value, F.text)
async def setting_save(message: Message, state: FSMContext, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    try:
        key, raw = message.text.split(maxsplit=1)
        if key not in DEFAULT_SETTINGS:
            raise ValueError
        value = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        await message.answer("❌ Неверный формат или ключ.", reply_markup=cancel_kb("ru"))
        return
    await set_setting(session, key, value)
    await state.clear()
    await message.answer("✅ Сохранено.")


# ---------- sponsors ----------

async def _sponsors_menu_view(session: AsyncSession):
    sponsors = (
        (await session.execute(select(Sponsor).where(Sponsor.is_active.is_(True)))).scalars().all()
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить спонсора", callback_data="adm:sp:add")
    for sp in sponsors:
        req = {
            "required": "🔒 обязательная",
            "optional": "🆓 необязательная",
            "recommend": "📢 рекомендация",
        }.get(sp.kind, "🔒 обязательная")
        kb.button(text=f"{req} · {sp.title} · {sp.reward_coins} 🪙", callback_data=f"adm:sp:req:{sp.id}")
        kb.button(text=f"🗑 Удалить «{sp.title}»", callback_data=f"adm:sp:del:{sp.id}")
    kb.adjust(1)
    text = (
        "📢 <b>Спонсоры</b>\n\n"
        "🔒 обязательная — бот не работает без подписки на канал\n"
        "🆓 необязательная — показывается в «Монеты бесплатно»\n"
        "📢 рекомендация — рекламируется во время просмотра кружков\n\n"
        "Нажми на спонсора, чтобы переключить тип."
    )
    return text, kb.as_markup()


@router.callback_query(F.data == "adm:sponsors")
async def sponsors_menu(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    text, kb = await _sponsors_menu_view(session)
    await cb.message.answer(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:sp:req:"))
async def sponsor_toggle_required(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    sp = await session.get(Sponsor, int(cb.data.split(":")[3]))
    labels = {
        "required": "🔒 Обязательная подписка",
        "optional": "🆓 Необязательная",
        "recommend": "📢 Рекомендация при просмотре",
    }
    if sp:
        sp.kind = {"required": "optional", "optional": "recommend"}.get(
            sp.kind, "required"
        )
        sp.required = sp.kind == "required"
        if sp.kind == "recommend":
            sp.reward_coins = 0
        await session.commit()
    text, kb = await _sponsors_menu_view(session)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await cb.answer(labels.get(sp.kind, "?") if sp else "?")


@router.callback_query(F.data == "adm:sp:add")
async def sponsor_add_start(cb: CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    await state.set_state(AdminStates.sponsor_add)
    await cb.message.answer(
        "Отправь ссылку на канал или его @username одним сообщением.\n"
        "Например: <code>@mychannel</code> или <code>https://t.me/mychannel</code>\n\n"
        "⚠️ Бот должен быть админом канала, иначе он не сможет проверять подписку.",
        reply_markup=cancel_kb("ru"),
    )
    await cb.answer()


@router.message(AdminStates.sponsor_add, F.text)
async def sponsor_add(
    message: Message, state: FSMContext, session: AsyncSession, is_admin: bool, bot: Bot
):
    if not is_admin:
        return
    raw = message.text.strip()
    username = raw
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "https://telegram.me/", "telegram.me/"):
        if username.lower().startswith(prefix):
            username = username[len(prefix):]
            break
    username = username.strip().strip("/").split("?")[0]
    from bot.services import mirrors as mirrors_service

    check_bot = mirrors_service.main_bot or bot
    try:
        if username.lstrip("-").isdigit():
            chat = await check_bot.get_chat(int(username))
        else:
            chat = await check_bot.get_chat("@" + username.lstrip("@"))
    except Exception:
        await message.answer(
            "❌ Не нашёл такой канал. Проверь ссылку и что бот добавлен админом в канал, и отправь ещё раз.",
            reply_markup=cancel_kb("ru"),
        )
        return
    link = f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or raw)
    await state.update_data(sp_chat_id=chat.id, sp_title=chat.title or username, sp_link=link)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔒 Обязательная (ОП)", callback_data="adm:sp:type:required")
    kb.button(text="🆓 Необязательная (за монеты)", callback_data="adm:sp:type:optional")
    kb.button(text="📢 Рекомендация при просмотре", callback_data="adm:sp:type:recommend")
    kb.adjust(1)
    await message.answer(
        f"✅ Канал найден: <b>{chat.title}</b>\n\nВыбери тип спонсора:",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("adm:sp:type:"))
async def sponsor_type(cb: CallbackQuery, state: FSMContext, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    kind = cb.data.split(":")[3]
    if kind not in ("required", "optional", "recommend"):
        await cb.answer()
        return
    await state.update_data(sp_kind=kind)
    await cb.answer()
    if kind == "recommend":
        # recommend sponsors don't pay for subscriptions — no reward question
        data = await state.get_data()
        sponsor = Sponsor(
            chat_id=data["sp_chat_id"],
            title=data["sp_title"],
            invite_link=data["sp_link"],
            required=False,
            kind="recommend",
            reward_coins=0,
        )
        session.add(sponsor)
        await session.commit()
        await state.clear()
        await cb.message.answer(
            f"✅ Спонсор «{sponsor.title}» добавлен (📢 рекомендация при просмотре)."
        )
        return
    await state.set_state(AdminStates.sponsor_reward)
    await cb.message.answer(
        "Сколько монет давать за подписку? Отправь число (например <code>2</code>, или <code>0</code> — без награды):",
        reply_markup=cancel_kb("ru"),
    )


@router.message(AdminStates.sponsor_reward, F.text)
async def sponsor_reward(message: Message, state: FSMContext, session: AsyncSession, is_admin: bool):
    if not is_admin:
        return
    try:
        reward = max(0, int(message.text.strip()))
    except ValueError:
        await message.answer("❌ Отправь число, например <code>2</code>:", reply_markup=cancel_kb("ru"))
        return
    data = await state.get_data()
    kind = data.get("sp_kind", "required")
    sponsor = Sponsor(
        chat_id=data["sp_chat_id"],
        title=data["sp_title"],
        invite_link=data["sp_link"],
        required=kind == "required",
        kind=kind,
        reward_coins=reward,
    )
    session.add(sponsor)
    await session.commit()
    await state.clear()
    req = "🔒 обязательная подписка" if kind == "required" else "🆓 необязательная"
    await message.answer(f"✅ Спонсор «{sponsor.title}» добавлен ({req}, {reward} 🪙).")


@router.callback_query(F.data.startswith("adm:sp:del:"))
async def sponsor_delete(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    sp = await session.get(Sponsor, int(cb.data.split(":")[3]))
    if sp:
        sp.is_active = False
        await session.commit()
    await cb.answer("Удалено")
    await cb.message.delete()


# ---------- mirrors ----------

@router.callback_query(F.data == "adm:mirrors")
async def mirrors_list(cb: CallbackQuery, session: AsyncSession, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    mirrors = await mirror_store.active_mirrors()
    await cb.answer()
    if not mirrors:
        await cb.message.answer("Зеркал нет.")
        return
    kb = InlineKeyboardBuilder()
    for m in mirrors:
        owner = await session.get(User, m.owner_id)
        prem = "⭐️" if m.is_premium else ""
        kb.button(
            text=f"🗑 @{m.bot_username} {prem} (владелец @{owner.username or owner.tg_id})",
            callback_data=f"mir:del:{m.id}",
        )
    kb.adjust(1)
    await cb.message.answer("🤖 Активные зеркала:", reply_markup=kb.as_markup())


# ---------- test payment (admin only) ----------

@router.callback_query(F.data == "adm:testpay")
async def test_pay(cb: CallbackQuery, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="🪙 Тест CryptoBot (1$)", callback_data="adm:test:crypto")
    kb.button(text="⭐️ Тест Stars (1⭐)", callback_data="adm:test:stars")
    kb.adjust(1)
    await cb.message.answer("🧪 Тестовая оплата (только для админа):", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "adm:test:crypto")
async def test_crypto(cb: CallbackQuery, is_admin: bool):
    if not is_admin:
        await cb.answer()
        return
    invoice = await cryptopay.create_invoice(1.0, "Test payment (admin)")
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить 1$", url=invoice.bot_invoice_url)
    await cb.message.answer("Тестовый счёт CryptoBot:", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "adm:test:stars")
async def test_stars(cb: CallbackQuery, is_admin: bool, bot: Bot):
    if not is_admin:
        await cb.answer()
        return
    await bot.send_invoice(
        chat_id=cb.message.chat.id,
        title="Test",
        description="Test payment (admin)",
        payload="test",
        currency="XTR",
        prices=[LabeledPrice(label="test", amount=1)],
    )
    await cb.answer()
