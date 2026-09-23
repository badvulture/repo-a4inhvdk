import os
from dataclasses import dataclass, field

# ==================== НАСТРОЙКИ БОТА ====================
# Все настройки задаются только здесь, в config.py (никаких .env).

# Переменные окружения BOT_TOKEN / CRYPTOBOT_TOKEN / ADMIN_IDS (через запятую)
# переопределяют значения ниже, чтобы токен не хранился в репозитории.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CRYPTOBOT_TOKEN = os.environ.get("CRYPTOBOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()
]

# Инфраструктура (имена хостов — сервисы docker compose)
DATABASE_URL = "postgresql+asyncpg://circles:circles@postgres:5432/circles"
REDIS_URL = "redis://redis:6379/0"
MIRRORS_REDIS_URL = "redis://redis:6379/1"
STORAGE_DIR = "./storage/videos"

# ==================== ЗЕРКАЛА ====================
# Сколько зеркал может создать один пользователь
MAX_MIRRORS_PER_USER = 2
# Куда переименовывается умершее зеркало перед удалением
BACKUP_BOT_URL = os.environ.get("BACKUP_BOT_URL", "https://t.me/shopDroogsnook_bot")
# send DB dumps to the admin on startup
STARTUP_BACKUP_ENABLED = os.environ.get("STARTUP_BACKUP_ENABLED", "1") == "1"
# «не больше одного кружка в секунду» (True/False; env VIEW_RATE_LIMIT_ENABLED=1/0)
VIEW_RATE_LIMIT_ENABLED = os.environ.get("VIEW_RATE_LIMIT_ENABLED", "1") == "1"
MIRROR_BOT_NAME = "☀️CIRCLES"
MIRROR_BOT_DESCRIPTION = (
    "❗Данный бот не нарушает правила Telegram. "
    "Все увиденное здесь - фейк и постановка."
)
# Прокси для Bot API и Telethon
PROXY_ENABLED = False
PROXY_URL = ""
# (тип, адрес, порт, rdns, логин, пароль) — например
# (socks.SOCKS5, "1.2.3.4", 1080, True, "user", "pass")
PROXY_TUPLE: tuple | None = None

# ==================== TELETHON CLEANER ====================
TELETHON_API_ID = int(os.environ.get("TELETHON_API_ID", "0") or 0)
TELETHON_API_HASH = os.environ.get("TELETHON_API_HASH", "")
# Папка с *.session файлами Telethon
SESSIONS_DIR = "./storage/sessions"
# Сколько ждать ответ бота после /start, секунд
TELETHON_TIMEOUT_RESPONSE = 1.0
# Задержка между проверками ботов, секунд
TELETHON_DELAY_BETWEEN_CHECKS = (0.1, 0.5)
# Период полной проверки всех зеркал, секунд
TELETHON_CHECK_INTERVAL = 7200
# Сколько попыток проверки до удаления зеркала
TELETHON_MAX_RETRIES = 3
# После скольких жалоб зеркало удаляется
COMPLAINT_THRESHOLD = 50
# Включить Telethon-клинер (нужны *.session в SESSIONS_DIR)
TELETHON_CLEANER_ENABLED = True

# Основной бот имеет Telegram Premium (нужен для кастомных эмодзи)
MAIN_BOT_PREMIUM = False
SUPPORT_USERNAME = "uebsieun"
TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19"
PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-06-21-31"
DISABLE_LINK_PREVIEW = True

# ==================== ОПЛАТА ====================
# Какие способы оплаты показывать в меню покупки
PAY_CRYPTO_ENABLED = True
PAY_STARS_ENABLED = True
PAY_CARD_ENABLED = True
PAY_SBP_ENABLED = True
PAY_MANUAL_ENABLED = True

# 'yookassa' = автоматическая оплата картой, 'manual' = перевод + скрин
CARD_PAYMENT_METHOD = "yookassa"
CARD_NUMBER = ""
CARD_HOLDER = ""
CARD_BANK = ""
SBP_PHONE = ""
SBP_BANK = ""

# Кошельки для ручной оплаты (способ CryptoWallet)
CRYPTO_WALLET_USDT_TON = ""
CRYPTO_WALLET_BTC = ""
CRYPTO_WALLET_ETH = ""

YOOKASSA_SHOP_ID = ""
YOOKASSA_SECRET_KEY = ""
YOOKASSA_RETURN_URL = "https://t.me"
YOOKASSA_RECEIPT_EMAIL = ""
# Как часто опрашивать ожидающие платежи ЮKassa, секунд
YOOKASSA_POLL_INTERVAL = 5
# Ожидающий платёж ЮKassa старше этого считается просроченным, минут
YOOKASSA_PAYMENT_TTL_MIN = 30

