import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.db.models import User
from bot.keyboards import main_menu
from bot.locales.texts import t

log = logging.getLogger(__name__)
router = Router()


@router.message()
async def handle_unknown(message: Message, state: FSMContext, user: User | None, lang: str):
    """Catches every message no other handler took: must stay the last router."""
    if await state.get_state() is not None:
        await state.clear()
        await message.answer(t(lang, "unknown_state_reset"), reply_markup=main_menu(lang))
        return
    if user is None:
        await message.answer(t(lang, "unknown_no_user"))
        return
    await message.answer(t(lang, "unknown_command"), reply_markup=main_menu(lang))
