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
DEFAULT_LOCAL_CALENDAR_COLOR = "#4CAF50"
DEFAULT_LOCAL_CALENDAR_EMOJI = '💻'
DEFAULT_EVENT_COLOR = '#555555'

# --- Caching ---
MAX_CACHE_SIZE = 7 # The number of months to keep in the cache (e.g., current month +/- 3 months)

# --- Theming ---
# (나중에 테마 관련 상수를 추가할 수 있습니다)
# LIGHT_THEME_STYLESHEET = "..."
# DARK_THEME_STYLESHEET = "..."
