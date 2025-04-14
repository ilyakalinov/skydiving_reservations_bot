from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from config import *
from database import data, save_data
from utils import show_month_selector, show_days_selector, is_date_available
from handlers import show_month_schedule
from datetime import datetime
from handlers import (
    start_booking,
    get_first_name,
    get_last_name,
    get_age,
    get_weight,
    get_phone,
    show_month_schedule
)

# Booking conversation
booking_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_booking, pattern="^book:")],
    states={
        GET_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
        GET_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
        GET_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        GET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
        GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)]
    },
    fallbacks=[],
    per_message=True
)

# Confirmation conversation
async def handle_admin_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith(("confirm_", "reject_")):
        action, date_str, user_id = query.data.split("_")
        user_id = int(user_id)
        
        booking = next(
            (b for b in data["pending_bookings"].get(date_str, []) if b["user_id"] == user_id),
            None
        )
        
        if not booking:
            await query.edit_message_text("❌ Заявка не найдена")
            return
        
        context.user_data["current_booking"] = booking
        context.user_data["original_date"] = date_str
        context.user_data["user_id"] = user_id
        
        if action == "confirm":
            keyboard = [
                [InlineKeyboardButton("✅ Подтвердить как есть", callback_data="approve_as_is")],
                [InlineKeyboardButton("✏️ Изменить дату", callback_data="change_date")],
                [InlineKeyboardButton("⏰ Установить время", callback_data="set_time")]
            ]
            await query.edit_message_text(
                "Выберите действие:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CONFIRM_ACTION
        else:
            data["pending_bookings"][date_str] = [
                b for b in data["pending_bookings"][date_str] 
                if b["user_id"] != user_id
            ]
            save_data()
            await context.bot.send_message(
                chat_id=user_id, 
                text="❌ Ваша заявка была отклонена администратором"
            )
            await query.edit_message_text("❌ Заявка отклонена")
            return ConversationHandler.END
    
    elif query.data == "approve_as_is":
        return await finalize_booking(update, context)
    
    elif query.data == "change_date":
        await query.edit_message_text("Выберите новую дату:")
        await show_month_selector(query.message)
        return CHANGE_DATE
    
    elif query.data == "set_time":
        await query.edit_message_text("Введите время в формате ЧЧ:ММ (например 14:30):")
        return SET_TIME

async def handle_date_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("month_"):
        month = int(query.data.split("_")[1])
        context.user_data["selected_month"] = month
        await show_days_selector(query, month)
        return CHANGE_DATE
    
    elif query.data.startswith("day_"):
        day = int(query.data.split("_")[1])
        month = context.user_data["selected_month"]
        year = datetime.now().year
        new_date = f"{year}-{month:02}-{day:02}"
        
        if not is_date_available(new_date):
            await query.answer("❌ Дата недоступна для бронирования", show_alert=True)
            return CHANGE_DATE
        
        context.user_data["new_date"] = new_date
        await query.edit_message_text(
            f"Новая дата: {new_date}\nХотите установить время?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏰ Установить время", callback_data="set_time")],
                [InlineKeyboardButton("✅ Подтвердить", callback_data="approve_as_is")]
            ])
        )
        return CONFIRM_ACTION

async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = update.message.text
        datetime.strptime(time_str, "%H:%M")
        context.user_data["booking_time"] = time_str
        return await finalize_booking(update, context)
    except ValueError:
        await update.message.reply_text("❌ Неверный формат времени. Используйте ЧЧ:ММ (например 14:30):")
        return SET_TIME

confirm_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(handle_admin_confirmation, pattern=r"^(confirm|reject)_")],
    states={
        CONFIRM_ACTION: [CallbackQueryHandler(handle_admin_confirmation)],
        CHANGE_DATE: [
            CallbackQueryHandler(handle_date_change, pattern=r"^month_"),
            CallbackQueryHandler(handle_date_change, pattern=r"^day_")
        ],
        SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_input)]
    },
    fallbacks=[],
    per_message=True
)

