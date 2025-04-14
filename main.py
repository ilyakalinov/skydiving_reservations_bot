from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
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
    show_month_schedule
)
from datetime import datetime
from conversations import (
    booking_conv, confirm_conv, settings_conv
)

def main():
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CommandHandler("book", book_cmd))
    app.add_handler(CommandHandler("view_bookings", view_bookings))
    
    # Conversations
    app.add_handler(booking_conv)
    app.add_handler(confirm_conv)
    app.add_handler(settings_conv)
    
    # Callback queries
    app.add_handler(CallbackQueryHandler(show_month_schedule, pattern=r"^month:"))
    
    app.run_polling()

if __name__ == "__main__":
    main()