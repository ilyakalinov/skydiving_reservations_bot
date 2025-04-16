import logging
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Обновленный кортеж состояний
(
    SETTING_ACTION, SET_DAYS, SET_SLOTS, SET_MONTHS, SET_SPECIFIC_DAY,
    BOOKING_START, GET_FIRST_NAME, GET_LAST_NAME, GET_AGE, GET_WEIGHT, GET_PHONE,
    CONFIRM_ACTION, CHANGE_DATE, SET_TIME,
    CHECK_EXISTING, CONFIRM_OVERRIDE  # Добавлены новые состояния
) = range(16)

DATA_FILE = "data.json"
ADMIN_ID = 918969159
BOT_TOKEN = "7895905602:AAHvpJDHHgLr-j9BHryDSrOZXQwDdtB8opc"

DEFAULT_SETTINGS = {
    "months_ahead": 3,
    "slots_per_day": 3,
    "working_days": [5, 6],
    "day_slots": {
        "5": 3,
        "6": 5
    },
    "specific_days": {}  
}