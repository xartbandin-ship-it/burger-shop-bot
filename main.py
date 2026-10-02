import os
import requests
from datetime import datetime, timedelta
import telebot
from telebot.types import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
from threading import Thread

BOT_VERSION = "v5.2-PERKS-FULL"
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Flask('')

pending_rewards = {}   # Очередь на выдачу доната
pending_removals = {}  # Очередь на снятие всех донатов
user_subscriptions = {}
admin_targets = {}

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

@app.route('/check-removal', methods=['GET'])
def check_removal():
    name = request.args.get('name', '').strip().lower()
    if not name:
        return jsonify({"status": "error", "message": "No name provided"})
    
    if name in pending_removals:
        pending_removals.pop(name)
        print(f"❌ Игрок {name} очистил донаты по запросу администратора")
        return jsonify({"status": "remove"})
    
    return jsonify({"status": "none"})

def run_flask():
    app.run(host='0.0.0.0', port=8080, use_reloader=False)

Thread(target=run_flask, daemon=True).start()

bot = telebot.TeleBot(BOT_TOKEN)
user_nicknames = {}

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
    
    tg_username = message.from_user.username
    if tg_username:
        tg_username = tg_username.lower()

    if code == "dev324":
        if tg_username != "meburger34":
            bot.send_message(chat_id, "❌ У вас нет прав для использования промокодов разработчика.")
            return
            
        bot.send_message(chat_id, "⚙️ Введите точный ник игрока в Minecraft, которым хотите управлять:")
        bot.register_next_step_handler(message, process_admin_target_nick)
    else:
        bot.send_message(chat_id, "❌ Неверный промокод.")

def process_admin_target_nick(message):
    target_nick = message.text.strip()
    chat_id = message.chat.id
    
    if not target_nick or " " in target_nick:
        bot.send_message(chat_id, "❌ Некорректный ник. Введите ник игрока еще раз:")
        bot.register_next_step_handler(message, process_admin_target_nick)
        return
        
    admin_targets[chat_id] = target_nick
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"🎁 Выдать [+] для {target_nick}", callback_data="admin_give_plus"))
    markup.add(InlineKeyboardButton(f"🎁 Выдать [++] для {target_nick}", callback_data="admin_give_plusplus"))
    markup.add(InlineKeyboardButton(f"❌ Снять все донаты с {target_nick}", callback_data="admin_remove_donuts"))
    markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))
    
    bot.send_message(
        chat_id,
        f"🛠️ **Панель управления игроком:** `{target_nick}`\nВыберите нужное действие:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    nickname = user_nicknames.get(chat_id)
    target_nick = admin_targets.get(chat_id)

    if call.data == "admin_give_plus":
        if not target_nick:
            bot.answer_callback_query(call.id, "Сначала укажите ник игрока!")
            return
        pending_rewards[target_nick.lower()] = "donor_plus"
        bot.send_message(chat_id, f"✅ Для `{target_nick}` добавлена награда [+] в очередь! Пропишите !claim в игре.", parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data == "admin_give_plusplus":
        if not target_nick:
            bot.answer_callback_query(call.id, "Сначала укажите ник игрока!")
            return
        pending_rewards[target_nick.lower()] = "donor_plus_plus"
        bot.send_message(chat_id, f"✅ Для `{target_nick}` добавлена награда [++] в очередь! Пропишите !claim в игре.", parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data == "admin_remove_donuts":
        if not target_nick:
            bot.answer_callback_query(call.id, "Сначала укажите ник игрока!")
            return
        pending_removals[target_nick.lower()] = True
        pending_rewards.pop(target_nick.lower(), None)
        user_subscriptions.pop(target_nick.lower(), None)
        bot.send_message(chat_id, f"❌ Запрос на снятие донатов добавлен для `{target_nick}`! Пропишите !claim в игре для применения.", parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    if call.data == "menu_more":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏳ Статус доната", callback_data="check_status"))
        markup.add(InlineKeyboardButton("🔑 Ввести промокод", callback_data="enter_promo"))
        markup.add(InlineKeyboardButton("✏ Сменить ник", callback_data="change_nick"))
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
            text="💎 **Привилегия [+] (Plus):**\n"
                 "• 5 точек дома во всех измерениях (включая Энд) (!sethome / !home)\n"
                 "• Случайный телепорт RTP 25k блоков (!rtp)\n"
                 "• Телепортация к игрокам и запросы ТП (!tp <ник> / !tpa)\n"
                 "• Право исключать игроков из племени (!tribe kick)\n"
                 "• Увеличенный лимит участников племени до 6 человек\n"
                 "• Персональный префикс [+]\n\n"
                 "*⚠️ Товар цифровой, возврату не подлежит.*\n\nВыберите срок:", 
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
            text="👑 **Привилегия [++] (PlusPlus):**\n"
                 "• 7 точек дома во всех измерениях (включая Энд) (!sethome / !home)\n"
                 "• RTP в обычном мире 30k блоков (!rtp)\n"
                 "• Безопасный RTP в Энде: радиус 10k блоков (от 1500 до 10000 блоков, чтобы не падать в пустоту между главным и внешними островами) (!rtpend)\n"
                 "• Телепорт по точным координатам в пределах 30k блоков (!tp X Z)\n"
                 "• Установка и телепорт на базу племени (!tribe sethome / home)\n"
                 "• Команда самоубийства (!kill)\n"
                 "• Телепортация к игрокам и запросы ТП (!tp <ник> / !tpa)\n"
                 "• Право исключать игроков из племени (!tribe kick)\n"
                 "• Увеличенный лимит участников племени до 8 человек\n"
                 "• Персональный префикс [++]\n\n"
                 "*⚠️ Товар цифровой, возврату не подлежит.*\n\nВыберите срок:", 
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
def successful_payment(message):
    chat_id = message.chat.id
    nickname = user_nicknames.get(chat_id, "Игрок")
    payload = message.successful_payment.invoice_payload

    days = 90 if "3m" in payload else 30
    is_plusplus = "plusplus" in payload
    
    new_tag = "donor_plus_plus" if is_plusplus else "donor_plus"
    new_tier_name = "PlusPlus [++]" if is_plusplus else "Plus [+]"

    # Защита от понижения: если у игрока уже активен PlusPlus, покупка Plus не сбрасывает его до Plus
    current_sub = user_subscriptions.get(nickname.lower())
    if current_sub and datetime.now() <= current_sub["expires_at"]:
        if current_sub["tier"] == "PlusPlus [++]" and not is_plusplus:
            new_tag = "donor_plus_plus"
            new_tier_name = "PlusPlus [++]"

    pending_rewards[nickname.lower()] = new_tag
    expires = datetime.now() + timedelta(days=days)
    user_subscriptions[nickname.lower()] = {"tier": new_tier_name, "expires_at": expires}

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 На главную", callback_data="back_menu"))

    bot.send_message(
        chat_id,
        f"✅ **Оплата прошла успешно!**\n\n👤 Игрок: `{nickname}`\n💎 Ранг: **{new_tier_name}**\n\nЗайдите на сервер и напишите команду **`!claim`**, чтобы активировать ранг!",
        reply_markup=markup,
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    bot.infinity_polling()
