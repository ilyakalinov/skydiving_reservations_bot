from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import *
from database import data, save_data
from utils import generate_schedule, is_date_available, show_month_selector, show_days_selector
from datetime import datetime
import re

# Basic commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🪂 Привет! Я бот для записи на прыжки с парашютом!\n"
        "📅 Команды:\n"
        "/schedule — Посмотреть расписание\n"
        "/book — Записаться на прыжок\n"
        "/help — Список команд"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Вот доступные команды:\n"
        "/schedule — Посмотреть расписание\n"
        "/book — Записаться на прыжок\n"
        "/view_bookings — Просмотр записей (админ)\n"
        "/settings — Настройки (админ)\n"
        "/help — Справка"
    )
    await update.message.reply_text(text)

# Schedule commands
async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().date()
    current_year = today.year
    current_month = today.month
    months_ahead = data["settings"]["months_ahead"]
    
    buttons = []
    for i in range(months_ahead):
        year = current_year + (current_month + i - 1) // 12
        month = (current_month + i) % 12 or 12
        month_name = datetime(year, month, 1).strftime("%B %Y")
        buttons.append(InlineKeyboardButton(month_name, callback_data=f"month:{year}:{month}"))
    
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    await update.message.reply_text(
        "Выберите месяц:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_month_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, year_str, month_str = query.data.split(":")
    year = int(year_str)
    month = int(month_str)
    
    schedule = generate_schedule(year, month)
    if not schedule:
        await query.edit_message_text(f"В {month}/{year} нет доступных дат.")
        return
    
    text = f"📅 Расписание на {datetime(year, month, 1).strftime('%B %Y')}:\n\n"
    for date, slots in schedule.items():
        text += f"{date} — {slots} свободных мест\n"
    await query.edit_message_text(text)

# Booking system
async def book_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    schedule = generate_schedule()
    keyboard = []
    for date, slots in schedule.items():
        keyboard.append([InlineKeyboardButton(f"{date} ({slots} мест)", callback_data=f"book:{date}")])
    await update.message.reply_text(
        "Выберите дату:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split(":")[1]
    context.user_data["booking_date"] = date_str
    await query.edit_message_text("Введите ваше имя:")
    return GET_FIRST_NAME

async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text("Введите вашу фамилию:")
    return GET_LAST_NAME

async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_name"] = update.message.text
    await update.message.reply_text("Введите ваш возраст:")
    return GET_AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if age < 18 or age > 100:
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Введите ваш вес (кг):")
        return GET_WEIGHT
    except ValueError:
        await update.message.reply_text("❌ Некорректный возраст. Введите число от 18 до 100:")
        return GET_AGE

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
        if weight < 40 or weight > 150:
            raise ValueError
        context.user_data["weight"] = weight
        await update.message.reply_text("Введите ваш номер телефона:")
        return GET_PHONE
    except ValueError:
        await update.message.reply_text("❌ Некорректный вес. Введите число от 40 до 150 кг:")
        return GET_WEIGHT

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    if not re.match(r'^\+?[1-9]\d{9,14}$', phone):
        await update.message.reply_text("❌ Некорректный формат телефона. Попробуйте еще раз:")
        return GET_PHONE
    
    booking_data = {
        "user_id": update.effective_user.id,
        "first_name": context.user_data["first_name"],
        "last_name": context.user_data["last_name"],
        "age": context.user_data["age"],
        "weight": context.user_data["weight"],
        "phone": phone,
        "timestamp": datetime.now().isoformat()
    }
    
    date_str = context.user_data["booking_date"]
    data["pending_bookings"].setdefault(date_str, []).append(booking_data)
    save_data()
    
    admin_text = f"🆕 Новая заявка на {date_str}:\n"
    admin_text += "\n".join([f"{k}: {v}" for k, v in booking_data.items()])
    admin_text += "\n\nПодтвердить заявку?"
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{date_str}_{update.effective_user.id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{date_str}_{update.effective_user.id}")]
    ]
    
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    await update.message.reply_text(
        "✅ Ваша заявка отправлена на модерацию. Мы свяжемся с вами после проверки данных.")
    return ConversationHandler.END

# Admin commands
async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён")
        return

    text = "📋 Список записей:\n\n"
    text += "⏳ Ожидают подтверждения:\n"
    for date, bookings in data["pending_bookings"].items():
        text += f"📅 {date}:\n"
        text += "\n".join([f"👤 {b['first_name']} {b['last_name']}" for b in bookings]) + "\n\n"
    
    text += "\n✅ Подтвержденные:\n"
    for date, bookings in data["confirmed_bookings"].items():
        text += f"📅 {date}:\n"
        text += "\n".join([f"👤 {b['first_name']} {b['last_name']} ⏰ {b.get('booking_time', '10:00')}" 
                          for b in bookings]) + "\n\n"
    
    await update.message.reply_text(text)