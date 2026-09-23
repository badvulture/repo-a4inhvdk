"""Premium (custom) emoji support.

Outgoing message texts/captions get known emoji wrapped in <tg-emoji> tags.
Custom emoji entities only work for bots that bought a Fragment username,
so on failure the request is retried with plain emoji.
Inline/reply keyboard buttons cannot contain custom emoji (Telegram limit).
"""

import re

from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.methods import (
    EditMessageCaption,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    SendPhoto,
    SendVideo,
    SendVideoNote,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

_BASE_IDS = {
    "👋": "5985478698722136468",
    "🎥": "5884252508603289902",
    "▶️": "5773626993010546707",
    "📤": "6039573425268201570",
    "💰": "5778421276024509124",
    "⭐️": "6028338546736107668",
    "📝": "5778299625370817409",
    "🌐": "5776233299424843260",
    "🎉": "6041731551845159060",
    "👍": "6041720006973067267",
    "👎": "6041716699848249286",
    "👑": "5805553606635559688",
    "💎": "5776023601941582822",
    "📈": "5935913431801532272",
    "📦": "5778672437122045013",
    "🔒": "5776227595708273495",
    "🔓": "6037496202990194718",
    "🤖": "5983580310292402968",
    "➕": "5882207227997066107",
    "✨": "5778226250149532337",
    "💬": "5767244474040192942",
    "🔔": "6039486778597970865",
    "📸": "5879995903955179148",
    "⌛️": "5891211339170326418",
    # ids provided by the owner
    "⚙️": "5870982283724328568",
    "👤": "5870994129244131212",
    "👥": "5870772616305839506",
    "📁": "5870528606328852614",
    "🙂": "5870764288364252592",
    "📊": "5870921681735781843",
    "🏘": "5873147866364514353",
    "✅": "5870633910337015697",
    "❌": "5870657884844462243",
    "🖋": "5870676941614354370",
    "🗑": "5870875489362513438",
    "📎": "6039451237743595514",
    "🔗": "5769289093221454192",
    "ℹ️": "6028435952299413210",
    "👁": "6037397706505195857",
    "⬆️": "5963103826075456248",
    "⬇️": "6039802767931871481",
    "🎁": "6032644646587338669",
    "⏰": "5983150113483134607",
    "✍️": "5870753782874246579",
    "🖼": "6035128606563241721",
    "📍": "6042011682497106307",
    "👛": "5769126056262898415",
    "👾": "5260752406890711732",
    "📅": "5890937706803894250",
    "🏷": "5886285355279193209",
    "🪙": "5904462880941545555",
    "🏧": "5879814368572478751",
    "🔨": "5940433880585605708",
    "🔄": "5345906554510012647",
    "📢": "6039422865189638057",
    "⬅️": "5960671702059848143",
    "📂": "6037373985400819577",
    "🙁": "5778197572652897847",
    "🎞": "5937999673510858217",
    "📄": "6034969813032374911",
    # no exact premium art exists — use the closest one
    "⏳": "5891211339170326418",
    "👀": "6037397706505195857",
    "🎬": "5937999673510858217",
    "💲": "5904462880941545555",
    "💳": "5769126056262898415",
    "💸": "5890848474563352982",
    "😔": "5778197572652897847",
    "😕": "5778197572652897847",
    "🛒": "5884479287171485878",
    "🧾": "6034969813032374911",
    "🎫": "5886285355279193209",
    "🆓": "6032644646587338669",
    "⚠️": "6028435952299413210",
    "⚖️": "5870921681735781843",
    "➡️": "5778593237925105705",
    "⏭️": "5778593237925105705",
    "✏️": "5870676941614354370",
    "🛠": "5870982283724328568",
    "🧪": "5940433880585605708",
    "📣": "6039422865189638057",
    "🇷🇺": "5776233299424843260",
    "🆘": "5767244474040192942",
    "❓": "6028435952299413210",
    "🔞": "5937999673510858217",
    "👇": "6039802767931871481",
    "🇬🇧": "5776233299424843260",
    "💵": "5778421276024509124",
    "💶": "5769126056262898415",
    "📱": "5983580310292402968",
    "🚀": "5778226250149532337",
    "🤝": "5870772616305839506",
    "🏆": "5805553606635559688",
    "♦️": "5776023601941582822",
    "♣️": "5776023601941582822",
    "❗️": "6028435952299413210",
    "🚫": "5870657884844462243",
    "🛑": "5870657884844462243",
    "📨": "5767244474040192942",
    "📛": "6028435952299413210",
    "💻": "5870982283724328568",
    "🪞": "5983580310292402968",
    "👨": "5870994129244131212",
}

VS16 = "\ufe0f"

# accept emoji both with and without the variation selector
PREMIUM_IDS: dict[str, str] = {}
for _e, _i in _BASE_IDS.items():
    PREMIUM_IDS[_e] = _i
    PREMIUM_IDS.setdefault(_e.rstrip(VS16), _i)
    PREMIUM_IDS.setdefault(_e.rstrip(VS16) + VS16, _i)

_ALTERNATION = "|".join(
    re.escape(e) for e in sorted(PREMIUM_IDS, key=len, reverse=True)
)
_PATTERN = re.compile(_ALTERNATION)
_LEADING = re.compile(f"^({_ALTERNATION})\\s*")
_TRAILING = re.compile(f"\\s*({_ALTERNATION})$")


def strip_leading_emoji(text: str) -> str:
    """Button text as Telegram sends it back when the emoji became an icon."""
    m = _LEADING.match(text)
    return text[m.end():].strip() if m else text


def pe(text: str) -> str:
    """Wrap known emoji in <tg-emoji> tags."""
    return _PATTERN.sub(
        lambda m: f'<tg-emoji emoji-id="{PREMIUM_IDS[m.group(0)]}">{m.group(0)}</tg-emoji>',
        text,
    )


def _iconize_markup(markup):
    """Move a leading known emoji of every button into icon_custom_emoji_id."""
    if isinstance(markup, (InlineKeyboardMarkup, ReplyKeyboardMarkup)):
        rows = markup.inline_keyboard if isinstance(markup, InlineKeyboardMarkup) else markup.keyboard
        changed = False
        new_rows = []
        for row in rows:
            new_row = []
            for btn in row:
                m = _LEADING.match(btn.text)
                stripped = btn.text[m.end():].strip() if m else ""
                if not (m and stripped):
                    m = _TRAILING.search(btn.text)
                    stripped = btn.text[: m.start()].strip() if m else ""
                if m and stripped and btn.icon_custom_emoji_id is None:
                    new_row.append(
                        btn.model_copy(
                            update={
                                "icon_custom_emoji_id": PREMIUM_IDS[m.group(1)],
                                "text": stripped,
                            }
                        )
                    )
                    changed = True
                else:
                    new_row.append(btn)
            new_rows.append(new_row)
        if changed:
            if isinstance(markup, InlineKeyboardMarkup):
                return markup.model_copy(update={"inline_keyboard": new_rows})
            return markup.model_copy(update={"keyboard": new_rows})
    return None


class PremiumEmojiMiddleware(BaseRequestMiddleware):
    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot,
        method: TelegramMethod[TelegramType],
    ) -> TelegramType:
        update: dict = {}
        if isinstance(method, (SendMessage, EditMessageText)) and method.text:
            new = pe(method.text)
            if new != method.text:
                update["text"] = new
        elif (
            isinstance(method, (SendPhoto, SendVideo, EditMessageCaption))
            and method.caption
        ):
            new = pe(method.caption)
            if new != method.caption:
                update["caption"] = new
        if isinstance(
            method,
            (
                SendMessage,
                SendPhoto,
                SendVideo,
                SendVideoNote,
                EditMessageText,
                EditMessageCaption,
                EditMessageReplyMarkup,
            ),
        ) and method.reply_markup is not None:
            new_markup = _iconize_markup(method.reply_markup)
            if new_markup is not None:
                update["reply_markup"] = new_markup
        if not update:
            return await make_request(bot, method)
        try:
            return await make_request(bot, method.model_copy(update=update))
        except Exception:
            # bot has no right to use custom emoji — send plain
            return await make_request(bot, method)
