# views/widgets.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal

class EventLabelWidget(QLabel):
    """
    이벤트 정보를 표시하고 더블클릭 시 수정 신호를 보내는 커스텀 라벨 위젯.
    월력 뷰와 주간 뷰에서 공통으로 사용됩니다.
    """
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
