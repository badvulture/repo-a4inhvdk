from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import mirror_store
from bot.db.models import User
from bot.db.repo import add_balance, display_name, get_or_create_user, get_setting
from bot.keyboards import lang_kb, main_menu
from bot.locales.texts import btn_variants, t
from bot.services.video import MAIN_BOT_ID

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message, command: CommandObject, session: AsyncSession, bot: Bot
):
    referrer_id = None
    if command.args and command.args.startswith("p_"):
        partner = (
            await session.execute(
                select(User).where(
                    User.partner_code == command.args[2:], User.is_partner.is_(True)
                )
            )
        ).scalar_one_or_none()
        if partner:
            referrer_id = partner.tg_id
    elif command.args and command.args.startswith("ref_"):
        ref_owner = (
            await session.execute(
                select(User).where(User.ref_code == command.args[4:])
            )
        ).scalar_one_or_none()
        if ref_owner:
            referrer_id = ref_owner.tg_id
    elif command.args and command.args.startswith("ref"):
        try:
            referrer_id = int(command.args[3:])
        except ValueError:
            pass
    if referrer_id == message.from_user.id:
        referrer_id = None

    # users joining through a mirror count as the mirror owner's referrals
    if referrer_id is None and bot.id != MAIN_BOT_ID:
        mirror = await mirror_store.by_bot_id(bot.id)
        if mirror:
            owner = await session.get(User, mirror.owner_id)
            if owner and owner.tg_id != message.from_user.id:
                referrer_id = owner.tg_id

    user, created = await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name,
        referrer_id,
        message.from_user.first_name,
    )
    # the context middleware may create the user before this handler runs,
    # so a "fresh" user is one who has not picked a language yet
    is_new = created or not user.lang_chosen
    if is_new and user.referrer_id is None and referrer_id:
        user.referrer_id = referrer_id
        await session.commit()
        created = True
    if created and referrer_id:
        reward = int(await get_setting(session, "referral_reward"))
        await add_balance(session, referrer_id, reward)
        ref_user = (
            await session.execute(select(User).where(User.tg_id == referrer_id))
        ).scalar_one_or_none()
        if ref_user:
            try:
                await bot.send_message(
                    referrer_id, t(ref_user.lang, "ref_bonus", reward=reward)
                )
            except Exception:
                pass

    # first the language, then the captcha (in the chosen language)
    if not user.lang_chosen:
        await message.answer(t("ru", "choose_lang"), reply_markup=lang_kb())
        return

    if not user.captcha_passed:
        kb = InlineKeyboardBuilder()
        kb.button(text=t(user.lang, "btn_captcha"), callback_data="captcha:ok")
        await message.answer(
            t(user.lang, "captcha_text"), reply_markup=kb.as_markup()
        )
        return

    await message.answer(
        t(user.lang, "welcome_back", first_name=display_name(user)),
        reply_markup=main_menu(user.lang),
    )


@router.callback_query(F.data == "captcha:ok")
async def captcha_ok(cb: CallbackQuery, session: AsyncSession, user: User):
    first_time = not user.captcha_passed
    user.captcha_passed = True

    # a "live" user: credit the partner once
    if first_time and user.referrer_id and not user.partner_credited:
        referrer = (
            await session.execute(select(User).where(User.tg_id == user.referrer_id))
        ).scalar_one_or_none()
        if referrer and referrer.is_partner:
            reward_rub = float(await get_setting(session, "partner_reward_rub"))
            referrer.partner_balance_rub += reward_rub
            user.partner_credited = True
    await session.commit()

    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(
        t(user.lang, "start", first_name=display_name(user)),
        reply_markup=main_menu(user.lang),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(cb: CallbackQuery, session: AsyncSession, user: User):
    lang = cb.data.split(":")[1]
    user.lang = lang
    user.lang_chosen = True
    await session.commit()
    await cb.message.delete()
    if not user.captcha_passed:
        kb = InlineKeyboardBuilder()
        kb.button(text=t(lang, "btn_captcha"), callback_data="captcha:ok")
        await cb.message.answer(t(lang, "captcha_text"), reply_markup=kb.as_markup())
        await cb.answer()
        return
    await cb.message.answer(t(lang, "lang_set"))
    await cb.message.answer(
        t(lang, "welcome_back", first_name=display_name(user)),
        reply_markup=main_menu(lang),
    )
    await cb.answer()


@router.message(Command("lang"))
@router.message(F.text.in_(btn_variants("btn_lang")))
async def change_lang(message: Message, lang: str):
    await message.answer(t(lang, "choose_lang"), reply_markup=lang_kb())


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, lang: str, state: FSMContext):
    await state.clear()
    await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))


@router.callback_query(F.data == "check_subs")
async def check_subs(cb: CallbackQuery, user: User, lang: str):
    # forced-sub middleware re-checks membership; reaching here means all fine
    await cb.message.delete()
    await cb.message.answer(
        t(lang, "welcome_back", first_name=display_name(user)),
        reply_markup=main_menu(lang),
    )
    await cb.answer()


@router.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery, lang: str, state: FSMContext):
    await state.clear()
    await cb.message.delete()
    await cb.message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang))
    await cb.answer()
