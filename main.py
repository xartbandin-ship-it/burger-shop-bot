import os
import json
import time
import threading
from flask import Flask, request, jsonify
import telebot
from telebot.types import (
    LabeledPrice,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)

# ==========================================
# 1. НАСТРОЙКИ БОТА И СЕРВЕРА
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬТЕ_ВАШ_ТОКЕН_ЗДЕСЬ")
ADMIN_ID = 7437101853  # Ваш Telegram ID администратора

SERVER_IP = "burgersmp.org"
SERVER_PORT = "19132"
TELEGRAM_CHAT = "https://t.me/burgerchatsmp"

# Цены в Telegram Stars (XTR) — Донат НАВСЕГДА
PRICE_PLUS = 150
PRICE_PLUS_PLUS = 300
PRICE_UPGRADE = 150  # Доплата с [+] до [++]

DATA_FILE = "shop_data.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==========================================
# 2. БАЗА ДАННЫХ И ОЧЕРЕДЬ (!claim)
# ==========================================
db = {
    "pending_rewards": {},
    "pending_removals": [],
    "user_nicknames": {},
    "owned_ranks": {}
}

waiting_for_nick = {}


def load_db():
    global db
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for k in db:
                    if k in loaded:
                        db[k] = loaded[k]
        except Exception as e:
            print(f"[DB] Ошибка загрузки базы: {e}")


def save_db():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[DB] Ошибка сохранения базы: {e}")


load_db()

# ==========================================
# 3. FLASK API ДЛЯ MINECRAFT СЕРВЕРА (!claim)
# ==========================================
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "Burger SMP Shop Bot API is running!", 200


@app.route("/check-reward", methods=["GET"])
def check_reward():
    player_name = request.args.get("name", "").strip()
    if not player_name:
        return jsonify({"status": "error", "message": "No name provided"}), 400

    key = player_name.lower()
    if key in db["pending_rewards"]:
        reward_info = db["pending_rewards"].pop(key)
        tag = reward_info["tag"]
        save_db()
        print(f"[API] Выдана привилегия {tag} игроку {player_name}")
        return jsonify({"status": "success", "tag": tag}), 200

    return jsonify({"status": "none"}), 200


@app.route("/check-removal", methods=["GET"])
def check_removal():
    player_name = request.args.get("name", "").strip()
    if not player_name:
        return jsonify({"status": "error", "message": "No name provided"}), 400

    key = player_name.lower()
    if key in db["pending_removals"]:
        db["pending_removals"].remove(key)
        if key in db["owned_ranks"]:
            del db["owned_ranks"][key]
        save_db()
        print(f"[API] Аннулирована привилегия у игрока {player_name}")
        return jsonify({"status": "remove"}), 200

    return jsonify({"status": "none"}), 200


# ==========================================
# 4. ТЕКСТЫ ПРИВИЛЕГИЙ И КОМАНД (БЕЗ ТП ПО КООРДИНАТАМ)
# ==========================================
WELCOME_TEXT = (
    "🍔 *Добро пожаловать в магазин BURGER SMP!*\n\n"
    f"🌍 *IP сервера:* `{SERVER_IP}`\n"
    f"🔌 *Порт:* `{SERVER_PORT}`\n"
    f"💬 *Наш чат:* {TELEGRAM_CHAT}\n\n"
    "🔥 *Все привилегии покупаются НАВСЕГДА!* Оплата происходит официально через *Telegram Stars (⭐️)*.\n"
    "После оплаты просто зайдите на сервер и введите в чат команду `!claim` — донат выдается автоматически за секунду!"
)

