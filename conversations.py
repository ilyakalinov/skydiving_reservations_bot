from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler
)
from config import *
from database import data, save_data
from utils import show_month_selector, show_days_selector, is_date_available
from handlers import (
    start_booking,
    get_first_name,
    get_last_name,
    get_age,
    get_weight,
    get_phone,
    handle_override,
    finalize_booking
)
from datetime import datetime

# ---------- Booking Conversation ----------
booking_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_booking, pattern=r"^book:\d{4}-\d{2}-\d{2}")],  
    states={
        CHECK_EXISTING: [CallbackQueryHandler(handle_override)],
        GET_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_first_name)],
        GET_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_last_name)],
        GET_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        GET_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
        GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
    },
    fallbacks=[],
    per_message=False,
)

# ---------- Confirmation Conversation ----------
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
                [InlineKeyboardButton("⏰ Установить время", callback_data="set_time")],
            ]
            await query.edit_message_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))
            return CONFIRM_ACTION
        else:
            data["pending_bookings"][date_str] = [
                b for b in data["pending_bookings"][date_str] if b["user_id"] != user_id
            ]
            save_data()
            await context.bot.send_message(chat_id=user_id, text="❌ Ваша заявка была отклонена администратором")
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
                [InlineKeyboardButton("✅ Подтвердить", callback_data="approve_as_is")],
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
            CallbackQueryHandler(handle_date_change, pattern=r"^day_"),
        ],
        SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_input)],
    },
    fallbacks=[],
    per_message=False,
)

# ---------- Settings Conversation ----------
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён")
        return ConversationHandler.END
    
    await show_month_selector(update.message, mode="settings")
    return SETTING_ACTION

async def handle_settings_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    month = int(query.data.split("_")[2])
    context.user_data["selected_month"] = month
    await show_days_selector(query, month, mode="settings")
    return SET_SPECIFIC_DAY

async def handle_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = int(query.data.split("_")[2])
    month = context.user_data["selected_month"]
    year = datetime.now().year
    date_str = f"{year}-{month:02}-{day:02}"
    
    context.user_data["selected_date"] = date_str
    await query.edit_message_text(f"Введите количество слотов для {date_str}:")
    return SET_SLOTS

async def save_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        slots = int(update.message.text)
        if slots < 1: raise ValueError
        date_str = context.user_data["selected_date"]
        data["settings"]["specific_days"][date_str] = slots
        save_data()
        await update.message.reply_text(f"✅ Для {date_str} установлено {slots} слотов!")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите целое число больше 0")
        return SET_SLOTS

settings_conv = ConversationHandler(
    entry_points=[CommandHandler('settings', settings_command)],
    states={
        SETTING_ACTION: [CallbackQueryHandler(handle_settings_month, pattern=r"^settings_month_")],
        SET_SPECIFIC_DAY: [
            CallbackQueryHandler(handle_day_selection, pattern=r"^config_day_"),
            CallbackQueryHandler(settings_command, pattern=r"^back_settings")
        ],
        SET_SLOTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_slots)]
    },
    fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)],
    per_message=False,
)