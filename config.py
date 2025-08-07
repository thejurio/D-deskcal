# config.py

# --- File Paths ---
DB_FILE = "calendar.db"
SETTINGS_FILE = "settings.json"
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"

# --- Identifiers ---
LOCAL_CALENDAR_ID = "local_calendar"
LOCAL_CALENDAR_PROVIDER_NAME = "LocalCalendarProvider"
GOOGLE_CALENDAR_PROVIDER_NAME = "GoogleCalendarProvider"

# --- UI Defaults ---
DEFAULT_WINDOW_GEOMETRY = [200, 200, 500, 450]
DEFAULT_SYNC_INTERVAL = 5  # minutes
DEFAULT_WINDOW_MODE = "AlwaysOnTop"  # "AlwaysOnTop", "Normal", "AlwaysOnBottom"
DEFAULT_LOCK_MODE_ENABLED = True
DEFAULT_LOCK_MODE_KEY = "Ctrl"  # "Ctrl", "Alt", "Shift", "Z"
DEFAULT_LOCK_MODE_ENABLED = False
DEFAULT_LOCK_MODE_KEY = "Ctrl"  # "Ctrl", "Alt", "Shift", "Z"
DEFAULT_LOCAL_CALENDAR_COLOR = "#4CAF50"
DEFAULT_LOCAL_CALENDAR_EMOJI = '💻'
DEFAULT_EVENT_COLOR = '#555555'

# --- Caching ---
MAX_CACHE_SIZE = 7 # The number of months to keep in the cache (e.g., current month +/- 3 months)

# --- Notifications ---
DEFAULT_NOTIFICATIONS_ENABLED = True
DEFAULT_NOTIFICATION_MINUTES = 10 # minutes before the event starts
DEFAULT_ALL_DAY_NOTIFICATION_ENABLED = True
DEFAULT_ALL_DAY_NOTIFICATION_TIME = "09:00" # HH:MM format
DEFAULT_NOTIFICATION_DURATION = 0 # seconds, 0 means "don't close"

# --- Theming ---
# (나중에 테마 관련 상수를 추가할 수 있습니다)
# LIGHT_THEME_STYLESHEET = "..."
# DARK_THEME_STYLESHEET = "..."
