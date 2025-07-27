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

# 스타일시트 정의
DARK_THEME_STYLESHEET = """
    /* 전체적인 창과 위젯 스타일 */
    QWidget {
        background-color: #2E2E2E;
        color: #FFFFFF;
        border: none;
        font-family: "Malgun Gothic";
        font-size: 10pt;
    }
    /* 메인 배경 위젯 */
    QWidget#main_background {
        background-color: rgba(30, 30, 30, 0.95);
        border-radius: 10px;
    }
    /* 다이얼로그 배경 위젯 */
    QWidget#dialog_background {
        background-color: #3C3C3C; /* 메인 창보다 살짝 밝은 색 */
        border-radius: 10px;
    }
    /* 다이얼로그 (설정, 이벤트 편집 창) - 투명 배경 */
    QDialog {
        background-color: transparent;
    }
    /* 라벨 */
    QLabel {
        background-color: transparent;
    }
    /* 버튼 */
    QPushButton {
        background-color: #555555;
        border: 1px solid #777777;
        padding: 5px 10px;
        border-radius: 5px;
        min-height: 20px; /* 버튼 최소 높이 지정 */
    }
    QPushButton:hover {
        background-color: #6E6E6E;
    }
    QPushButton:pressed {
        background-color: #454545;
    }
    QPushButton:checked {
        background-color: #0078D7;
        border-color: #005A9E;
    }
    /* 텍스트 입력 필드 */
    QLineEdit, QTextEdit {
        background-color: #424242;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
        padding: 5px;
    }
    QLineEdit:focus, QTextEdit:focus {
        border-color: #0078D7;
    }
    /* 콤보박스 (드롭다운 메뉴) */
    QComboBox {
        background-color: #424242;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
        padding: 3px 5px;
    }
    QComboBox::drop-down {
        border: none;
    }
    QComboBox::down-arrow {
        image: url(./views/down_arrow.png); /* 화살표 아이콘 경로 (나중에 추가 필요) */
        width: 12px;
        height: 12px;
    }
    QComboBox QAbstractItemView {
        background-color: #424242;
        border: 1px solid #5A5A5A;
        selection-background-color: #0078D7;
    }
    /* 스크롤바 */
    QScrollBar:vertical {
        border: none;
        background: #2E2E2E;
        width: 10px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:vertical {
        background: #5A5A5A;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar:horizontal {
        border: none;
        background: #2E2E2E;
        height: 10px;
        margin: 0px 0px 0px 0px;
    }
    QScrollBar::handle:horizontal {
        background: #5A5A5A;
        min-width: 20px;
        border-radius: 5px;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    /* 메뉴 */
    QMenu {
        background-color: #424242;
        border: 1px solid #5A5A5A;
        padding: 5px;
    }
    QMenu::item {
        padding: 5px 20px;
    }
    QMenu::item:selected {
        background-color: #0078D7;
    }
    QMenu::separator {
        height: 1px;
        background: #5A5A5A;
        margin: 5px 0;
    }
    /* 체크박스 */
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
    }
    QCheckBox::indicator:unchecked {
        border: 1px solid #777;
        background-color: #424242;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        background-color: #0078D7;
        border: 1px solid #005A9E;
        border-radius: 3px;
        /* 체크 표시는 나중에 이미지로 추가 가능 */
    }
    /* 날짜/시간 편집 위젯 */
    QDateTimeEdit {
        background-color: #424242;
        border: 1px solid #5A5A5A;
        border-radius: 4px;
        padding: 3px;
    }
    QDateTimeEdit::up-button, QDateTimeEdit::down-button {
        width: 0px; /* 스핀 버튼 숨기기 */
    }
    QDateTimeEdit::drop-down {
        border: none;
    }
    /* 캘린더 팝업 */
    QCalendarWidget QWidget {
        alternate-background-color: #424242;
    }
    /* 메시지 박스 */
    QMessageBox {
        background-color: #3C3C3C;
    }
    QMessageBox QLabel {
        color: #FFFFFF;
    }
"""

class MainWidget(QWidget):
    def __init__(self, settings): # 'service' 파라미터 제거
        super().__init__()
        self.settings = settings
        # DataManager 생성 시 'service' 객체를 전달하지 않습니다.
        self.data_manager = DataManager(settings)
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Glassy Calendar')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        geometry = self.settings.get("geometry", [200, 200, 500, 450])
        self.setGeometry(*geometry)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        # ID를 설정하여 스타일시트에서 특정 스타일을 적용할 수 있도록 합니다.
        self.background_widget.setObjectName("main_background")
        
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
        month_button, list_button = QPushButton("월력"), QPushButton("목록")
        # 개별 스타일 지정 제거 (전역 스타일시트 사용)
        # view_button_style = "QPushButton { color: white; background-color: #555; border: 1px solid #777; padding: 5px; border-radius: 5px; } QPushButton:checked { background-color: #0078d7; }"
        # month_button.setStyleSheet(view_button_style)
        # list_button.setStyleSheet(view_button_style)
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
    # ... (이하 기존 메서드들은 변경 없음) ...
    def initial_load(self):
        """현재 달을 기준으로 초기 캐싱 계획을 수립합니다."""
        self.data_manager.load_initial_month()

    def on_data_updated(self, year, month):
        """
        데이터 변경 신호를 받아 현재 활성화된 뷰에 새로고침이 필요한지 확인합니다.
        MonthView는 자체적으로 신호를 처리하므로, 여기서는 다른 뷰(ListView)를 위해 처리합니다.
        """
        # MonthView가 보고 있는 월의 데이터가 변경되었고, 현재 ListView가 활성화 상태일 때
        if (year == self.month_view.current_date.year and 
            month == self.month_view.current_date.month and
            self.stacked_widget.currentWidget() == self.list_view):
            self.list_view.refresh()

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
        with self.data_manager.user_action_priority():
            settings_dialog = SettingsWindow(self.data_manager, self.settings, self)
            if settings_dialog.exec():
                print("설정이 변경되었습니다. UI 및 동기화 설정을 업데이트합니다.")
                self.data_manager.update_sync_timer() # 동기화 주기 즉시 변경
                self.data_manager.data_updated.emit() # 필터링된 캘린더 다시 적용


    # ui_main.py 파일입니다.

    def open_event_editor(self, data):
        """
        새 일정을 추가하거나 기존 일정을 수정하는 창을 엽니다.
        """
        with self.data_manager.user_action_priority():
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

    def add_common_context_menu_actions(self, menu):
        """공통 컨텍스트 메뉴 액션을 주어진 메뉴에 추가합니다."""
        if menu.actions(): # 기존에 액션이 있으면 구분선을 추가
            menu.addSeparator()

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
        self.add_common_context_menu_actions(menu)
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
    app = QApplication(sys.argv)
    
    # 전역 스타일시트 적용
    app.setStyleSheet(DARK_THEME_STYLESHEET)
    
    widget = MainWidget(settings)
    widget.show()
    widget.start()
    
    sys.exit(app.exec())