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
ADMIN_USERNAME = "meburger34"  # Юзернейм для доступа по слову dev324

SERVER_IP = "burgersmp.org"
SERVER_PORT = "19132"
TELEGRAM_CHAT = "https://t.me/burgerchatsmp"

PRICE_PLUS = 150
PRICE_PLUS_PLUS = 300
PRICE_UPGRADE = 150

DATA_FILE = "shop_data.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==========================================
# 2. БАЗА ДАННЫХ И СОСТОЯНИЯ АДМИНА
# ==========================================
db = {
    "pending_rewards": {},
    "pending_removals": [],
    "user_nicknames": {},
    "owned_ranks": {}
}

waiting_for_nick = {}      # Для покупки доната игроками
admin_dev_mode = {}        # Для режима dev324 (какой админ какому нику выдает донат)


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
# 4. ТЕКСТЫ И КЛАВИАТУРЫ (СТАРИННЫЙ ДИЗАЙН)
# ==========================================
WELCOME_TEXT = (
    "🍔 *Добро пожаловать в магазин BURGER SMP!*\n\n"
    f"🌍 *IP сервера:* `{SERVER_IP}`\n"
    f"🔌 *Порт:* `{SERVER_PORT}`\n"
    f"💬 *Наш чат:* {TELEGRAM_CHAT}\n\n"
    "🔥 *Все привилегии покупаются НАВСЕГДА!* Оплата происходит через *Telegram Stars (⭐️)*.\n"
    "После оплаты введите в игре команду `!claim` для получения доната!"
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
    "• Префикс `[+]` в чате и над головой\n"
    "• 5 домов | 15 слотов `!ah` | 7 слотов `!orders` | RTP 25k | кик из клана\n\n"
    "━━━━━━━━━━━━━━━\n"
    f"👑 *Привилегия BURGER [++] — {PRICE_PLUS_PLUS} ⭐️ (Навсегда):*\n"
    "• Золотой префикс `[++]` в чате и над головой\n"
    "• 7 домов | 20 слотов `!ah` | 10 слотов `!orders` | RTP 30k\n"
    "• `!rtpend`, установка базы клана `!tribe sethome` и `!kill`"
)

COMMANDS_INFO_TEXT = (
    "📜 *КОМАНДЫ СЕРВЕРА BURGER SMP:*\n\n"
    "⚡ В игре отправьте *`!`* в чат для открытия быстрого меню команд!\n\n"
    "• `!ah` — Аукцион (с воронкой сортировки и осмотром предметов)\n"
    "• `!orders` — Стол Заказов (с карточкой осмотра заказа)\n"
    "• `!sell` — Продажа ресурсов (авто-сдача в выгодные заказы)\n"
    "• `!bounty` — Охота за головами\n"
    "• `!bal` / `!pay` / `!baltop` / `!killtop` — Экономика и топы\n"
    "• `!spawn` / `!rtp` / `!tp` / `!home` — Телепортация и дома\n"
    "• `!tribe` — Управление кланом\n"
    "• `!claim` — Забрать купленный донат"
)


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
        InlineKeyboardButton(f"🔹 Купить BURGER [+] — {PRICE_PLUS} ⭐️", callback_data="buy_donor_plus"),
        InlineKeyboardButton(f"👑 Купить BURGER [++] — {PRICE_PLUS_PLUS} ⭐️", callback_data="buy_donor_plus_plus")
    )
    if current_rank == "donor_plus":
        kb.add(InlineKeyboardButton(f"⬆️ Апгрейд с [+] до [++] — {PRICE_UPGRADE} ⭐️", callback_data="buy_upgrade"))
    kb.add(InlineKeyboardButton("✏️ Изменить мой ник в Minecraft", callback_data="change_nick"))
    return kb


# ==========================================
# 5. ОБРАБОТЧИКИ СООБЩЕНИЙ И СЛОВА dev324
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_main_reply_kb()
    )


@bot.message_handler(commands=["commands", "help"])
def cmd_help(message):
    bot.send_message(message.chat.id, COMMANDS_INFO_TEXT, parse_mode="Markdown")


# Проверка прав администратора для dev324
def is_dev_admin(user):
    if user.id == ADMIN_ID:
        return True
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        return True
    return False


