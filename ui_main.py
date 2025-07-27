import sys
import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QMenu, QPushButton, QStackedWidget, QSizeGrip, QDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction

from settings_manager import load_settings, save_settings
from config import DEFAULT_WINDOW_GEOMETRY

from data_manager import DataManager
from views.month_view import MonthViewWidget
from views.week_view import WeekViewWidget
from settings_window import SettingsWindow
from event_editor_window import EventEditorWindow 

# 스타일시트 정의 (기존과 동일)
DARK_THEME_STYLESHEET = """
    /* ... (기존 스타일시트 내용은 변경 없음) ... */
    QWidget { background-color: #2E2E2E; color: #FFFFFF; border: none; font-family: "Malgun Gothic"; font-size: 10pt; }
    QWidget#dialog_background { background-color: #3C3C3C; border-radius: 10px; }
    QDialog { background-color: transparent; }
    QLabel { background-color: transparent; }
    QPushButton { background-color: #555555; border: 1px solid #777777; padding: 5px 10px; border-radius: 5px; min-height: 20px; }
    QPushButton:hover { background-color: #6E6E6E; border-color: #888888; }
    QPushButton:pressed { background-color: #4D4D4D; border-color: #666666; }
    QPushButton:checked { background-color: #0078D7; border-color: #005A9E; }
    QPushButton#today_button { background-color: #0078D7; border-color: #005A9E; }
    QPushButton#today_button:hover { background-color: #0082F0; }
    QPushButton#today_button:pressed { background-color: #006AC5; }
    QLineEdit, QTextEdit { background-color: #424242; border: 1px solid #5A5A5A; border-radius: 4px; padding: 5px; }
    QLineEdit:focus, QTextEdit:focus { border-color: #0078D7; }
    QComboBox { background-color: #424242; border: 1px solid #5A5A5A; border-radius: 4px; padding: 3px 5px; }
    QComboBox::drop-down { border: none; }
    QComboBox::down-arrow { image: url(./views/down_arrow.png); width: 12px; height: 12px; }
    QComboBox QAbstractItemView { background-color: #424242; border: 1px solid #5A5A5A; selection-background-color: #0078D7; }
    QScrollBar:vertical { border: none; background: #2E2E2E; width: 10px; margin: 0px 0px 0px 0px; }
    QScrollBar::handle:vertical { background: #5A5A5A; min-height: 20px; border-radius: 5px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar:horizontal { border: none; background: #2E2E2E; height: 10px; margin: 0px 0px 0px 0px; }
    QScrollBar::handle:horizontal { background: #5A5A5A; min-width: 20px; border-radius: 5px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
    QMenu { background-color: #424242; border: 1px solid #5A5A5A; padding: 5px; }
    QMenu::item { padding: 5px 20px; }
    QMenu::item:selected { background-color: #0078D7; }
    QMenu::separator { height: 1px; background: #5A5A5A; margin: 5px 0; }
    QCheckBox::indicator { width: 16px; height: 16px; }
    QCheckBox::indicator:unchecked { border: 1px solid #777; background-color: #424242; border-radius: 3px; }
    QCheckBox::indicator:checked { background-color: #0078D7; border: 1px solid #005A9E; border-radius: 3px; }
    QDateTimeEdit { background-color: #424242; border: 1px solid #5A5A5A; border-radius: 4px; padding: 3px; }
    QDateTimeEdit::up-button, QDateTimeEdit::down-button { width: 0px; }
    QDateTimeEdit::drop-down { border: none; }
    QCalendarWidget QWidget { alternate-background-color: #424242; }
    QMessageBox { background-color: #3C3C3C; }
    QMessageBox QLabel { color: #FFFFFF; }
    DayCellWidget { border: 1px solid #484848; }
    QToolTip { background-color: #424242; color: #FFFFFF; border: none; border-radius: 5px; padding: 5px; opacity: 230; }
"""

