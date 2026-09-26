import os
from datetime import datetime, timedelta
import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
from threading import Thread

BOT_VERSION = "v3.6-CLOUD"
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Веб-сервер Flask для 24/7 работы и выдачи наград
app = Flask('')

# Хранилище выданных наград в облаке: {никнейм: {"tag": тег, "days": дни}}
pending_rewards = {}
user_subscriptions = {}

@app.route('/')
def home():
    return f"Burger Shop Bot is running! Version: {BOT_VERSION}"

# Ссылка, по которой сервер может проверять и забирать награды
@app.route('/check-reward', methods=['GET'])
def check_reward():
    nickname = request.args.get('name', '').strip().lower()
    for nick, data in list(pending_rewards.items()):
        if nick.lower() == nickname:
            pending_rewards.pop(nick)
            return jsonify({"status": "success", "tag": data["tag"], "days": data["days"]})
    return jsonify({"status": "none"})

def run_flask():
    app.run(host='0.0.0.0', port=8080, use_reloader=False)

Thread(target=run_flask, daemon=True).start()

bot = telebot.TeleBot(BOT_TOKEN)
user_nicknames = {}

# ЦЕНЫ В TELEGRAM STARS
PRICE_PLUS_1M = 100
PRICE_PLUS_3M = 270   
PRICE_PLUSPLUS_1M = 200
PRICE_PLUSPLUS_3M = 540 


@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        f"Привет! 🍔 Добро пожаловать в магазин сервера **Burger Empire** (`burgersmp.org`).\n"
        f"⚙️ *Версия бота:* `{BOT_VERSION}`\n\n"
        "Пожалуйста, напиши свой **точный никнейм** в Minecraft, чтобы продолжить:",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, save_nickname)


def save_nickname(message):
    nickname = message.text.strip()
    if not nickname or " " in nickname:
        bot.send_message(message.chat.id, "❌ Ник не должен содержать пробелов. Введите ник еще раз:")
        bot.register_next_step_handler(message, save_nickname)
        return

    user_nicknames[message.chat.id] = nickname
    show_main_menu(message.chat.id, nickname)


def show_main_menu(chat_id, nickname):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💎 Купить Донат [+] (100 ⭐)", callback_data="menu_plus"),
        InlineKeyboardButton("👑 Купить Донат [++] (200 ⭐)", callback_data="menu_plusplus"),
        InlineKeyboardButton("⏳ Проверить срок моего доната", callback_data="check_status"),
        InlineKeyboardButton("🔑 Ввести промокод", callback_data="enter_promo"),
        InlineKeyboardButton("✏️ Сменить ник", callback_data="change_nick")
    )

    bot.send_message(
        chat_id,
        f"👤 Твой ник: **{nickname}**\n\nВыбери нужный раздел в меню:",
        reply_markup=markup,
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['promo'])
def cmd_promo(message):
    bot.send_message(message.chat.id, "🔑 Введите секретный промокод разработчика:")
    bot.register_next_step_handler(message, process_promo_input)

