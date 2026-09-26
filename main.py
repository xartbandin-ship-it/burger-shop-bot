import os
from datetime import datetime, timedelta
import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from mcrcon import MCRcon
from flask import Flask
from threading import Thread

# Версия бота для проверки обновления на Render
BOT_VERSION = "v3.5-FIXED"

# Загружаем настройки из облака Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RCON_HOST = os.environ.get("RCON_HOST")
RCON_PORT = int(os.environ.get("RCON_PORT", 5520))
RCON_PASSWORD = os.environ.get("RCON_PASSWORD")

# Веб-сервер Flask для поддержания бота в сети 24/7 на Render
app = Flask('')

@app.route('/')
def home():
    return f"Burger Shop Bot is running! Version: {BOT_VERSION}"

def run_flask():
    # use_reloader=False полностью решает ошибку signal only works in main thread
    app.run(host='0.0.0.0', port=8080, use_reloader=False)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

bot = telebot.TeleBot(BOT_TOKEN)
user_nicknames = {}
user_subscriptions = {}  # Хранит информацию о подписках игроков

# ЦЕНЫ В TELEGRAM STARS
PRICE_PLUS_1M = 100
PRICE_PLUS_3M = 270   
PRICE_PLUSPLUS_1M = 200
PRICE_PLUSPLUS_3M = 540 


# Функция отправки Bedrock-команды на сервер через RCON
def send_bedrock_command(command):
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(command)
            return True, response
    except Exception as e:
        return False, str(e)


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
    
    btn_plus = InlineKeyboardButton("💎 Купить Донат [+] (100 ⭐)", callback_data="menu_plus")
    btn_plusplus = InlineKeyboardButton("👑 Купить Донат [++] (200 ⭐)", callback_data="menu_plusplus")
    btn_check = InlineKeyboardButton("⏳ Проверить срок моего доната", callback_data="check_status")
    btn_promo = InlineKeyboardButton("🔑 Ввести промокод", callback_data="enter_promo")
    btn_change = InlineKeyboardButton("✏️ Сменить ник", callback_data="change_nick")
    
    markup.add(btn_plus, btn_plusplus, btn_check, btn_promo, btn_change)

    bot.send_message(
        chat_id,
        f"👤 Твой ник: **{nickname}**\n\n"
        "Выбери нужный раздел в меню:",
        reply_markup=markup,
        parse_mode="Markdown"
    )


