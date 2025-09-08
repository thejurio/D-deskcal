# constants/__init__.py
"""
상수 패키지 초기화
모든 상수들을 중앙에서 관리하고 쉽게 import할 수 있도록 함
"""

from .ui_constants import (
    WindowSize, Spacing, Size, Opacity, Timer, Duration, DateTimeFormat,
    Animation, MonthViewLayout, VisualEffects, BaseViewLayout, WeekViewLayout
)
from .color_constants import (
    BaseColors, LightTheme, DarkTheme, BrandColors, 
    CalendarColors, hex_to_rgba, get_theme_colors
)
from .text_constants import (
    GeneralText, MenuText, CalendarText, SettingsText,
    ErrorMessages, SuccessMessages, ConfirmationMessages, 
    TooltipText, EventEditorText, get_text, format_text
)

# 편의성을 위한 단축 alias
UI = WindowSize
Colors = BrandColors
Text = GeneralText

__all__ = [
    # UI Constants
    'WindowSize', 'Spacing', 'Size', 'Opacity', 'Timer', 'Duration', 'DateTimeFormat',
    'Animation', 'MonthViewLayout', 'VisualEffects', 'BaseViewLayout', 'WeekViewLayout',
    
    # Color Constants  
    'BaseColors', 'LightTheme', 'DarkTheme', 'BrandColors', 
    'CalendarColors', 'hex_to_rgba', 'get_theme_colors',
    
    # Text Constants
    'GeneralText', 'MenuText', 'CalendarText', 'SettingsText',
    'ErrorMessages', 'SuccessMessages', 'ConfirmationMessages',
    'TooltipText', 'EventEditorText', 'get_text', 'format_text',
    
    # Aliases
    'UI', 'Colors', 'Text'
]