def process_promo_input(message):
    code = message.text.strip()
    chat_id = message.chat.id
    nickname = user_nicknames.get(chat_id)

    if code == "Burgerbetacheckdev013":
        if not nickname:
            bot.send_message(chat_id, "❌ Сначала укажите свой ник в Minecraft через /start!")
            return
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🎁 [+] Бесплатно (30 дней)", callback_data="free_plus"),
            InlineKeyboardButton("🎁 [++] Бесплатно (30 дней)", callback_data="free_plusplus")
        )
        bot.send_message(
            chat_id,
            "✅ **Промокод принят!** Режим бета-теста активирован.\nВыберите привилегию для бесплатной выдачи:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(chat_id, "❌ Неверный промокод.")


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    nickname = user_nicknames.get(chat_id)

    if call.data == "change_nick":
        bot.send_message(chat_id, "Введите ваш новый ник в Minecraft:")
        bot.register_next_step_handler(call.message, save_nickname)
        bot.answer_callback_query(call.id)
        return

    if call.data == "enter_promo":
        bot.send_message(chat_id, "🔑 Введите секретный промокод разработчика:")
        bot.register_next_step_handler(call.message, process_promo_input)
        bot.answer_callback_query(call.id)
        return

    # Выдача по промокоду (тест)
    if call.data in ["free_plus", "free_plusplus"]:
        if not nickname:
            bot.answer_callback_query(call.id, "Сначала укажите ник!")
            return
        
        tag = "donor_plus" if call.data == "free_plus" else "donor_plus_plus"
        tier_name = "Plus [+]" if call.data == "free_plus" else "PlusPlus [++]"
        
        pending_rewards[nickname] = {"tag": tag, "days": 30}
        expires = datetime.now() + timedelta(days=30)
        user_subscriptions[nickname.lower()] = {"tier": tier_name, "expires_at": expires}

        bot.send_message(
            chat_id, 
            f"🛠️ **[БЕТА-ТЕСТ]** Привилегия `{tier_name}` для игрока `{nickname}` добавлена в облачную очередь выдачи!",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "check_status":
        if not nickname:
            bot.answer_callback_query(call.id, "⚠️ Сначала введите ник через /start!")
            return
        
        sub = user_subscriptions.get(nickname.lower())
        if not sub or datetime.now() > sub["expires_at"]:
            bot.send_message(chat_id, f"❌ У игрока `{nickname}` нет активных привилегий.", parse_mode="Markdown")
        else:
            left = sub["expires_at"] - datetime.now()
            bot.send_message(
                chat_id,
                f"⏳ **Статус для `{nickname}`:**\n• Уровень: **{sub['tier']}**\n• Осталось: **{left.days} дн. {left.seconds // 3600} ч.**",
                parse_mode="Markdown"
            )
        bot.answer_callback_query(call.id)
        return

    if call.data == "menu_plus":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("1 месяц (100 ⭐)", callback_data="buy_plus_1m"),
            InlineKeyboardButton("3 месяца (270 ⭐)", callback_data="buy_plus_3m"),
            InlineKeyboardButton("⬅️ Назад", callback_data="back_menu")
        )
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="💎 **Привилегия [+] (Plus):**\n• 5 домов\n• RTP 25k\n• Префикс [+]\n\nВыбери срок:", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data == "menu_plusplus":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("1 месяц (200 ⭐)", callback_data="buy_plusplus_1m"),
            InlineKeyboardButton("3 месяца (540 ⭐)", callback_data="buy_plusplus_3m"),
            InlineKeyboardButton("⬅️ Назад", callback_data="back_menu")
        )
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="👑 **Привилегия [++] (PlusPlus):**\n• 7 домов\n• RTP 30k\n• Префикс [++]\n\nВыбери срок:", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data == "back_menu":
        if nickname:
            show_main_menu(chat_id, nickname)
        bot.answer_callback_query(call.id)
        return

    if not nickname:
        bot.answer_callback_query(call.id, "⚠️ Сначала введите ник!")
        return

    if call.data == "buy_plus_1m":
        bot.send_invoice(chat_id=chat_id, title="Донат [+] 1 мес", description=f"Для {nickname}", invoice_payload="pay_plus_1m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUS_1M)])
    elif call.data == "buy_plus_3m":
        bot.send_invoice(chat_id=chat_id, title="Донат [+] 3 мес", description=f"Для {nickname}", invoice_payload="pay_plus_3m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUS_3M)])
    elif call.data == "buy_plusplus_1m":
        bot.send_invoice(chat_id=chat_id, title="Донат [++] 1 мес", description=f"Для {nickname}", invoice_payload="pay_plusplus_1m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUSPLUS_1M)])
    elif call.data == "buy_plusplus_3m":
        bot.send_invoice(chat_id=chat_id, title="Донат [++] 3 мес", description=f"Для {nickname}", invoice_payload="pay_plusplus_3m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUSPLUS_3M)])
    
    bot.answer_callback_query(call.id)


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(q):
    bot.answer_pre_checkout_query(q.id, ok=True)


@bot.message_handler(content_types=['successful_payment'])
def success_payment(message):
    chat_id = message.chat.id
    nickname = user_nicknames.get(chat_id, "Игрок")
    payload = message.successful_payment.invoice_payload

    days = 90 if "3m" in payload else 30
    if "plusplus" in payload:
        tag = "donor_plus_plus"
        tier_name = "PlusPlus [++]"
    else:
        tag = "donor_plus"
        tier_name = "Plus [+]"

    pending_rewards[nickname] = {"tag": tag, "days": days}
    expires = datetime.now() + timedelta(days=days)
    user_subscriptions[nickname.lower()] = {"tier": tier_name, "expires_at": expires}

    bot.send_message(
        chat_id,
        f"✅ **Оплата прошла успешно!**\nИгрок: `{nickname}`\nПривилегия **{tier_name}** на `{days} дн.` добавлена в очередь! Спасибо! 🍔",
        parse_mode="Markdown"
    )


if __name__ == "__main__":
    bot.infinity_polling()
