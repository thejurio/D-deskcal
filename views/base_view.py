# views/base_view.py
from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QCursor, QAction
import datetime

from custom_dialogs import CustomMessageBox, BaseDialog

class BaseViewWidget(QWidget):
    add_event_requested = pyqtSignal(object) # date 또는 datetime을 모두 받을 수 있도록 object 사용
    edit_event_requested = pyqtSignal(dict)
    navigation_requested = pyqtSignal(str)  # "forward", "backward"
    date_selected = pyqtSignal(datetime.date)

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

    def confirm_delete_event(self, event_data):
        """이벤트 삭제 확인 대화상자를 표시하고, 확인 시 이벤트를 삭제합니다."""
        summary = event_data.get('summary', '(제목 없음)')
        event_id = event_data.get('id', '')
        
        is_recurring_instance = '_' in event_id and event_data.get('provider') == 'LocalCalendarProvider'
        is_recurring_master = 'recurrence' in event_data

        text = f"'{summary}' 일정을 정말 삭제하시겠습니까?"
        if is_recurring_master:
            text = f"'{summary}'은(는) 반복 일정입니다.\n이 일정을 삭제하면 모든 관련 반복 일정이 삭제됩니다.\n\n정말 삭제하시겠습니까?"
        elif is_recurring_instance:
            text = f"'{summary}'은(는) 반복 일정의 일부입니다.\n현재 버전에서는 이 항목만 따로 삭제할 수 없습니다.\n\n전체 반복 일정을 삭제하시겠습니까?"

        msg_box = CustomMessageBox(
            self,
            title='삭제 확인',
            text=text,
            settings=self.main_widget.settings,
            pos=QCursor.pos()
        )
        if msg_box.exec():
            if is_recurring_instance:
                original_id = event_data.get('originalId', event_id.split('_')[0])
                event_data['body']['id'] = original_id
                event_data['id'] = original_id
            self.data_manager.delete_event(event_data)

    def show_context_menu(self, global_pos, target_event, date_info=None):
        """모든 뷰에서 공통으로 사용할 컨텍스트 메뉴를 생성하고 표시합니다."""
        menu = QMenu(self)
        main_opacity = self.main_widget.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)

        if target_event:
            event_id = target_event.get('id')
            is_completed = self.data_manager.is_event_completed(event_id)

            edit_action = QAction("수정", self)
            edit_action.triggered.connect(lambda: self.edit_event_requested.emit(target_event))
            menu.addAction(edit_action)

            if is_completed:
                reopen_action = QAction("진행", self)
                reopen_action.triggered.connect(lambda: self.data_manager.unmark_event_as_completed(event_id))
                menu.addAction(reopen_action)
            else:
                complete_action = QAction("완료", self)
                complete_action.triggered.connect(lambda: self.data_manager.mark_event_as_completed(event_id))
                menu.addAction(complete_action)

            delete_action = QAction("삭제", self)
            delete_action.triggered.connect(lambda: self.confirm_delete_event(target_event))
            menu.addAction(delete_action)
        
        elif date_info:
            add_action = QAction("일정 추가", self)
            add_action.triggered.connect(lambda: self.add_event_requested.emit(date_info))
            menu.addAction(add_action)
            
        self.main_widget.add_common_context_menu_actions(menu)
        menu.exec(global_pos)