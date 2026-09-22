from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import config
from bot.locales.texts import t

router = Router()


@router.message(Command("support"))
async def support_cmd(message: Message, lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(
        text=t(lang, "btn_support_link"),
        url=f"https://t.me/{config.support_username}",
    )
    await message.answer(
        t(lang, "support_text", username=config.support_username),
        reply_markup=kb.as_markup(),
    )


@router.message(Command("s"))
async def terms_cmd(message: Message, lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_terms"), url=config.terms_url)
    kb.button(text=t(lang, "btn_privacy"), url=config.privacy_url)
    kb.adjust(1)
    await message.answer(t(lang, "terms_text"), reply_markup=kb.as_markup())
