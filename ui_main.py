import sys
import datetime
import copy
import logging

if sys.platform == "win32":
    import win32gui
    import win32con
    import windows_startup

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QHBoxLayout, QMenu, QPushButton, QStackedWidget, QSizeGrip, QDialog, QSystemTrayIcon)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QEvent
from PyQt6.QtGui import QAction, QIcon

import keyboard
from hotkey_manager import HotkeyManager
from auth_manager import AuthManager
from settings_manager import load_settings, save_settings
from config import (
                    DEFAULT_WINDOW_GEOMETRY,
                    DEFAULT_LOCK_MODE_ENABLED,
                    DEFAULT_LOCK_MODE_KEY,
                    DEFAULT_WINDOW_MODE,
                    DEFAULT_NOTIFICATION_DURATION
)

from data_manager import DataManager
from views.month_view import MonthViewWidget
from views.week_view import WeekViewWidget
from views.agenda_view import AgendaViewWidget
from settings_window import SettingsWindow
from event_editor_window import EventEditorWindow
from search_dialog import SearchDialog
from notification_manager import NotificationPopup
from timezone_helper import get_timezone_from_ip
from custom_dialogs import AIEventInputDialog, CustomMessageBox
from ai_confirmation_dialog import AIConfirmationDialog
import gemini_parser