# Settings conversation
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён")
        return ConversationHandler.END
        
    keyboard = [
        [InlineKeyboardButton("📅 Рабочие дни", callback_data="set_days")],
        [InlineKeyboardButton("🔢 Слоты по умолчанию", callback_data="set_slots")],
        [InlineKeyboardButton("🗓️ Месяцев вперед", callback_data="set_months")],
        [InlineKeyboardButton("⭐ Особые дни", callback_data="set_specific")]
    ]
    
    await update.message.reply_text(
        "⚙️ Меню настроек:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SETTING_ACTION

async def setting_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data
    if action == "set_days":
        await show_days_selector(query)
        return SET_DAYS
    elif action == "set_slots":
        await query.edit_message_text("Введите новое количество слотов в день:")
        return SET_SLOTS
    elif action == "set_months":
        await query.edit_message_text("Введите количество месяцев для планирования:")
        return SET_MONTHS
    elif action == "set_specific":
        await show_specific_days_menu(query)
        return SET_SPECIFIC_DAY
    
    return ConversationHandler.END

async def show_days_selector(query):
    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard = []
    for i, day in enumerate(days):
        status = "✅" if i in data["settings"]["working_days"] else "❌"
        keyboard.append([InlineKeyboardButton(f"{day} {status}", callback_data=f"toggle_{i}")])
    
    keyboard.append([InlineKeyboardButton("Готово", callback_data="done")])
    
    await query.edit_message_text(
        "Выберите рабочие дни:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_days_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "done":
        save_data()
        await query.edit_message_text("Настройки дней сохранены!")
        return ConversationHandler.END
    
    day = int(query.data.split("_")[1])
    if day in data["settings"]["working_days"]:
        data["settings"]["working_days"].remove(day)
    else:
        data["settings"]["working_days"].append(day)
    
    await show_days_selector(query)
    return SET_DAYS

async def set_slots_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        slots = int(update.message.text)
        data["settings"]["slots_per_day"] = slots
        save_data()
        await update.message.reply_text(f"✅ Установлено {slots} слотов в день")
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение. Введите число:")
        return SET_SLOTS
    return ConversationHandler.END

async def set_months_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        months = int(update.message.text)
        data["settings"]["months_ahead"] = months
        save_data()
        await update.message.reply_text(f"✅ Установлено {months} месяцев для планирования")
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение. Введите число:")
        return SET_MONTHS
    return ConversationHandler.END

async def show_specific_days_menu(query):
    keyboard = [
        [InlineKeyboardButton("Добавить день", callback_data="add_day")],
        [InlineKeyboardButton("Удалить день", callback_data="remove_day")],
        [InlineKeyboardButton("Назад", callback_data="back")]
    ]
    await query.edit_message_text(
        "Управление особыми днями:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def specific_days_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back":
        await settings_command(query.message, context)
        return SETTING_ACTION
    elif query.data == "add_day":
        await query.edit_message_text("Введите дату в формате ГГГГ-ММ-ДД:")
        context.user_data["action"] = "add"
        return SET_SPECIFIC_DAY
    elif query.data == "remove_day":
        await query.edit_message_text("Введите дату в формате ГГГГ-ММ-ДД:")
        context.user_data["action"] = "remove"
        return SET_SPECIFIC_DAY

async def handle_specific_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        date_str = update.message.text
        datetime.strptime(date_str, "%Y-%m-%d")
        action = context.user_data.get("action")
        
        if action == "add":
            await set_specific_day_slots(update, date_str)
        elif action == "remove":
            if date_str in data["settings"]["day_slots"]:
                del data["settings"]["day_slots"][date_str]
                save_data()
                await update.message.reply_text(f"✅ День {date_str} удалён из особых")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат даты. Используйте ГГГГ-ММ-ДД:")
        return SET_SPECIFIC_DAY
    return ConversationHandler.END

async def set_specific_day_slots(update: Update, date_str: str):
    await update.message.reply_text(f"Введите количество слотов для {date_str}:")
    context.user_data["current_date"] = date_str
    return SET_SPECIFIC_DAY

async def save_specific_day_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        slots = int(update.message.text)
        date_str = context.user_data["current_date"]
        data["settings"]["day_slots"][date_str] = slots
        save_data()
        await update.message.reply_text(f"✅ Для {date_str} установлено {slots} слотов")
    except ValueError:
        await update.message.reply_text("❌ Некорректное значение. Введите число:")
        return SET_SPECIFIC_DAY
    return ConversationHandler.END

settings_conv = ConversationHandler(
    entry_points=[CommandHandler('settings', settings_command)],
    states={
        SETTING_ACTION: [CallbackQueryHandler(setting_action)],
        SET_DAYS: [CallbackQueryHandler(set_days_handler)],
        SET_SLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_slots_handler)],
        SET_MONTHS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_months_handler)],
        SET_SPECIFIC_DAY: [
            CallbackQueryHandler(specific_days_handler),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_specific_day),
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_specific_day_slots)
        ]
    },
    fallbacks=[],
    per_message=True
)

async def finalize_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    booking = context.user_data["current_booking"]
    original_date = context.user_data["original_date"]
    user_id = context.user_data["user_id"]
    
    new_date = context.user_data.get("new_date", original_date)
    booking_time = context.user_data.get("booking_time", "10:00")
    
    data["confirmed_bookings"].setdefault(new_date, []).append({
        **booking,
        "booking_time": booking_time
    })
    
    data["pending_bookings"][original_date] = [
        b for b in data["pending_bookings"][original_date] 
        if b["user_id"] != user_id
    ]
    
    if not data["pending_bookings"][original_date]:
        del data["pending_bookings"][original_date]
    
    save_data()
    
    user_text = (
        "🎉 Ваша заявка подтверждена!\n"
        f"📅 Дата: {new_date}\n"
        f"⏰ Время: {booking_time}\n"
        "📍 Место: Аэродром 'Сокол'\n"
        "👨✈️ Инструктор: Иван Петров\n\n"
        "При себе иметь:\n"
        "- Паспорт\n"
        "- Медицинскую справку\n"
        "- Спортивную одежду"
    )
    
    await context.bot.send_message(chat_id=user_id, text=user_text)
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("✅ Бронь подтверждена")
    else:
        query = update.callback_query
        await query.edit_message_text("✅ Бронь подтверждена")
    
    return ConversationHandler.END