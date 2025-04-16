from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import calendar
from database import data

def generate_schedule(year=None, month=None):
    today = datetime.now().date()
    schedule = {}
    
    if year and month:
        months = [(year, month)]
    else:
        current_year = today.year
        current_month = today.month
        months = []
        for _ in range(data["settings"]["months_ahead"]):
            months.append((current_year, current_month))
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

    for year, month in months:
        month_start = datetime(year, month, 1).date()
        month_end = (month_start.replace(month=month % 12 + 1) - timedelta(days=1)).date()
        
        current_date = month_start
        while current_date <= month_end:
            if current_date >= today and current_date.weekday() in data["settings"]["working_days"]:
                date_str = current_date.isoformat()
                booked = len(data["confirmed_bookings"].get(date_str, []))
                weekday = current_date.weekday()
                slots = data["settings"]["day_slots"].get(str(weekday), data["settings"]["slots_per_day"])
                available = slots - booked
                if available > 0:
                    schedule[date_str] = available
            current_date += timedelta(days=1)
    return schedule

def is_date_available(date_str):
    date_obj = datetime.fromisoformat(date_str).date()
    weekday = date_obj.weekday()
    max_slots = data["settings"]["day_slots"].get(str(weekday), data["settings"]["slots_per_day"])
    current_bookings = len(data["confirmed_bookings"].get(date_str, []))
    return current_bookings < max_slots

def show_month_selector(message):
    now = datetime.now()
    keyboard = []
    for month in range(1, 13):
        month_name = datetime(now.year, month, 1).strftime("%B")
        keyboard.append([InlineKeyboardButton(month_name, callback_data=f"month_{month}")])
    return message.reply_text(
        "Выберите месяц:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def show_days_selector(query, month):
    year = datetime.now().year
    num_days = calendar.monthrange(year, month)[1]
    
    keyboard = []
    week = []
    for day in range(1, num_days + 1):
        date = datetime(year, month, day)
        btn_text = f"{day}⭐" if date.weekday() in data["settings"]["working_days"] else str(day)
        week.append(InlineKeyboardButton(btn_text, callback_data=f"day_{day}"))
        if date.weekday() == 6:
            keyboard.append(week)
            week = []
    if week:
        keyboard.append(week)
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back")])
    
    return query.edit_message_text(
        f"Выберите день:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )