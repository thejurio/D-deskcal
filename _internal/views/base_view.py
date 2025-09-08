# views/base_view.py
from PyQt6.QtWidgets import QWidget, QMenu, QApplication
from PyQt6.QtCore import pyqtSignal, QTimer, pyqtProperty
from PyQt6.QtGui import QCursor, QAction, QColor
import datetime

from custom_dialogs import CustomMessageBox, EventPopover
from event_editor_window import EventEditorWindow
from config import LOCAL_CALENDAR_PROVIDER_NAME

class BaseViewWidget(QWidget):
    add_event_requested = pyqtSignal(object)
    edit_event_requested = pyqtSignal(dict)
    edit_requested = pyqtSignal(dict)  # 더블클릭 편집 요청 시그널
    detail_requested = pyqtSignal(dict)  # 상세보기 요청 시그널
    navigation_requested = pyqtSignal(str)
    date_selected = pyqtSignal(datetime.date)

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.current_date = datetime.date.today()
        self.is_resizing = False
        self.event_widgets = []
        
        # QSS 속성을 위한 내부 변수 초기화
        self._weekdayColor = QColor()
        self._saturdayColor = QColor()
        self._sundayColor = QColor()
        self._otherMonthColor = QColor()
        self._todayBackgroundColor = QColor()
        self._todayForegroundColor = QColor()

        self.popover_timer = QTimer(self)
        self.popover_timer.setSingleShot(True)
        self.popover_timer.setInterval(500)
        self.popover_timer.timeout.connect(self.show_popover)
        
        self.current_popover = None
        self.hovered_event_widget = None
        self.hovered_event_data = None # 어떤 이벤트 데이터 위에 있는지 직접 저장

        self.setMouseTracking(True)
        self.data_manager.data_updated.connect(self.on_data_updated)

    # weekdayColor 속성 정의
    def getWeekdayColor(self): return self._weekdayColor
    def setWeekdayColor(self, color): self._weekdayColor = color
    weekdayColor = pyqtProperty(QColor, getWeekdayColor, setWeekdayColor)

    # saturdayColor 속성 정의
    def getSaturdayColor(self): return self._saturdayColor
    def setSaturdayColor(self, color): self._saturdayColor = color
    saturdayColor = pyqtProperty(QColor, getSaturdayColor, setSaturdayColor)

    # sundayColor 속성 정의
    def getSundayColor(self): return self._sundayColor
    def setSundayColor(self, color): self._sundayColor = color
    sundayColor = pyqtProperty(QColor, getSundayColor, setSundayColor)

    # otherMonthColor 속성 정의
    def getOtherMonthColor(self): return self._otherMonthColor
    def setOtherMonthColor(self, color): self._otherMonthColor = color
    otherMonthColor = pyqtProperty(QColor, getOtherMonthColor, setOtherMonthColor)

    # todayBackgroundColor 속성 정의
    def getTodayBackgroundColor(self): return self._todayBackgroundColor
    def setTodayBackgroundColor(self, color): self._todayBackgroundColor = color
    todayBackgroundColor = pyqtProperty(QColor, getTodayBackgroundColor, setTodayBackgroundColor)

    # todayForegroundColor 속성 정의
    def getTodayForegroundColor(self): return self._todayForegroundColor
    def setTodayForegroundColor(self, color): self._todayForegroundColor = color
    todayForegroundColor = pyqtProperty(QColor, getTodayForegroundColor, setTodayForegroundColor)
    
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
        
        self.current_popover = EventPopover(self.hovered_event_data, self.main_widget.settings, self)
        
        # 팝오버 신호 연결
        print(f"[DEBUG] BaseView: 팝오버 신호 연결 중 - {self.hovered_event_data.get('summary', '')}")
        self.current_popover.detail_requested.connect(self.detail_requested.emit)
        self.current_popover.edit_requested.connect(self.edit_requested.emit)
        print(f"[DEBUG] BaseView: 팝오버 신호 연결 완료")
        
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
        
        # 팝오버가 화면 밖으로 나가지 않도록 최종 보정 (현재 위젯이 있는 화면 기준)
        screen_rect = self.screen().availableGeometry() if self.screen() else \
                      QApplication.primaryScreen().availableGeometry()
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
        
        # 디버그 정보 추가
        print(f"[DEBUG] BaseView: 팝오버 위치 설정 - x={x}, y={y}, size={popover_size}")
        print(f"[DEBUG] BaseView: 커서 위치 - {cursor_pos}")
        print(f"[DEBUG] BaseView: 화면 크기 - {screen_rect}")
        
        self.current_popover.show()
        print(f"[DEBUG] BaseView: 팝오버 show() 호출 완료")
        print(f"[DEBUG] BaseView: 팝오버 visible={self.current_popover.isVisible()}, pos={self.current_popover.pos()}")
    
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

    # views/base_view.py 파일의 BaseViewWidget 클래스 내부에 위치

    def confirm_delete_event(self, event_data):
        """
        [수정됨] EventEditorWindow의 정적 메서드를 직접 호출하여
        수정창을 띄우지 않고 바로 삭제 확인창을 보여줍니다.
        또한, DataManager가 요구하는 데이터 형식으로 변환하여 전달합니다.
        """
        # EventEditorWindow에서 삭제 확인 로직을 가져와 직접 사용
        chosen_mode = EventEditorWindow.show_delete_confirmation(
            event_data, self, self.main_widget.settings
        )

        if chosen_mode:
            # 사용자가 삭제를 확정했을 경우, DataManager 호출
            event_to_delete = event_data.copy()

            # DataManager가 'body' 키를 포함하는 래핑된 딕셔너리를 예상하므로,
            # 'body' 키가 없는 경우 데이터 구조를 맞춰줍니다.
            if 'body' not in event_to_delete:
                 event_to_delete = {
                    'calendarId': event_data.get('calendarId'),
                    'provider': event_data.get('provider'),
                    'body': event_data
                 }
            
            self.data_manager.delete_event(event_to_delete, deletion_mode=chosen_mode)
    # ▲▲▲ [핵심 수정] 여기까지 입니다. ▲▲▲

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