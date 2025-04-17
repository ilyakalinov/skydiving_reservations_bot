from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import *
from database import data, save_data
from utils import (
    generate_month_calendar,
    create_calendar_keyboard,
    get_available_months
)
from datetime import datetime
import re

CHECK_EXISTING, CONFIRM_OVERRIDE = range(14, 16)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🪂 Привет! Я бот для записи на прыжки с парашютом!\n"
        "📅 Основные команды:\n"
        "/schedule - Посмотреть свободные даты и забронировать\n"
        "/mybookings - Мои активные брони"
    )

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bookings = []
    
    # Поиск броней во всех датах
    for date_str, bookings_list in data["confirmed_bookings"].items():
        for booking in bookings_list:
            if booking["user_id"] == user_id:
                bookings.append({
                    "date": date_str,
                    "time": booking.get("time", "время не указано")
                })
    
    if not bookings:
        await update.message.reply_text("❌ У вас нет активных бронирований")
        return
    
    text = "📌 Ваши активные брони:\n\n"
    for idx, booking in enumerate(bookings, 1):
        text += f"{idx}. {booking['date']} ({booking['time']})\n"
    
    keyboard = [
        [InlineKeyboardButton(f"❌ Отменить бронь #{idx+1}", callback_data=f"cancel_booking:{booking['date']}:{user_id}")]
        for idx, booking in enumerate(bookings)
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Исправленный парсинг callback_data
    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != "cancel_booking":
        await query.edit_message_text("❌ Ошибка формата запроса")
        return
    
    _, date_str, user_id_str = parts
    user_id = int(user_id_str)
    
    if update.effective_user.id != user_id:
        await query.edit_message_text("❌ Это не ваша бронь!")
        return
    
    # Проверяем существование брони
    if date_str not in data["confirmed_bookings"]:
        await query.edit_message_text("❌ Бронь не найдена")
        return
    
    # Удаление брони
    data["confirmed_bookings"][date_str] = [
        b for b in data["confirmed_bookings"][date_str]
        if b["user_id"] != user_id
    ]
    
    # Удаляем дату если нет броней
    if not data["confirmed_bookings"][date_str]:
        del data["confirmed_bookings"][date_str]
    
    save_data()
    
    # Уведомление админа
    await context.bot.send_message(
        ADMIN_ID,
        f"❌ Пользователь {user_id} отменил бронь на {date_str}"
    )
    
    await query.edit_message_text("✅ Бронь успешно отменена. Место освобождено.")


async def check_existing_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    selected_date = context.user_data["booking_date"]
    
    # Проверяем есть ли активные брони
    existing = any(
        booking["user_id"] == user_id
        for booking in data["confirmed_bookings"].get(selected_date, [])
    )
    
    if existing:
        keyboard = [
            [InlineKeyboardButton("✅ Перезаписать", callback_data="confirm_override")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_override")]
        ]
        await update.message.reply_text(
            "⚠️ У вас уже есть бронь на эту дату. Перезаписать?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHECK_EXISTING
    else:
        return await get_first_name(update, context)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Доступные команды:\n/schedule - Просмотр расписания и бронирование\n"
    if update.effective_user.id == ADMIN_ID:
        text += "\n/settings - Управление расписанием (только для администратора)"
    await update.message.reply_text(text)


async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    available_months = get_available_months()
    if not available_months:
        await update.message.reply_text("❌ На ближайшие месяцы нет свободных мест")
        return
    
    buttons = []
    for year, month in available_months:
        month_name = datetime(year, month, 1).strftime("%B %Y")
        buttons.append(InlineKeyboardButton(month_name, callback_data=f"month:{year}:{month}"))
    
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    await update.message.reply_text(
        "📅 Выберите месяц:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_month_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        _, year_str, month_str = query.data.split(":")
        year = int(year_str)
        month = int(month_str)
        
        schedule = generate_month_calendar(year, month)
        if not schedule:
            await query.edit_message_text("❌ В этом месяце нет доступных дней")
            return
        
        keyboard = create_calendar_keyboard(schedule, mode="booking")
        await query.edit_message_text(
            f"🗓️ {datetime(year, month, 1).strftime('%B %Y')}\nДоступные дни:",
            reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text("❌ Ошибка при загрузке расписания")

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_date = query.data.split(":")[1]  # Получаем выбранную дату
    context.user_data["booking_date"] = selected_date

    # Проверяем брони ТОЛЬКО в выбранный день
    user_id = update.effective_user.id
    existing = any(
        booking["user_id"] == user_id
        for booking in data["confirmed_bookings"].get(selected_date, [])
    )

    if existing:
        keyboard = [
            [InlineKeyboardButton("✅ Перезаписать", callback_data="confirm_override")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_override")]
        ]
        await query.edit_message_text(
            "⚠️ У вас уже есть бронь на эту дату. Перезаписать?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHECK_EXISTING
    else:
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
        if not 18 <= age <= 100: raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Введите вес (кг):")
        return GET_WEIGHT
    except ValueError:
        await update.message.reply_text("❌ Введите число от 18 до 100")
        return GET_AGE

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
        if not 40 <= weight <= 150: raise ValueError
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

async def finalize_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    booking = context.user_data.get("current_booking")
    date = context.user_data.get("original_date")
    
    # Получаем установленное время
    booking_time = context.user_data.get("booking_time", "")
    
    if not booking or not date:
        await update.message.reply_text("❌ Ошибка: данные брони не найдены")
        return ConversationHandler.END
    
    # Добавляем время в данные брони
    if booking_time:
        booking["time"] = booking_time
        date_message = f"{date} в {booking_time}"
    else:
        date_message = date
    
    data["confirmed_bookings"].setdefault(date, []).append(booking)
    if date in data["pending_bookings"]:
        data["pending_bookings"][date] = [
            b for b in data["pending_bookings"][date] 
            if b["user_id"] != booking["user_id"]
        ]
    save_data()
    
    # Сообщение с временем
    await context.bot.send_message(
        booking["user_id"],
        "🎉 Ваша заявка подтверждена!\n"
        f"📅 Дата и время: {date_message}\n"
        "📍 Аэродром 'Сокол'\n"
        "При себе иметь паспорт и мед. справку"
    )
    await update.message.reply_text("✅ Бронь подтверждена")
    
    # Очищаем временные данные
    context.user_data.clear()
    return ConversationHandler.END

async def handle_override(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_override":
        # Удаляем старую бронь
        user_id = update.effective_user.id
        selected_date = context.user_data["booking_date"]
        data["confirmed_bookings"][selected_date] = [
            b for b in data["confirmed_bookings"].get(selected_date, [])
            if b["user_id"] != user_id
        ]
        await query.edit_message_text("Введите ваше имя:")
        return GET_FIRST_NAME
    else:
        await query.edit_message_text("❌ Бронирование отменено")
        return ConversationHandler.END