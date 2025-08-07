import sys
import datetime
import copy
import os

if sys.platform == "win32":
    import win32gui
    import win32con
    import win32api
    import windows_startup

from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, 
                             QHBoxLayout, QMenu, QPushButton, QStackedWidget, QSizeGrip, QDialog, QSystemTrayIcon, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QCursor, QIcon

from pynput import keyboard
from auth_manager import AuthManager
from settings_manager import load_settings, save_settings
from config import (DEFAULT_WINDOW_GEOMETRY, DEFAULT_LOCK_MODE_ENABLED, 
                    DEFAULT_LOCK_MODE_KEY, DEFAULT_WINDOW_MODE,
                    DEFAULT_NOTIFICATION_DURATION)

from data_manager import DataManager
from views.month_view import MonthViewWidget
from views.week_view import WeekViewWidget
from settings_window import SettingsWindow
from event_editor_window import EventEditorWindow
from search_dialog import SearchDialog
from notification_manager import NotificationPopup
from timezone_helper import get_timezone_from_ip

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
        self.current_date = datetime.date.today()
        self.is_resizing = False
        self.is_moving = False
        self.border_width = 5
        self.active_dialog = None # [추가] 현재 활성화된 다이얼로그를 추적

        self._interaction_unlocked = False
        self.lock_key_is_pressed = False
        self.keyboard_listener = None
        self.start_keyboard_listener()
        
        self.initUI()
        
        # DataManager의 sync_timer가 DataManager의 새로운 메서드를 호출하도록 연결
        self.data_manager.sync_timer.timeout.connect(self.data_manager.request_current_month_sync)
        self.data_manager.notification_triggered.connect(self.show_notification_popup)

        if sys.platform == "win32":
            self.set_as_desktop_child()
        
        self.apply_window_settings()
        self.sync_startup_setting()

    def show_notification_popup(self, title, message):
        # 여러 알림이 동시에 뜰 경우를 대비하여 리스트로 관리
        if not hasattr(self, 'notification_popups'):
            self.notification_popups = []

        # 이전 팝업이 있다면 새 팝업을 그 위에 쌓이도록 위치 조정
        offset = len(self.notification_popups) * 10
        
        duration = self.settings.get("notification_duration", DEFAULT_NOTIFICATION_DURATION)
        popup = NotificationPopup(title, message, duration_seconds=duration)
        
        # 화면 오른쪽 하단 기준으로 위치 조정
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        popup_x = screen_geometry.width() - popup.width() - 15
        popup_y = screen_geometry.height() - popup.height() - 15 - offset
        popup.move(popup_x, popup_y)
        
        popup.show()
        
        # 팝업이 닫힐 때 리스트에서 제거되도록 연결
        popup.destroyed.connect(lambda: self.notification_popups.remove(popup))
        self.notification_popups.append(popup)

    def sync_startup_setting(self):
        """설정 파일과 레지스트리의 자동 시작 상태를 동기화합니다."""
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
            # 사용자에게 오류를 알릴 수 있는 방법을 고려 (예: 상태 표시줄, 대화상자)
            print(f"자동 시작 설정 동기화 중 오류 발생: {e}")

    def set_as_desktop_child(self):
        try:
            progman = win32gui.FindWindow("Progman", None)
            win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
            worker_w = 0
            def find_worker_w(hwnd, param):
                if win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
                    nonlocal worker_w
                    worker_w = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
                return True
            win32gui.EnumWindows(find_worker_w, None)
            hwnd = self.winId()
            win32gui.SetParent(hwnd, worker_w)
        except Exception as e:
            print(f"바탕화면 자식창 설정 실패: {e}")

             # ▼▼▼ [추가] 누락된 is_interaction_unlocked 메서드 ▼▼▼
    def is_interaction_unlocked(self):
        """현재 상호작용이 잠금 해제되었는지 여부를 반환합니다."""
        if not self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            return True # 잠금 모드가 비활성화 상태면 항상 상호작용 가능
        return self._interaction_unlocked
    # ▲▲▲ 여기까지 추가 ▲▲▲

    def _is_lock_key(self, key):
        lock_key_str = self.settings.get("lock_mode_key", DEFAULT_LOCK_MODE_KEY).lower()
        if lock_key_str == 'ctrl':
            return key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]
        if lock_key_str == 'alt':
            return key in [keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr]
        if lock_key_str == 'shift':
            return key in [keyboard.Key.shift_l, keyboard.Key.shift_r]
        if hasattr(key, 'char') and key.char:
            return key.char.lower() == lock_key_str
        return False

    def on_key_press(self, key):
        if self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            if self._is_lock_key(key) and not self._interaction_unlocked:
                self._interaction_unlocked = True
                self.lock_key_is_pressed = True
                QTimer.singleShot(0, self.unlock_interactions)

    def on_key_release(self, key):
        if self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            if self._is_lock_key(key):
                self.lock_key_is_pressed = False
                self._interaction_unlocked = False
                if QApplication.instance().mouseButtons() == Qt.MouseButton.NoButton:
                    self.lock_interactions()

    def start_keyboard_listener(self):
        if self.keyboard_listener is None:
            self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
            self.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

    # ▼▼▼ [핵심 수정] setWindowFlags 대신 SetWindowLong API 사용 ▼▼▼
    def lock_interactions(self):
        """[Windows 전용] 클릭 통과 기능을 활성화합니다."""
        if sys.platform != "win32": return
        try:
            hwnd = self.winId()
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            # WS_EX_TRANSPARENT 스타일 추가
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_TRANSPARENT)
        except Exception as e:
            print(f"Lock interactions error: {e}")

    def unlock_interactions(self):
        """[Windows 전용] 클릭 통과 기능을 비활성화합니다."""
        if sys.platform != "win32": return
        try:
            hwnd = self.winId()
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            # WS_EX_TRANSPARENT 스타일 제거
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style & ~win32con.WS_EX_TRANSPARENT)
            self.activateWindow()
        except Exception as e:
            print(f"Unlock interactions error: {e}")
    # ▲▲▲ 여기까지 수정 ▲▲▲

    def apply_window_settings(self):
        # 1. 창 위치 설정 적용
        mode = self.settings.get("window_mode", DEFAULT_WINDOW_MODE)
        flags = self.windowFlags()

        # 기존 위치 관련 플래그 초기화
        flags &= ~Qt.WindowType.WindowStaysOnTopHint
        flags &= ~Qt.WindowType.WindowStaysOnBottomHint

        if mode == "AlwaysOnTop":
            flags |= Qt.WindowType.WindowStaysOnTopHint
        elif mode == "AlwaysOnBottom":
            flags |= Qt.WindowType.WindowStaysOnBottomHint
        
        self.setWindowFlags(flags)
        self.show() # setWindowFlags 호출 후 창이 숨겨질 수 있으므로 다시 표시

        # "항상 아래에" 모드일 때 Z-order를 맨 아래로 강제
        if mode == "AlwaysOnBottom" and sys.platform == "win32":
            self._push_to_desktop_bottom()

        # 2. 잠금 모드 설정 적용
        if self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED):
            self.lock_interactions()
        else:
            self.unlock_interactions()
        self.update_lock_icon()

    def toggle_lock_mode(self):
        """잠금 모드를 토글하고 설정을 저장한 뒤 UI를 업데이트합니다."""
        is_enabled = self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED)
        self.settings["lock_mode_enabled"] = not is_enabled
        save_settings(self.settings)
        self.apply_window_settings()

    def update_lock_icon(self):
        """현재 잠금 설정에 따라 아이콘을 업데이트합니다."""
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
        
        # 화면 크기에 비례하여 최소 크기 설정
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        min_width = int(screen_geometry.width() * 0.20)
        min_height = int(screen_geometry.height() * 0.25)
        self.setMinimumSize(min_width, min_height)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        self.background_widget.setObjectName("main_background")
        self.background_widget.setMouseTracking(True)
        
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
        self.data_manager.error_occurred.connect(self.show_error_message)
        
        view_mode_layout = QHBoxLayout()
        month_button, week_button = QPushButton("월력"), QPushButton("주간")
        month_button.setCheckable(True)
        week_button.setCheckable(True)
        
        today_button = QPushButton("오늘")
        today_button.setObjectName("today_button")
        today_button.clicked.connect(self.go_to_today)

        search_button = QPushButton()
        search_button.setIcon(QIcon("icons/search.svg"))
        search_button.setIconSize(QSize(20, 20))
        search_button.setObjectName("search_button")
        search_button.setFixedSize(30, 28)
        search_button.setStyleSheet("padding-bottom: 2px;")
        search_button.clicked.connect(self.open_search_dialog)

        self.lock_button = QPushButton()
        self.lock_button.setIconSize(QSize(20, 20))
        self.lock_button.setObjectName("lock_button")
        self.lock_button.setFixedSize(30, 28)
        self.lock_button.setStyleSheet("padding-bottom: 2px;")
        self.lock_button.clicked.connect(self.toggle_lock_mode)

        view_mode_layout = QHBoxLayout()
        view_mode_layout.setSpacing(5) # 버튼 간 최소 간격

        # 1. 왼쪽 절반 컨테이너
        left_half = QHBoxLayout()
        left_half.addWidget(search_button)
        left_half.addStretch(1)
        left_half.addWidget(month_button)
        
        # 2. 오른쪽 절반 컨테이너
        right_half = QHBoxLayout()
        right_half.addWidget(week_button)
        right_half.addStretch(1)
        right_half.addWidget(self.lock_button)
        right_half.addWidget(today_button)

        # 두 개의 절반 컨테이너를 메인 레이아웃에 추가
        view_mode_layout.addLayout(left_half, 1) # 1의 비율로 공간 차지
        view_mode_layout.addLayout(right_half, 1) # 1의 비율로 공간 차지
        
        content_layout.addLayout(view_mode_layout)

        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        self.month_view = MonthViewWidget(self)
        self.week_view = WeekViewWidget(self)
        
        self.month_view.add_event_requested.connect(self.open_event_editor)
        self.month_view.edit_event_requested.connect(self.open_event_editor)
        self.month_view.navigation_requested.connect(self.handle_month_navigation)
        self.month_view.date_selected.connect(self.set_current_date)

        self.week_view.add_event_requested.connect(self.open_event_editor)
        self.week_view.edit_event_requested.connect(self.open_event_editor)
        self.week_view.navigation_requested.connect(self.handle_week_navigation)
        self.week_view.date_selected.connect(self.set_current_date)

        self.stacked_widget.addWidget(self.month_view)
        self.stacked_widget.addWidget(self.week_view)
        
        month_button.clicked.connect(lambda: self.change_view(0, month_button, [week_button]))
        week_button.clicked.connect(lambda: self.change_view(1, week_button, [month_button]))
        
        month_button.setChecked(True)
        self.oldPos = None
        
        self.set_current_date(self.current_date, is_initial=True)
        self.setup_tray_icon()

    def setup_tray_icon(self):
        """시스템 트레이 아이콘을 설정합니다."""
        self.tray_icon = QSystemTrayIcon(QIcon("icons/tray_icon.svg"), self)
        self.tray_icon.setToolTip("Glassy Calendar")

        tray_menu = QMenu()
        show_action = QAction("열기", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

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
        """트레이 아이콘 클릭 시 창을 보여줍니다."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger: # 왼쪽 클릭
            self.show_window()

    def show_window(self):
        """창을 보여주고 활성화합니다."""
        self.show()
        self.activateWindow()

    def _get_dialog_pos(self):
        """현재 위젯이 속한 화면의 중앙 위치를 반환합니다."""
        screen = QApplication.screenAt(self.pos())
        if not screen:
            screen = QApplication.primaryScreen()
        
        screen_center = screen.availableGeometry().center()
        # 대화상자 크기를 대략적으로 추정하여 중앙 정렬 (필요 시 조절)
        # 여기서는 대화상자 크기를 모르므로, 일단 화면 중앙을 기준으로 합니다.
        # 더 정확하게 하려면 대화상자 크기를 알아야 합니다.
        # 예: pos.setX(pos.x() - dialog.width() / 2)
        return screen_center

    def _push_to_desktop_bottom(self):
        """[Windows 전용] 창을 Z-order의 가장 아래로 보냅니다."""
        if sys.platform != "win32": return
        try:
            hwnd = self.winId()
            # Z-order를 가장 아래로 설정합니다.
            win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        except Exception as e:
            print(f"Push to desktop bottom error: {e}")

    def quit_application(self):
        """애플리케이션을 완전히 종료합니다."""
        self.settings["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        save_settings(self.settings)
        self.data_manager.stop_caching_thread()
        self.stop_keyboard_listener()
        self.tray_icon.hide()
        QApplication.instance().quit()

    def set_current_date(self, new_date, is_initial=False):
        direction = "none"
        if not is_initial:
            if new_date > self.current_date: direction = "forward"
            elif new_date < self.current_date: direction = "backward"

        self.current_date = new_date
        self.month_view.current_date = new_date
        self.week_view.current_date = new_date
        
        self.data_manager.notify_date_changed(self.current_date, direction=direction)
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

    def set_window_opacity(self, opacity):
        self.setWindowOpacity(opacity)

    def go_to_today(self):
        self.set_current_date(datetime.date.today())

    def start(self):
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
            self.active_dialog.activateWindow() # 이미 열려있으면 해당 창을 활성화
            return
        with self.data_manager.user_action_priority():
            original_settings_snapshot = copy.deepcopy(self.settings)

            settings_dialog = SettingsWindow(self.data_manager, self.settings, self, pos=self._get_dialog_pos())
            self.active_dialog = settings_dialog
            settings_dialog.transparency_changed.connect(self.set_window_opacity)
            settings_dialog.theme_changed.connect(self.apply_theme)
            
            result = settings_dialog.exec()
            self.active_dialog = None # 다이얼로그가 닫히면 초기화
            
            if result == QDialog.DialogCode.Accepted:
                changed_fields = settings_dialog.get_changed_fields()
                
                if "window_opacity" in changed_fields:
                    self.set_window_opacity(self.settings.get("window_opacity", 0.95))
                if "theme" in changed_fields:
                    self.apply_theme(self.settings.get("theme", "dark"))
                if "sync_interval_minutes" in changed_fields:
                    self.data_manager.update_sync_timer()
                
                if any(field in changed_fields for field in ["window_mode", "lock_mode_enabled", "lock_mode_key"]):
                    self.apply_window_settings()
                
                if "start_on_boot" in changed_fields:
                    self.sync_startup_setting()

                grid_structure_changes = {"start_day_of_week", "hide_weekends"}
                if any(field in changed_fields for field in grid_structure_changes):
                    self.refresh_current_view()
                    return 

                if "calendar_colors" in changed_fields:
                    self.handle_visual_preview()

                if "selected_calendars" in changed_fields:
                    if "calendar_colors" not in changed_fields:
                        self.handle_visual_preview()

            else:
                self.settings.clear()
                self.settings.update(original_settings_snapshot)
                self.set_window_opacity(self.settings.get("window_opacity", 0.95))
                self.apply_theme(self.settings.get("theme", "dark"))
                self.apply_window_settings()
                self.refresh_current_view()

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
            
            # 열려있는 모든 최상위 창의 스타일을 강제로 다시 적용
            for widget in app.topLevelWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()

            # 월간/주간 뷰 강제 새로고침
            self.month_view.refresh()
            self.week_view.refresh()
            
        except FileNotFoundError:
            print(f"경고: '{theme_name}_theme.qss' 파일을 찾을 수 없습니다.")

    def open_event_editor(self, data):
                # ▼▼▼ [수정] 다른 다이얼로그가 열려있는지 확인합니다. ▼▼▼
        if self.active_dialog is not None:
            self.active_dialog.activateWindow()
            return
        # ▲▲▲ 여기까지 수정 ▲▲▲
        with self.data_manager.user_action_priority():
            # all_calendars를 미리 가져오지 않습니다.
            editor = None
            cursor_pos = self._get_dialog_pos()
            if isinstance(data, (datetime.date, datetime.datetime)):
                # calendars 인자 제거
                editor = EventEditorWindow(mode='new', data=data, settings=self.settings, parent=self, pos=cursor_pos, data_manager=self.data_manager)
            elif isinstance(data, dict):
                # calendars 인자 제거
                editor = EventEditorWindow(mode='edit', data=data, settings=self.settings, parent=self, pos=cursor_pos, data_manager=self.data_manager)
            
            if editor:
                 # ▼▼▼ [추가] 활성화된 다이얼로그로 등록하고, 닫힐 때 초기화합니다. ▼▼▼
                self.active_dialog = editor
                result = editor.exec()
                self.active_dialog = None # 다이얼로그가 닫히면 초기화
                # ▲▲▲ 여기까지 추가 ▲▲▲
                if result == QDialog.DialogCode.Accepted:
                    event_data = editor.get_event_data()
                    # 캘린더 목록이 로딩되지 않았을 경우를 대비한 방어 코드
                    if not event_data.get('calendarId'):
                        self.show_error_message("캘린더 목록이 아직 로딩되지 않았습니다. 잠시 후 다시 시도해주세요.")
                        return
                    
                    is_recurring = 'recurrence' in event_data.get('body', {})
                    if editor.mode == 'new': 
                        self.data_manager.add_event(event_data)
                    else: 
                        self.data_manager.update_event(event_data)
                    self.settings['last_selected_calendar_id'] = event_data.get('calendarId')
                    if is_recurring:
                        QTimer.singleShot(500, self.data_manager.request_full_sync)
                elif result == EventEditorWindow.DeleteRole:
                    event_to_delete = editor.get_event_data()
                    self.data_manager.delete_event(event_to_delete)

    def show_error_message(self, message):
        """사용자에게 오류 메시지 대화상자를 표시합니다."""
        if not self.is_interaction_unlocked():
            # 잠금 모드일 경우 상호작용이 불가능하므로, 트레이 아이콘 메시지로 대체
            self.tray_icon.showMessage(
                "오류 발생",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )
        else:
            # 일반 모드에서는 메시지 박스 사용
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Warning)
            error_dialog.setText("오류가 발생했습니다.")
            error_dialog.setInformativeText(message)
            error_dialog.setWindowTitle("오류")
            error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            error_dialog.exec()

    def add_common_context_menu_actions(self, menu):
        if menu.actions(): menu.addSeparator()
        refreshAction = QAction("새로고침 (Refresh)", self)
        # 현재 보고 있는 월만 강제 동기화하도록 변경
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
        """창을 닫을 때 트레이로 최소화합니다."""
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

            if self.is_resizing:
                self.end_resize()

            self.is_moving = False
            self.is_resizing = False
            self.oldPos = None
            self.unsetCursor()

        if self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED) and not self.lock_key_is_pressed:
            QTimer.singleShot(50, self.lock_interactions)

    def snap_to_screen_edges(self):
        """창을 모든 화면 가장자리에 스냅합니다."""
        snap_threshold = 45
        win_rect = self.frameGeometry()
        screens = QApplication.screens()
        
        closest_screen = None
        min_dist = float('inf')

        # 창의 중심과 가장 가까운 화면을 찾습니다.
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

        # 가로 스냅
        if abs(win_rect.left() - screen_geometry.left()) < snap_threshold:
            new_pos.setX(screen_geometry.left())
            moved = True
        elif abs(win_rect.right() - screen_geometry.right()) < snap_threshold:
            new_pos.setX(screen_geometry.right() - win_rect.width())
            moved = True

        # 세로 스냅
        if abs(win_rect.top() - screen_geometry.top()) < snap_threshold:
            new_pos.setY(screen_geometry.top())
            moved = True
        elif abs(win_rect.bottom() - screen_geometry.bottom()) < snap_threshold:
            new_pos.setY(screen_geometry.bottom() - win_rect.height())
            moved = True

        if moved:
            self.move(new_pos)

if __name__ == '__main__':
    settings = load_settings()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # --- Auto Timezone Detection ---
    if "user_timezone" not in settings:
        user_timezone = get_timezone_from_ip()
        settings["user_timezone"] = user_timezone
        save_settings(settings)
    # --------------------------------

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