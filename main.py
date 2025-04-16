from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import BOT_TOKEN
from database import load_data
from handlers import (
    start, help_cmd, schedule_cmd, 
    book_cmd, view_bookings, show_month_schedule
)
from conversations import booking_conv, confirm_conv, settings_conv

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