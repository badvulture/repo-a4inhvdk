from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.locales.texts import t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_next_circle"))],
            [
                KeyboardButton(text=t(lang, "btn_profile")),
                KeyboardButton(text=t(lang, "btn_buy")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_view_profiles")),
                KeyboardButton(text=t(lang, "btn_buy_sub")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_mirrors")),
                KeyboardButton(text=t(lang, "btn_lang")),
            ],
        ],
        resize_keyboard=True,
    )


def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(2)
    return kb.as_markup()


async def smart_edit(message, text: str, reply_markup=None):
    """Edit the message in place when possible, otherwise send a new one."""
    try:
        if message.photo or message.video:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        await message.answer(text, reply_markup=reply_markup)


def back_kb(lang: str, callback_data: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_back"), callback_data=callback_data)
    return kb.as_markup()


def cancel_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_cancel"), callback_data="cancel")
    return kb.as_markup()