RANKS_INFO_TEXT = (
    "💎 *СРАВНЕНИЕ ПРИВИЛЕГИЙ (НАВСЕГДА):*\n\n"
    "👤 *Обычный игрок (Бесплатно):*\n"
    "• Точек дома (`!sethome`): *3 дома*\n"
    "• Слотов на Аукционе (`!ah`): *10 слотов*\n"
    "• Слотов в Столе Заказов (`!orders`): *5 заказов*\n"
    "• Радиус рандом-ТП (`!rtp`): *20,000 блоков*\n\n"
    "━━━━━━━━━━━━━━━\n"
    f"🔹 *Привилегия BURGER [+] — {PRICE_PLUS} ⭐️ (Навсегда):*\n"
    "• Красивый префикс `[+]` в чате и над головой\n"
    "• Увеличенный лимит домов: *5 домов* (вместо 3)\n"
    "• Слотов на Аукционе (`!ah`): *15 слотов* (вместо 10)\n"
    "• Слотов в Столе Заказов (`!orders`): *7 заказов* (вместо 5)\n"
    "• Увеличенный радиус `!rtp`: *25,000 блоков*\n"
    "• Право исключать участников из племени: `!tribe kick <ник>`\n\n"
    "━━━━━━━━━━━━━━━\n"
    f"👑 *Привилегия BURGER [++] — {PRICE_PLUS_PLUS} ⭐️ (Навсегда):*\n"
    "• Элитный золотой префикс `[++]` в чате и над головой\n"
    "• Максимальный лимит домов: *7 домов*\n"
    "• Слотов на Аукционе (`!ah`): *20 слотов*\n"
    "• Слотов в Столе Заказов (`!orders`): *10 заказов*\n"
    "• Максимальный радиус `!rtp`: *30,000 блоков*\n"
    "• Эксклюзивный РТП в Энд: *`!rtpend`* (с плавным падением)\n"
    "• Установка общей базы племени: *`!tribe sethome`* (телепорт для клана по `!tribe home`)\n"
    "• Право исключать участников из племени: `!tribe kick <ник>`\n"
    "• Быстрое самоубийство командой: *`!kill`*"
)

COMMANDS_INFO_TEXT = (
    "📜 *ВСЕ КОМАНДЫ СЕРВЕРА BURGER SMP:*\n\n"
    "⚡ *Быстрое меню (для телефона и ПК):*\n"
    "• Отправьте просто *`!`* (один восклицательный знак) в чат — откроется удобное меню всех систем сервера!\n"
    "• `!settings` — Настройка звуков и правой мини-панели\n\n"
    "💰 *Рынок, Экономика и Награды:*\n"
    "• `!ah` — Открыть Аукцион игроков (покупка, продажа, осмотр прочности/чар и фильтр-воронка)\n"
    "• `!ah sell <цена>` — Быстро выставить предмет в руке на аукцион\n"
    "• `!orders` — Стол Заказов (осмотр любых заказов, создание своих и сдача ресурсов)\n"
    "• `!sell` (или `!sell hand` / `!sell all`) — Продать ресурсы серверу (автоматически сдает в выгодные заказы игроков!)\n"
    "• `!bounty` — Охота за головами (назначить или посмотреть награды за игроков)\n"
    "• `!bal [ник]` — Посмотреть точный баланс до доллара\n"
    "• `!pay <ник> <сумма>` — Перевести деньги игроку\n"
    "• `!baltop` — Топ-5 богачей сервера\n"
    "• `!killtop` — Топ-5 PvP бойцов и рейтинга\n\n"
    "🧭 *Телепортация и Выживание:*\n"
    "• `!spawn` — Телепорт на спавн\n"
    "• `!rtp` — Случайный телепорт в обычном мире (20k / 25k `[+]` / 30k `[++]`)\n"
    "• `!rtpnether` — Случайный телепорт в Незере (с огнестойкостью)\n"
    "• `!rtpend` — Случайный телепорт в Энде *(только для `[++]`)*\n"
    "• `!tp <ник>` — Запрос на телепорт к игроку (`!tpaccept` / `!tpdeny`)\n"
    "• `!sethome <имя>` / `!home <имя>` / `!delhome <имя>` / `!homes` — Управление домами\n\n"
    "⚔️ *Племена (Кланы) и Прочее:*\n"
    "• `!tribe create <название>` — Создать племя\n"
    "• `!tribe invite <ник>` / `!tribe join` / `!tribe leave` / `!tribe info` / `!tribe list`\n"
    "• `!tribe kick <ник>` — Кикнуть участника *(для `[+]` и `[++]`)*\n"
    "• `!tribe sethome` / `!tribe home` — База племени *(установка для `[++]`)*\n"
    "• `!stats [ник]` — Подробная статистика игрока\n"
    "• `!nv` — Бесплатное ночное зрение на 2 часа\n"
    "• `!report <ник> <причина>` — Отправить жалобу администрации\n"
    "• `!claim` — Получить купленный донат на сервере"
)

# ==========================================
# 5. КЛАВИАТУРЫ БОТА
# ==========================================
def get_main_reply_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🛒 Купить донат"),
        KeyboardButton("💎 Описание привилегий"),
        KeyboardButton("📜 Команды сервера"),
        KeyboardButton("👤 Мой ник / Профиль"),
        KeyboardButton("🌍 IP и Чат сервера")
    )
    return kb


