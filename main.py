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

# НОВЫЕ ЦЕНЫ В TELEGRAM STARS
# Уровень [+] (100 звезд за 1 месяц, 270 за 3 месяца со скидкой)
PRICE_PLUS_1M = 100
PRICE_PLUS_3M = 270   

# Уровень [++] (200 звезд за 1 месяц, 540 за 3 месяца со скидкой)
PRICE_PLUSPLUS_1M = 200
PRICE_PLUSPLUS_3M = 540 


@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "Привет! 🍔 Добро пожаловать в магазин сервера **Burger Empire** (`burgersmp.org`).\n\n"
        "Пожалуйста, напиши свой **точный никнейм** в Minecraft, чтобы продолжить:"
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
    
    markup.add(btn_plus)
    markup.add(btn_plusplus)
    markup.add(btn_check)
    markup.add(btn_promo)
    markup.add(btn_change)

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

    # Бесплатная выдача по промокоду
    if call.data == "free_plus":
        if not nickname:
            bot.answer_callback_query(call.id, "Сначала укажите ник!")
            return
        execute_free_rcon(chat_id, nickname, f"lp user {nickname} parent addtemp donor_plus 30d", "[+] (Бета-тест)")
        bot.answer_callback_query(call.id)
        return

    if call.data == "free_plusplus":
        if not nickname:
            bot.answer_callback_query(call.id, "Сначала укажите ник!")
            return
        execute_free_rcon(chat_id, nickname, f"lp user {nickname} parent addtemp donor_plus_plus 30d", "[++] (Бета-тест)")
        bot.answer_callback_query(call.id)
        return

    if call.data == "check_status":
        if not nickname:
            bot.answer_callback_query(call.id, "⚠️ Сначала введите ник через /start!")
            return
        
        rcon_response = "Не удалось подключиться к серверу."
        try:
            with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
                rcon_response = mcr.command(f"lp user {nickname} info")
        except Exception as e:
            rcon_response = f"Ошибка связи с сервером: {e}"

        bot.send_message(
            chat_id,
            f"⏳ **Информация о привилегии для `{nickname}`:**\n\n"
            f"```text\n{rcon_response[:900]}\n```\n"
            f"(Тут указаны твои текущие группы и точное время до окончания срока)",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    # Меню [+]
    if call.data == "menu_plus":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("1 месяц — 100 ⭐", callback_data="buy_plus_1m"))
        markup.add(InlineKeyboardButton("3 месяца (-10%) — 270 ⭐", callback_data="buy_plus_3m"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_menu"))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=(
                "💎 **Привилегия [+] (Plus) — 100 ⭐:**\n"
                "• 5 точек дома (вместо 3)\n"
                "• Радиус RTP: 25 000 блоков\n"
                "• Лимит в клане: до 6 человек\n"
                "• Префикс `[+]` в чате и над головой\n"
                "• Сохранение домов в Энде\n"
                "• Кик из клана (`!tribe kick`)\n\n"
                "Выбери срок подписки:"
            ),
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        return

    # Меню [++]
    if call.data == "menu_plusplus":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("1 месяц — 200 ⭐", callback_data="buy_plusplus_1m"))
        markup.add(InlineKeyboardButton("3 месяца (-10%) — 540 ⭐", callback_data="buy_plusplus_3m"))
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_menu"))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=(
                "👑 **Привилегия [++] (PlusPlus) — 200 ⭐:**\n"
                "• Все возможности Plus +\n"
                "• 7 точек дома\n"
                "• Радиус RTP: 30 000 блоков\n"
                "• Лимит в клане: до 8 человек\n"
                "• Префикс `[++]` в чате и над головой\n"
                "• RTP в Энде (`!rtpend`)\n"
                "• Телепорт по координатам (`!tp X Z`, КД 1ч)\n"
                "• База племени (`!tribe sethome`)\n"
                "• Самоубийство (`!kill`)\n\n"
                "Выбери срок подписки:"
            ),
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

    # Инвойсы Telegram Stars с новыми ценами
    if call.data == "buy_plus_1m":
        prices = [LabeledPrice(label="Донат [+] на 1 месяц", amount=PRICE_PLUS_1M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [+] (1 месяц)", description=f"Пакет Plus для {nickname}", invoice_payload="pay_plus_1m", provider_token="", currency="XTR", prices=prices)
    elif call.data == "buy_plus_3m":
        prices = [LabeledPrice(label="Донат [+] на 3 месяца", amount=PRICE_PLUS_3M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [+] (3 месяца)", description=f"Пакет Plus для {nickname}", invoice_payload="pay_plus_3m", provider_token="", currency="XTR", prices=prices)
    elif call.data == "buy_plusplus_1m":
        prices = [LabeledPrice(label="Донат [++] на 1 месяц", amount=PRICE_PLUSPLUS_1M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [++] (1 месяц)", description=f"Пакет PlusPlus для {nickname}", invoice_payload="pay_plusplus_1m", provider_token="", currency="XTR", prices=prices)
    elif call.data == "buy_plusplus_3m":
        prices = [LabeledPrice(label="Донат [++] на 3 месяца", amount=PRICE_PLUSPLUS_3M)]
        bot.send_invoice(chat_id=chat_id, title="Привилегия [++] (3 месяца)", description=f"Пакет PlusPlus для {nickname}", invoice_payload="pay_plusplus_3m", provider_token="", currency="XTR", prices=prices)
    
    bot.answer_callback_query(call.id)


def execute_free_rcon(chat_id, nickname, command, rank_name):
    success = False
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            mcr.command(command)
            success = True
    except Exception as e:
        print(f"RCON Error: {e}")

    if success:
        bot.send_message(chat_id, f"🛠️ **[РЕЖИМ ТЕСТА]** Привилегия `{rank_name}` успешно выдана игроку `{nickname}` бесплатно!")
    else:
        bot.send_message(chat_id, "⚠️ Ошибка подключения к серверу по RCON.")


@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout_handler(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@bot.message_handler(content_types=['successful_payment'])
def success_payment(message):
    chat_id = message.chat.id
    nickname = user_nicknames.get(chat_id, "Игрок")
    payload = message.successful_payment.invoice_payload

    command = ""
    duration_text = ""

    if payload == "pay_plus_1m":
        command = f"lp user {nickname} parent addtemp donor_plus 30d"
        duration_text = "30 дней (1 месяц)"
    elif payload == "pay_plus_3m":
        command = f"lp user {nickname} parent addtemp donor_plus 90d"
        duration_text = "90 дней (3 месяца)"
    elif payload == "pay_plusplus_1m":
        command = f"lp user {nickname} parent addtemp donor_plus_plus 30d"
        duration_text = "30 дней (1 месяц)"
    elif payload == "pay_plusplus_3m":
        command = f"lp user {nickname} parent addtemp donor_plus_plus 90d"
        duration_text = "90 дней (3 месяца)"

    success = False
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            mcr.command(command)
            success = True
    except Exception as e:
        print(f"RCON Error: {e}")

    if success:
        bot.send_message(
            chat_id,
            f"✅ **Оплата прошла успешно!**\n\n"
            f"Игрок: `{nickname}`\n"
            f"Срок: `{duration_text}`\n"
            f"Привилегия автоматически активирована на сервере `burgersmp.org`! Спасибо за поддержку! 🍔"
        )
    else:
        bot.send_message(
            chat_id,
            f"⚠️ Оплата прошла, но сервер не ответил. Администратор скоро выдаст привилегию вручную для `{nickname}`."
        )


if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
