import os
import requests
from datetime import datetime, timedelta
import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
from threading import Thread

BOT_VERSION = "v4.3-SECURE-ADMIN"
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Flask('')

# Очередь на выдачу: хранит ник (в нижнем регистре) и тег доната
pending_rewards = {}
user_subscriptions = {}

@app.route('/')
def home():
    return f"Burger Shop Bot is running! Version: {BOT_VERSION}"

@app.route('/check-reward', methods=['GET'])
def check_reward():
    name = request.args.get('name', '').strip().lower()
    if not name:
        return jsonify({"status": "error", "message": "No name provided"})
    
    if name in pending_rewards:
        tag = pending_rewards.pop(name)
        print(f"🎁 Игрок {name} забрал свою награду: {tag}")
        return jsonify({"status": "success", "tag": tag})
    
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
        "Привет! 🍔 Добро пожаловать в магазин сервера **Burger Empire**.\n\n"
        "Пожалуйста, напиши свой **точный никнейм** в Minecraft:",
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
    markup.add(InlineKeyboardButton("💎 Купить Донат [+] (100 ⭐)", callback_data="menu_plus"))
    markup.add(InlineKeyboardButton("👑 Купить Донат [++] (200 ⭐)", callback_data="menu_plusplus"))
    markup.add(InlineKeyboardButton("⚙️ Другое / Настройки", callback_data="menu_more"))

    bot.send_message(
        chat_id,
        f"👤 Твой ник: **{nickname}**\n\nВыберите привилегию:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['promo'])
def cmd_promo(message):
    bot.send_message(message.chat.id, "🔑 Введите промокод:")
    bot.register_next_step_handler(message, process_promo_input)

def process_promo_input(message):
    code = message.text.strip()
    chat_id = message.chat.id
    nickname = user_nicknames.get(chat_id)
    
    # Получаем юзернейм пользователя из Telegram (без @)
    tg_username = message.from_user.username
    if tg_username:
        tg_username = tg_username.lower()

    if code == "dev324":
        # Строгая привязка промокода к твоему аккаунту Telegram
        if tg_username != "meburger34":
            bot.send_message(chat_id, "❌ У вас нет прав для использования промокодов разработчика.")
            return
            
        if not nickname:
            bot.send_message(chat_id, "❌ Сначала укажите свой ник в Minecraft через /start!")
            return
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎁 Выдать [+] (30 дн)", callback_data="free_plus"))
        markup.add(InlineKeyboardButton("🎁 Выдать [++] (30 дн)", callback_data="free_plusplus"))
        markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))
        
        perks_text = (
            "✅ **Промокод разработчика принят!**\n\n"
            "💎 **Привилегия [+] (Plus):**\n"
            "• Голубой префикс `[+]` в чате\n"
            "• 5 точек дома\n"
            "• RTP на 25 000 блоков\n"
            "• Лимит клана: 6 игроков\n"
            "• Кик из клана для лидера\n\n"
            "👑 **Привилегия [++] (PlusPlus):**\n"
            "• Золотой префикс `[++]` в чате\n"
            "• 7 точек дома\n"
            "• RTP на 30 000 блоков\n"
            "• RTP в Энде (`!rtpend`)\n"
            "• ТП по точным координатам (`!tp X Z`)\n"
            "• Команда самоубийства (`!kill`)\n"
            "• База клана (`!tribe sethome` / `home`)\n"
            "• Лимит клана: 8 игроков\n\n"
            "Выберите привилегию для выдачи:"
        )
        
        bot.send_message(
            chat_id,
            perks_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(chat_id, "❌ Неверный промокод.")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    nickname = user_nicknames.get(chat_id)

    if call.data == "menu_more":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏳ Статус доната", callback_data="check_status"))
        markup.add(InlineKeyboardButton("🔑 Ввести промокод", callback_data="enter_promo"))
        markup.add(InlineKeyboardButton("✏️ Сменить ник", callback_data="change_nick"))
        markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))
        
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id, 
            text="⚙️ **Дополнительное меню:**", 
            reply_markup=markup, parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "change_nick":
        bot.send_message(chat_id, "Введите ваш новый ник в Minecraft:")
        bot.register_next_step_handler(call.message, save_nickname)
        bot.answer_callback_query(call.id)
        return

    if call.data == "enter_promo":
        bot.send_message(chat_id, "🔑 Введите промокод:")
        bot.register_next_step_handler(call.message, process_promo_input)
        bot.answer_callback_query(call.id)
        return

    if call.data in ["free_plus", "free_plusplus"]:
        if not nickname:
            bot.answer_callback_query(call.id, "Укажите ник!")
            return
        
        tag = "donor_plus" if call.data == "free_plus" else "donor_plus_plus"
        tier_name = "Plus [+]" if call.data == "free_plus" else "PlusPlus [++]"
        
        pending_rewards[nickname.lower()] = tag
        expires = datetime.now() + timedelta(days=30)
        user_subscriptions[nickname.lower()] = {"tier": tier_name, "expires_at": expires}

        bot.send_message(
            chat_id, 
            f"🛠️ В очередь добавлено: `{tier_name}`\nЗайдите на сервер и введите `!claim`.",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "check_status":
        if not nickname:
            bot.answer_callback_query(call.id, "Сначала введите ник /start!")
            return
        
        sub = user_subscriptions.get(nickname.lower())
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))

        if not sub or datetime.now() > sub["expires_at"]:
            bot.send_message(chat_id, f"❌ У `{nickname}` нет активных привилегий.", reply_markup=markup, parse_mode="Markdown")
        else:
            left = sub["expires_at"] - datetime.now()
            bot.send_message(
                chat_id,
                f"⏳ **Статус для `{nickname}`:**\n• Уровень: **{sub['tier']}**\n• Осталось: **{left.days} дн. {left.seconds // 3600} ч.**",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        bot.answer_callback_query(call.id)
        return

    if call.data == "menu_plus":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("1 месяц (100 ⭐)", callback_data="buy_plus_1m"))
        markup.add(InlineKeyboardButton("3 месяца (270 ⭐)", callback_data="buy_plus_3m"))
        markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))
        
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id, 
            text="💎 **Привилегия [+] (Plus):**\n• 5 домов\n• RTP 25k\n• Префикс [+]\n\n*⚠️ Товар цифровой, возврату и переносу при вайпе не подлежит.*\n\nВыберите срок:", 
            reply_markup=markup, parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "menu_plusplus":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("1 месяц (200 ⭐)", callback_data="buy_plusplus_1m"))
        markup.add(InlineKeyboardButton("3 месяца (540 ⭐)", callback_data="buy_plusplus_3m"))
        markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))
        
        bot.edit_message_text(
            chat_id=chat_id, message_id=call.message.message_id, 
            text="👑 **Привилегия [++] (PlusPlus):**\n• 7 домов\n• RTP 30k\n• Префикс [++]\n\n*⚠️ Товар цифровой, возврату и переносу при вайпе не подлежит.*\n\nВыберите срок:", 
            reply_markup=markup, parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "back_menu":
        if nickname:
            show_main_menu(chat_id, nickname)
        else:
            bot.send_message(chat_id, "Введите ваш ник через /start")
        bot.answer_callback_query(call.id)
        return

    if not nickname:
        bot.answer_callback_query(call.id, "⚠️ Сначала введите ник!")
        return

    if call.data == "buy_plus_1m":
        bot.send_invoice(chat_id=chat_id, title="Донат [+] (1 мес)", description=f"Цифровой товар для {nickname}.", invoice_payload="pay_plus_1m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUS_1M)])
    elif call.data == "buy_plus_3m":
        bot.send_invoice(chat_id=chat_id, title="Донат [+] (3 мес)", description=f"Цифровой товар для {nickname}.", invoice_payload="pay_plus_3m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUS_3M)])
    elif call.data == "buy_plusplus_1m":
        bot.send_invoice(chat_id=chat_id, title="Донат [++] (1 мес)", description=f"Цифровой товар для {nickname}.", invoice_payload="pay_plusplus_1m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUSPLUS_1M)])
    elif call.data == "buy_plusplus_3m":
        bot.send_invoice(chat_id=chat_id, title="Донат [++] (3 мес)", description=f"Цифровой товар для {nickname}.", invoice_payload="pay_plusplus_3m", provider_token="", currency="XTR", prices=[LabeledPrice("Донат", PRICE_PLUSPLUS_3M)])
    
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

    pending_rewards[nickname.lower()] = tag
    expires = datetime.now() + timedelta(days=days)
    user_subscriptions[nickname.lower()] = {"tier": tier_name, "expires_at": expires}

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))

    bot.send_message(
        chat_id,
        f"✅ **Успешно!**\n\n👤 Игрок: `{nickname}`\n💎 Ранг: **{tier_name}**\n\nЗайдите на `burgersmp.org` и напишите **`!claim`**!",
        reply_markup=markup,
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    bot.infinity_polling()