def get_shop_inline_kb(user_id):
    kb = InlineKeyboardMarkup(row_width=1)
    saved_nick = db["user_nicknames"].get(str(user_id))
    current_rank = db["owned_ranks"].get(saved_nick.lower()) if saved_nick else None

    kb.add(
        InlineKeyboardButton(
            f"🔹 Купить BURGER [+] — {PRICE_PLUS} ⭐️ (Навсегда)",
            callback_data="buy_donor_plus"
        ),
        InlineKeyboardButton(
            f"👑 Купить BURGER [++] — {PRICE_PLUS_PLUS} ⭐️ (Навсегда)",
            callback_data="buy_donor_plus_plus"
        )
    )
    if current_rank == "donor_plus":
        kb.add(
            InlineKeyboardButton(
                f"⬆️ Апгрейд с [+] до [++] — {PRICE_UPGRADE} ⭐️",
                callback_data="buy_upgrade"
            )
        )
    kb.add(
        InlineKeyboardButton("✏️ Изменить мой ник в Minecraft", callback_data="change_nick")
    )
    return kb


# ==========================================
# 6. ОБРАБОТЧИКИ КОМАНД TELEGRAM
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_reply_kb()
    )
    bot.send_message(
        message.chat.id,
        "👇 *Выберите привилегию для покупки или ознакомьтесь с описанием:*",
        parse_mode="Markdown",
        reply_markup=get_shop_inline_kb(message.from_user.id)
    )


@bot.message_handler(commands=["commands", "help"])
def cmd_help(message):
    bot.send_message(message.chat.id, COMMANDS_INFO_TEXT, parse_mode="Markdown")