# --- СЕКРЕТНЫЙ ПРОМОКОД ДЛЯ ТЕСТОВ ---
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
        markup.add(InlineKeyboardButton("🎁 [+] Бесплатно (30 дней)", callback_data="free_plus"))
        markup.add(InlineKeyboardButton("🎁 [++] Бесплатно (30 дней)", callback_data="free_plusplus"))
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

    # Бесплатная выдача по промокоду через RCON
    if call.data in ["free_plus", "free_plusplus"]:
        if not nickname:
            bot.answer_callback_query(call.id, "Сначала укажите ник!")
            return
        
        tag = "donor_plus" if call.data == "free_plus" else "donor_plus_plus"
        tier_name = "Plus [+]" if call.data == "free_plus" else "PlusPlus [++]"
        
        command = f'tag "{nickname}" add {tag}'
        success, rcon_resp = send_bedrock_command(command)

        if success:
            expires = datetime.now() + timedelta(days=30)
            user_subscriptions[nickname.lower()] = {"tier": tier_name, "expires_at": expires}
            bot.send_message(
                chat_id, 
                f"🛠️ **[БЕТА-ТЕСТ]** Привилегия `{tier_name}` успешно выдана игроку `{nickname}` на 30 дней!",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id,
                f"⚠️ **Ошибка RCON!** Сервер не принял команду.\nПричина: `{rcon_resp}`",
                parse_mode="Markdown"
            )
        bot.answer_callback_query(call.id)
        return

    # Проверка оставшегося времени доната
    if call.data == "check_status":
        if not nickname:
            bot.answer_callback_query(call.id, "⚠️ Сначала введите ник через /start!")
            return
        
        sub = user_subscriptions.get(nickname.lower())
        if not sub or datetime.now() > sub["expires_at"]:
            bot.send_message(
                chat_id,
                f"❌ У игрока `{nickname}` нет активных платных привилегий или срок их действия истек.",
                parse_mode="Markdown"
            )
        else:
            left = sub["expires_at"] - datetime.now()
            days = left.days
            hours = left.seconds // 3600
            minutes = (left.seconds % 3600) // 60
            bot.send_message(
                chat_id,
                f"⏳ **Статус доната для `{nickname}`:**\n"
                f"• Уровень: **{sub['tier']}**\n"
                f"• Осталось до конца: **{days} дн. {hours} ч. {minutes} мин.**",
                parse_mode="Markdown"
            )
        bot.answer_callback_query(call.id)
        return

    # Меню [+]
    if call.data == "menu_plus":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("1 месяц (100 ⭐)", callback_data="buy_plus_1m"))
        markup.add(InlineKeyboardButton("3 месяца (-10%) (270 ⭐)", callback_data="buy_plus_3m"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_menu"))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="💎 **Привилегия [+] (Plus):**\n• 5 домов\n• RTP 25k\n• Префикс [+]\n\nВыбери срок подписки:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    # Меню [++]
    if call.data == "menu_plusplus":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("1 месяц (200 ⭐)", callback_data="buy_plusplus_1m"))
        markup.add(InlineKeyboardButton("3 месяца (-10%) (540 ⭐)", callback_data="buy_plusplus_3m"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_menu"))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="👑 **Привилегия [++] (PlusPlus):**\n• 7 домов\n• RTP 30k\n• Префикс [++]\n\nВыбери срок подписки:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "back_menu":
        if nickname:
            show_main_menu(chat_id, nickname)
        bot.answer_callback_query(call.id)
        return

    if not nickname:
        bot.answer_callback_query(call.id, "⚠️ Сначала введите ник через /start!")
        return

    # Инвойсы Telegram Stars для покупки
    if call.data == "buy_plus_1m":
        prices = [LabeledPrice(label="Донат [+] 1 мес", amount=PRICE_PLUS_1M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [+] (1 месяц)", description=f"Для {nickname}", invoice_payload="pay_plus_1m", provider_token="", currency="XTR", prices=prices)
    elif call.data == "buy_plus_3m":
        prices = [LabeledPrice(label="Донат [+] 3 мес", amount=PRICE_PLUS_3M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [+] (3 месяца)", description=f"Для {nickname}", invoice_payload="pay_plus_3m", provider_token="", currency="XTR", prices=prices)
    elif call.data == "buy_plusplus_1m":
        prices = [LabeledPrice(label="Донат [++] 1 мес", amount=PRICE_PLUSPLUS_1M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [++] (1 месяц)", description=f"Для {nickname}", invoice_payload="pay_plusplus_1m", provider_token="", currency="XTR", prices=prices)
    elif call.data == "buy_plusplus_3m":
        prices = [LabeledPrice(label="Донат [++] 3 мес", amount=PRICE_PLUSPLUS_3M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [++] (3 месяца)", description=f"Для {nickname}", invoice_payload="pay_plusplus_3m", provider_token="", currency="XTR", prices=prices)
    
    bot.answer_callback_query(call.id)


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


# ВЫДАЧА ДОНАТА ЧЕРЕЗ RCON ПОСЛЕ УСПЕШНОЙ ОПЛАТЫ ЗВЕЗДАМИ
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

    command = f'tag "{nickname}" add {tag}'
    success, rcon_resp = send_bedrock_command(command)

    if success:
        expires = datetime.now() + timedelta(days=days)
        user_subscriptions[nickname.lower()] = {"tier": tier_name, "expires_at": expires}
        bot.send_message(
            chat_id,
            f"✅ **Оплата прошла успешно!**\n\n"
            f"Игрок: `{nickname}`\n"
            f"Привилегия **{tier_name}** выдана на `{days} дн.` прямо в игру! Спасибо за поддержку! 🍔",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(
            chat_id,
            f"⚠️ Оплата прошла, но сервер не ответил по RCON.\nОшибка: `{rcon_resp}`\nАдминистратор выдаст привилегию вручную."
        )


if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