@bot.message_handler(func=lambda m: m.text and m.text.strip() == "dev324")
def handle_dev324_trigger(message):
    if not is_dev_admin(message.from_user):
        return
    
    admin_uid = message.from_user.id
    admin_dev_mode[admin_uid] = "waiting_target_nick"
    bot.reply_to(message, "⚙️ *Введите точный ник игрока в Minecraft, которым хотите управлять:*", parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.from_user.id in admin_dev_mode and admin_dev_mode[m.from_user.id] == "waiting_target_nick")
def handle_dev_target_nick(message):
    admin_uid = message.from_user.id
    target_nick = message.text.strip()
    
    if not target_nick or target_nick.startswith("/"):
        bot.reply_to(message, "❌ Некорректный ник! Попробуйте еще раз:")
        return

    admin_dev_mode[admin_uid] = {"mode": "managing_nick", "nick": target_nick}

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(f"🎁 Выдать [+] для {target_nick}", callback_data=f"dev_give_+_{target_nick}"),
        InlineKeyboardButton(f"🎁 Выдать [++] для {target_nick}", callback_data=f"dev_give_++_{target_nick}"),
        InlineKeyboardButton(f"❌ Снять все донаты с {target_nick}", callback_data=f"dev_remove_{target_nick}"),
        InlineKeyboardButton("🏠 На главную", callback_data="dev_cancel")
    )

    bot.send_message(
        message.chat.id,
        f"🛠 *Панель управления игроком: {target_nick}*\nВыберите нужное действие:",
        parse_mode="Markdown",
        reply_markup=kb
    )


