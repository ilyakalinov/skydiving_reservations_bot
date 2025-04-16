import json
from config import DATA_FILE, DEFAULT_SETTINGS

data = {
    "settings": DEFAULT_SETTINGS.copy(),
    "pending_bookings": {},
    "confirmed_bookings": {}
}

def load_data():
    global data
    try:
        with open(DATA_FILE, "r") as f:
            loaded_data = json.load(f)
            loaded_data["settings"] = {**DEFAULT_SETTINGS, **loaded_data.get("settings", {})}
            data.update(loaded_data)
    except (FileNotFoundError, json.JSONDecodeError):
        save_data()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)