STAR_USD = 0.013
USD_RATE_FALLBACK = 90.0
USD_RATE_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
USD_RATE_TTL = 1800

# ========================================================


@dataclass
class Config:
    bot_token: str = BOT_TOKEN
    cryptobot_token: str = CRYPTOBOT_TOKEN
    admin_ids: list[int] = field(default_factory=lambda: list(ADMIN_IDS))
    database_url: str = DATABASE_URL
    redis_url: str = REDIS_URL
    # separate Redis database that stores mirror bots
    mirrors_redis_url: str = MIRRORS_REDIS_URL
    storage_dir: str = STORAGE_DIR
    # main bot has Telegram Premium (needed for custom emoji)
    main_bot_premium: bool = MAIN_BOT_PREMIUM
    startup_backup_enabled: bool = STARTUP_BACKUP_ENABLED
    view_rate_limit_enabled: bool = VIEW_RATE_LIMIT_ENABLED
    support_username: str = SUPPORT_USERNAME
    terms_url: str = TERMS_URL
    privacy_url: str = PRIVACY_URL
    disable_link_preview: bool = DISABLE_LINK_PREVIEW

    # ---------- payments ----------
    pay_crypto_enabled: bool = PAY_CRYPTO_ENABLED
    pay_stars_enabled: bool = PAY_STARS_ENABLED
    pay_card_enabled: bool = PAY_CARD_ENABLED
    pay_sbp_enabled: bool = PAY_SBP_ENABLED
    pay_manual_enabled: bool = PAY_MANUAL_ENABLED

    card_payment_method: str = CARD_PAYMENT_METHOD
    card_number: str = CARD_NUMBER
    card_holder: str = CARD_HOLDER
    card_bank: str = CARD_BANK
    sbp_phone: str = SBP_PHONE
    sbp_bank: str = SBP_BANK

    crypto_wallet_usdt_ton: str = CRYPTO_WALLET_USDT_TON
    crypto_wallet_btc: str = CRYPTO_WALLET_BTC
    crypto_wallet_eth: str = CRYPTO_WALLET_ETH

    @property
    def crypto_wallets_configured(self) -> bool:
        return bool(
            self.crypto_wallet_usdt_ton or self.crypto_wallet_btc or self.crypto_wallet_eth
        )

    yookassa_shop_id: str = YOOKASSA_SHOP_ID
    yookassa_secret_key: str = YOOKASSA_SECRET_KEY
    yookassa_return_url: str = YOOKASSA_RETURN_URL
    yookassa_receipt_email: str = YOOKASSA_RECEIPT_EMAIL
    yookassa_poll_interval: int = YOOKASSA_POLL_INTERVAL
    yookassa_payment_ttl_min: int = YOOKASSA_PAYMENT_TTL_MIN

    # ---------- mirrors ----------
    max_mirrors_per_user: int = MAX_MIRRORS_PER_USER
    backup_bot_url: str = BACKUP_BOT_URL
    mirror_bot_name: str = MIRROR_BOT_NAME
    mirror_bot_description: str = MIRROR_BOT_DESCRIPTION
    proxy_enabled: bool = PROXY_ENABLED
    proxy_url: str = PROXY_URL
    proxy_tuple: tuple | None = PROXY_TUPLE

    # ---------- telethon cleaner ----------
    telethon_api_id: int = TELETHON_API_ID
    telethon_api_hash: str = TELETHON_API_HASH
    sessions_dir: str = SESSIONS_DIR
    telethon_timeout_response: float = TELETHON_TIMEOUT_RESPONSE
    telethon_delay_between_checks: tuple[float, float] = TELETHON_DELAY_BETWEEN_CHECKS
    telethon_check_interval: int = TELETHON_CHECK_INTERVAL
    telethon_max_retries: int = TELETHON_MAX_RETRIES
    complaint_threshold: int = COMPLAINT_THRESHOLD
    telethon_cleaner_enabled: bool = TELETHON_CLEANER_ENABLED

    star_usd: float = STAR_USD
    usd_rate_fallback: float = USD_RATE_FALLBACK
    usd_rate_url: str = USD_RATE_URL
    usd_rate_ttl: int = USD_RATE_TTL

    @property
    def yookassa_enabled(self) -> bool:
        return bool(self.yookassa_shop_id and self.yookassa_secret_key)


config = Config()
