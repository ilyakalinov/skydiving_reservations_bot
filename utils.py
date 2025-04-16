from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import calendar
from database import data

def get_weekday_name(date):
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return weekdays[date.weekday()]

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
        # Исправлено: убрано .date() в конце
        month_start = datetime(year, month, 1).date()
        month_end = (month_start.replace(month=month % 12 + 1) - timedelta(days=1))
        
        current_date = month_start
        while current_date <= month_end:
            if current_date >= today:
                date_str = current_date.isoformat()
                booked = len(data["confirmed_bookings"].get(date_str, []))
                
                # Получаем количество слотов с приоритетом specific_days
                slots = data["settings"]["specific_days"].get(
                    date_str,
                    data["settings"]["day_slots"].get(
                        str(current_date.weekday()),
                        data["settings"]["slots_per_day"]
                    )
                )
                
                available = slots - booked
                if available > 0:
                    schedule[date_str] = available
            current_date += timedelta(days=1)
    return schedule

def is_date_available(date_str):
    date_obj = datetime.fromisoformat(date_str).date()
    booked = len(data["confirmed_bookings"].get(date_str, []))
    slots = data["settings"]["specific_days"].get(
        date_str,
        data["settings"]["day_slots"].get(
            str(date_obj.weekday()),
            data["settings"]["slots_per_day"]
        )
    )
    return booked < slots

def show_month_selector(message, mode="booking"):
    now = datetime.now()
    keyboard = []
    for month in range(1, 13):
        month_name = datetime(now.year, month, 1).strftime("%B")
        callback_data = f"settings_month_{month}" if mode == "settings" else f"month_{month}"
        keyboard.append([InlineKeyboardButton(month_name, callback_data=callback_data)])
    return message.reply_text(
        "Выберите месяц:" if mode == "booking" else "Выберите месяц для настройки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def show_days_selector(query, month, mode="booking"):
    year = datetime.now().year
    num_days = calendar.monthrange(year, month)[1]
    
    keyboard = []
    week = []
    for day in range(1, num_days + 1):
        date = datetime(year, month, day)
        weekday_name = get_weekday_name(date)
        
        if mode == "settings":
            date_str = date.date().isoformat()
            slots = data["settings"]["specific_days"].get(date_str, "")
            btn_text = f"{weekday_name} {day}"
            if slots:
                btn_text += f" ({slots})"
            callback = f"config_day_{day}"
        else:
            btn_text = f"{day}⭐" if date.weekday() in data["settings"]["working_days"] else str(day)
            callback = f"day_{day}"

        week.append(InlineKeyboardButton(btn_text, callback_data=callback))
        if date.weekday() == 6:
            keyboard.append(week)
            week = []
    if week:
        keyboard.append(week)
    
    back_callback = "back_settings" if mode == "settings" else "back"
    keyboard.append([InlineKeyboardButton("Назад", callback_data=back_callback)])
    
    return query.edit_message_text(
        "Выберите день:" if mode == "booking" else "Выберите день для настройки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def generate_month_calendar(year: int, month: int) -> dict:
    today = datetime.now().date()
    schedule = {}
    
    month_start = datetime(year, month, 1).date()
    next_month = month_start.replace(day=28) + timedelta(days=4)
    month_end = next_month - timedelta(days=next_month.day)
    
    current_date = month_start
    while current_date <= month_end:
        if current_date >= today:
            date_str = current_date.isoformat()
            # Учитываем ТОЛЬКО специфические дни
            if date_str in data["settings"]["specific_days"]:
                booked = len(data["confirmed_bookings"].get(date_str, []))
                slots = data["settings"]["specific_days"][date_str]
                available = slots - booked
                if available > 0:
                    schedule[date_str] = available
        current_date += timedelta(days=1)
    return schedule

def format_day_button(date_str: str, available: int) -> str:
    """Форматирование кнопки с днём"""
    date_obj = datetime.fromisoformat(date_str).date()
    weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date_obj.weekday()]
    return f"{weekday} {date_obj.day} ({available})"

def create_calendar_keyboard(schedule: dict, mode: str) -> InlineKeyboardMarkup:
    """Создание клавиатуры с календарём"""
    keyboard = []
    week = []
    for date_str, available in schedule.items():
        date_obj = datetime.fromisoformat(date_str).date()
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][date_obj.weekday()]
        
        # Определяем callback_data в зависимости от режима
        callback_data = (
            f"book:{date_str}" 
            if mode == "booking" 
            else f"config_day:{date_str}"
        )
        
        button = InlineKeyboardButton(
            f"{weekday} {date_obj.day} ({available})", 
            callback_data=callback_data
        )
        week.append(button)
        
        if date_obj.weekday() == 6:  # Воскресенье
            keyboard.append(week)
            week = []
    if week:
        keyboard.append(week)
    return InlineKeyboardMarkup(keyboard)

def get_available_months() -> list:
    today = datetime.now().date()
    available_months = set()
    
    # Проверяем только специфические дни
    for date_str in data["settings"]["specific_days"]:
        date_obj = datetime.fromisoformat(date_str).date()
        if date_obj >= today and data["settings"]["specific_days"][date_str] > 0:
            available_months.add((date_obj.year, date_obj.month))
    
    return sorted(available_months, key=lambda x: (x[0], x[1]))
