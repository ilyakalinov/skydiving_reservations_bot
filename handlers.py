from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import *
from database import data, save_data
from utils import generate_schedule, is_date_available, show_month_selector, show_days_selector
from datetime import datetime
import re

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

async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().date()
    buttons = []
    for i in range(data["settings"]["months_ahead"]):
        year = today.year + (today.month + i - 1) // 12
        month = (today.month + i) % 12 or 12
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
    schedule = generate_schedule(int(year_str), int(month_str))
    
    text = f"📅 Расписание:\n" + "\n".join(
        f"{date} — {slots} мест" for date, slots in schedule.items()
    )
    await query.edit_message_text(text)

async def book_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    schedule = generate_schedule()
    keyboard = [
        [InlineKeyboardButton(f"{date} ({slots})", callback_data=f"book:{date}")]
        for date, slots in schedule.items()
    ]
    await update.message.reply_text(
        "Выберите дату:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["booking_date"] = query.data.split(":")[1]
    await query.edit_message_text("Введите ваше имя:")
    return GET_FIRST_NAME

async def get_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["first_name"] = update.message.text
    await update.message.reply_text("Введите фамилию:")
    return GET_LAST_NAME

async def get_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["last_name"] = update.message.text
    await update.message.reply_text("Введите возраст:")
    return GET_AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if not 18 <= age <= 100:
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Введите вес (кг):")
        return GET_WEIGHT
    except ValueError:
        await update.message.reply_text("❌ Введите число от 18 до 100")
        return GET_AGE

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
        if not 40 <= weight <= 150:
            raise ValueError
        context.user_data["weight"] = weight
        await update.message.reply_text("Введите телефон:")
        return GET_PHONE
    except ValueError:
        await update.message.reply_text("❌ Введите число от 40 до 150")
        return GET_WEIGHT

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    if not re.match(r'^\+?[1-9]\d{9,14}$', phone):
        await update.message.reply_text("❌ Неверный формат телефона")
        return GET_PHONE
    
    booking = {
        **context.user_data,
        "user_id": update.effective_user.id,
        "phone": phone
    }
    date = context.user_data["booking_date"]
    data["pending_bookings"].setdefault(date, []).append(booking)
    save_data()
    
    await context.bot.send_message(
        ADMIN_ID,
        f"Новая заявка на {date}:\n" + "\n".join(f"{k}: {v}" for k, v in booking.items()),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{date}_{update.effective_user.id}"),
             InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{date}_{update.effective_user.id}")]
        ])
    )
    
    await update.message.reply_text("✅ Заявка отправлена на модерацию")
    return ConversationHandler.END

async def view_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён")
        return
    
    text = "⏳ Ожидают подтверждения:\n"
    for date, bookings in data["pending_bookings"].items():
        text += f"{date}:\n" + "\n".join(f"- {b['first_name']} {b['last_name']}" for b in bookings) + "\n\n"
    
    text += "✅ Подтвержденные:\n"
    for date, bookings in data["confirmed_bookings"].items():
        text += f"{date}:\n" + "\n".join(f"- {b['first_name']} {b['last_name']}" for b in bookings) + "\n\n"
    
    await update.message.reply_text(text)

async def finalize_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    booking = context.user_data["booking"]
    date = context.user_data["date"]
    data["confirmed_bookings"].setdefault(date, []).append(booking)
    data["pending_bookings"][date] = [b for b in data["pending_bookings"][date] if b["user_id"] != booking["user_id"]]
    save_data()
    
    await context.bot.send_message(
        booking["user_id"],
        "🎉 Ваша заявка подтверждена!\n"
        f"📅 Дата: {date}\n"
        "📍 Аэродром 'Сокол'\n"
        "При себе иметь паспорт и мед. справку"
    )
    await update.message.reply_text("✅ Бронь подтверждена")
    return ConversationHandler.END