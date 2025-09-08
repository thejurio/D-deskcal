# constants/color_constants.py
"""
색상 관련 상수 정의
모든 색상 값을 중앙에서 관리하여 테마 시스템과 연동
"""

# ============================================================================
# 기본 색상 팔레트
# ============================================================================
class BaseColors:
    # 주요 색상
    WHITE = "#FFFFFF"
    BLACK = "#000000"
    TRANSPARENT = "transparent"
    
    # 회색 스케일
    GRAY_LIGHTEST = "#F8F9FA"
    GRAY_LIGHTER = "#E9ECEF" 
    GRAY_LIGHT = "#DEE2E6"
    GRAY = "#ADB5BD"
    GRAY_DARK = "#6C757D"
    GRAY_DARKER = "#495057"
    GRAY_DARKEST = "#212529"


# ============================================================================
# 테마별 색상 (라이트 테마)
# ============================================================================
class LightTheme:
    # 배경색
    BACKGROUND_PRIMARY = BaseColors.WHITE
    BACKGROUND_SECONDARY = BaseColors.GRAY_LIGHTEST
    BACKGROUND_HOVER = BaseColors.GRAY_LIGHTER
    
    # 텍스트 색상
    TEXT_PRIMARY = BaseColors.GRAY_DARKEST
    TEXT_SECONDARY = BaseColors.GRAY_DARK
    TEXT_MUTED = BaseColors.GRAY
    
    # 경계선
    BORDER_PRIMARY = BaseColors.GRAY_LIGHT
    BORDER_SECONDARY = BaseColors.GRAY_LIGHTER
    
    # 상태 색상
    SUCCESS = "#28A745"
    WARNING = "#FFC107"
    ERROR = "#DC3545"
    INFO = "#17A2B8"


# ============================================================================
# 테마별 색상 (다크 테마)
# ============================================================================ 
class DarkTheme:
    # 배경색
    BACKGROUND_PRIMARY = BaseColors.GRAY_DARKEST
    BACKGROUND_SECONDARY = BaseColors.GRAY_DARKER
    BACKGROUND_HOVER = BaseColors.GRAY_DARK
    
    # 텍스트 색상
    TEXT_PRIMARY = BaseColors.GRAY_LIGHTEST
    TEXT_SECONDARY = BaseColors.GRAY_LIGHTER
    TEXT_MUTED = BaseColors.GRAY_LIGHT
    
    # 경계선
    BORDER_PRIMARY = BaseColors.GRAY_DARK
    BORDER_SECONDARY = BaseColors.GRAY_DARKER
    
    # 상태 색상
    SUCCESS = "#198754"
    WARNING = "#FD7E14"
    ERROR = "#B02A37"
    INFO = "#0DCAF0"


# ============================================================================
# 브랜드 색상
# ============================================================================
class BrandColors:
    PRIMARY = "#0078D4"
    PRIMARY_DARK = "#106EBE"
    PRIMARY_LIGHT = "#40E0D0"
    
    ACCENT = "#FF6B6B"
    ACCENT_DARK = "#FF5252"
    ACCENT_LIGHT = "#FF8A80"


# ============================================================================
# 캘린더 특화 색상
# ============================================================================
class CalendarColors:
    # 오늘 날짜 하이라이트
    TODAY_BACKGROUND = BrandColors.PRIMARY
    TODAY_BORDER = BrandColors.PRIMARY_DARK
    TODAY_TEXT = BaseColors.WHITE
    
    # 주말 색상
    WEEKEND_BACKGROUND = BaseColors.GRAY_LIGHTEST
    WEEKEND_TEXT = BaseColors.GRAY_DARK
    
    # 다른 달 날짜
    OTHER_MONTH_TEXT = BaseColors.GRAY
    OTHER_MONTH_BACKGROUND = BaseColors.TRANSPARENT
    
    # 이벤트 색상 (기본값)
    EVENT_DEFAULT = BrandColors.PRIMARY
    EVENT_IMPORTANT = BrandColors.ACCENT
    EVENT_COMPLETED = BaseColors.GRAY
    
    # 선택된 날짜
    SELECTED_BACKGROUND = BrandColors.PRIMARY_LIGHT
    SELECTED_BORDER = BrandColors.PRIMARY_DARK
    
    # 월간뷰 전용 색상
    TODAY_HIGHLIGHT_RGB = (0, 120, 215)  # Windows 10 블루
    MORE_EVENTS_LINK = "#82a7ff"         # 더보기 링크 색상
    DEFAULT_EVENT_COLOR = "#555555"      # 기본 이벤트 색상
    
    # 주간뷰 전용 색상
    HEADER_BG_DARK = "#2A2A2A"          # 다크 테마 헤더 배경
    HEADER_BG_LIGHT = "#F0F0F0"         # 라이트 테마 헤더 배경
    MORE_BUTTON_BG_RGB = (100, 100, 100, 100)     # 더보기 버튼 배경 (RGBA)
    MORE_BUTTON_BORDER_RGB = (150, 150, 150)      # 더보기 버튼 테두리 (RGB)
    MORE_BUTTON_TEXT_RGB = (255, 255, 255)        # 더보기 버튼 텍스트 (RGB)


# ============================================================================
# RGB 변환 유틸리티
# ============================================================================
def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """HEX 색상을 RGBA로 변환"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16) 
    b = int(hex_color[4:6], 16)
    
    return f"rgba({r}, {g}, {b}, {alpha})"


# ============================================================================
# 색상 조합 함수
# ============================================================================
def get_theme_colors(theme_name: str) -> dict:
    """테마별 색상 팔레트 반환"""
    if theme_name.lower() == 'dark':
        return {
            'background_primary': DarkTheme.BACKGROUND_PRIMARY,
            'background_secondary': DarkTheme.BACKGROUND_SECONDARY,
            'text_primary': DarkTheme.TEXT_PRIMARY,
            'text_secondary': DarkTheme.TEXT_SECONDARY,
            'border_primary': DarkTheme.BORDER_PRIMARY,
            'success': DarkTheme.SUCCESS,
            'warning': DarkTheme.WARNING,
            'error': DarkTheme.ERROR,
            'info': DarkTheme.INFO,
        }
    else:  # light theme
        return {
            'background_primary': LightTheme.BACKGROUND_PRIMARY,
            'background_secondary': LightTheme.BACKGROUND_SECONDARY,
            'text_primary': LightTheme.TEXT_PRIMARY,
            'text_secondary': LightTheme.TEXT_SECONDARY,
            'border_primary': LightTheme.BORDER_PRIMARY,
            'success': LightTheme.SUCCESS,
            'warning': LightTheme.WARNING,
            'error': LightTheme.ERROR,
            'info': LightTheme.INFO,
        }