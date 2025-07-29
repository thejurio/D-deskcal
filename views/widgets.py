# views/widgets.py
from PyQt6.QtWidgets import QLabel, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen

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