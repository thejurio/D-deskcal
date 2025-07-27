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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hour_height = 40
        self.total_hours = 24
        self.padding = 10  # 상하 여백
        self.setMinimumHeight(self.hour_height * self.total_hours + self.padding * 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = painter.fontMetrics()

        # 0시부터 24시까지 시간과 가로선을 그립니다.
        for hour in range(self.total_hours + 1):
            # 모든 y 좌표를 여백만큼 아래로 이동시킵니다.
            y = hour * self.hour_height + self.padding

            # 가로선 그리기 (시간 라벨 영역(50px) 제외)
            if hour > 0:
                painter.setPen(QColor("#444"))
                painter.drawLine(50, y, self.width(), y)

            # 시간 텍스트 그리기
            painter.setPen(QColor("#aaa"))
            text = f"{hour:02d}:00"
            text_height = fm.height()
            # 텍스트를 y 좌표의 중앙에 오도록 사각형을 계산합니다.
            draw_rect = QRect(0, y - text_height // 2, 50, text_height)
            painter.drawText(draw_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, text)