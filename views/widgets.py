# views/widgets.py
from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QFontMetrics, QTextDocument, QPainterPath

# views/widgets.py
from PyQt6.QtWidgets import QGraphicsOpacityEffect
# views/widgets.py 의 EventLabelWidget 클래스
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
        
        # 완료 또는 다른 달 이벤트일 경우 투명도 조절
        opacity = 1.0
        if self.is_completed:
            opacity = 0.6
        elif self.is_other_month:
            opacity = 0.5 # 다른 달 이벤트는 더 투명하게

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
    """
    시간 눈금자와 가로선을 직접 그려주는 위젯. (여백 포함)
    """
    # views/widgets.py

    def __init__(self, hour_height, parent=None):
        super().__init__(parent)
        self.hour_height = hour_height
        self.total_hours = 24
        self.padding = 10  # 상하 여백
        self.setMinimumHeight(self.hour_height * self.total_hours + self.padding * 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = painter.fontMetrics()

        # 0시부터 24시까지 시간만 그립니다.
        for hour in range(self.total_hours + 1):
            y = hour * self.hour_height + self.padding

            # 테마에 따라 텍스트 색상을 가져오도록 수정
            current_theme = self.window().settings.get("theme", "dark") # 이 부분을 수정합니다.
            text_color = "#D0D0D0" if current_theme == "dark" else "#222222"
            painter.setPen(QColor(text_color))

            text = f"{hour:02d}:00"
            text_height = fm.height()
            draw_rect = QRect(0, y - text_height // 2, 45, text_height) # 오른쪽 여백 확보
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
          
def get_text_color_for_background(hex_color):
    """주어진 배경색(hex)에 대해 검은색과 흰색 중 더 적합한 글자색을 반환합니다."""
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return '#000000' if luminance > 149 else '#FFFFFF'
    except Exception:
        return '#FFFFFF'

def draw_event(painter, rect, event_data, time_text, summary_text, is_completed=False):
    """하나의 이벤트를 그리는 중앙 함수"""
    painter.save()

    # 완료된 이벤트 처리
    if is_completed:
        painter.setOpacity(0.5)

    # 1. 배경 그리기 및 클리핑 경로 설정
    event_color = QColor(event_data.get('color', '#555555'))
    painter.setBrush(event_color)
    painter.setPen(Qt.PenStyle.NoPen)
    
    clip_path = QPainterPath()
    clip_path.addRoundedRect(QRectF(rect), 4, 4)
    painter.drawPath(clip_path)
    painter.setClipPath(clip_path)

    # 2. 텍스트 그리기 준비
    text_color = QColor(get_text_color_for_background(event_data.get('color', '#555555')))
    painter.setPen(text_color)
    text_rect = rect.adjusted(4, -2, -4, -1)

    # 가로 폭이 3글자 미만이면 텍스트를 그리지 않음
    font_metrics = QFontMetrics(painter.font())
    min_text_width = font_metrics.horizontalAdvance('가나다')
    
    if text_rect.width() < min_text_width:
        painter.restore()
        return

    # 3. 그릴 텍스트 조합 (HTML 사용)
    full_html = ""
    if time_text:
        escaped_time = time_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        full_html += f"<p style='margin:0; font-size:8pt;'>{escaped_time}</p>"

    escaped_summary = summary_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    summary_style = "text-decoration:line-through;" if is_completed else ""
    full_html += f"<p style='margin:0; {summary_style}'>{escaped_summary}</p>"
    
    # 4. QTextDocument를 사용하여 Rich Text 그리기 (수직 오버플로우 체크 제거)
    doc = QTextDocument()
    doc.setDefaultStyleSheet(f"p {{ color: {text_color.name()}; line-height: 100%; }}")
    doc.setTextWidth(text_rect.width())
    doc.setHtml(full_html)

    painter.translate(text_rect.topLeft())
    doc.drawContents(painter, QRectF(0, 0, text_rect.width(), text_rect.height()))
    
    painter.restore()