def load_stylesheet(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

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

class MainWidget(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.auth_manager = AuthManager()
        self.data_manager = DataManager(settings, self.auth_manager)
        self.hotkey_manager = HotkeyManager(settings)
        self.hotkey_manager.hotkey_triggered.connect(self.handle_hotkey)
        self.hotkey_manager.register_and_start()
        self.current_date = datetime.date.today()
        self.is_resizing = False
        self.is_moving = False
        self.border_width = 5
        self.active_dialog = None

        self._interaction_unlocked = False
        self.lock_key_is_pressed = False

        self.initUI()

        self.data_manager.sync_timer.timeout.connect(self.data_manager.request_current_month_sync)
        self.data_manager.notification_triggered.connect(self.show_notification_popup)

        self.apply_window_settings()
        self.sync_startup_setting()

        self.lock_status_timer = QTimer(self)
        self.lock_status_timer.timeout.connect(self.check_lock_status)
        self.lock_status_timer.start(50)

        if sys.platform == "win32":
            QTimer.singleShot(100, self.force_set_desktop_widget_mode)

    def check_lock_status(self):
        # Skip lock status checking when a dialog is active
        if self.active_dialog is not None:
            return
            
        if not self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            if not self._interaction_unlocked:
                self.unlock_interactions()
            return

        lock_key = self.settings.get("lock_mode_key", DEFAULT_LOCK_MODE_KEY).lower()
        is_pressed = keyboard.is_pressed(lock_key)

        if is_pressed and not self.lock_key_is_pressed:
            self.lock_key_is_pressed = True
            self.unlock_interactions()
        elif not is_pressed and self.lock_key_is_pressed:
            self.lock_key_is_pressed = False
            if QApplication.instance().mouseButtons() == Qt.MouseButton.NoButton:
                self.lock_interactions()

    def handle_hotkey(self, action_name):
        if action_name == "ai_add_event":
            if self.active_dialog is not None:
                self.tray_icon.showMessage(
                    "알림",
                    "다른 창이 열려 있어 AI 일정 추가를 실행할 수 없습니다.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000
                )
                return
            self.open_ai_input_dialog()

    def show_notification_popup(self, title, message):
        if not hasattr(self, 'notification_popups'):
            self.notification_popups = []

        offset = len(self.notification_popups) * 10

        duration = self.settings.get("notification_duration", DEFAULT_NOTIFICATION_DURATION)
        popup = NotificationPopup(title, message, duration_seconds=duration)

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        popup_x = screen_geometry.width() - popup.width() - 15
        popup_y = screen_geometry.height() - popup.height() - 15 - offset
        popup.move(popup_x, popup_y)

        popup.show()

        popup.destroyed.connect(lambda: self.notification_popups.remove(popup))
        self.notification_popups.append(popup)

    def sync_startup_setting(self):
        if sys.platform != "win32":
            return

        should_start_on_boot = self.settings.get("start_on_boot", False)
        is_currently_in_startup = windows_startup.is_in_startup()

        try:
            if should_start_on_boot and not is_currently_in_startup:
                windows_startup.add_to_startup()
            elif not should_start_on_boot and is_currently_in_startup:
                windows_startup.remove_from_startup()
        except Exception as e:
            print(f"자동 시작 설정 동기화 중 오류 발생: {e}")

    def force_set_desktop_widget_mode(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = self.winId()
            
            # Set window style to prevent minimization by Win+D
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style &= ~win32con.WS_EX_APPWINDOW  # Remove from taskbar
            ex_style |= win32con.WS_EX_TOOLWINDOW  # Tool window style (prevents Win+D minimization)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
            
            # Set window to always stay at bottom (behind all other windows)
            win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

        except Exception as e:
            print(f"바탕화면 위젯 동작 설정 실패: {e}")
    
    def focusInEvent(self, event):
        """메인 윈도우가 포커스를 받을 때 항상 최하위로 보냄"""
        super().focusInEvent(event)
        # Always keep main window at desktop level
        QTimer.singleShot(0, self.force_set_desktop_widget_mode)
    
    def changeEvent(self, event):
        """메인 윈도우 상태 변경 시 항상 최하위 유지"""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange or event.type() == QEvent.Type.ActivationChange:
            # Always keep main window at desktop level
            QTimer.singleShot(0, self.force_set_desktop_widget_mode)
    

    def is_interaction_unlocked(self):
        if not self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            return True
        return self._interaction_unlocked

    def lock_interactions(self):
        if self._interaction_unlocked:
            self._interaction_unlocked = False
            if sys.platform == "win32":
                try:
                    hwnd = self.winId()
                    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_TRANSPARENT)
                except Exception as e:
                    print(f"Lock interactions error: {e}")

    def unlock_interactions(self):
        if not self._interaction_unlocked:
            self._interaction_unlocked = True
            if sys.platform == "win32":
                try:
                    hwnd = self.winId()
                    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style & ~win32con.WS_EX_TRANSPARENT)
                    # Don't activate main window - keep it at desktop level
                    # Force it back to bottom after unlocking interactions
                    QTimer.singleShot(0, self.force_set_desktop_widget_mode)
                except Exception as e:
                    print(f"Unlock interactions error: {e}")

    def apply_window_settings(self):
        self.show()
        if self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            self.lock_interactions()
        else:
            self.unlock_interactions()
        self.update_lock_icon()
        # Ensure main window stays at desktop level
        QTimer.singleShot(100, self.force_set_desktop_widget_mode)

    def toggle_lock_mode(self):
        is_enabled = self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED)
        self.settings["lock_mode_enabled"] = not is_enabled
        save_settings(self.settings)
        self.apply_window_settings()

    def update_lock_icon(self):
        is_enabled = self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED)
        if is_enabled:
            self.lock_button.setIcon(QIcon("icons/lock_locked.svg"))
            self.lock_button.setToolTip("잠금 모드 활성화됨 (클릭하여 비활성화)")
        else:
            self.lock_button.setIcon(QIcon("icons/lock_unlocked.svg"))
            self.lock_button.setToolTip("잠금 모드 비활성화됨 (클릭하여 활성화)")

    def initUI(self):
        self.setWindowTitle('Glassy Calendar')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        geometry = self.settings.get("geometry", DEFAULT_WINDOW_GEOMETRY)
        self.setGeometry(*geometry)

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        min_width = int(screen_geometry.width() * 0.20)
        min_height = int(screen_geometry.height() * 0.25)
        self.setMinimumSize(min_width, min_height)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        self.background_widget.setObjectName("main_background")
        self.background_widget.setMouseTracking(True)

        self.apply_background_opacity()

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
        self.data_manager.error_occurred.connect(self.show_error_message)

        month_button = QPushButton("월간")
        week_button = QPushButton("주간")
        agenda_button = QPushButton("안건")
        month_button.setCheckable(True)
        week_button.setCheckable(True)
        agenda_button.setCheckable(True)

        today_button = QPushButton("오늘")
        today_button.setObjectName("today_button")
        today_button.clicked.connect(self.go_to_today)

        search_button = QPushButton()
        search_button.setIcon(QIcon("icons/search.svg"))
        search_button.setIconSize(QSize(20, 20))
        search_button.setObjectName("search_button")
        search_button.setFixedSize(30, 30)
        search_button.setStyleSheet("padding-bottom: 2px;")
        search_button.clicked.connect(self.open_search_dialog)

        self.lock_button = QPushButton()
        self.lock_button.setIconSize(QSize(20, 20))
        self.lock_button.setObjectName("lock_button")
        self.lock_button.setFixedSize(30, 30)
        self.lock_button.setStyleSheet("padding-bottom: 2px;")
        self.lock_button.clicked.connect(self.toggle_lock_mode)

        ai_add_button = QPushButton()
        ai_add_button.setIcon(QIcon("icons/gemini.svg"))
        ai_add_button.setIconSize(QSize(20, 20))
        ai_add_button.setObjectName("ai_add_button")
        ai_add_button.setFixedSize(30, 30)
        ai_add_button.setToolTip("AI로 일정 추가")
        ai_add_button.clicked.connect(self.open_ai_input_dialog)

        view_mode_layout = QHBoxLayout()
        view_mode_layout.setSpacing(5)
        
        # 좌측: 안건, 검색
        left_layout = QHBoxLayout()
        left_layout.addWidget(agenda_button)
        left_layout.addWidget(search_button)
        left_layout.addStretch(1)

        # 중앙: 월간, 주간
        center_layout = QHBoxLayout()
        center_layout.addStretch(1)
        center_layout.addWidget(month_button)
        center_layout.addWidget(week_button)
        center_layout.addStretch(1)

        # 우측: AI, 잠금, 오늘
        right_layout = QHBoxLayout()
        right_layout.addStretch(1)
        right_layout.addWidget(ai_add_button)
        right_layout.addWidget(self.lock_button)
        right_layout.addWidget(today_button)

        view_mode_layout.addLayout(left_layout)
        view_mode_layout.addLayout(center_layout)
        view_mode_layout.addLayout(right_layout)

        content_layout.addLayout(view_mode_layout)

        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        self.month_view = MonthViewWidget(self)
        self.week_view = WeekViewWidget(self)
        self.agenda_view = AgendaViewWidget(self)

        self.month_view.add_event_requested.connect(self.open_event_editor)
        self.month_view.edit_event_requested.connect(self.open_event_editor)
        self.month_view.navigation_requested.connect(self.handle_month_navigation)
        self.month_view.date_selected.connect(self.set_current_date)

        self.week_view.add_event_requested.connect(self.open_event_editor)
        self.week_view.edit_event_requested.connect(self.open_event_editor)
        self.week_view.navigation_requested.connect(self.handle_week_navigation)
        self.week_view.date_selected.connect(self.set_current_date)

        self.agenda_view.edit_event_requested.connect(self.open_event_editor)
        
        self.data_manager.event_completion_changed.connect(self.month_view.refresh)
        self.data_manager.event_completion_changed.connect(self.week_view.refresh)
        self.data_manager.event_completion_changed.connect(self.agenda_view.refresh)

        self.stacked_widget.addWidget(self.month_view)
        self.stacked_widget.addWidget(self.week_view)
        self.stacked_widget.addWidget(self.agenda_view)

        month_button.clicked.connect(lambda: self.change_view(0, month_button, [week_button, agenda_button]))
        week_button.clicked.connect(lambda: self.change_view(1, week_button, [month_button, agenda_button]))
        agenda_button.clicked.connect(lambda: self.change_view(2, agenda_button, [month_button, week_button]))

        month_button.setChecked(True)
        self.oldPos = None

        self.set_current_date(self.current_date, is_initial=True)
        self.setup_tray_icon()

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(QIcon("icons/tray_icon.svg"), self)
        self.tray_icon.setToolTip("Glassy Calendar")

        tray_menu = QMenu()

        add_event_action = QAction("일정 추가", self)
        add_event_action.triggered.connect(lambda: self.open_event_editor(datetime.date.today()))
        tray_menu.addAction(add_event_action)

        settings_action = QAction("설정", self)
        settings_action.triggered.connect(self.open_settings_window)
        tray_menu.addAction(settings_action)

        refresh_action = QAction("새로고침", self)
        refresh_action.triggered.connect(lambda: self.data_manager.force_sync_month(self.current_date.year, self.current_date.month))
        tray_menu.addAction(refresh_action)

        tray_menu.addSeparator()

        quit_action = QAction("종료", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def show_window(self):
        self.show()
        # Don't activate main window - keep it at desktop level
        QTimer.singleShot(0, self.force_set_desktop_widget_mode)

    def _get_dialog_pos(self):
        screen = QApplication.screenAt(self.pos())
        if not screen:
            screen = QApplication.primaryScreen()
        return screen.availableGeometry().center()

    def _push_to_desktop_bottom(self):
        if sys.platform != "win32": return
        try:
            hwnd = self.winId()
            # Always keep window at the bottom layer
            win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        except Exception as e:
            print(f"Push to desktop bottom error: {e}")

    def quit_application(self):
        self.settings["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        save_settings(self.settings)
        self.data_manager.stop_caching_thread()
        self.hotkey_manager.stop()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def set_current_date(self, new_date, is_initial=False):
        self.current_date = new_date
        self.month_view.current_date = new_date
        self.week_view.current_date = new_date

        # data_manager.get_events()가 notify_date_changed를 호출하므로, 여기서 직접 호출할 필요 없음
        self.refresh_current_view()

    def handle_month_navigation(self, direction):
        if direction == "forward":
            new_date = (self.current_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        else:
            new_date = self.current_date.replace(day=1) - datetime.timedelta(days=1)
        self.set_current_date(new_date)

    def handle_week_navigation(self, direction):
        days_to_move = 7 if direction == "forward" else -7
        new_date = self.current_date + datetime.timedelta(days=days_to_move)
        self.set_current_date(new_date)

    def start_resize(self):
        if not self.is_resizing:
            self.is_resizing = True
            self.month_view.set_resizing(True)
            self.week_view.set_resizing(True)

    def end_resize(self):
        if self.is_resizing:
            self.is_resizing = False
            self.month_view.set_resizing(False)
            self.week_view.set_resizing(False)

    def apply_background_opacity(self, opacity=None):
        if opacity is None:
            opacity = self.settings.get("window_opacity", 0.95)

        theme_name = self.settings.get("theme", "dark")
        alpha = int(opacity * 255)

        if theme_name == "dark":
            base_color = "30, 30, 30"
        else: # light theme
            base_color = "250, 250, 250"

        style = f"""
            QWidget#main_background {{
                background-color: rgba({base_color}, {alpha});
                border-radius: 10px;
            }}
        """
        self.background_widget.setStyleSheet(style)

    def go_to_today(self):
        self.set_current_date(datetime.date.today())

    def start(self):
        QTimer.singleShot(0, self.initial_load)

    def initial_load(self):
        self.data_manager.load_initial_month()

    def on_data_updated(self, year, month):
        if self.is_resizing:
            return

        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'current_date'):
            if current_widget.current_date.year == year and current_widget.current_date.month == month:
                if hasattr(current_widget, 'schedule_draw_events'):
                    current_widget.schedule_draw_events()
                else:
                    self.refresh_current_view()

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

    def handle_visual_preview(self):
        current_widget = self.stacked_widget.currentWidget()
        if current_widget:
            current_widget.update()

    def open_settings_window(self):
        if self.active_dialog is not None:
            self.active_dialog.activateWindow()
            return
        with self.data_manager.user_action_priority():
            original_settings_snapshot = copy.deepcopy(self.settings)

            settings_dialog = SettingsWindow(self.data_manager, self.settings, None, pos=self._get_dialog_pos())
            self.active_dialog = settings_dialog

            settings_dialog.transparency_changed.connect(self.apply_background_opacity)
            settings_dialog.theme_changed.connect(self.apply_theme)

            result = settings_dialog.exec()
            self.active_dialog = None

            if result == QDialog.DialogCode.Accepted:
                changed_fields = settings_dialog.get_changed_fields()

                if "window_opacity" in changed_fields:
                    self.apply_background_opacity()
                if "theme" in changed_fields:
                    self.apply_theme(self.settings.get("theme", "dark"))
                if "sync_interval_minutes" in changed_fields:
                    self.data_manager.update_sync_timer()

                if any(field in changed_fields for field in ["window_mode", "lock_mode_enabled", "lock_mode_key"]):
                    self.apply_window_settings()

                if "start_on_boot" in changed_fields:
                    self.sync_startup_setting()

                if "ai_add_event_hotkey" in changed_fields:
                    self.hotkey_manager.register_and_start()

                grid_structure_changes = {"start_day_of_week", "hide_weekends"}
                if any(field in changed_fields for field in grid_structure_changes):
                    self.refresh_current_view()
                    return

                if "calendar_colors" in changed_fields:
                    self.handle_visual_preview()

                if "selected_calendars" in changed_fields:
                    if "calendar_colors" not in changed_fields:
                        self.handle_visual_preview()

            else: # Cancelled
                self.settings.clear()
                self.settings.update(original_settings_snapshot)
                self.apply_background_opacity()
                self.apply_theme(self.settings.get("theme", "dark"))
                self.apply_window_settings()
                self.refresh_current_view()

            if sys.platform == "win32":
                self.force_set_desktop_widget_mode()

    def open_ai_input_dialog(self):
        if not self.is_interaction_unlocked():
            return

        input_dialog = AIEventInputDialog(None, self.settings, pos=self._get_dialog_pos())
        if not input_dialog.exec():
            return

        text_to_analyze = input_dialog.get_text()
        if not text_to_analyze:
            self.show_error_message("분석할 텍스트가 입력되지 않았습니다.")
            return

        api_key = self.settings.get("gemini_api_key")
        if not api_key:
            self.show_error_message("Gemini API 키가 설정되지 않았습니다.\n[설정 > 계정] 탭에서 API 키를 먼저 등록해주세요.")
            return

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            parsed_events = gemini_parser.parse_events_with_gemini(api_key, text_to_analyze)
            QApplication.restoreOverrideCursor()

            if not parsed_events:
                self.show_error_message("텍스트에서 유효한 일정 정보를 찾지 못했습니다.")
                return

            confirmation_dialog = AIConfirmationDialog(parsed_events, self.data_manager, None, self.settings, pos=self._get_dialog_pos())
            if confirmation_dialog.exec():
                final_events, calendar_id, provider_name = confirmation_dialog.get_final_events_and_calendar()

                if not calendar_id:
                    self.show_error_message("일정을 추가할 캘린더를 선택해주세요.")
                    return

                for event in final_events:
                    is_deadline_only = event.get('isDeadlineOnly', False)
                    is_all_day = event.get('isAllDay', False)

                    event_body = {
                        'summary': event['title'],
                        'start': {},
                        'end': {},
                        'location': event.get('location', ''),
                        'description': event.get('description', '')
                    }

                    if is_deadline_only:
                        event_body['summary'] = f"[마감] {event['title']}"
                        event_body['start']['date'] = event['endDate']
                        end_date_obj = datetime.date.fromisoformat(event['endDate']) + datetime.timedelta(days=1)
                        event_body['end']['date'] = end_date_obj.isoformat()

                    elif is_all_day:
                        event_body['start']['date'] = event['startDate']
                        end_date_obj = datetime.date.fromisoformat(event['endDate']) + datetime.timedelta(days=1)
                        event_body['end']['date'] = end_date_obj.isoformat()

                    else: # 시간 지정 이벤트
                        user_timezone = self.settings.get("user_timezone", "Asia/Seoul") # 기본값 설정
                        event_body['start']['dateTime'] = f"{event['startDate']}T{event['startTime']}:00"
                        event_body['start']['timeZone'] = user_timezone
                        event_body['end']['dateTime'] = f"{event['endDate']}T{event['endTime']}:00"
                        event_body['end']['timeZone'] = user_timezone

                    event_to_add = {
                        'calendarId': calendar_id,
                        'provider': provider_name,
                        'body': event_body
                    }
                    self.data_manager.add_event(event_to_add)

                self.settings['last_selected_calendar_id'] = calendar_id
                save_settings(self.settings) # AI 추가 후에도 캘린더 ID 저장
                self.show_error_message(f"{len(final_events)}개의 일정을 성공적으로 추가했습니다.", ok_only=True, title="알림")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.show_error_message(f"AI 분석 중 오류가 발생했습니다:\n{e}")

    def open_search_dialog(self):
        with self.data_manager.user_action_priority():
            dialog = SearchDialog(self.data_manager, self, self.settings, pos=self._get_dialog_pos())
            dialog.event_selected.connect(self.go_to_event)
            dialog.exec()

    def go_to_event(self, event_data):
        start_info = event_data.get('start', {})
        date_str = start_info.get('dateTime', start_info.get('date'))

        if not date_str:
            self.open_event_editor(event_data)
            return

        if date_str.endswith('Z'):
            date_str = date_str[:-1]

        target_dt = datetime.datetime.fromisoformat(date_str)
        target_date = target_dt.date()

        self.set_current_date(target_date)
        QTimer.singleShot(50, lambda: self.open_event_editor(event_data))

    def apply_theme(self, theme_name):
        try:
            stylesheet = load_stylesheet(f'themes/{theme_name}_theme.qss')
            app = QApplication.instance()
            app.setStyleSheet(stylesheet)

            self.apply_background_opacity()

            for widget in app.topLevelWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()

            self.month_view.refresh()
            self.week_view.refresh()

        except FileNotFoundError:
            print(f"경고: '{theme_name}_theme.qss' 파일을 찾을 수 없습니다.")

    def open_event_editor(self, data):
        if self.active_dialog is not None:
            self.active_dialog.activateWindow()
            return
            
        # user_action_priority 컨텍스트에서 데드락 발생하므로 제거
        editor = None
        cursor_pos = self._get_dialog_pos()
        
        if isinstance(data, (datetime.date, datetime.datetime)):
            editor = EventEditorWindow(mode='new', data=data, settings=self.settings, parent=None, pos=cursor_pos, data_manager=self.data_manager)
        elif isinstance(data, dict):
            editor = EventEditorWindow(mode='edit', data=data, settings=self.settings, parent=None, pos=cursor_pos, data_manager=self.data_manager)

        if editor:
            self.active_dialog = editor
            result = editor.exec()
            self.active_dialog = None
            if result == QDialog.DialogCode.Accepted:
                event_data = editor.get_event_data()
                if not event_data.get('calendarId'):
                    self.show_error_message("캘린더 목록이 아직 로딩되지 않았습니다. 잠시 후 다시 시도해주세요.")
                    return

                is_recurring = 'recurrence' in event_data.get('body', {})
                if editor.mode == 'new':
                    self.data_manager.add_event(event_data)
                else:
                    self.data_manager.update_event(event_data)

                self.settings['last_selected_calendar_id'] = event_data.get('calendarId')
                save_settings(self.settings)

                if is_recurring:
                    # --- BUG FIX ---
                    event_body = event_data.get('body', {})
                    start_info = event_body.get('start', {})
                    date_str = start_info.get('dateTime', start_info.get('date'))
                    event_date = datetime.date.fromisoformat(date_str[:10])
                    year_to_sync = event_date.year
                    month_to_sync = event_date.month

                    QTimer.singleShot(500, lambda: self.data_manager.force_sync_month(year_to_sync, month_to_sync))

            elif result == EventEditorWindow.DeleteRole:
                event_to_delete = editor.get_event_data()
                deletion_mode = editor.get_deletion_mode() # Get the user's choice
                self.data_manager.delete_event(event_to_delete, deletion_mode=deletion_mode)

    def show_error_message(self, message, ok_only=False, title="오류"):
        if not self.is_interaction_unlocked():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Warning if title == "오류" else QSystemTrayIcon.MessageIcon.Information,
                5000
            )
        else:
            dialog = CustomMessageBox(
                parent=None,
                title=title,
                text=message,
                settings=self.settings,
                pos=self._get_dialog_pos(),
                ok_only=ok_only
            )
            dialog.exec()

    def add_common_context_menu_actions(self, menu):
        if menu.actions(): menu.addSeparator()
        refreshAction = QAction("새로고침 (Refresh)", self)
        refreshAction.triggered.connect(lambda: self.data_manager.force_sync_month(self.current_date.year, self.current_date.month))
        menu.addAction(refreshAction)
        settingsAction = QAction("설정 (Settings)", self)
        settingsAction.triggered.connect(self.open_settings_window)
        menu.addAction(settingsAction)
        menu.addSeparator()
        exitAction = QAction("종료 (Exit)", self)
        exitAction.triggered.connect(self.quit_application)
        menu.addAction(exitAction)

    def contextMenuEvent(self, event):
        if not self.is_interaction_unlocked():
            return
        menu = QMenu(self)
        main_opacity = self.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)
        self.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Glassy Calendar",
            "캘린더가 백그라운드에서 실행 중입니다.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def mousePressEvent(self, event):
        if not self.is_interaction_unlocked():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
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
        if not self.is_interaction_unlocked():
            return
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            if self.is_moving:
                self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if not self.is_interaction_unlocked() and not self.lock_key_is_pressed:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.is_moving:
                self.snap_to_screen_edges()
                # Ensure window stays at bottom after moving
                QTimer.singleShot(50, self._push_to_desktop_bottom)

            if self.is_resizing:
                self.end_resize()

            self.is_moving = False
            self.is_resizing = False
            self.oldPos = None
            self.unsetCursor()

        if self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED) and not self.lock_key_is_pressed:
            QTimer.singleShot(50, self.lock_interactions)

    def snap_to_screen_edges(self):
        snap_threshold = 45
        win_rect = self.frameGeometry()
        screens = QApplication.screens()

        closest_screen = None
        min_dist = float('inf')

        for screen in screens:
            screen_center = screen.availableGeometry().center()
            win_center = win_rect.center()
            dist = (screen_center - win_center).manhattanLength()
            if dist < min_dist:
                min_dist = dist
                closest_screen = screen

        if not closest_screen:
            closest_screen = QApplication.primaryScreen()

        screen_geometry = closest_screen.availableGeometry()
        new_pos = win_rect.topLeft()
        moved = False

        if abs(win_rect.left() - screen_geometry.left()) < snap_threshold:
            new_pos.setX(screen_geometry.left())
            moved = True
        elif abs(win_rect.right() - screen_geometry.right()) < snap_threshold:
            new_pos.setX(screen_geometry.right() - win_rect.width())
            moved = True

        if abs(win_rect.top() - screen_geometry.top()) < snap_threshold:
            new_pos.setY(screen_geometry.top())
            moved = True
        elif abs(win_rect.bottom() - screen_geometry.bottom()) < snap_threshold:
            new_pos.setY(screen_geometry.bottom() - win_rect.height())
            moved = True

        if moved:
            self.move(new_pos)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='error.log',
        filemode='a'
    )
    
    settings = load_settings()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if "user_timezone" not in settings:
        user_timezone = get_timezone_from_ip()
        settings["user_timezone"] = user_timezone
        save_settings(settings)

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