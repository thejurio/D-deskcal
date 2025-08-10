# views/widgets.py
import datetime
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QFontMetrics, QTextDocument, QPainterPath
from PyQt6.QtWidgets import QGraphicsOpacityEffect

class EventLabelWidget(QLabel):
    edit_requested = pyqtSignal(dict)

    def __init__(self, event, is_completed=False, is_other_month=False, main_widget=None, parent=None):
        super().__init__(parent)
        self.event_data = event
        self.is_completed = is_completed
        self.is_other_month = is_other_month
        self.main_widget = main_widget
        self.setMouseTracking(True) 
        self.parent_view = self.main_widget.stacked_widget.currentWidget()

        summary = event.get('summary', '제목 없음')
        if 'recurrence' in event:
            summary = f"{summary}"
        
        self.setText(summary)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.set_styles()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.parent_view:
            self.parent_view.handle_hover_enter(self, self.event_data)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self.parent_view:
            self.parent_view.handle_hover_leave(self)

    def set_styles(self):
        bg_color = self.event_data.get('color', '#555555')
        text_color = get_text_color_for_background(bg_color)
        
        style = f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 3px;
                padding: 0px 4px;
            }}
        """
        if self.is_completed:
            style += "QLabel { text-decoration: line-through; }"

        self.setStyleSheet(style)
        
        opacity = 1.0
        if self.is_completed:
            opacity = 0.6
        elif self.is_other_month:
            opacity = 0.5

        if opacity < 1.0:
            opacity_effect = QGraphicsOpacityEffect(self)
            opacity_effect.setOpacity(opacity)
            self.setGraphicsEffect(opacity_effect)
        else:
            self.setGraphicsEffect(None)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        font_metrics = QFontMetrics(self.font())

        original_text = self.event_data.get('summary', '제목 없음')
        if 'recurrence' in self.event_data:
            original_text = f"{original_text}"

        elided_text = font_metrics.elidedText(original_text, Qt.TextElideMode.ElideRight, self.width())
        super().setText(elided_text)


    def setText(self, text):
        super().setText(text)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.main_widget and self.main_widget.is_interaction_unlocked():
                self.edit_requested.emit(self.event_data)
                event.accept() 
        else:
            super().mouseDoubleClickEvent(event)

class TimeScaleWidget(QWidget):
    def __init__(self, hour_height, parent=None):
        super().__init__(parent)
        self.hour_height = hour_height
        self.total_hours = 24
        self.padding = 10
        self.setMinimumHeight(self.hour_height * self.total_hours + self.padding * 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = painter.fontMetrics()

        for hour in range(self.total_hours + 1):
            y = hour * self.hour_height + self.padding
            current_theme = self.window().settings.get("theme", "dark")
            text_color = "#D0D0D0" if current_theme == "dark" else "#222222"
            painter.setPen(QColor(text_color))
            text = f"{hour:02d}:00"
            text_height = fm.height()
            draw_rect = QRect(0, y - text_height // 2, 45, text_height)
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
          
def get_text_color_for_background(hex_color):
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return '#000000' if luminance > 149 else '#FFFFFF'
    except Exception:
        return '#FFFFFF'

def draw_event(painter, rect, event_data, time_text, summary_text, is_completed=False):
    painter.save()

    if is_completed:
        painter.setOpacity(0.5)

    event_color = QColor(event_data.get('color', '#555555'))
    painter.setBrush(event_color)
    painter.setPen(Qt.PenStyle.NoPen)
    
    clip_path = QPainterPath()
    clip_path.addRoundedRect(QRectF(rect), 4, 4)
    painter.drawPath(clip_path)
    painter.setClipPath(clip_path)

    text_color = QColor(get_text_color_for_background(event_data.get('color', '#555555')))
    painter.setPen(text_color)
    text_rect = rect.adjusted(4, -2, -4, -1)

    font_metrics = QFontMetrics(painter.font())
    min_text_width = font_metrics.horizontalAdvance('가나다')
    
    if text_rect.width() < min_text_width:
        painter.restore()
        return

    full_html = ""
    if time_text:
        escaped_time = time_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        full_html += f"<p style='margin:0; font-size:8pt;'>{escaped_time}</p>"

    escaped_summary = summary_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    summary_style = "text-decoration:line-through;" if is_completed else ""
    full_html += f"<p style='margin:0; {summary_style}'>{escaped_summary}</p>"
    
    doc = QTextDocument()
    doc.setDefaultStyleSheet(f"p {{ color: {text_color.name()}; line-height: 100%; }}")
    doc.setTextWidth(text_rect.width())
    doc.setHtml(full_html)

    painter.translate(text_rect.topLeft())
    doc.drawContents(painter, QRectF(0, 0, text_rect.width(), text_rect.height()))
    
    painter.restore()

class AgendaEventWidget(QWidget):
    """안건 뷰에 표시될 단일 이벤트 위젯입니다."""
    def __init__(self, event_data, parent_view=None, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.parent_view = parent_view
        self.init_ui()

    def _format_event_time(self):
        """[수정됨] 여러 날에 걸친 일정을 기간에 맞게 표시하도록 개선합니다."""
        start = self.event_data.get('start', {})
        end = self.event_data.get('end', {})
        
        is_all_day = 'date' in start
        
        try:
            start_str = start.get('dateTime', start.get('date'))
            end_str = end.get('dateTime', end.get('date'))
            if start_str.endswith('Z'): start_str = start_str[:-1] + '+00:00'
            if end_str.endswith('Z'): end_str = end_str[:-1] + '+00:00'

            start_dt = datetime.datetime.fromisoformat(start_str)
            end_dt = datetime.datetime.fromisoformat(end_str)
            
            # 종일 이벤트의 종료일 보정
            if is_all_day:
                end_dt -= datetime.timedelta(days=1)

            start_date = start_dt.date()
            end_date = end_dt.date()
            
            # 현재 이 위젯이 표시되는 날짜
            display_date = self.event_data.get('agenda_display_date', start_date)

            # 하루짜리 이벤트
            if start_date == end_date:
                return "종일" if is_all_day else f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"
            
            # 여러 날에 걸친 이벤트
            else:
                if is_all_day:
                    return "종일"
                
                if display_date == start_date:
                    return f"{start_dt.strftime('%H:%M')} 부터"
                elif display_date == end_date:
                    return f"{end_dt.strftime('%H:%M')} 까지"
                else:
                    return "→ 진행 중"

        except (ValueError, TypeError):
            return "" # 파싱 실패 시 빈 문자열 반환

    def init_ui(self):
        """컬러 바, 시간, 제목을 포함하는 블록 형태의 UI를 생성합니다."""
        self.setMinimumHeight(40)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 3, 5, 3)
        main_layout.setSpacing(10)

        # 완료 상태 확인
        is_completed = self.parent_view.data_manager.is_event_completed(self.event_data.get('id'))

        # 1. 컬러 바 (Color Bar)
        color_bar = QFrame()
        color_bar.setFixedWidth(4)
        bg_color = self.event_data.get('color', '#555555')
        color_bar.setStyleSheet(f"background-color: {bg_color}; border-radius: 2px;")
        
        # 2. 시간 텍스트 (Time Label)
        time_text = self._format_event_time()
        time_label = QLabel(time_text)
        time_label.setFixedWidth(110)
        time_label.setObjectName("agenda_time_label")

        # 3. 제목 텍스트 (Title Label)
        title_text = self.event_data.get('summary', '제목 없음')
        title_label = QLabel(title_text)
        title_label.setObjectName("agenda_title_label")
        
        # 완료 상태일 경우 취소선 추가
        if is_completed:
            font = title_label.font()
            font.setStrikeOut(True)
            title_label.setFont(font)

        main_layout.addWidget(color_bar)
        main_layout.addWidget(time_label)
        main_layout.addWidget(title_label, 1) # Stretch factor 1

        # 완료 상태일 경우 투명도 조절
        if is_completed:
            opacity_effect = QGraphicsOpacityEffect(self)
            opacity_effect.setOpacity(0.5)
            self.setGraphicsEffect(opacity_effect)

    def contextMenuEvent(self, event):
        if self.parent_view and self.parent_view.main_widget.is_interaction_unlocked():
            self.parent_view.show_context_menu(event.globalPos(), self.event_data)
