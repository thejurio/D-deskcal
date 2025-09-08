# UI Constants for DCWidget Application

# === Window and Layout Constants ===

# Window Dimensions
WINDOW_MIN_WIDTH_RATIO = 0.20  # 20% of screen width
WINDOW_MIN_HEIGHT_RATIO = 0.25  # 25% of screen height

# Layout Spacing and Margins
CONTENT_MARGIN = 10
LAYOUT_SPACING = 5
BUTTON_SPACING = 5

# Widget Sizes
ICON_SIZE = 20
BUTTON_SIZE = 30
SEARCH_BUTTON_SIZE = 30
LOCK_BUTTON_SIZE = 30
AI_BUTTON_SIZE = 30

# Border and Visual Elements
BORDER_WIDTH = 5
CORNER_RADIUS = 10

# === Timer and Timing Constants ===

# Timer Intervals (milliseconds)
LOCK_STATUS_CHECK_INTERVAL = 50
DESKTOP_MODE_DELAY = 100
TRAY_ACTIVATION_DELAY = 0
INITIAL_LOAD_DELAY = 0
FORCE_DESKTOP_DELAY = 50
EVENT_NAVIGATION_DELAY = 50

# === Positioning and Geometry ===

# Notification Positioning
NOTIFICATION_MARGIN = 15
NOTIFICATION_SPACING = 10

# Screen Edge Snapping
SNAP_THRESHOLD = 45

# Socket Port for Single Instance
SINGLE_INSTANCE_PORT = 23741
SINGLE_INSTANCE_HOST = '127.0.0.1'

# === Opacity and Visual Effects ===

# Default Opacity Values
DEFAULT_WINDOW_OPACITY = 0.95
MENU_OPACITY_MULTIPLIER = 0.85

# Theme Colors (RGB values)
DARK_THEME_RGB = "30, 30, 30"
LIGHT_THEME_RGB = "250, 250, 250"

# === Button Styles and Padding ===

BUTTON_PADDING_BOTTOM = "2px"

# === Notification Duration ===

TRAY_NOTIFICATION_DURATION = 5000  # milliseconds
CLOSE_NOTIFICATION_DURATION = 2000  # milliseconds
HOTKEY_BLOCKED_DURATION = 3000  # milliseconds

# === Recurring Event Sync Delay ===

RECURRING_EVENT_SYNC_DELAY = 500  # milliseconds

# === UI Text Strings ===

# Window Title
WINDOW_TITLE = 'Glassy Calendar'

# Button Labels
BUTTON_TEXT_MONTH = "월간"
BUTTON_TEXT_WEEK = "주간"
BUTTON_TEXT_AGENDA = "안건"
BUTTON_TEXT_TODAY = "오늘"

# Tooltip Messages
TOOLTIP_SEARCH = "검색"
TOOLTIP_AI_ADD = "AI로 일정 추가"
TOOLTIP_LOCK_ENABLED = "잠금 모드 활성화됨 (클릭하여 비활성화)"
TOOLTIP_LOCK_DISABLED = "잠금 모드 비활성화됨 (클릭하여 활성화)"

# Tray Icon
TRAY_TOOLTIP = "Glassy Calendar"

# Menu Items
MENU_ADD_EVENT = "일정 추가"
MENU_SETTINGS = "설정"
MENU_REFRESH = "새로고침"
MENU_UPDATE_CHECK = "업데이트 확인"
MENU_EXIT = "종료"

# Context Menu Items
CONTEXT_MENU_REFRESH = "새로고침 (Refresh)"
CONTEXT_MENU_SETTINGS = "설정 (Settings)"
CONTEXT_MENU_EXIT = "종료 (Exit)"

# Notification Messages
NOTIFICATION_HOTKEY_BLOCKED = "다른 창이 열려 있어 AI 일정 추가를 실행할 수 없습니다."
NOTIFICATION_BACKGROUND_RUNNING = "캘린더가 백그라운드에서 실행 중입니다."

# Dialog Titles
DIALOG_TITLE_ERROR = "오류"
DIALOG_TITLE_NOTIFICATION = "알림"

# Error Messages
ERROR_NO_TEXT_INPUT = "분석할 텍스트가 입력되지 않았습니다."
ERROR_NO_API_KEY = "Gemini API 키가 설정되지 않았습니다.\n[설정 > 계정] 탭에서 API 키를 먼저 등록해주세요."
ERROR_NO_EVENTS_FOUND = "텍스트에서 유효한 일정 정보를 찾지 못했습니다."
ERROR_NO_CALENDAR_SELECTED = "일정을 추가할 캘린더를 선택해주세요."
ERROR_CALENDAR_NOT_LOADED = "캘린더 목록이 아직 로딩되지 않았습니다. 잠시 후 다시 시도해주세요."
ERROR_AI_ANALYSIS = "AI 분석 중 오류가 발생했습니다:\n{}"
ERROR_EVENT_DETAIL = "이벤트 상세정보를 표시하는 중 오류가 발생했습니다: {}"

# Success Messages
SUCCESS_EVENTS_ADDED = "{}개의 일정을 성공적으로 추가했습니다."

# === Icon File Names ===

ICON_SEARCH = "search.svg"
ICON_LOCK_LOCKED = "lock_locked.svg"
ICON_LOCK_UNLOCKED = "lock_unlocked.svg"
ICON_GEMINI = "gemini.svg"
ICON_TRAY = "tray_icon.svg"

# === Event Prefixes ===

EVENT_PREFIX_DEADLINE = "[마감] "

# === Time Zones ===

DEFAULT_TIMEZONE = "Asia/Seoul"

# === Object Names (for CSS styling) ===

OBJECT_NAME_MAIN_BACKGROUND = "main_background"
OBJECT_NAME_TODAY_BUTTON = "today_button"
OBJECT_NAME_SEARCH_BUTTON = "search_button"
OBJECT_NAME_LOCK_BUTTON = "lock_button"
OBJECT_NAME_AI_ADD_BUTTON = "ai_add_button"