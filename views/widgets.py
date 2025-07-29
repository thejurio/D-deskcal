# views/widgets.py
from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QTextOption, QFontMetrics, QTextDocument

class EventLabelWidget(QLabel):
    edit_requested = pyqtSignal(dict)
    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.event_data = event
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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

def draw_event(painter, rect, event_data, time_text, summary_text):
    """하나의 이벤트를 그리는 중앙 함수"""
    painter.save()

    # 1. 배경 그리기
    event_color = QColor(event_data.get('color', '#555555'))
    painter.setBrush(event_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, 4, 4)

    # 2. 텍스트 그리기 준비
    text_color = QColor(get_text_color_for_background(event_data.get('color', '#555555')))
    painter.setPen(text_color)
    # 상하 여백을 2에서 1로 줄여 텍스트를 위로 이동
    text_rect = rect.adjusted(4, -2, -4, -1)
    
    original_font = painter.font()
    
    # 3. 그릴 텍스트 조합 (HTML 사용)
    full_html = ""
    if time_text:
        escaped_time = time_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        full_html += f"<p style='margin:0; font-size:8pt;'>{escaped_time}</p>"

    escaped_summary = summary_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    full_html += f"<p style='margin:0;'>{escaped_summary}</p>"
    
    # 4. QTextDocument를 사용하여 Rich Text 그리기
    doc = QTextDocument()
    doc.setDefaultStyleSheet(f"p {{ color: {text_color.name()}; line-height: 100%; }}") # 줄 간격 조절
    doc.setHtml(full_html)
    doc.setTextWidth(text_rect.width())
    
    painter.translate(text_rect.topLeft())
    doc.drawContents(painter, QRectF(0, 0, text_rect.width(), text_rect.height()))
    
    painter.restore()