from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import BotCommand, BotCommandScopeChat
from config import BOT_TOKEN, ADMIN_ID
from database import load_data
from handlers import start, help_cmd, schedule_cmd, show_month_schedule, my_bookings  # Добавлен импорт
from conversations import booking_conv, confirm_conv, settings_conv
import logging


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def post_init(application):
    # Команды для всех пользователей
    await application.bot.set_my_commands([
        BotCommand("schedule", "Посмотреть расписание и забронировать"),
        BotCommand("help", "Справка по командам")
    ])
    
    # Команды только для администратора
    await application.bot.set_my_commands(
        [
            BotCommand("schedule", "Посмотреть расписание"),
            BotCommand("settings", "Настройки слотов"),
            BotCommand("help", "Справка"),
            BotCommand("mybookings", "Мои брони")
        ],
        scope=BotCommandScopeChat(chat_id=ADMIN_ID)
    )

def main():
    load_data()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mybookings", my_bookings))
    
    app.add_handler(CallbackQueryHandler(show_month_schedule, pattern=r"^month:"))
    app.add_handler(booking_conv)
    app.add_handler(confirm_conv)
    app.add_handler(settings_conv)
    
    app.run_polling()

if __name__ == "__main__":
    main()