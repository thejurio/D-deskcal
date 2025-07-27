import sys
import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QMenu, QPushButton, QStackedWidget, QSizeGrip)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction

from settings_manager import load_settings, save_settings

from data_manager import DataManager
from views.month_view import MonthViewWidget
from views.list_view import ListViewWidget
from settings_window import SettingsWindow
from event_editor_window import EventEditorWindow 

class MainWidget(QWidget):
    def __init__(self, settings): # 'service' 파라미터 제거
        super().__init__()
        self.settings = settings
        # DataManager 생성 시 'service' 객체를 전달하지 않습니다.
        self.data_manager = DataManager(settings)
        self.initUI()
        self.init_sync_timer()

    def initUI(self):
        self.setWindowTitle('Glassy Calendar')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        geometry = self.settings.get("geometry", [200, 200, 500, 450])
        self.setGeometry(*geometry)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        self.background_widget.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px;")
        
        content_layout_wrapper = QVBoxLayout(self.background_widget)
        content_layout_wrapper.setContentsMargins(0,0,0,0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout_wrapper.addLayout(content_layout)

        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addStretch(1)
        size_grip = QSizeGrip(self.background_widget)
        bottom_bar_layout.addWidget(size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        content_layout_wrapper.addLayout(bottom_bar_layout)
        
        main_layout.addWidget(self.background_widget)

        self.data_manager.data_updated.connect(self.refresh_current_view)
        
        view_mode_layout = QHBoxLayout()
        month_button, list_button = QPushButton("월력"), QPushButton("목록")
        view_button_style = "QPushButton { color: white; background-color: #555; border: 1px solid #777; padding: 5px; border-radius: 5px; } QPushButton:checked { background-color: #0078d7; }"
        month_button.setStyleSheet(view_button_style)
        list_button.setStyleSheet(view_button_style)
        month_button.setCheckable(True)
        list_button.setCheckable(True)
        view_mode_layout.addStretch(1)
        view_mode_layout.addWidget(month_button)
        view_mode_layout.addWidget(list_button)
        view_mode_layout.addStretch(1)
        content_layout.addLayout(view_mode_layout)

        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        self.month_view = MonthViewWidget(self)
        self.list_view = ListViewWidget(self)
        self.month_view.add_event_requested.connect(self.open_event_editor)
        self.month_view.edit_event_requested.connect(self.open_event_editor)

        self.stacked_widget.addWidget(self.month_view)
        self.stacked_widget.addWidget(self.list_view)
        
        month_button.clicked.connect(lambda: self.change_view(0, month_button, [list_button]))
        list_button.clicked.connect(lambda: self.change_view(1, list_button, [month_button]))
        
        month_button.setChecked(True)
        self.oldPos = None

    def start(self):
        QTimer.singleShot(0, self.initial_load)

    def initial_load(self):
        """현재 달을 먼저 로딩하고, 점진적 백그라운드 캐싱을 시작합니다."""
        self.data_manager.load_initial_month()
        self.data_manager.start_progressive_precaching()

    def init_sync_timer(self):
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(300000)
        self.sync_timer.timeout.connect(self.background_sync)
        self.sync_timer.start()
        print("자동 동기화 타이머가 시작되었습니다. (주기: 5분)")

    def background_sync(self):
        print(f"백그라운드에서 캐시된 모든 월의 동기화를 시작합니다...")
        cached_months = list(self.data_manager.event_cache.keys())
        for year, month in cached_months:
            self.data_manager.sync_month(year, month, emit_signal=False)
        self.refresh_current_view()
        print("모든 캐시 동기화 완료.")

    def change_view(self, index, checked_button=None, other_buttons=None):
        self.stacked_widget.setCurrentIndex(index)
        if checked_button:
            checked_button.setChecked(True)
            if other_buttons:
                for button in other_buttons:
                    button.setChecked(False)
        self.refresh_current_view()

    def refresh_current_view(self):
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'refresh'):
            current_widget.refresh()

    def open_settings_window(self):
        """설정 창을 열고, 변경사항이 저장되면 UI를 새로고침하여 필터를 다시 적용합니다."""
        settings_dialog = SettingsWindow(self.data_manager, self.settings, self)
        if settings_dialog.exec():
            print("설정이 변경되었습니다. 필터를 다시 적용합니다.")
            # 전체 데이터를 다시 불러오는 대신, UI만 새로고침하도록 신호를 보냅니다.
            self.data_manager.data_updated.emit()


    # ui_main.py 파일입니다.

    def open_event_editor(self, data):
        """
        새 일정을 추가하거나 기존 일정을 수정하는 창을 엽니다.
        """
        all_calendars = self.data_manager.get_all_calendars()
        if not all_calendars:
            print("편집할 캘린더가 없습니다. 설정을 확인해주세요.")
            return

        if isinstance(data, datetime.date):
            editor = EventEditorWindow(mode='new', data=data, calendars=all_calendars, settings=self.settings, parent=self)
            if editor.exec():
                new_event_data = editor.get_event_data()
                self.data_manager.add_event(new_event_data)
                # --- ▼▼▼ 마지막 선택 캘린더 ID를 저장합니다. ▼▼▼ ---
                self.settings['last_selected_calendar_id'] = new_event_data.get('calendarId')

        elif isinstance(data, dict):
            editor = EventEditorWindow(mode='edit', data=data, calendars=all_calendars, settings=self.settings, parent=self)
            if editor.exec():
                updated_event_data = editor.get_event_data()
                self.data_manager.update_event(updated_event_data)
                # --- ▼▼▼ 마지막 선택 캘린더 ID를 저장합니다. ▼▼▼ ---
                self.settings['last_selected_calendar_id'] = updated_event_data.get('calendarId')

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        settingsAction = QAction("설정 (Settings)", self)
        settingsAction.triggered.connect(self.open_settings_window)
        menu.addAction(settingsAction)
        refreshAction = QAction("새로고침 (Refresh)", self)
        refreshAction.triggered.connect(self.background_sync)
        menu.addAction(refreshAction)
        menu.addSeparator()
        exitAction = QAction("종료 (Exit)", self)
        exitAction.triggered.connect(self.close)
        menu.addAction(exitAction)
        menu.exec(event.globalPos())
        
    def closeEvent(self, event):
        self.settings["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        save_settings(self.settings)
        self.data_manager.save_cache_to_file()
        self.data_manager.stop_caching_thread() # <--- 이 줄을 추가합니다.
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.oldPos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y()); self.oldPos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self.oldPos = None


if __name__ == '__main__':
    settings = load_settings()
    # 'service' 객체를 미리 생성하지 않습니다.
    app = QApplication(sys.argv)
    # MainWidget 생성 시 'service'를 전달하지 않습니다.
    widget = MainWidget(settings)
    widget.show()
    widget.start()
    
    sys.exit(app.exec())