from bot.services.premium_emoji import strip_leading_emoji

RU = {
    "choose_lang": "Выберите язык / Choose language:",
    "start": (
        "👋 <b>Привет, {first_name}!</b>\n\n"
        "🎥 Здесь ты смотришь <b>кружки</b> других людей и загружаешь свои.\n\n"
        "▶️ «Следующий кружок» — случайный кружок (1 🪙)\n"
        "📤 Загружай свои кружки и <b>зарабатывай монеты</b>\n"
        "🎫 С подпиской — просмотр бесплатно\n\n"
        "💰 На старте у тебя <b>5 🪙</b>. Погнали!"
    ),
    "welcome_back": (
        "👋 <b>С возвращением, {first_name}!</b>\n\n"
        "🎥 Здесь ты смотришь <b>кружки</b> других людей и загружаешь свои.\n\n"
        "▶️ «Следующий кружок» — случайный кружок (1 🪙)\n"
        "📤 Загружай свои кружки и <b>зарабатывай монеты</b>\n"
        "🎫 С подпиской — просмотр бесплатно"
    ),
    "spent_toast": "−{spent} 🪙\nБаланс: {balance} 🪙",
    "btn_next_circle": "▶️ Следующий кружок",
    "btn_profile": "👤 Профиль",
    "btn_buy": "💰 Приобрести",
    "btn_view_profiles": "👀 Смотреть профили",
    "btn_buy_sub": "🎫 Купить подписку",
    "btn_mirrors": "🤖 Мои зеркала",
    "btn_lang": "🌐 Язык",
    "no_videos": "😔 Пока нет кружков. Загрузи первый в профиле!",
    "no_balance": "😕 Недостаточно монет. Пополни баланс в «Приобрести» или купи подписку.",
    "daily_limit": "⏳ Дневной лимит просмотров по подписке исчерпан. Возвращайся завтра!",
    "too_fast": "⏳ <b>Подожди 2 сек.</b>\n<i>Не больше одного кружка в секунду.</i>",
    "free_view_toast": "🎁 Первый кружок бесплатно!",
    "send_failed": "⚠️ Не удалось отправить кружок, монеты возвращены.",
    "recommend_channel": "📢 Рекомендуем канал: <b>{title}</b>",
    "btn_recommend_open": "➡️ Перейти",
    "btn_recommend_hide": "🚫 Больше не показывать",
    "recommend_hidden": "Больше не будем показывать",
    "unsupported_media": "❌ Поддерживаются только видео, GIF и фото.",
    "convert_failed": "❌ Не удалось сделать кружок из этого файла.",
    "circle_caption": "🎬 <b>Кружок #{seq}</b> · автор #{author}\n👍 {likes} | 👎 {dislikes} | 👁 {views}",
    "btn_like": "👍",
    "btn_dislike": "👎",
    "btn_view_author": "👤 Посмотреть профиль",
    "btn_next": "▶️ Следующий кружок",
    "rated": "Оценка учтена!",
    "already_rated": "Ты уже оценивал этот кружок.",
    "profile": (
        "👤 <b>Твой профиль</b>\n\n"
        "🏷 ID: <code>{tg_id}</code>\n"
        "📤 Загружено кружков: <b>{uploaded}</b>\n"
        "⚖️ Оценки: 👍 <b>{likes}</b> | 👎 <b>{dislikes}</b>\n"
        "👁 Просмотрено кружков: <b>{viewed}</b>\n"
        "💰 Баланс: <b>{balance}</b> 🪙\n"
        "🎫 Подписка: <b>{sub}</b>\n\n"
        "Хочешь зарабатывать Кружки — жми «Профиль автора»"
    ),
    "sub_none": "нет",
    "sub_forever": "навсегда",
    "sub_until": "до {date}",
    "btn_upload": "📤 Загрузить кружок",
    "btn_my_circles": "🎬 Мои кружки",
    "btn_author_profile": "⭐️ Профиль автора",
    "btn_my_purchases": "🧾 Мои покупки",
    "btn_promo": "🏷 Ввести промокод",
    "promo_prompt": "🏷 Отправь промокод одним сообщением:\n\n❌ Отмена - /cancel",
    "promo_invalid": "❌ Промокод не найден или уже исчерпан.",
    "promo_used": "❌ Ты уже активировал этот промокод.",
    "promo_success": "🎉 Промокод активирован! Получено: {rewards}",
    "banned": "🔒 Ты заблокирован администратором.",
    "btn_support": "🆘 Поддержка",
    "support_text": "🆘 Возникли проблемы или вопросы?\nПиши @{username}",
    "btn_support_link": "💬 Написать в поддержку",
    "terms_text": (
        "📄 <b>Документы</b>\n\n"
        "Используя бота, вы соглашаетесь с пользовательским соглашением "
        "и политикой конфиденциальности:"
    ),
    "btn_terms": "📄 Пользовательское соглашение",
    "btn_privacy": "🔒 Политика конфиденциальности",
    "btn_author_agree": "✅ Согласен — настроить профиль",
    "author_info": (
        "🪙 <b>Хотите зарабатывать на кружках?</b>\n\n"
        "1. 👤 Настройте свой профиль красиво и привлекательно!\n"
        "    — Поставьте справедливую цену\n"
        "    — Выставите красивую фотографию\n"
        "    — Напишите привлекательное описание\n\n"
        "2. 🔞 Загружайте интересные кружки, чтобы привлечь больше людей\n\n"
        "3. ❓ <b>Как всё работает?</b>\n"
        "    Пользователям будут показываться ваши кружки, и у них будет доступ "
        "к просмотру вашего профиля. Поэтому сделайте очень привлекательный "
        "профиль и много интересных кружков\n\n"
        "4. 💸 <b>Доступные способы вывода денег:</b>\n"
        "    Крипта 💰\n"
        "    Тг старс ⭐️\n"
        "    Перевод на карту 💳\n"
        "С каждой покупки берётся 50% в качестве комиссии\n\n"
        "Нажмите на кнопку соглашения, чтобы начать настройку профиля.\n\n"
        "<i>*Это меню можно призвать, отправив команду /info</i>"
    ),
    "profile_card_hint": "ℹ️ После покупки вам будут доступны все кружки этого пользователя.",
    "btn_purchased_author": "👤 {name}",
    "purchases_hint": "👇 Выбери автора, чтобы посмотреть его кружки:",
    "upload_prompt": "Отправь видео или кружок не длиннее 60 сек (до 20 МБ) — он загрузится в твой профиль.",
    "upload_too_long": "❌ Видео длиннее 60 секунд.",
    "upload_too_big": "❌ Файл больше 20 МБ.",
    "upload_processing": "⏳ Обрабатываю видео...",
    "upload_done": "✅ Кружок #{seq} загружен в твой профиль!",
    "upload_failed": "❌ Не удалось обработать видео. Попробуй другое.",
    "my_circles_empty": "У тебя пока нет кружков.",
    "my_circle_caption": "Кружок #{seq} | 👍 {likes} 👎 {dislikes} | 👁 {views}",
    "btn_delete": "🗑 Удалить",
    "deleted": "Кружок удалён.",
    "author_profile": (
        "⭐️ Профиль автора\n\n"
        "Описание: {description}\n"
        "Цена доступа к профилю: {price} 🪙\n"
        "Заработано: {earned} 🪙"
    ),
    "no_description": "не задано",
    "btn_set_price": "💲 Изменить цену",
    "btn_set_photo": "🖼 Фото-шапка",
    "btn_set_description": "📝 Изменить описание",
    "btn_withdraw": "💸 Вывести",
    "set_price_prompt": "Отправь новую цену доступа к профилю (в монетах):",
    "set_photo_prompt": "Отправь фото для шапки профиля:",
    "set_description_prompt": "Отправь новое описание профиля:",
    "saved": "✅ Сохранено!",
    "withdraw_prompt": "Отправь сумму и реквизиты для вывода (например: 100 TON-кошелёк ...):",
    "withdraw_sent": "✅ Заявка на вывод отправлена админу.",
    "withdraw_min": "❌ Вывод доступен от {min} 🪙. У тебя заработано: {earned} 🪙",
    "purchases_empty": "Покупок пока нет.",
    "purchases_title": "🧾 <b>Мои покупки:</b>",
    "buy_menu": (
        "💰 <b>Получение монет</b>\n\n"
        "💳 Купить — CryptoBot, Telegram Stars или перевод\n"
        "🆓 Бесплатно — друзья и спонсоры\n\n"
        "Выбирай"
    ),
    "btn_buy_coins": "💳 Купить",
    "btn_free_coins": "🆓 Бесплатно",
    "buy_packs": "💳 <b>Пакеты монет</b>\n\nЦена в рублях, оплата в $ по актуальному курсу",
    "pack_btn": "🪙 {coins} — {price}",
    "btn_custom_amount": "🪙 Другая сумма",
    "custom_amount_prompt": "🪙 Введите количество монет (от 10 до 50000):\n\n❌ Отмена - /cancel",
    "custom_amount_invalid": "❌ Введите число от 10 до 50000.",
    "pay_method": "<b>{coins} 🪙</b>\n\nЦена: {price}",
    "btn_pay_crypto": "CryptoBot 💲",
    "btn_pay_stars": "Telegram Stars ⭐️",
    "btn_pay_manual": "CryptoWallet 💶",
    "btn_pay_card": "Карта 💳",
    "btn_pay_card_semi": "Карта 💳 Полуавтомат",
    "btn_pay_sbp": "СБП 📱",
    "btn_pay_card_link": "💳 Перейти к оплате",
    "btn_i_paid": "✅ Я оплатил",
    "btn_pay_stars_go": "⭐ Оплатить Stars",
    "btn_pay_cryptobot_go": "💵Оплатить",
    "payment_create_error": "❌ Не удалось создать платёж. Попробуй позже или выбери другой способ.",
    "offer_invalid": "❌ Неверная сумма, выбери пакет заново.",
    "card_auto": (
        "<b>💳 Оплата картой</b>\n\n"
        "📦 <b>Товар:</b> {coins} 🪙\n"
        "💰 <b>Цена:</b> {price}\n\n"
        "<b>1. Нажмите кнопку ниже</b>\n"
        "<b>2. Оплатите через ЮKassa</b>\n"
        "<b>3. Товар придёт автоматически</b>"
    ),
    "card_manual": (
        "<b>Способ оплаты: Карта 💳\n"
        "Цена: {price}\n"
        "👋Приветствую, {name}.\n"
        "👛Для оплаты \"{coins} 🪙\", переведите на эту карту <code>{card}</code> ({bank}) {price}, "
        "после оплаты нажмите «✅ Я оплатил» и отправьте боту фотографию квитанции.</b>"
    ),
    "sbp_manual": (
        "<b>Способ оплаты: СБП 📱\n"
        "Цена: {price}\n"
        "👋Приветствую, {name}.\n"
        "👛Для оплаты \"{coins} 🪙\", переведите по СБП на этот номер <code>{phone}</code> ({bank}) {price}, "
        "после оплаты отправьте боту фотографию квитанции и получите товар.</b>"
    ),
    "crypto_wallets": (
        "<b>Сποϲοб οπλατы: CryptoWallet 💶\n"
        "Сумма к оплате: {price}\n"
        "1. 💵 Дλя οπλατы в USDT или GRAM, περεвεдиτε нα эτοτ κρиπτο κοшεлёκ👇\n"
        "<code>{usdt_ton_wallet}</code>\n"
        "{usdt} USDT или {ton} GRAM, ποϲлε οπλατы, οτпрαвьτε φοτο περεвοдa.\n"
        "❗️<b>ΠΕΡΕΒΟДИΤΕ ΤΟΛЬΚΟ USDT или GRAM Β СΕΤИ TON, ИΗΑЧΕ ΜΟΗΕΤЫ ДΟ ΜΕΗЯ ΗΕ ДΟЙДУΤ</b>❗️\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "2. 💵 Дλя οπλατы в BTC, περεвεдиτε нα эτοτ κρиπτο κοшεлёκ👇\n"
        "<code>{btc_wallet}</code>\n"
        "{btc} BTC, ποϲлε οπλατы, οτпрαвьτε φοτο περεвοдa.\n"
        "❗️<b>ΠΕΡΕΒΟДИΤΕ ΤΟΛЬΚΟ BTC Β СΕΤИ BITCOIN, ИΗΑЧΕ ΜΟΗΕΤЫ ДΟ ΜΕΗЯ ΗΕ ДΟЙДУΤ</b>❗️\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "3. 💵 Дλя οπλατы в ETH, περεвεдиτε нα эτοτ κρиπτο κοшεлёκ👇\n"
        "<code>{eth_wallet}</code>\n"
        "{eth} ETH, ποϲлε οπλατы, οτпрαвьτε φοτο περεвοдa.\n"
        "❗️<b>ΠΕΡΕΒΟДИΤΕ ΤΟΛЬΚΟ ETH Β СΕΤИ ETH, ИΗΑЧΕ ΜΟΗΕΤЫ ДΟ ΜΕΗЯ ΗΕ ДΟЙДУΤ</b>❗️</b>"
    ),
    "stars_pay": (
        "<b>⭐️ Оπλατα Telegram Stars</b>\n\n"
        "📦 <b>Тοвαρ:</b> {coins} 🪙\n"
        "💰 <b>Цεнα:</b> {price}\n"
        "⭐ <b>К οπλατε:</b> {stars} Stars\n\n"
        "<b>1. Нαжмиτε кнοπку «⭐ Оπλατиτь Stars»</b>\n"
        "<b>2. Оπλατиτε ϲчёτ</b>\n"
        "<b>3. Тοвαρ πρидёτ ϲюдα αвτοмατичεϲки</b>"
    ),
    "payment_photo_instruction": "📸 Отправьте боту фотографию квитанции об оплате:",
    "unknown_command": "❌ Неизвестная команда. Используй кнопки меню.",
    "unknown_state_reset": "❌ Действие отменено. Если хотел что-то ввести — начни заново.",
    "unknown_no_user": "❌ Для начала работы используй команду /start",
    "cmd_start": "🚀 Запустить бота / главное меню",
    "cmd_circle": "▶️ Следующий кружок",
    "cmd_profile": "👤 Мой профиль",
    "cmd_buy": "💰 Купить монеты",
    "cmd_free": "🆓 Монеты бесплатно",
    "cmd_ref": "👥 Реферальная ссылка",
    "cmd_sub": "🎫 Купить подписку",
    "cmd_profiles": "👀 Смотреть профили авторов",
    "cmd_mirrors": "🤖 Мои зеркала",
    "cmd_partner": "🤝 Партнёрская программа",
    "cmd_promo": "🏷 Активировать промокод",
    "cmd_info": "⭐️ Как зарабатывать на кружках",
    "cmd_lang": "🌐 Сменить язык",
    "cmd_support": "🆘 Поддержка",
    "cmd_terms": "📄 Пользовательское соглашение",
    "cryptobot_currency_choice": "💲 Выберите валюту для оплаты:",
    "crypto_invoice": (
        "<b>👛Дλя οπλατы \"{coins} 🪙\", нαжмиτε \n"
        "\"💵Оπλατиτь\" и οπλατиτε τοвαρ.\n"
        "🧾Суммα к οπλατε: {amount} {symbol}\n\n"
        "📦Пοϲλε οπλατы, бοτ αвτοмατичεϲки выдαϲτ вαм τοвαρ.\n\n"
        "📄Гαйд нα ποкуπку кρиπτы: https://telegra.ph/Kak-oplatit-tovar-v-bote-cherez-CryptoBot-12-29</b>"
    ),
    "btn_pay_invoice": "💳 Оплатить {usd}$",
    "btn_check_payment": "🔄 Проверить оплату",
    "payment_not_found": "Оплата ещё не найдена. Попробуй чуть позже.",
    "payment_success": "<b>♦️Оплата прошла успешно. Спасибо за покупку!‍‍ ♣️</b>\n\n✅ Зачислено {coins} 🪙.",
    "manual_prompt": "Переведи {rub} ₽ (крипта/звёзды/деньги) и пришли сюда скрин перевода.",
    "manual_sent": "<b>♦️Квитанция отправлена на проверку, вы получите товар в течение дня.‍‍ ♣️</b>",
    "manual_approved": "<b>♦️Оплата прошла успешно. Спасибо за покупку!‍‍ ♣️</b>\n\n✅ Зачислено {coins} 🪙.",
    "manual_rejected": "❌ Ваша заявка на оплату была отклонена. Попробуйте ещё раз или обратитесь в поддержку.",
    "manual_rejected_reason": "❌ Ваша заявка на оплату была отклонена.\n\n📝 Причина: {reason}\n\nПопробуйте ещё раз или обратитесь в поддержку.",
    "free_menu": (
        "🆓 <b>Монеты бесплатно</b>\n\n"
        "👥 Приглашай друзей по реф-ссылке\n"
        "📢 Подписывайся на спонсоров"
    ),
    "btn_ref": "👥 Пригласить друзей",
    "btn_share_ref": "📤 Поделиться ссылкой",
    "btn_sponsors": "📢 Подписаться на спонсоров",
    "ref_text": (
        "Приглашай друзей по своей ссылке и получай {reward} 🪙 за каждого:\n\n{link}\n\n"
        "Приглашено: {count}"
    ),
    "ref_bonus": "🎉 По твоей ссылке пришёл новый пользователь! +{reward} 🪙",
    "sponsors_empty": "Сейчас нет доступных спонсоров.",
    "sponsors_text": "Подпишись на каналы и нажми «Проверить», чтобы получить монеты:",
    "btn_check_subs": "✅ Проверить",
    "sponsors_reward": "🎉 Начислено {coins} 🪙 за подписки!",
    "sponsors_not_all": "Ты подписан не на все каналы.",
    "forced_sub": "🔒 Для использования бота подпишись на каналы:",
    "view_profiles_title": "👀 Профили авторов (стр. {page}):",
    "profile_card": (
        "👤 <b>Автор #{id}</b> {name}\n\n"
        "📝 {description}\n\n"
        "🎬 Кружков: <b>{count}</b>\n"
        "👍 <b>{likes}</b> | 👎 <b>{dislikes}</b>\n"
        "🛒 Купили доступ: <b>{buyers}</b>\n"
        "🔓 Цена доступа: <b>{price}</b> 🪙"
    ),
    "btn_buy_access": "🔓 Купить доступ — {price} монет",
    "btn_next_profile": "➡️ Следующий профиль",
    "no_authors": "🙁 Авторов пока нет. Загрузи кружок — стань первым автором!",
    "btn_open_profile": "📂 Открыть кружки",
    "access_bought": "✅ Доступ куплен! Присылаю кружки автора.",
    "access_already": "У тебя уже есть доступ.",
    "author_no_videos": "У автора пока нет кружков.",
    "subs_menu": (
        "🎫 <b>Все кружки станут бесплатными сразу после покупки подписки.</b>\n\n"
        "Выберите тип подписки:\n\n"
        "💎 <b>А+</b>\n"
        "    • Бесплатный просмотр кружков из общего пула\n"
        "    • До {a_limit} кружков в день бесплатно\n"
        "⏳ Срок: <b>{a_days} дней</b>\n"
        "💰 Цена: <b>{a_price}</b> 🪙\n\n"
        "💎 <b>A++</b>\n"
        "    • Бесплатный просмотр всех кружков\n"
        "    • Безлимит кружков\n"
        "    • Пересылка кружков\n"
        "    • Скачивание кружков\n"
        "⏳ Срок: <b>{app_days} дней</b>\n"
        "💰 Цена: <b>{app_price}</b> 🪙\n\n"
        "⭐️ <b>PREMIUM</b>\n"
        "    • Бесплатный просмотр всех кружков\n"
        "    • Безлимит кружков\n"
        "    • Пересылка кружков\n"
        "    • Скачивание кружков\n"
        "⏳ Срок: <b>БЕССРОЧНО / НАВСЕГДА</b>\n"
        "💰 Цена: <b>{p_price}</b> 🪙"
    ),
    "btn_sub_a": "💎 А+ — {price} монет",
    "btn_sub_app": "💎 A++ — {price} монет",
    "btn_sub_premium": "⭐️ PREMIUM — {price} монет",
    "sub_bought": "✅ Подписка {tier} активирована!",
    "mirrors_menu": (
        "🤖 Конструктор ботов (зеркала)\n\n"
        "Создай своё зеркало этого бота в 1 клик — "
        "и зеркало запустится с общей базой.\n\n"
        "🎁 За своё первое рабочее зеркало ты получишь +{reward} 🪙. "
        "За второе и следующие зеркала монеты не начисляются.\n\n"
        "Твои зеркала: {count}"
    ),
    "btn_add_mirror": "➕ Создать зеркало",
    "btn_add_mirror_reward": "➕ Создать зеркало (+{reward} 🪙)",
    "btn_create_bot_1click": "⚡️ Создать бота в 1 клик",
    "mirror_1click_hint": "👇 Кнопка для создания бота:",
    "mirror_1click_prompt": (
        "🤖 <b>Создание зеркала</b>\n\n"
        "Нажми кнопку «⚡️ Создать бота в 1 клик» внизу экрана — "
        "Telegram сам создаст бота, а я запущу его как зеркало с общей базой.\n\n"
        "🎁 За своё первое рабочее зеркало ты получишь +{reward} 🪙. "
        "За второе и следующие зеркала монеты не начисляются."
    ),
    "mirror_bot_created": "✅ Бот @{username} создан, токен получен автоматически.",
    "mirror_token_fetch_failed": "❌ Не удалось получить токен созданного бота. Попробуй ещё раз.",
    "menu_restored": "📋 Меню",
    "mirror_premium_prompt": (
        "⭐️ У владельца бота есть Telegram Premium (нужен для премиум-эмодзи)?\n\n"
        "Если выбрать «Премиум» без Premium-аккаунта — эмодзи будут отображаться криво."
    ),
    "btn_mirror_premium": "⭐️ Премиум-эмодзи",
    "btn_mirror_regular": "🤖 Обычный бот",
    "mirror_created": "✅ Зеркало @{username} запущено!",
    "mirror_reward": "🎁 +{reward} 🪙 за создание зеркала! Баланс: {balance} 🪙\nВсе, кто зайдёт в твоё зеркало, станут твоими рефералами.",
    "mirror_invalid": "❌ Сервис зеркал недоступен, попробуй позже.",
    "mirror_exists": "⚠️ Это зеркало уже добавлено и работает.",
    "mirror_limit": "❌ Лимит зеркал: {max}",
    "mirror_deleted": "Зеркало остановлено и удалено.",
    "btn_back": "⬅️ Назад",
    "btn_cancel": "❌ Отмена",
    "cancelled": "❌ Действие отменено.",
    "cancel_hint": "❌ Отмена - /cancel",
    "cmd_cancel": "❌ Отменить текущее действие",
    "lang_set": "✅ Язык переключён на русский.",
    "partner_ask": "🤝 <b>Хочешь стать партнёром?</b>\n\nПриглашай людей по реф-ссылке, зарабатывай монеты и выводи их в рубли.",
    "btn_partner_yes": "✅ Да",
    "btn_partner_no": "❌ Нет",
    "partner_joined": "🎉 <b>Ты стал партнёром!</b>",
    "partner_info": (
        "🤝 <b>Партнёр</b>\n\n"
        "🔗 Ваша ссылка:\n{link}\n\n"
        "📊 <b>Статистика</b>\n"
        "Привёл: <b>{count}</b>\n"
        "Баланс: <b>{balance} ₽</b>\n"
        "Выведено: <b>{withdrawn} ₽</b>\n"
        "На выводе: <b>{pending} ₽</b>\n"
        "Донаты с ссылки: <b>{donates} ₽</b>\n"
        "Просмотры кружков: <b>{views}</b>\n"
        "Подписки на спонсоров: <b>{sponsor_subs}</b>\n\n"
        "🏆 Награда: <b>{reward} ₽</b> за каждого живого пользователя"
    ),
    "btn_partner_refresh": "🔄 Обновить",
    "btn_partner_withdraw": "💰 Вывод",
    "captcha_text": "🤖 Подтверди, что ты не бот:",
    "btn_captcha": "✅ Я не бот",
    "partner_withdraw_min": "❌ Вывод доступен от {min_rub} ₽. У тебя: {rub} ₽",
    "partner_withdraw_prompt": "💸 К выводу: {rub} ₽. Отправь реквизиты (карта / кошелёк / тг старс):",
}

