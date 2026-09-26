import os
import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from mcrcon import MCRcon
from flask import Flask
from threading import Thread

# Загружаем настройки из облака
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RCON_HOST = os.environ.get("RCON_HOST")
RCON_PORT = int(os.environ.get("RCON_PORT", 5520))
RCON_PASSWORD = os.environ.get("RCON_PASSWORD")

# Веб-сервер для поддержания работы бота 24/7
app = Flask('')

@app.route('/')
def home():
    return "Burger Shop Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

bot = telebot.TeleBot(BOT_TOKEN)
user_nicknames = {}

# Цены в Telegram Stars
PRICE_1M = 50   # VIP на 1 месяц
PRICE_3M = 135  # VIP+ на 3 месяца (-10% скидка)

@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "Привет! 🍔 Добро пожаловать в магазин сервера **Burger Empire**.\n\n"
        "Напиши свой **точный никнейм** в Minecraft, чтобы продолжить:"
    )
    bot.register_next_step_handler(message, save_nickname)

def save_nickname(message):
    nickname = message.text.strip()
    if not nickname or " " in nickname:
        bot.send_message(message.chat.id, "❌ Ник не должен содержать пробелов. Введите ник еще раз:")
        bot.register_next_step_handler(message, save_nickname)
        return

    user_nicknames[message.chat.id] = nickname
    show_shop_menu(message.chat.id, nickname)

def show_shop_menu(chat_id, nickname):
    markup = InlineKeyboardMarkup()
    btn_1m = InlineKeyboardButton("💎 VIP (1 месяц) - 50 ⭐", callback_data="buy_1m")
    btn_3m = InlineKeyboardButton("👑 VIP+ (3 месяца, -10%) - 135 ⭐", callback_data="buy_3m")
    btn_change = InlineKeyboardButton("✏️ Сменить ник", callback_data="change_nick")
    markup.add(btn_1m, btn_3m, btn_change)

    bot.send_message(
        chat_id,
        f"👤 Твой ник: **{nickname}**\nВыбери пакет привилегий:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    nickname = user_nicknames.get(chat_id)

    if call.data == "change_nick":
        bot.send_message(chat_id, "Введите ваш новый ник в Minecraft:")
        bot.register_next_step_handler(call.message, save_nickname)
        bot.answer_callback_query(call.id)
        return

    if not nickname:
        bot.answer_callback_query(call.id, "⚠️ Сначала введите ник через /start!")
        return

    if call.data == "buy_1m":
        prices = [LabeledPrice(label="VIP 1 Месяц", amount=PRICE_1M)]
        bot.send_invoice(
            chat_id=chat_id,
            title="VIP Донат (1 Месяц)",
            description=f"Привилегия для игрока {nickname} на 30 дней",
            invoice_payload="buy_vip_1m",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    elif call.data == "buy_3m":
        prices = [LabeledPrice(label="VIP+ 3 Месяца (-10%)", amount=PRICE_3M)]
        bot.send_invoice(
            chat_id=chat_id,
            title="VIP+ 3 Месяца со скидкой 10%",
            description=f"Привилегия для игрока {nickname} на 90 дней",
            invoice_payload="buy_vip_3m",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    bot.answer_callback_query(call.id)

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def success_payment(message):
    chat_id = message.chat.id
    nickname = user_nicknames.get(chat_id, "Игрок")
    payload = message.successful_payment.invoice_payload

    command = ""
    if payload == "buy_vip_1m":
        command = f"lp user {nickname} parent addtemp donor_plus 30d"
    elif payload == "buy_vip_3m":
        command = f"lp user {nickname} parent addtemp donor_plus_plus 90d"

    success = False
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            mcr.command(command)
            success = True
    except Exception as e:
        print(f"RCON Error: {e}")

    if success:
        bot.send_message(chat_id, f"✅ Оплата прошла! Привилегия для `{nickname}` успешно выдана на сервере Burger Empire! 🍔")
    else:
        bot.send_message(chat_id, f"⚠️ Оплата прошла, но сервер не ответил. Администратор выдаст привилегию вручную.")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
