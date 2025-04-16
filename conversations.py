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
    show_month_schedule,
    finalize_booking
)
from datetime import datetime

# ---------- Booking Conversation ----------
booking_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_booking, pattern=r"^book:")],
    states={
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

# ---------- Settings Conversation (добавим заглушки) ----------

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Настройки пока в разработке.")

async def setting_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

async def set_days_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

async def set_slots_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

async def set_months_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

async def specific_days_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

async def handle_specific_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

async def save_specific_day_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # заглушка

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
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_specific_day_slots),
        ],
    },
    fallbacks=[],
    per_message=False,
)