@bot.message_handler(commands=["give"])
def cmd_admin_give(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 3 or parts[2] not in ["donor_plus", "donor_plus_plus"]:
        bot.reply_to(message, "❌ Использование: `/give <Ник> <donor_plus|donor_plus_plus>`", parse_mode="Markdown")
        return

    nick = parts[1].strip()
    tag = parts[2].strip()
    key = nick.lower()

    db["pending_rewards"][key] = {"original_name": nick, "tag": tag}
    db["owned_ranks"][key] = tag
    if key in db["pending_removals"]:
        db["pending_removals"].remove(key)
    save_db()

    bot.reply_to(
        message,
        f"✅ Игроку `{nick}` добавлен ранг `{tag}` в очередь выдачи!\nОн получит его при вводе `!claim` на сервере.",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["remove"])
def cmd_admin_remove(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Использование: `/remove <Ник>`", parse_mode="Markdown")
        return

    nick = parts[1].strip()
    key = nick.lower()
    if key in db["pending_rewards"]:
        del db["pending_rewards"][key]
    if key not in db["pending_removals"]:
        db["pending_removals"].append(key)
    save_db()

    bot.reply_to(
        message,
        f"🚫 Привилегия игрока `{nick}` помечена на удаление при следующем `!claim`.",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["queue"])
def cmd_admin_queue(message):
    if message.from_user.id != ADMIN_ID:
        return
    rewards_str = "\n".join([f"• `{v['original_name']}` -> `{v['tag']}`" for v in db["pending_rewards"].values()]) or "Пусто"
    removals_str = ", ".join([f"`{r}`" for r in db["pending_removals"]]) or "Пусто"
    bot.reply_to(
        message,
        f"📋 *Очередь на выдачу (!claim):*\n{rewards_str}\n\n🗑 *Очередь на снятие:*\n{removals_str}",
        parse_mode="Markdown"
    )


# ==========================================
# 7. ОБРАБОТКА КНОПОК МЕНЮ И ПОКУПКИ ЗА STARS
# ==========================================
@bot.message_handler(func=lambda m: m.text in [
    "🛒 Купить донат",
    "💎 Описание привилегий",
    "📜 Команды сервера",
    "👤 Мой ник / Профиль",
    "🌍 IP и Чат сервера"
])
def handle_menu_buttons(message):
    uid = str(message.from_user.id)
    if message.text == "🛒 Купить донат":
        saved_nick = db["user_nicknames"].get(uid, "Не указан")
        bot.send_message(
            message.chat.id,
            f"🛒 *МАГАЗИН ПРИВИЛЕГИЙ BURGER SMP*\n"
            f"👤 Ваш текущий ник: `{saved_nick}`\n\n"
            "Выберите нужный пакет ниже:",
            parse_mode="Markdown",
            reply_markup=get_shop_inline_kb(message.from_user.id)
        )
    elif message.text == "💎 Описание привилегий":
        bot.send_message(
            message.chat.id,
            RANKS_INFO_TEXT,
            parse_mode="Markdown",
            reply_markup=get_shop_inline_kb(message.from_user.id)
        )
    elif message.text == "📜 Команды сервера":
        bot.send_message(message.chat.id, COMMANDS_INFO_TEXT, parse_mode="Markdown")
    elif message.text == "👤 Мой ник / Профиль":
        saved_nick = db["user_nicknames"].get(uid)
        rank = db["owned_ranks"].get(saved_nick.lower(), "Обычный игрок") if saved_nick else "Неизвестно"
        in_queue = "✅ Да (введите !claim в игре)" if (saved_nick and saved_nick.lower() in db["pending_rewards"]) else "Нет"

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✏️ Изменить ник", callback_data="change_nick"))
        bot.send_message(
            message.chat.id,
            f"👤 *ВАШ ПРОФИЛЬ:*\n\n"
            f"🎮 Ник в Minecraft: `{saved_nick or 'Не привязан'}`\n"
            f"💎 Статус: `{rank}`\n"
            f"📦 Ожидает получения в `!claim`: *{in_queue}*",
            parse_mode="Markdown",
            reply_markup=kb
        )
    elif message.text == "🌍 IP и Чат сервера":
        bot.send_message(
            message.chat.id,
            f"🌍 *ДАННЫЕ ДЛЯ ВХОДА НА СЕРВЕР:*\n\n"
            f"• *Имя:* `Burger SMP`\n"
            f"• *IP:* `{SERVER_IP}`\n"
            f"• *Порт:* `{SERVER_PORT}`\n\n"
            f"💬 *Телеграм-чат игроков:* {TELEGRAM_CHAT}\n"
            f"⚡ В игре отправьте в чат символ `!` для открытия быстрого меню всех команд!",
            parse_mode="Markdown"
        )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data == "change_nick":
        waiting_for_nick[uid] = "change_nick"
        bot.send_message(
            call.message.chat.id,
            "✏️ *Введите ваш точный никнейм в Minecraft Bedrock* (с учетом пробелов и цифр):",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if data in ["buy_donor_plus", "buy_donor_plus_plus", "buy_upgrade"]:
        action_map = {
            "buy_donor_plus": "donor_plus",
            "buy_donor_plus_plus": "donor_plus_plus",
            "buy_upgrade": "upgrade"
        }
        chosen_type = action_map[data]
        saved_nick = db["user_nicknames"].get(str(uid))

        if not saved_nick:
            waiting_for_nick[uid] = chosen_type
            bot.send_message(
                call.message.chat.id,
                "🎮 *Перед покупкой напишите ваш точный никнейм на сервере Minecraft:*",
                parse_mode="Markdown"
            )
            bot.answer_callback_query(call.id)
            return

        send_stars_invoice(call.message.chat.id, uid, saved_nick, chosen_type)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("revoke_"):
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "Только для администратора!", show_alert=True)
            return

        target_nick = data.replace("revoke_", "").strip()
        key = target_nick.lower()
        if key in db["pending_rewards"]:
            del db["pending_rewards"][key]
        if key not in db["pending_removals"]:
            db["pending_removals"].append(key)
        save_db()

        bot.edit_message_text(
            call.message.text + f"\n\n🚫 [АННУЛИРОВАНО АДМИНИСТРАТОРОМ для {target_nick}]",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, f"Донат игрока {target_nick} аннулирован!")


@bot.message_handler(func=lambda m: m.from_user.id in waiting_for_nick)
def handle_nick_input(message):
    uid = message.from_user.id
    nick = message.text.strip()

    if len(nick) < 2 or len(nick) > 32 or nick.startswith("/"):
        bot.reply_to(message, "❌ Пожалуйста, введите корректный ник из Minecraft!")
        return

    mode = waiting_for_nick.pop(uid)
    db["user_nicknames"][str(uid)] = nick
    save_db()

    if mode == "change_nick":
        bot.reply_to(
            message,
            f"✅ Ваш никнейм сохранен как: `{nick}`",
            parse_mode="Markdown",
            reply_markup=get_shop_inline_kb(uid)
        )
    else:
        bot.reply_to(
            message,
            f"✅ Никнейм `{nick}` сохранен! Формируем счет на оплату...",
            parse_mode="Markdown"
        )
        send_stars_invoice(message.chat.id, uid, nick, mode)


def send_stars_invoice(chat_id, user_id, nick, purchase_type):
    if purchase_type == "donor_plus":
        title = "Привилегия BURGER [+] (Навсегда)"
        description = (
            f"Выдача привилегии [+] для игрока {nick} НАВСЕГДА: "
            "5 домов, 15 слотов на Аукционе (!ah), 7 заказов (!orders), RTP 25k и кик из племени."
        )
        price = PRICE_PLUS
        tag = "donor_plus"
    elif purchase_type == "upgrade":
        title = "Апгрейд с [+] до BURGER [++] (Навсегда)"
        description = (
            f"Повышение до [++] для игрока {nick}: "
            "7 домов, 20 слотов !ah, 10 заказов !orders, RTP 30k, !rtpend, база племени !tribe sethome и !kill."
        )
        price = PRICE_UPGRADE
        tag = "donor_plus_plus"
    else:
        title = "Привилегия BURGER [++] (Навсегда)"
        description = (
            f"Выдача привилегии [++] для игрока {nick} НАВСЕГДА: "
            "7 домов, 20 слотов !ah, 10 заказов !orders, RTP 30k, !rtpend, база племени !tribe sethome и !kill."
        )
        price = PRICE_PLUS_PLUS
        tag = "donor_plus_plus"

    payload = json.dumps({"nick": nick, "tag": tag, "uid": user_id})
    prices = [LabeledPrice(label=title, amount=price)]

    bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        invoice_payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices
    )


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def got_payment(message):
    payment_info = message.successful_payment
    try:
        payload = json.loads(payment_info.invoice_payload)
        nick = payload["nick"]
        tag = payload["tag"]
    except Exception:
        nick = db["user_nicknames"].get(str(message.from_user.id), "Unknown")
        tag = "donor_plus"

    key = nick.lower()
    db["pending_rewards"][key] = {"original_name": nick, "tag": tag}
    db["owned_ranks"][key] = tag
    if key in db["pending_removals"]:
        db["pending_removals"].remove(key)
    save_db()

    rank_display = "BURGER [++]" if tag == "donor_plus_plus" else "BURGER [+]"
    stars_paid = payment_info.total_amount

    bot.send_message(
        message.chat.id,
        f"🎉 *ОПЛАТА УСПЕШНА! СПАСИБО ЗА ПОДДЕРЖКУ СЕРВЕРА!*\n\n"
        f"👤 Игрок: `{nick}`\n"
        f"👑 Привилегия: *{rank_display} (НАВСЕГДА)*\n"
        f"⭐️ Оплачено: *{stars_paid} Stars*\n\n"
        f"👉 *КАК ЗАБРАТЬ ДОНАТ:*\n"
        f"Зайдите на сервер `{SERVER_IP}` и напишите в чат команду:\n"
        f"`!claim`\n"
        f"*(или выберите «Забрать покупку (!claim)» в быстром меню `!`)*",
        parse_mode="Markdown"
    )

    try:
        admin_kb = InlineKeyboardMarkup()
        admin_kb.add(
            InlineKeyboardButton(
                f"🚫 Аннулировать донат ({nick})",
                callback_data=f"revoke_{nick}"
            )
        )
        username_str = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
        bot.send_message(
            ADMIN_ID,
            f"💰 *НОВАЯ ПОКУПКА В МАГАЗИНЕ!*\n\n"
            f"👤 Покупатель: `{username_str}`\n"
            f"🎮 Ник в игре: `{nick}`\n"
            f"💎 Выдан тег: `{tag}`\n"
            f"⭐️ Сумма: *{stars_paid} XTR*",
            parse_mode="Markdown",
            reply_markup=admin_kb
        )
    except Exception as e:
        print(f"[Admin Notify Error] {e}")


# ==========================================
# 8. ЗАПУСК FLASK И TELEGRAM БОТА (С ЗАЩИТОЙ ОТ 409 CONFLICT)
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def start_bot_polling():
    # Ждем 5 секунд перед стартом, чтобы старый контейнер Render успел завершиться
    time.sleep(5)
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            print("[BurgerShopBot] Telegram-пуллинг активен!")
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"[Polling Retry] Ожидание освобождения токена (409): {e}")
            time.sleep(5)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("[BurgerShopBot] Flask API запущен! Подключаем Telegram-бота...")
    start_bot_polling()