# ==========================================
# 6. КНОПКИ ГЛАВНОГО МЕНЮ И DEV-ПАНЕЛИ
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
    if message.from_user.id in admin_dev_mode:
        admin_dev_mode.pop(message.from_user.id)

    if message.text == "🛒 Купить донат":
        saved_nick = db["user_nicknames"].get(uid, "Не указан")
        bot.send_message(
            message.chat.id,
            f"🛒 *МАГАЗИН ПРИВИЛЕГИЙ BURGER SMP*\n👤 Ваш ник: `{saved_nick}`\n\nВыберите пакет ниже:",
            parse_mode="Markdown",
            reply_markup=get_shop_inline_kb(message.from_user.id)
        )
    elif message.text == "💎 Описание привилегий":
        bot.send_message(message.chat.id, RANKS_INFO_TEXT, parse_mode="Markdown", reply_markup=get_shop_inline_kb(message.from_user.id))
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
            f"👤 *ПРОФИЛЬ:*\n🎮 Ник: `{saved_nick or 'Не привязан'}`\n💎 Статус: `{rank}`\n📦 Ожидает выдачи: *{in_queue}*",
            parse_mode="Markdown",
            reply_markup=kb
        )
    elif message.text == "🌍 IP и Чат сервера":
        bot.send_message(
            message.chat.id,
            f"🌍 *IP:* `{SERVER_IP}` | *Порт:* `{SERVER_PORT}`\n💬 *Чат:* {TELEGRAM_CHAT}\n⚡ В игре пишите `!` для быстрого меню!",
            parse_mode="Markdown"
        )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data == "dev_cancel":
        if uid in admin_dev_mode:
            admin_dev_mode.pop(uid)
        bot.edit_message_text("🏠 Панель закрыта.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    if data.startswith("dev_give_+_") or data.startswith("dev_give_++_") or data.startswith("dev_remove_"):
        if not is_dev_admin(call.from_user):
            bot.answer_callback_query(call.id, "Нет прав!", show_alert=True)
            return

        parts = data.split("_")
        if data.startswith("dev_remove_"):
            target_nick = data.replace("dev_remove_", "").strip()
            key = target_nick.lower()
            if key in db["pending_rewards"]:
                del db["pending_rewards"][key]
            if key not in db["pending_removals"]:
                db["pending_removals"].append(key)
            save_db()
            bot.answer_callback_query(call.id, f"Сняты донаты с {target_nick}!")
            bot.send_message(call.message.chat.id, f"❌ Все донаты сняты с {target_nick} в очередь !")
        else:
            rank_type = "donor_plus" if parts[2] == "+" else "donor_plus_plus"
            target_nick = parts[3].strip()
            key = target_nick.lower()

            db["pending_rewards"][key] = {"original_name": target_nick, "tag": rank_type}
            db["owned_ranks"][key] = rank_type
            if key in db["pending_removals"]:
                db["pending_removals"].remove(key)
            save_db()

            plus_sign = "+" if rank_type == "donor_plus" else "++"
            bot.answer_callback_query(call.id, f"Выдано {plus_sign} для {target_nick}!")
            bot.send_message(call.message.chat.id, f"✅ Для {target_nick} добавлена награда {plus_sign} в очередь! Пропишите !claim в игре.")

        if uid in admin_dev_mode:
            admin_dev_mode.pop(uid)
        return

    if data == "change_nick":
        waiting_for_nick[uid] = "change_nick"
        bot.send_message(call.message.chat.id, "✏️ *Введите ваш точный никнейм в Minecraft Bedrock:*", parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if data in ["buy_donor_plus", "buy_donor_plus_plus", "buy_upgrade"]:
        action_map = {"buy_donor_plus": "donor_plus", "buy_donor_plus_plus": "donor_plus_plus", "buy_upgrade": "upgrade"}
        chosen_type = action_map[data]
        saved_nick = db["user_nicknames"].get(str(uid))

        if not saved_nick:
            waiting_for_nick[uid] = chosen_type
            bot.send_message(call.message.chat.id, "🎮 *Перед покупкой напишите ваш точный никнейм на сервере:*", parse_mode="Markdown")
            bot.answer_callback_query(call.id)
            return

        send_stars_invoice(call.message.chat.id, uid, saved_nick, chosen_type)
        bot.answer_callback_query(call.id)
        return


@bot.message_handler(func=lambda m: m.from_user.id in waiting_for_nick)
def handle_nick_input(message):
    uid = message.from_user.id
    nick = message.text.strip()
    if len(nick) < 2 or len(nick) > 32 or nick.startswith("/"):
        bot.reply_to(message, "❌ Пожалуйста, введите корректный ник!")
        return

    mode = waiting_for_nick.pop(uid)
    db["user_nicknames"][str(uid)] = nick
    save_db()

    if mode == "change_nick":
        bot.reply_to(message, f"✅ Ник сохранен: `{nick}`", parse_mode="Markdown", reply_markup=get_shop_inline_kb(uid))
    else:
        send_stars_invoice(message.chat.id, uid, nick, mode)


def send_stars_invoice(chat_id, user_id, nick, purchase_type):
    if purchase_type == "donor_plus":
        title, price, tag = "Привилегия BURGER [+] (Навсегда)", PRICE_PLUS, "donor_plus"
    elif purchase_type == "upgrade":
        title, price, tag = "Апгрейд с [+] до [++] (Навсегда)", PRICE_UPGRADE, "donor_plus_plus"
    else:
        title, price, tag = "Привилегия BURGER [++] (Навсегда)", PRICE_PLUS_PLUS, "donor_plus_plus"

    payload = json.dumps({"nick": nick, "tag": tag, "uid": user_id})
    prices = [LabeledPrice(label=title, amount=price)]

    bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=f"Выдача {tag} для {nick} НАВСЕГДА",
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
        nick, tag = payload["nick"], payload["tag"]
    except Exception:
        nick, tag = db["user_nicknames"].get(str(message.from_user.id), "Unknown"), "donor_plus"

    key = nick.lower()
    db["pending_rewards"][key] = {"original_name": nick, "tag": tag}
    db["owned_ranks"][key] = tag
    if key in db["pending_removals"]:
        db["pending_removals"].remove(key)
    save_db()

    bot.send_message(
        message.chat.id,
        f"🎉 *ОПЛАТА УСПЕШНА!*\nИгрок: `{nick}`\nПривилегия выдана навсегда!\nЗайдите в игру и введите:\n`!claim`",
        parse_mode="Markdown"
    )


# ==========================================
# 7. ЗАПУСК БОТА С ЗАЩИТОЙ ОТ 409 КОНФЛИКТА
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def start_bot_polling():
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
