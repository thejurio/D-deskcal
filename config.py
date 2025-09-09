# config.py
import os
import sys

def get_app_dir():
    """Get the application directory (where executable and resources are located)."""
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller EXE - use the temporary directory where files are extracted
        return sys._MEIPASS
    else:
        # Running in development mode - use current directory
        return os.path.dirname(os.path.abspath(__file__))

def get_data_dir():
    """Get the appropriate data directory for user files."""
    if hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller EXE - use user's AppData directory
        if sys.platform == "win32":
            data_dir = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'DCWidget')
        else:
            data_dir = os.path.join(os.path.expanduser('~'), '.dcwidget')
    else:
        # Running in development mode - use current directory
        data_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

# --- File Paths ---
_DATA_DIR = get_data_dir()
_APP_DIR = get_app_dir()
DB_FILE = os.path.join(_DATA_DIR, "calendar.db")
CACHE_DB_FILE = os.path.join(_DATA_DIR, "calendar_cache.db")
SETTINGS_FILE = os.path.join(_DATA_DIR, "settings.json")
TOKEN_FILE = os.path.join(_DATA_DIR, "token.json")
CREDENTIALS_FILE = os.path.join(_APP_DIR, "credentials.json")  # 앱 디렉토리에서 찾기
ERROR_LOG_FILE = os.path.join(_DATA_DIR, "error.log")

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
MAX_CACHE_SIZE = 13 # The number of months to keep in the cache (current month ±6 months = 13 months total)

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
