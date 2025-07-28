# views/base_view.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal
import datetime

class BaseViewWidget(QWidget):
    add_event_requested = pyqtSignal(object) # date 또는 datetime을 모두 받을 수 있도록 object 사용
    edit_event_requested = pyqtSignal(dict)

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.current_date = datetime.date.today()
        self.is_resizing = False
        self.event_widgets = []

        # 데이터가 업데이트되면 현재 뷰를 새로고침하도록 연결
        self.data_manager.data_updated.connect(self.on_data_updated)

    def set_resizing(self, is_resizing):
        """리사이즈 상태를 설정하고, 상태에 따라 이벤트 위젯을 숨기거나 다시 그립니다."""
        self.is_resizing = is_resizing
        if self.is_resizing:
            for widget in self.event_widgets:
                widget.hide()
        else:
            self.redraw_events_with_current_data()

    def on_data_updated(self, year, month):
        # 현재 뷰가 표시하고 있는 기간과 관련이 있는지 확인 후 새로고침
        # (이 부분은 자식 클래스에서 더 정교하게 구현할 수 있음)
        self.redraw_events_with_current_data()

    def redraw_events_with_current_data(self):
        """데이터 매니저로부터 현재 뷰에 맞는 데이터를 가져와 이벤트를 다시 그립니다."""
        # 이 메서드는 각 뷰(월/주)의 특성에 맞게 자식 클래스에서 반드시 재정의(override)해야 합니다.
        raise NotImplementedError("This method must be implemented by subclasses.")

    def refresh(self):
        """뷰의 전체 UI를 새로고칩니다. (날짜, 이벤트 등)"""
        # 이 메서드도 자식 클래스에서 재정의해야 합니다.
        raise NotImplementedError("This method must be implemented by subclasses.")
