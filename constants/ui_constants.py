# constants/ui_constants.py
"""
UI 관련 상수 정의
모든 UI 크기, 여백, 간격 등을 중앙에서 관리
"""

# ============================================================================
# 윈도우 크기 관련 상수
# ============================================================================
class WindowSize:
    # 기본 창 크기
    DEFAULT_WIDTH = 800
    DEFAULT_HEIGHT = 600
    
    # 최소 창 크기
    MIN_WIDTH = 600
    MIN_HEIGHT = 400
    
    # 다이얼로그 크기
    DIALOG_WIDTH = 400
    DIALOG_HEIGHT = 300
    
    # 설정 창 크기
    SETTINGS_WIDTH = 500
    SETTINGS_HEIGHT = 600


# ============================================================================
# 여백 및 간격 상수
# ============================================================================
class Spacing:
    # 기본 여백
    SMALL = 5
    MEDIUM = 10
    LARGE = 15
    XLARGE = 20
    
    # 컨테이너 여백
    CONTAINER_MARGIN = 15
    WIDGET_SPACING = 10
    
    # 버튼 관련
    BUTTON_SPACING = 10
    BUTTON_MARGIN = 5


# ============================================================================
# 크기 관련 상수
# ============================================================================
class Size:
    # 버튼 크기
    BUTTON_WIDTH = 80
    BUTTON_HEIGHT = 30
    
    # 아이콘 크기
    ICON_SMALL = 16
    ICON_MEDIUM = 24
    ICON_LARGE = 32
    
    # 입력 필드
    INPUT_HEIGHT = 30
    
    # 리스트 아이템
    LIST_ITEM_HEIGHT = 40
    
    # 이벤트 에디터 관련
    TEXT_EDIT_MIN_HEIGHT = 100
    CALENDAR_ICON_SIZE = 16
    
    # 윈도우 최소 크기
    EVENT_EDITOR_MIN_WIDTH = 450


# ============================================================================
# 투명도 상수
# ============================================================================
class Opacity:
    FULL = 1.0
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5
    VERY_LOW = 0.3


# ============================================================================
# 타이머 상수 (ms)
# ============================================================================
class Timer:
    SHORT_DELAY = 100
    MEDIUM_DELAY = 500
    LONG_DELAY = 1000
    VERY_LONG_DELAY = 3000
    
    # 특정 기능별
    POPOVER_DELAY = 500
    TOOLTIP_DELAY = 1000
    AUTO_SAVE_DELAY = 2000
    
    # 이벤트 관련
    SINGLE_SHOT_DELAY = 0  # QTimer.singleShot immediate execution
    
    # 월간뷰 전용 타이머
    HOVER_LEAVE_DELAY = 10        # 팝오버 안정성을 위한 극한 응답성
    DEBOUNCE_UPDATE_DELAY = 50    # 배치 업데이트 디바운스
    DRAW_EVENTS_DELAY = 10        # 이벤트 렌더링 지연
    PENDING_UPDATE_DELAY = 50     # 펜딩 업데이트 처리
    POPOVER_CLOSE_DELAY = 100     # 팝오버 종료 후 처리
    

# ============================================================================
# 시간/기간 상수 (초)
# ============================================================================
class Duration:
    HOUR_SECONDS = 3600  # 1시간 = 3600초
    DAY_SECONDS = 86400   # 1일 = 86400초
    

# ============================================================================
# 날짜/시간 형식 상수
# ============================================================================
class DateTimeFormat:
    # PyQt 날짜 형식
    DATE_DISPLAY = "yyyy-MM-dd"
    
    # Python 날짜 형식
    DATE_PYTHON = "%Y-%m-%d"
    DATETIME_ISO = "%Y-%m-%dT%H:%M:%S"
    
    # 기본 시간대
    DEFAULT_TIMEZONE = "Asia/Seoul"


# ============================================================================
# 애니메이션 상수
# ============================================================================
class Animation:
    # 회전 애니메이션
    ROTATION_DURATION = 1200    # 회전 애니메이션 지속 시간 (ms)
    ROTATION_START = 0          # 시작 각도
    ROTATION_END = 360          # 끝 각도
    INFINITE_LOOP = -1          # 무한 반복


# ============================================================================
# 월간뷰 레이아웃 상수
# ============================================================================
class MonthViewLayout:
    # 셀 여백
    CELL_MARGIN = 2             # 날짜 셀 외곽 마진
    CELL_SPACING = 2            # 셀 내부 간격
    EVENTS_SPACING = 1          # 이벤트 목록 간격
    
    # 네비게이션
    NAV_SPACING = 0             # 네비게이션 간격
    NAV_MARGIN = 25             # 네비게이션 왼쪽 마진
    NAV_TOP_SPACING = 3         # 네비게이션 상단 간격
    
    # 이벤트 렌더링
    EVENT_HEIGHT = 18           # 기본 이벤트 높이
    MIN_EVENT_HEIGHT = 16       # 최소 이벤트 높이
    LANE_SPACING = 2            # 이벤트 레인 간격
    EVENT_MARGIN = 2            # 이벤트 좌우 마진 (rect 안쪽)
    EVENT_PADDING = 4           # 이벤트 텍스트 패딩
    
    # 히트 테스트
    HIT_MARGIN_NORMAL = 3.0     # 일반 히트 테스트 마진
    HIT_MARGIN_EXTENDED = 8.0   # 확장된 히트 테스트 마진 (PyInstaller)


# ============================================================================
# 시각적 효과 상수
# ============================================================================
class VisualEffects:
    # 둥근 모서리
    BORDER_RADIUS_SMALL = 5     # 작은 둥근 모서리
    BORDER_RADIUS_MEDIUM = 6    # 중간 둥근 모서리
    
    # 오늘 하이라이트
    TODAY_HIGHLIGHT_ALPHA = 80  # 오늘 배경 투명도
    TODAY_HIGHLIGHT_MARGIN = 2  # 오늘 하이라이트 마진


# ============================================================================
# 베이스뷰 상수
# ============================================================================
class BaseViewLayout:
    # 팝오버 위치 오프셋
    POPOVER_OFFSET = 15         # 팝오버 커서 오프셋
    
    # 메뉴 투명도
    MENU_OPACITY_FACTOR = 0.85  # 메뉴 투명도 계산용 팩터


# ============================================================================
# 주간뷰 상수
# ============================================================================
class WeekViewLayout:
    # 그리드 레이아웃
    TIME_GRID_LEFT = 50         # 시간 그리드 왼쪽 여백
    HEADER_HEIGHT = 30          # 헤더 높이
    ALL_DAY_LANE_HEIGHT = 25    # 종일 이벤트 레인 높이
    MAX_ALL_DAY_LANES = 2       # 최대 종일 이벤트 레인 수
    HORIZONTAL_MARGIN = 2       # 수평 마진
    
    # 이벤트 배치
    EVENT_VERTICAL_MARGIN = 2   # 이벤트 세로 마진
    EVENT_VERTICAL_OFFSET = 4   # 이벤트 세로 오프셋
    LANE_BOTTOM_MARGIN = 5      # 레인 하단 마진
    
    # 더보기 버튼
    MORE_BUTTON_BORDER_RADIUS = 3  # 더보기 버튼 둥근 모서리