EN = {
    "choose_lang": "Выберите язык / Choose language:",
    "start": (
        "👋 <b>Hi, {first_name}!</b>\n\n"
        "🎥 Watch other people's <b>circles</b> and upload your own.\n\n"
        "▶️ “Next circle” — a random circle (1 🪙)\n"
        "📤 Upload your circles and <b>earn coins</b>\n"
        "🎫 With a subscription — watch for free\n\n"
        "💰 You start with <b>5 🪙</b>. Let's go!"
    ),
    "welcome_back": (
        "👋 <b>Welcome back, {first_name}!</b>\n\n"
        "🎥 Watch other people's <b>circles</b> and upload your own.\n\n"
        "▶️ “Next circle” — a random circle (1 🪙)\n"
        "📤 Upload your circles and <b>earn coins</b>\n"
        "🎫 With a subscription — watch for free"
    ),
    "spent_toast": "−{spent} 🪙\nBalance: {balance} 🪙",
    "btn_next_circle": "▶️ Next circle",
    "btn_profile": "👤 Profile",
    "btn_buy": "💰 Get coins",
    "btn_view_profiles": "👀 View profiles",
    "btn_buy_sub": "🎫 Buy subscription",
    "btn_mirrors": "🤖 My mirrors",
    "btn_lang": "🌐 Language",
    "no_videos": "😔 No circles yet. Upload the first one in your profile!",
    "no_balance": "😕 Not enough coins. Top up in “Get coins” or buy a subscription.",
    "daily_limit": "⏳ Daily view limit for your subscription reached. Come back tomorrow!",
    "too_fast": "⏳ <b>Wait 2 sec.</b>\n<i>No more than one circle per second.</i>",
    "free_view_toast": "🎁 First circle is free!",
    "send_failed": "⚠️ Failed to send the circle, coins refunded.",
    "recommend_channel": "📢 Recommended channel: <b>{title}</b>",
    "btn_recommend_open": "➡️ Open",
    "btn_recommend_hide": "🚫 Don't show again",
    "recommend_hidden": "Won't show it again",
    "unsupported_media": "❌ Only video, GIF and photo are supported.",
    "convert_failed": "❌ Couldn't make a circle from this file.",
    "circle_caption": "🎬 <b>Circle #{seq}</b> · author #{author}\n👍 {likes} | 👎 {dislikes} | 👁 {views}",
    "btn_like": "👍",
    "btn_dislike": "👎",
    "btn_view_author": "👤 View profile",
    "btn_next": "▶️ Next circle",
    "rated": "Rating saved!",
    "already_rated": "You already rated this circle.",
    "profile": (
        "👤 <b>Your profile</b>\n\n"
        "🏷 ID: <code>{tg_id}</code>\n"
        "📤 Uploaded circles: <b>{uploaded}</b>\n"
        "⚖️ Ratings: 👍 <b>{likes}</b> | 👎 <b>{dislikes}</b>\n"
        "👁 Circles watched: <b>{viewed}</b>\n"
        "💰 Balance: <b>{balance}</b> 🪙\n"
        "🎫 Subscription: <b>{sub}</b>\n\n"
        "Want to earn Coins — tap “Author profile”"
    ),
    "sub_none": "none",
    "sub_forever": "forever",
    "sub_until": "until {date}",
    "btn_upload": "📤 Upload circle",
    "btn_my_circles": "🎬 My circles",
    "btn_author_profile": "⭐️ Author profile",
    "btn_my_purchases": "🧾 My purchases",
    "btn_promo": "🏷 Enter promo code",
    "promo_prompt": "🏷 Send the promo code in one message:\n\n❌ Cancel - /cancel",
    "promo_invalid": "❌ Promo code not found or already used up.",
    "promo_used": "❌ You have already activated this promo code.",
    "promo_success": "🎉 Promo code activated! Received: {rewards}",
    "banned": "🔒 You are banned by the administrator.",
    "btn_support": "🆘 Support",
    "support_text": "🆘 Having problems or questions?\nMessage @{username}",
    "btn_support_link": "💬 Contact support",
    "terms_text": (
        "📄 <b>Documents</b>\n\n"
        "By using this bot you agree to the terms of service "
        "and the privacy policy:"
    ),
    "btn_terms": "📄 Terms of service",
    "btn_privacy": "🔒 Privacy policy",
    "btn_author_agree": "✅ I agree — set up my profile",
    "author_info": (
        "🪙 <b>Want to earn on circles?</b>\n\n"
        "1. 👤 Make your profile beautiful and attractive!\n"
        "    — Set a fair price\n"
        "    — Upload a nice photo\n"
        "    — Write an attractive description\n\n"
        "2. 🔞 Upload interesting circles to attract more people\n\n"
        "3. ❓ <b>How does it work?</b>\n"
        "    Users will see your circles and can buy access to your profile. "
        "So make a very attractive profile and lots of interesting circles\n\n"
        "4. 💸 <b>Withdrawal methods:</b>\n"
        "    Crypto 💰\n"
        "    TG Stars ⭐️\n"
        "    Card transfer 💳\n"
        "A 50% commission is taken from every purchase\n\n"
        "Press the agreement button to start setting up your profile.\n\n"
        "<i>*You can open this menu with the /info command</i>"
    ),
    "profile_card_hint": "ℹ️ After purchase you will get access to all circles of this user.",
    "btn_purchased_author": "👤 {name}",
    "purchases_hint": "👇 Pick an author to view their circles:",
    "upload_prompt": "Send a video or a circle up to 60 sec (max 20 MB) — it will be added to your profile.",
    "upload_too_long": "❌ Video is longer than 60 seconds.",
    "upload_too_big": "❌ File is bigger than 20 MB.",
    "upload_processing": "⏳ Processing video...",
    "upload_done": "✅ Circle #{seq} uploaded to your profile!",
    "upload_failed": "❌ Failed to process the video. Try another one.",
    "my_circles_empty": "You have no circles yet.",
    "my_circle_caption": "Circle #{seq} | 👍 {likes} 👎 {dislikes} | 👁 {views}",
    "btn_delete": "🗑 Delete",
    "deleted": "Circle deleted.",
    "author_profile": (
        "⭐️ Author profile\n\n"
        "Description: {description}\n"
        "Profile access price: {price} 🪙\n"
        "Earned: {earned} 🪙"
    ),
    "no_description": "not set",
    "btn_set_price": "💲 Change price",
    "btn_set_photo": "🖼 Header photo",
    "btn_set_description": "📝 Edit description",
    "btn_withdraw": "💸 Withdraw",
    "set_price_prompt": "Send the new profile access price (in coins):",
    "set_photo_prompt": "Send a photo for your profile header:",
    "set_description_prompt": "Send the new profile description:",
    "saved": "✅ Saved!",
    "withdraw_prompt": "Send the amount and payout details (e.g. 100 TON-wallet ...):",
    "withdraw_sent": "✅ Withdrawal request sent to the admin.",
    "withdraw_min": "❌ Withdrawal is available from {min} 🪙. You have earned: {earned} 🪙",
    "purchases_empty": "No purchases yet.",
    "purchases_title": "🧾 <b>My purchases:</b>",
    "buy_menu": "💰 How do you want to get coins?",
    "btn_buy_coins": "💳 Buy",
    "btn_free_coins": "🆓 For free",
    "buy_packs": "💳 <b>Coin packs</b>\n\nChoose a pack:",
    "pack_btn": "🪙 {coins} — {price}",
    "btn_custom_amount": "🪙 Custom amount",
    "custom_amount_prompt": "🪙 Enter the number of coins (from 10 to 50000):\n\n❌ Cancel - /cancel",
    "custom_amount_invalid": "❌ Enter a number from 10 to 50000.",
    "pay_method": "<b>{coins} 🪙</b>\n\nPrice: {price}",
    "btn_pay_crypto": "CryptoBot 💲",
    "btn_pay_stars": "Telegram Stars ⭐️",
    "btn_pay_manual": "CryptoWallet 💶",
    "btn_pay_card": "Card 💳",
    "btn_pay_card_semi": "Card 💳 Semi-auto",
    "btn_pay_sbp": "SBP 📱",
    "btn_pay_card_link": "💳 Go to payment",
    "btn_i_paid": "✅ I paid",
    "btn_pay_stars_go": "⭐ Pay with Stars",
    "btn_pay_cryptobot_go": "💵Pay",
    "payment_create_error": "❌ Cannot create the payment. Try later or choose another method.",
    "offer_invalid": "❌ Invalid amount, please pick a pack again.",
    "card_auto": (
        "<b>💳 Card payment</b>\n\n"
        "📦 <b>Product:</b> {coins} 🪙\n"
        "💰 <b>Price:</b> {price}\n\n"
        "<b>1. Click the button below</b>\n"
        "<b>2. Pay via YooKassa</b>\n"
        "<b>3. The product will be delivered here</b>"
    ),
    "card_manual": (
        "<b>Payment method: Card 💳\n"
        "Price: {price}\n"
        "👋Hello, {name}.\n"
        "👛To pay for \"{coins} 🪙\", transfer to this card <code>{card}</code> ({bank}) {price}, "
        "after payment click «✅ I paid» and send a photo of the receipt to the bot.</b>"
    ),
    "sbp_manual": (
        "<b>Payment method: SBP 📱\n"
        "Price: {price}\n"
        "👋Hello, {name}.\n"
        "👛To pay for \"{coins} 🪙\", transfer via SBP to number <code>{phone}</code> ({bank}) {price}, "
        "after payment send photo of receipt to bot and get product.</b>"
    ),
    "crypto_wallets": (
        "<b>Payment method: CryptoWallet 💶\n"
        "Amount to pay: {price}\n"
        "1. 💵 To pay in USDT or GRAM, transfer to this crypto wallet👇\n"
        "<code>{usdt_ton_wallet}</code>\n"
        "{usdt} USDT or {ton} GRAM, after payment, send a photo of the transfer.\n"
        "❗️<b>SEND ONLY USDT or TON IN TON NETWORK, OTHERWISE THE MONEY WILL NOT REACH ME</b>❗️\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "2. 💵 To pay in BTC, transfer to this crypto wallet👇\n"
        "<code>{btc_wallet}</code>\n"
        "{btc} BTC, after payment, send a photo of the transfer.\n"
        "❗️<b>SEND ONLY BTC IN BITCOIN NETWORK, OTHERWISE THE MONEY WILL NOT REACH ME</b>❗️\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        "3. 💵 To pay in ETH, transfer to this crypto wallet👇\n"
        "<code>{eth_wallet}</code>\n"
        "{eth} ETH, after payment, send a photo of the transfer.\n"
        "❗️<b>SEND ONLY ETH IN ETH NETWORK, OTHERWISE THE MONEY WILL NOT REACH ME</b>❗️</b>"
    ),
    "stars_pay": (
        "<b>⭐ Payment by Telegram Stars</b>\n\n"
        "📦 <b>Product:</b> {coins} 🪙\n"
        "💰 <b>Price:</b> {price}\n"
        "⭐ <b>To pay:</b> {stars} Stars\n\n"
        "<b>1. Click the «⭐ Pay with Stars» button</b>\n"
        "<b>2. Pay the invoice</b>\n"
        "<b>3. The product will be delivered here automatically</b>"
    ),
    "payment_photo_instruction": "📸 Send a photo of the payment receipt to the bot:",
    "unknown_command": "❌ Unknown command. Use the menu buttons.",
    "unknown_state_reset": "❌ Action cancelled. If you wanted to enter something, start over.",
    "unknown_no_user": "❌ Use the /start command to begin",
    "cmd_start": "🚀 Start the bot / main menu",
    "cmd_circle": "▶️ Next circle",
    "cmd_profile": "👤 My profile",
    "cmd_buy": "💰 Buy coins",
    "cmd_free": "🆓 Free coins",
    "cmd_ref": "👥 Referral link",
    "cmd_sub": "🎫 Buy subscription",
    "cmd_profiles": "👀 View author profiles",
    "cmd_mirrors": "🤖 My mirrors",
    "cmd_partner": "🤝 Partner program",
    "cmd_promo": "🏷 Activate promo code",
    "cmd_info": "⭐️ How to earn on circles",
    "cmd_lang": "🌐 Change language",
    "cmd_support": "🆘 Support",
    "cmd_terms": "📄 Terms of use",
    "cryptobot_currency_choice": "💲 Choose the currency for payment:",
    "crypto_invoice": (
        "<b>👛To pay for \"{coins} 🪙\", click \n"
        "\"💵Pay\" and pay for the product.\n"
        "🧾Amount: {amount} {symbol}\n\n"
        "📦After payment, the bot will automatically give you the product.\n\n"
        "📄Guide to crypto purchase: https://telegra.ph/Kak-oplatit-tovar-v-bote-cherez-CryptoBot-12-29</b>"
    ),
    "btn_pay_invoice": "💳 Pay {usd}$",
    "btn_check_payment": "🔄 Check payment",
    "payment_not_found": "Payment not found yet. Try again later.",
    "payment_success": "<b>✅ Payment was successful. Thank you for your purchase!</b>\n\n✅ Credited {coins} 🪙.",
    "manual_prompt": "Transfer {rub} ₽ (crypto/stars/money) and send a screenshot here.",
    "manual_sent": "<b>♦️Receipt sent for verification, you will receive the product within a day.‍‍ ♣️</b>",
    "manual_approved": "<b>✅ Payment was successful. Thank you for your purchase!</b>\n\n✅ Credited {coins} 🪙.",
    "manual_rejected": "❌ Your payment request was declined. Try again or contact support.",
    "manual_rejected_reason": "❌ Your payment request was declined.\n\n📝 Reason: {reason}\n\nTry again or contact support.",
    "free_menu": "🆓 Get coins for free:",
    "btn_ref": "👥 Invite friends",
    "btn_share_ref": "📤 Share link",
    "btn_sponsors": "📢 Subscribe to sponsors",
    "ref_text": (
        "Invite friends with your link and get {reward} 🪙 for each:\n\n{link}\n\n"
        "Invited: {count}"
    ),
    "ref_bonus": "🎉 A new user joined via your link! +{reward} 🪙",
    "sponsors_empty": "No sponsors available right now.",
    "sponsors_text": "Subscribe to the channels and tap “Check” to get coins:",
    "btn_check_subs": "✅ Check",
    "sponsors_reward": "🎉 Credited {coins} 🪙 for subscriptions!",
    "sponsors_not_all": "You are not subscribed to all channels.",
    "forced_sub": "🔒 To use the bot, subscribe to the channels:",
    "view_profiles_title": "👀 Author profiles (page {page}):",
    "profile_card": (
        "👤 <b>Author #{id}</b> {name}\n\n"
        "📝 {description}\n\n"
        "🎬 Circles: <b>{count}</b>\n"
        "👍 <b>{likes}</b> | 👎 <b>{dislikes}</b>\n"
        "🛒 Access bought: <b>{buyers}</b>\n"
        "🔓 Access price: <b>{price}</b> 🪙"
    ),
    "btn_buy_access": "🔓 Buy access — {price} coins",
    "btn_next_profile": "➡️ Next profile",
    "no_authors": "🙁 No authors yet. Upload a circle to become the first one!",
    "btn_open_profile": "📂 Open circles",
    "access_bought": "✅ Access purchased! Sending the author's circles.",
    "access_already": "You already have access.",
    "author_no_videos": "The author has no circles yet.",
    "subs_menu": (
        "🎫 All circles become free right after buying a subscription.\n\n"
        "Choose a subscription:\n\n"
        "А+\n"
        "    -Free viewing of circles from the common pool\n"
        "    -Up to {a_limit} circles per day for free\n"
        "⏳ Duration: {a_days} days\n"
        "Price: {a_price} 🪙\n\n"
        "A++\n"
        "    -Free viewing of all circles\n"
        "    -Unlimited circles\n"
        "    -Forwarding circles\n"
        "    -Downloading circles\n"
        "⏳ Duration: {app_days} days\n"
        "Price: {app_price} 🪙\n\n"
        "⭐️ PREMIUM\n"
        "    -Free viewing of all circles\n"
        "    -Unlimited circles\n"
        "    -Forwarding circles\n"
        "    -Downloading circles\n"
        "⏳ Duration: FOREVER\n"
        "Price: {p_price} 🪙"
    ),
    "btn_sub_a": "💎 А+ — {price} coins",
    "btn_sub_app": "💎 A++ — {price} coins",
    "btn_sub_premium": "⭐️ PREMIUM — {price} coins",
    "sub_bought": "✅ Subscription {tier} activated!",
    "mirrors_menu": (
        "🤖 Bot constructor (mirrors)\n\n"
        "Create your own mirror of this bot in 1 click — "
        "the mirror will start with the shared database.\n\n"
        "🎁 You get +{reward} 🪙 for your first working mirror. "
        "No coins for the second and further mirrors.\n\n"
        "Your mirrors: {count}"
    ),
    "btn_add_mirror": "➕ Create mirror",
    "btn_add_mirror_reward": "➕ Create mirror (+{reward} 🪙)",
    "btn_create_bot_1click": "⚡️ Create a bot in 1 click",
    "mirror_1click_hint": "👇 Button to create the bot:",
    "mirror_1click_prompt": (
        "🤖 <b>Create a mirror</b>\n\n"
        "Tap the “⚡️ Create a bot in 1 click” button at the bottom of the screen — "
        "Telegram will create the bot and I'll launch it as a mirror with the shared database.\n\n"
        "🎁 You get +{reward} 🪙 for your first working mirror. "
        "No coins for the second and further mirrors."
    ),
    "mirror_bot_created": "✅ Bot @{username} created, token received automatically.",
    "mirror_token_fetch_failed": "❌ Couldn't fetch the new bot's token. Try again.",
    "menu_restored": "📋 Menu",
    "mirror_premium_prompt": (
        "⭐️ Does the bot owner have Telegram Premium (needed for premium emoji)?\n\n"
        "If you choose “Premium” without a Premium account — emoji will display incorrectly."
    ),
    "btn_mirror_premium": "⭐️ Premium emoji",
    "btn_mirror_regular": "🤖 Regular bot",
    "mirror_created": "✅ Mirror @{username} is running!",
    "mirror_reward": "🎁 +{reward} 🪙 for creating a mirror! Balance: {balance} 🪙\nEveryone who joins your mirror becomes your referral.",
    "mirror_invalid": "❌ Mirror service unavailable, try later.",
    "mirror_exists": "⚠️ This mirror is already added and running.",
    "mirror_limit": "❌ Mirror limit reached: {max}",
    "mirror_deleted": "Mirror stopped and deleted.",
    "btn_back": "⬅️ Back",
    "btn_cancel": "❌ Cancel",
    "cancelled": "❌ Action cancelled.",
    "cancel_hint": "❌ Cancel - /cancel",
    "cmd_cancel": "❌ Cancel current action",
    "lang_set": "✅ Language switched to English.",
    "partner_ask": "🤝 <b>Want to become a partner?</b>\n\nInvite people with your referral link, earn coins and withdraw them in RUB.",
    "btn_partner_yes": "✅ Yes",
    "btn_partner_no": "❌ No",
    "partner_joined": "🎉 <b>You are now a partner!</b>",
    "partner_info": (
        "🤝 <b>Partner</b>\n\n"
        "🔗 Your link:\n{link}\n\n"
        "📊 <b>Statistics</b>\n"
        "Invited: <b>{count}</b>\n"
        "Balance: <b>{balance} ₽</b>\n"
        "Withdrawn: <b>{withdrawn} ₽</b>\n"
        "Pending withdrawal: <b>{pending} ₽</b>\n"
        "Donations from your link: <b>{donates} ₽</b>\n"
        "Circle views: <b>{views}</b>\n"
        "Sponsor subscriptions: <b>{sponsor_subs}</b>\n\n"
        "🏆 Reward: <b>{reward} ₽</b> per live user"
    ),
    "btn_partner_refresh": "🔄 Refresh",
    "btn_partner_withdraw": "💰 Withdraw",
    "captcha_text": "🤖 Confirm you are not a bot:",
    "btn_captcha": "✅ I'm not a bot",
    "partner_withdraw_min": "❌ Withdrawal is available from {min_rub} ₽. You have: {rub} ₽",
    "partner_withdraw_prompt": "💸 To withdraw: {rub} ₽. Send your payout details (card / wallet / tg stars):",
}

TEXTS = {"ru": RU, "en": EN}


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, RU).get(key, RU.get(key, key))
    return text.format(**kwargs) if kwargs else text


def btn_variants(key: str) -> set[str]:
    """All texts a menu button can arrive as: with the emoji, or without it
    when the emoji was turned into a premium icon."""
    texts = {t(lang, key) for lang in TEXTS}
    return texts | {strip_leading_emoji(x) for x in texts}
