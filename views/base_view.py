# views/base_view.py
from PyQt6.QtWidgets import QWidget, QMenu, QToolTip, QApplication
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QCursor, QAction
import datetime

from custom_dialogs import CustomMessageBox, BaseDialog, EventPopover
from .widgets import EventLabelWidget

class BaseViewWidget(QWidget):
    add_event_requested = pyqtSignal(object)
    edit_event_requested = pyqtSignal(dict)
    navigation_requested = pyqtSignal(str)
    date_selected = pyqtSignal(datetime.date)

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.current_date = datetime.date.today()
        self.is_resizing = False
        self.event_widgets = []
        
        self.popover_timer = QTimer(self)
        self.popover_timer.setSingleShot(True)
        self.popover_timer.setInterval(500)
        self.popover_timer.timeout.connect(self.show_popover)
        
        self.current_popover = None
        self.hovered_event_widget = None
        self.hovered_event_data = None # 어떤 이벤트 데이터 위에 있는지 직접 저장

        self.setMouseTracking(True)
        self.data_manager.data_updated.connect(self.on_data_updated)
    
    # ▼▼▼ [핵심 수정] 자식 위젯이 직접 호출할 새로운 핸들러 함수들 ▼▼▼
    def handle_hover_enter(self, target_widget, event_data):
        """자식 위젯이 마우스 진입을 알리면 호출됩니다."""
        # 이전에 호버된 위젯/데이터와 다를 경우에만 타이머 시작
        if self.hovered_event_widget != target_widget or self.hovered_event_data != event_data:
            self.handle_hover_leave(self.hovered_event_widget)
            self.hovered_event_widget = target_widget
            self.hovered_event_data = event_data
            self.popover_timer.start()

    def handle_hover_leave(self, target_widget):
        """자식 위젯이 마우스 이탈을 알리면 호출됩니다."""
        if self.hovered_event_widget == target_widget:
            self.popover_timer.stop()
            if self.current_popover:
                self.current_popover.close()
                self.current_popover = None
            self.hovered_event_widget = None
            self.hovered_event_data = None
    # ▲▲▲ [핵심 수정] 종료 ▲▲▲

# views/base_view.py 파일의 BaseViewWidget 클래스

    def show_popover(self):
        if not self.hovered_event_data or not self.main_widget.is_interaction_unlocked():
            return

        if self.current_popover:
            self.current_popover.close()
            self.current_popover = None
        
        self.current_popover = EventPopover(self.hovered_event_data, self)
        
        # ▼▼▼ [수정] 팝오버 위치 계산 로직 전체 변경 ▼▼▼
        popover_size = self.current_popover.sizeHint()
        cursor_pos = QCursor.pos()
        main_window_rect = self.main_widget.geometry()
        main_window_center = main_window_rect.center()

        # 커서가 메인 창의 어느 쪽에 있는지에 따라 팝오버 위치 결정
        # 가로 위치
        if cursor_pos.x() < main_window_center.x():
            # 커서가 왼쪽에 있으면 팝오버는 커서 오른쪽에 표시
            x = cursor_pos.x() + 15
        else:
            # 커서가 오른쪽에 있으면 팝오버는 커서 왼쪽에 표시
            x = cursor_pos.x() - popover_size.width() - 15

        # 세로 위치
        if cursor_pos.y() < main_window_center.y():
            # 커서가 위쪽에 있으면 팝오버는 커서 아래쪽에 표시
            y = cursor_pos.y() + 15
        else:
            # 커서가 아래쪽에 있으면 팝오버는 커서 위쪽에 표시
            y = cursor_pos.y() - popover_size.height() - 15
        
        # 팝오버가 화면 밖으로 나가지 않도록 최종 보정
        screen_rect = QApplication.primaryScreen().availableGeometry()
        if x < screen_rect.left():
            x = screen_rect.left()
        if x + popover_size.width() > screen_rect.right():
            x = screen_rect.right() - popover_size.width()
        if y < screen_rect.top():
            y = screen_rect.top()
        if y + popover_size.height() > screen_rect.bottom():
            y = screen_rect.bottom() - popover_size.height()

        self.current_popover.move(x, y)
        # ▲▲▲ [수정] 종료 ▲▲▲
        
        self.current_popover.show()
    
    # ▼▼▼ [수정] 아래 두 함수는 이제 비워두거나 간단하게 유지합니다. ▼▼▼
    def mouseMoveEvent(self, event):
        """복잡한 로직을 제거하고, 자식 위젯이 처리하지 못한 경우에 대비합니다."""
        super().mouseMoveEvent(event)
        # 뷰의 빈 공간을 호버하면 팝오버가 사라져야 함
        if self.childAt(event.pos()) is None:
             self.handle_hover_leave(self.hovered_event_widget)

    def leaveEvent(self, event):
        """창을 벗어날 때 팝오버를 확실히 닫습니다."""
        super().leaveEvent(event)
        self.handle_hover_leave(self.hovered_event_widget)

    def set_resizing(self, is_resizing):
        self.is_resizing = is_resizing
        if self.is_resizing:
            for widget in self.event_widgets:
                widget.hide()
        else:
            self.refresh()

    def on_data_updated(self, year, month):
        self.redraw_events_with_current_data()

    def redraw_events_with_current_data(self):
        raise NotImplementedError("This method must be implemented by subclasses.")

    def refresh(self):
        raise NotImplementedError("This method must be implemented by subclasses.")

    def confirm_delete_event(self, event_data):
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
            self, title='삭제 확인', text=text,
            settings=self.main_widget.settings, pos=QCursor.pos()
        )
        if msg_box.exec():
            if is_recurring_instance:
                original_id = event_data.get('originalId', event_id.split('_')[0])
                event_data['body']['id'] = original_id
                event_data['id'] = original_id
            self.data_manager.delete_event(event_data)

    def show_context_menu(self, global_pos, target_event, date_info=None):
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