class MainWidget(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.data_manager = DataManager(settings)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Glassy Calendar')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        geometry = self.settings.get("geometry", DEFAULT_WINDOW_GEOMETRY)
        self.setGeometry(*geometry)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        self.background_widget.setObjectName("main_background")
        
        # 배경 위젯의 자체 투명도는 제거하고, 창 전체 투명도를 사용합니다.
        # background-color의 alpha 값을 제거합니다.
        self.background_widget.setStyleSheet("""
            QWidget#main_background {
                background-color: rgb(30, 30, 30);
                border-radius: 10px;
            }
        """)
        
        # 시작 시 저장된 창 전체 투명도 적용
        self.setWindowOpacity(self.settings.get("window_opacity", 0.95))
        
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

        self.data_manager.data_updated.connect(self.on_data_updated)
        
        view_mode_layout = QHBoxLayout()
        month_button, week_button = QPushButton("월력"), QPushButton("주간")
        month_button.setCheckable(True)
        week_button.setCheckable(True)
        
        today_button = QPushButton("오늘")
        today_button.setObjectName("today_button")
        today_button.clicked.connect(self.go_to_today)

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

    def set_window_opacity(self, opacity):
        """창의 전체 투명도를 설정합니다."""
        self.setWindowOpacity(opacity)

    def go_to_today(self):
        today = datetime.date.today()
        self.month_view.current_date = today
        self.week_view.current_date = today
        self.refresh_current_view()

    def start(self):
        QTimer.singleShot(0, self.initial_load)

    def initial_load(self):
        self.data_manager.load_initial_month()
    
    def on_data_updated(self, year, month):
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
            settings_dialog = SettingsWindow(self.data_manager, self.settings, self)
            # 실시간 미리보기 신호 연결
            settings_dialog.transparency_changed.connect(self.set_window_opacity)
            
            result = settings_dialog.exec()
            
            if result: # 저장 버튼 클릭
                print("설정이 변경되었습니다. UI 및 동기화 설정을 업데이트합니다.")
                self.data_manager.update_sync_timer()
                self.set_window_opacity(self.settings.get("window_opacity", 0.95)) # 저장된 값으로 최종 적용
                self.refresh_current_view() # 필터링된 캘린더 다시 적용
            else: # 취소 버튼 클릭 또는 그냥 닫았을 때
                self.set_window_opacity(original_opacity) # 원래 값으로 복구

    def open_event_editor(self, data):
        with self.data_manager.user_action_priority():
            all_calendars = self.data_manager.get_all_calendars()
            if not all_calendars:
                print("편집할 캘린더가 없습니다. 설정을 확인해주세요.")
                return

            editor = None
            if isinstance(data, (datetime.date, datetime.datetime)):
                editor = EventEditorWindow(mode='new', data=data, calendars=all_calendars, settings=self.settings, parent=self)
            elif isinstance(data, dict):
                editor = EventEditorWindow(mode='edit', data=data, calendars=all_calendars, settings=self.settings, parent=self)
            
            if editor:
                result = editor.exec()
                if result == QDialog.DialogCode.Accepted:
                    event_data = editor.get_event_data()
                    if editor.mode == 'new': self.data_manager.add_event(event_data)
                    else: self.data_manager.update_event(event_data)
                    self.settings['last_selected_calendar_id'] = event_data.get('calendarId')
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
        # 이 이벤트는 MonthViewWidget에서 처리되지 않은 경우 (예: 뷰 외부의 빈 공간 클릭)에만 호출됩니다.
        menu = QMenu(self)
        
        # --- ▼▼▼ 투명도 적용 코드 추가 ▼▼▼ ---
        main_opacity = self.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)
        # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

        self.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())
        
    def closeEvent(self, event):
        self.settings["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        save_settings(self.settings)
        self.data_manager.save_cache_to_file()
        self.data_manager.stop_caching_thread()
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
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_STYLESHEET)
    widget = MainWidget(settings)
    widget.show()
    widget.start()
    sys.exit(app.exec())
