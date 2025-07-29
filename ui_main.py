import sys
import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QMenu, QPushButton, QStackedWidget, QSizeGrip, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QCursor, QIcon

from settings_manager import load_settings, save_settings
from config import DEFAULT_WINDOW_GEOMETRY

from data_manager import DataManager
from views.month_view import MonthViewWidget
from views.week_view import WeekViewWidget
from settings_window import SettingsWindow
from event_editor_window import EventEditorWindow
from search_dialog import SearchDialog

def load_stylesheet(file_path):
    """지정된 경로의 스타일시트 파일을 읽어서 문자열로 반환합니다."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# --- ▼▼▼ 리사이즈 상태 감지를 위한 커스텀 QSizeGrip 추가 ▼▼▼ ---
class CustomSizeGrip(QSizeGrip):
    grip_pressed = pyqtSignal()
    grip_released = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.grip_pressed.emit()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.grip_released.emit()
# --- ▲▲▲ 여기까지 추가 ▲▲▲ ---


class MainWidget(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.data_manager = DataManager(settings)
        self.is_resizing = False # 크기 조절 상태 플래그
        self.is_moving = False # 이동 상태 플래그
        self.border_width = 5 # 리사이즈 감지 영역
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Glassy Calendar')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # --- ▼▼▼ 마우스 트래킹 활성화 ▼▼▼ ---
        self.setMouseTracking(True) 
        # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---
        geometry = self.settings.get("geometry", DEFAULT_WINDOW_GEOMETRY)
        self.setGeometry(*geometry)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        self.background_widget.setObjectName("main_background")
        # --- ▼▼▼ 마우스 트래킹 활성화 ▼▼▼ ---
        self.background_widget.setMouseTracking(True)
        # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---
        
        
        
        self.setWindowOpacity(self.settings.get("window_opacity", 0.95))
        
        content_layout_wrapper = QVBoxLayout(self.background_widget)
        content_layout_wrapper.setContentsMargins(0,0,0,0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout_wrapper.addLayout(content_layout)

        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addStretch(1)
        
        size_grip = CustomSizeGrip(self.background_widget)
        size_grip.grip_pressed.connect(self.start_resize)
        size_grip.grip_released.connect(self.end_resize)

        bottom_bar_layout.addWidget(size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        content_layout_wrapper.addLayout(bottom_bar_layout)
        
        main_layout.addWidget(self.background_widget)

        self.data_manager.data_updated.connect(self.on_data_updated)
        
        view_mode_layout = QHBoxLayout()
        month_button, week_button = QPushButton("월력"), QPushButton("주간")
        month_button.setCheckable(True)
        week_button.setCheckable(True)
        
        today_button = QPushButton("오늘")
        today_button.setObjectName("today_button")
        today_button.clicked.connect(self.go_to_today)

        search_button = QPushButton() # 텍스트 제거
        search_button.setIcon(QIcon("icons/search.svg")) # 아이콘 설정
        search_button.setIconSize(QSize(20, 20)) # 아이콘 크기 설정
        search_button.setObjectName("search_button")
        search_button.setFixedSize(30, 28)
        search_button.setStyleSheet("padding-bottom: 2px;")
        search_button.clicked.connect(self.open_search_dialog)

        view_mode_layout.addWidget(search_button)
        view_mode_layout.addStretch(1)
        view_mode_layout.addWidget(month_button)
        view_mode_layout.addWidget(week_button)
        view_mode_layout.addStretch(1)
        view_mode_layout.addWidget(today_button)
        content_layout.addLayout(view_mode_layout)

        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        self.month_view = MonthViewWidget(self)
        self.week_view = WeekViewWidget(self)
        self.month_view.add_event_requested.connect(self.open_event_editor)
        self.month_view.edit_event_requested.connect(self.open_event_editor)
        self.week_view.add_event_requested.connect(self.open_event_editor)
        self.week_view.edit_event_requested.connect(self.open_event_editor)

        self.stacked_widget.addWidget(self.month_view)
        self.stacked_widget.addWidget(self.week_view)
        
        month_button.clicked.connect(lambda: self.change_view(0, month_button, [week_button]))
        week_button.clicked.connect(lambda: self.change_view(1, week_button, [month_button]))
        
        month_button.setChecked(True)
        self.oldPos = None

    def start_resize(self):
        """크기 조절 시작 시 호출됩니다."""
        if not self.is_resizing:
            self.is_resizing = True
            self.month_view.set_resizing(True)
            self.week_view.set_resizing(True)

    def end_resize(self):
        """크기 조절 종료 시 호출됩니다."""
        if self.is_resizing:
            self.is_resizing = False
            self.month_view.set_resizing(False)
            self.week_view.set_resizing(False)

    def set_window_opacity(self, opacity):
        self.setWindowOpacity(opacity)

    def go_to_today(self):
        today = datetime.date.today()
        self.month_view.current_date = today
        self.week_view.current_date = today
        self.refresh_current_view()

    def start(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.initial_load)

    def initial_load(self):
        self.data_manager.load_initial_month()
    
    def on_data_updated(self, year, month):
        if not self.is_resizing:
            self.refresh_current_view()

    def change_view(self, index, checked_button=None, other_buttons=None):
        self.stacked_widget.setCurrentIndex(index)
        if checked_button:
            checked_button.setChecked(True)
            if other_buttons:
                for button in other_buttons:
                    button.setChecked(False)
        if self.stacked_widget.currentWidget() == self.week_view:
            self.week_view.current_date = self.month_view.current_date
        self.refresh_current_view()

    def refresh_current_view(self):
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()

    def open_settings_window(self):
        with self.data_manager.user_action_priority():
            original_opacity = self.settings.get("window_opacity", 0.95)
            original_theme = self.settings.get("theme", "dark")

            settings_dialog = SettingsWindow(self.data_manager, self.settings, self, pos=QCursor.pos())
            settings_dialog.transparency_changed.connect(self.set_window_opacity)
            settings_dialog.theme_changed.connect(self.apply_theme) # 테마 변경 신호 연결
            
            result = settings_dialog.exec()
            
            if result:
                self.data_manager.update_cached_events_colors()
                self.data_manager.update_sync_timer()
                self.set_window_opacity(self.settings.get("window_opacity", 0.95))
                self.apply_theme(self.settings.get("theme", "dark"))
            else:
                # 취소 시, 원래 테마와 투명도로 복구
                self.set_window_opacity(original_opacity)
                self.apply_theme(original_theme)

    def open_search_dialog(self):
        """검색 다이얼로그를 엽니다."""
        with self.data_manager.user_action_priority():
            dialog = SearchDialog(self.data_manager, self, self.settings, pos=QCursor.pos())
            dialog.event_selected.connect(self.go_to_event)
            dialog.exec()

    def go_to_event(self, event_data):
        """선택된 이벤트의 날짜로 뷰를 이동하고 편집기를 엽니다."""
        start_info = event_data.get('start', {})
        date_str = start_info.get('dateTime', start_info.get('date'))
        
        if not date_str:
            # 날짜 정보가 없으면 편집기만 바로 엽니다.
            self.open_event_editor(event_data)
            return

        # 'Z'를 제거하고 datetime 객체로 변환
        if date_str.endswith('Z'):
            date_str = date_str[:-1]
        
        target_dt = datetime.datetime.fromisoformat(date_str)
        target_date = target_dt.date()

        # 뷰 이동
        self.month_view.current_date = target_date
        self.week_view.current_date = target_date
        
        # 현재 활성화된 뷰를 새로고침
        self.refresh_current_view()
        
        # 잠시 후 편집기 열기 (뷰 전환 및 렌더링 시간 확보)
        QTimer.singleShot(50, lambda: self.open_event_editor(event_data))

    def apply_theme(self, theme_name):
        """애플리케이션 전체에 테마를 적용합니다."""
        try:
            stylesheet = load_stylesheet(f'themes/{theme_name}_theme.qss')
            QApplication.instance().setStyleSheet(stylesheet)
        except FileNotFoundError:
            print(f"경고: '{theme_name}_theme.qss' 파일을 찾을 수 없습니다.")

    def open_event_editor(self, data):
        with self.data_manager.user_action_priority():
            all_calendars = self.data_manager.get_all_calendars()
            if not all_calendars:
                return

            editor = None
            cursor_pos = QCursor.pos() # 커서 위치 저장
            if isinstance(data, (datetime.date, datetime.datetime)):
                editor = EventEditorWindow(mode='new', data=data, calendars=all_calendars, settings=self.settings, parent=self, pos=cursor_pos, data_manager=self.data_manager)
            elif isinstance(data, dict):
                editor = EventEditorWindow(mode='edit', data=data, calendars=all_calendars, settings=self.settings, parent=self, pos=cursor_pos, data_manager=self.data_manager)
            
            if editor:
                result = editor.exec()
                if result == QDialog.DialogCode.Accepted:
                    event_data = editor.get_event_data()
                    
                    is_recurring = 'recurrence' in event_data.get('body', {})

                    if editor.mode == 'new': 
                        self.data_manager.add_event(event_data)
                    else: 
                        self.data_manager.update_event(event_data)
                    
                    self.settings['last_selected_calendar_id'] = event_data.get('calendarId')

                    # 반복 일정이면 즉시 동기화를 요청하여 나머지 일정을 빨리 가져옴
                    if is_recurring:
                        QTimer.singleShot(500, self.data_manager.request_full_sync)

                elif result == EventEditorWindow.DeleteRole:
                    event_to_delete = editor.get_event_data()
                    self.data_manager.delete_event(event_to_delete)

    def add_common_context_menu_actions(self, menu):
        if menu.actions(): menu.addSeparator()
        refreshAction = QAction("새로고침 (Refresh)", self)
        refreshAction.triggered.connect(self.data_manager.request_full_sync)
        menu.addAction(refreshAction)
        settingsAction = QAction("설정 (Settings)", self)
        settingsAction.triggered.connect(self.open_settings_window)
        menu.addAction(settingsAction)
        menu.addSeparator()
        exitAction = QAction("종료 (Exit)", self)
        exitAction.triggered.connect(self.close)
        menu.addAction(exitAction)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        main_opacity = self.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)
        self.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())
        
    def closeEvent(self, event):
        self.settings["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        save_settings(self.settings)
        self.data_manager.stop_caching_thread()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            
            # 클릭 위치가 가장자리인지 확인하여 리사이즈 모드 결정
            in_left = pos.x() < self.border_width
            in_right = pos.x() > self.width() - self.border_width
            in_top = pos.y() < self.border_width
            in_bottom = pos.y() > self.height() - self.border_width

            if in_left or in_right or in_top or in_bottom:
                self.is_resizing = True
                self.start_resize()
            else:
                self.is_moving = True
            
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            if self.is_moving:
                self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_resizing:
                self.end_resize()
            self.is_moving = False
            self.is_resizing = False
            self.oldPos = None
            self.unsetCursor() # 커서 모양 원래대로

if __name__ == '__main__':
    settings = load_settings()
    app = QApplication(sys.argv)
    
    # 설정에 저장된 테마를 불러와 적용
    selected_theme = settings.get("theme", "dark")
    try:
        stylesheet = load_stylesheet(f'themes/{selected_theme}_theme.qss')
        app.setStyleSheet(stylesheet)
    except FileNotFoundError:
        print(f"경고: 'themes/{selected_theme}_theme.qss' 파일을 찾을 수 없습니다.")

    widget = MainWidget(settings)
    widget.show()
    widget.start()
    sys.exit(app.exec())
