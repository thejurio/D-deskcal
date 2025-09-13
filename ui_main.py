import sys
import os
import datetime
import copy
import logging
import time
import psutil
import socket

# Crash detection system
from crash_detector import crash_detector

# 로깅 설정 초기화
from logger_config import setup_logger
setup_logger()
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    import win32gui
    import win32con
    import windows_startup

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QHBoxLayout, QMenu, QPushButton, QStackedWidget, QSizeGrip, QDialog, QSystemTrayIcon, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QEvent
from PyQt6.QtGui import QAction, QIcon

import keyboard
from hotkey_manager import HotkeyManager
from auth_manager import AuthManager
from settings_manager import load_settings, save_settings, save_settings_safe
from config import (
                    DEFAULT_WINDOW_GEOMETRY,
                    DEFAULT_LOCK_MODE_ENABLED,
                    DEFAULT_LOCK_MODE_KEY,
                    DEFAULT_WINDOW_MODE,
                    DEFAULT_NOTIFICATION_DURATION,
                    ERROR_LOG_FILE
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
from custom_dialogs import AIEventInputDialog, CustomMessageBox, APIKeyRequiredDialog
from ai_confirmation_dialog import AIConfirmationDialog
import gemini_parser
from resource_path import resource_path, get_theme_path, get_icon_path, load_theme_with_icons
from simple_event_detail_dialog import SimpleEventDetailDialog

# Auto-update integration
try:
    from auto_update_integration import integrate_auto_update
    AUTO_UPDATE_AVAILABLE = True
except ImportError:
    print("Warning: Auto-update module not found. Auto-update disabled.")
    AUTO_UPDATE_AVAILABLE = False


class SingleInstanceApp:
    """Single instance application manager using socket lock."""
    def __init__(self, app_name="DCWidget"):
        self.app_name = app_name
        self.lock_socket = None
        
    def is_already_running(self):
        """Check if another instance is already running."""
        try:
            self.lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Use a less common port to avoid conflicts
            self.lock_socket.bind(('127.0.0.1', 23741))
            return False
        except socket.error:
            return True
            
    def cleanup(self):
        """Clean up the socket lock."""
        if self.lock_socket:
            try:
                self.lock_socket.close()
            except:
                pass


def load_stylesheet(file_path):
    """Load stylesheet with proper resource path handling and icon path preprocessing"""
    try:
        # If file_path is just a filename, treat it as a theme file and process icons
        if not os.path.dirname(file_path):
            return load_theme_with_icons(file_path)
        else:
            # For other paths, load normally
            resolved_path = resource_path(file_path)
            with open(resolved_path, "r", encoding="utf-8") as f:
                return f.read()
    except FileNotFoundError:
        print(f"Warning: Stylesheet not found: {file_path}")
        return ""

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

        # Auto-update integration - initialize before initUI to avoid AttributeError
        self.auto_updater = None
        if AUTO_UPDATE_AVAILABLE and self.settings.get("auto_update_enabled", True):
            try:
                self.auto_updater = integrate_auto_update(self)
                print("Auto-update system initialized successfully")
            except Exception as e:
                print(f"Failed to initialize auto-update system: {e}")

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

        # 설정창에서 설정한 잠금해제 키 사용 (unlock_key), 없으면 기본값 사용
        lock_key = self.settings.get("unlock_key", "").strip()
        if not lock_key:
            lock_key = self.settings.get("lock_mode_key", DEFAULT_LOCK_MODE_KEY)
        lock_key = lock_key.lower()
        is_pressed = keyboard.is_pressed(lock_key)

        if is_pressed and not self.lock_key_is_pressed:
            self.lock_key_is_pressed = True
            self.unlock_interactions()
        elif not is_pressed and self.lock_key_is_pressed:
            self.lock_key_is_pressed = False
            if QApplication.instance().mouseButtons() == Qt.MouseButton.NoButton:
                self.lock_interactions()

    def reload_hotkeys(self):
        """설정 변경 후 핫키를 다시 로드합니다"""
        try:
            logger.info("설정 변경으로 인한 핫키 매니저 새로고침 중...")
            self.hotkey_manager.stop()
            self.hotkey_manager = HotkeyManager(self.settings)
            self.hotkey_manager.hotkey_triggered.connect(self.handle_hotkey)
            self.hotkey_manager.register_and_start()
            logger.info("핫키 매니저 새로고침 완료")
        except Exception as e:
            logger.error(f"핫키 매니저 새로고침 실패: {e}")

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

        duration = self.settings.get("notification_duration", DEFAULT_NOTIFICATION_DURATION)
        popup = NotificationPopup(title, message, duration_seconds=duration, settings=self.settings)

        # 팝업이 표시된 후 크기 계산을 위해 show() 먼저 호출
        popup.show()
        
        # 기존 팝업들의 총 높이 계산하여 세로로 쌓기
        total_height_offset = 0
        for existing_popup in self.notification_popups:
            if existing_popup.isVisible():
                total_height_offset += existing_popup.height() + 10  # 10px 간격

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        popup_x = screen_geometry.width() - popup.width() - 15
        popup_y = screen_geometry.height() - popup.height() - 15 - total_height_offset
        popup.move(popup_x, popup_y)

        # 팝업이 닫힐 때 목록에서 제거
        def on_popup_destroyed():
            if popup in self.notification_popups:
                self.notification_popups.remove(popup)
                # 남은 팝업들의 위치 재조정
                self.reposition_notification_popups()
        
        popup.destroyed.connect(on_popup_destroyed)
        self.notification_popups.append(popup)

    def reposition_notification_popups(self):
        """남은 알림 팝업들의 위치를 재조정"""
        if not hasattr(self, 'notification_popups'):
            return
            
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        current_offset = 0
        
        # 아래에서 위로 순서대로 위치 재조정
        for popup in reversed(self.notification_popups):
            if popup.isVisible():
                popup_x = screen_geometry.width() - popup.width() - 15
                popup_y = screen_geometry.height() - popup.height() - 15 - current_offset
                popup.move(popup_x, popup_y)
                current_offset += popup.height() + 10  # 10px 간격

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

    def handle_auto_update_setting_changed(self):
        """자동 업데이트 설정 변경 처리"""
        if not AUTO_UPDATE_AVAILABLE:
            return

        auto_update_enabled = self.settings.get("auto_update_enabled", True)
        
        try:
            if auto_update_enabled and not self.auto_updater:
                # 자동 업데이트 활성화
                self.auto_updater = integrate_auto_update(self)
                print("Auto-update enabled")
            elif not auto_update_enabled and self.auto_updater:
                # 자동 업데이트 비활성화
                self.auto_updater.stop_periodic_check()
                self.auto_updater = None
                print("Auto-update disabled")
            # 트레이 메뉴 다시 설정 (업데이트 메뉴 표시/숨김)
            self.setup_tray_icon()
        except Exception as e:
            print(f"Auto-update setting change error: {e}")

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
        save_settings_safe(self.settings)
        self.apply_window_settings()

    def update_lock_icon(self):
        is_enabled = self.settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED)
        if is_enabled:
            self.lock_button.setIcon(QIcon(get_icon_path("lock_locked.svg")))
            self.lock_button.setToolTip("잠금 모드 활성화됨 (클릭하여 비활성화)")
        else:
            self.lock_button.setIcon(QIcon(get_icon_path("lock_unlocked.svg")))
            self.lock_button.setToolTip("잠금 모드 비활성화됨 (클릭하여 활성화)")

    def initUI(self):
        self.setWindowTitle('D-DeskCal')
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
        search_button.setIcon(QIcon(get_icon_path("search.svg")))
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
        ai_add_button.setIcon(QIcon(get_icon_path("gemini.svg")))
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
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        
        # 상세보기 시그널 연결
        self.month_view.detail_requested.connect(self.show_event_detail)
        self.week_view.detail_requested.connect(self.show_event_detail)
        self.agenda_view.detail_requested.connect(self.show_event_detail)
        
        # 편집 요청 시그널 연결 (더블클릭)
        self.month_view.edit_requested.connect(self.open_event_editor)
        self.week_view.edit_requested.connect(self.open_event_editor)
        self.agenda_view.edit_requested.connect(self.open_event_editor)
        
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
        self.tray_icon = QSystemTrayIcon(QIcon(get_icon_path("tray_icon.svg")), self)
        self.tray_icon.setToolTip("D-DeskCal")

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

        # Auto-update menu item
        if AUTO_UPDATE_AVAILABLE and hasattr(self, 'auto_updater') and self.auto_updater:
            update_action = QAction("업데이트 확인", self)
            update_action.triggered.connect(self.auto_updater.manual_check)
            tray_menu.addAction(update_action)

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
        """🛑 애플리케이션 완전 종료"""
        print("🛑 [UI] DCWidget 종료 시작...")
        
        try:
            # 1. 설정 저장
            self.settings["geometry"] = [self.x(), self.y(), self.width(), self.height()]
            save_settings_safe(self.settings)
            print("💾 설정 저장 완료")
            
            # 2. 데이터 매니저 완전 종료 (모든 스레드 정리)
            if hasattr(self, 'data_manager'):
                self.data_manager.stop_caching_thread()
                print("🔄 데이터 매니저 종료 완료")
            
            # 3. 핫키 매니저 중지
            if hasattr(self, 'hotkey_manager'):
                self.hotkey_manager.stop()
                print("⌨️ 핫키 매니저 중지 완료")
            
            # 4. 트레이 아이콘 숨기기
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
                print("🔔 트레이 아이콘 숨김 완료")
            
            # 5. 소켓 정리 (중복 실행 방지용)
            try:
                import __main__
                if hasattr(__main__, 'single_instance'):
                    __main__.single_instance.cleanup()
                    print("🔒 소켓 락 정리 완료")
            except Exception as e:
                print(f"⚠️ 소켓 정리 중 오류: {e}")
            
            # 6. Qt 애플리케이션 종료
            app = QApplication.instance()
            if app:
                app.quit()
                print("✅ Qt 애플리케이션 종료 완료")
            
            print("🎉 [UI] DCWidget 종료 프로세스 완료!")
            
        except Exception as e:
            print(f"❌ [UI] 종료 중 오류: {e}")
            # 강제 종료
            QApplication.instance().quit()

    def set_current_date(self, new_date, is_initial=False):
        self.current_date = new_date
        self.month_view.current_date = new_date
        self.week_view.current_date = new_date

        # data_manager에 현재 보고 있는 월 업데이트 및 캐시 윈도우 변화 확인
        if hasattr(self, 'data_manager') and self.data_manager:
            self.data_manager.current_view_month = (new_date.year, new_date.month)
            if not is_initial:  # 초기 설정이 아닐 때만 캐시 정리 확인
                self.data_manager._schedule_cache_cleanup(new_date.year, new_date.month)

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

    def apply_background_opacity(self, opacity=None, theme_name=None):
        if opacity is None:
            opacity = self.settings.get("window_opacity", 0.95)

        if theme_name is None:
            theme_name = self.settings.get("theme", "dark")
        
        # 메인 위젯은 완전히 불투명하게 설정 (콘텐츠가 투명해지지 않도록)
        self.setWindowOpacity(1.0)
        
        # 배경 위젯에만 RGBA 투명도 적용 (배경만 투명)
        if theme_name == "dark":
            base_color = "30, 30, 30"
        else: # light theme
            base_color = "250, 250, 250"

        style = f"""
            QWidget#main_background {{
                background-color: rgba({base_color}, {opacity});
                border: 1px solid rgba(100, 100, 100, 0.8);
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
        # with self.data_manager.user_action_priority():  # DISABLED - mutex fixes removed _activity_lock
        if True:
            original_settings_snapshot = copy.deepcopy(self.settings)

            settings_dialog = SettingsWindow(self.data_manager, self.settings, None, pos=self._get_dialog_pos())
            self.active_dialog = settings_dialog

            settings_dialog.transparency_changed.connect(self.on_opacity_preview_changed)
            settings_dialog.theme_changed.connect(self.on_theme_preview_changed)
            settings_dialog.start_day_changed.connect(self.on_start_day_preview_changed)
            settings_dialog.hide_weekends_changed.connect(self.on_hide_weekends_preview_changed)
            settings_dialog.refresh_requested.connect(lambda: [
                self.data_manager.force_sync_month(self.current_date.year, self.current_date.month),
                self.reload_hotkeys()
            ])

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

                # 핫키 변경사항은 reload_hotkeys()에서 일괄 처리됨

                if "auto_update_enabled" in changed_fields:
                    self.handle_auto_update_setting_changed()

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
            logger.debug("AI input dialog blocked due to interaction lock")
            return
        
        # API 키 체크 - 다이얼로그 열기 전에 확인
        gemini_api_key = self.settings.get("gemini_api_key", "").strip()
        if not gemini_api_key:
            self.show_api_key_error_with_redirect("Gemini API 키가 설정되지 않았습니다.\n\nAPI 키를 발급받아 [설정 > 계정] 탭에서 등록해주세요.")
            return

        logger.info("Starting AI event input dialog")
        input_dialog = AIEventInputDialog(None, self.settings, pos=self._get_dialog_pos())
        if not input_dialog.exec():
            logger.info("AI input dialog cancelled by user")
            return

        text_to_analyze = input_dialog.get_text()
        if not text_to_analyze:
            logger.warning("AI input dialog: No text provided for analysis")
            self.show_error_message("분석할 텍스트가 입력되지 않았습니다.")
            return

        api_key = self.settings.get("gemini_api_key")
        if not api_key:
            logger.error("AI event creation failed: Gemini API key not configured")
            self.show_api_key_error_with_redirect("Gemini API 키가 설정되지 않았습니다.\n\nAPI 키를 발급받아 [설정 > 계정] 탭에서 등록해주세요.")
            return

        logger.info(f"Starting AI event parsing with text length: {len(text_to_analyze)} characters")
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            parsed_events = gemini_parser.parse_events_with_gemini(api_key, text_to_analyze)
            QApplication.restoreOverrideCursor()

            if not parsed_events:
                logger.warning("AI parsing completed but no valid events were found")
                self.show_error_message("텍스트에서 유효한 일정 정보를 찾지 못했습니다.")
                return
            
            logger.info(f"AI parsing successful: {len(parsed_events)} events parsed")

            confirmation_dialog = AIConfirmationDialog(parsed_events, self.data_manager, None, self.settings, pos=self._get_dialog_pos())
            if confirmation_dialog.exec():
                final_events, calendar_id, provider_name = confirmation_dialog.get_final_events_and_calendar()
                logger.info(f"AI confirmation dialog completed: {len(final_events)} events confirmed, target calendar: {calendar_id}")

                if not calendar_id:
                    logger.error("AI event creation failed: No calendar selected")
                    self.show_error_message("일정을 추가할 캘린더를 선택해주세요.")
                    return

                logger.info(f"Starting creation of {len(final_events)} AI-generated events")
                for i, event in enumerate(final_events):
                    logger.debug(f"Processing AI event {i+1}/{len(final_events)}: {event.get('title', 'Unnamed')}")
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
                    QApplication.processEvents()  # UI 반응성 유지
                    self.data_manager.add_event(event_to_add)
                    QApplication.processEvents()  # UI 반응성 유지

                logger.info(f"AI event creation completed successfully: {len(final_events)} events added to calendar {calendar_id}")
                self.settings['last_selected_calendar_id'] = calendar_id
                save_settings_safe(self.settings) # AI 추가 후에도 캘린더 ID 저장
                self.show_error_message(f"{len(final_events)}개의 일정을 성공적으로 추가했습니다.", ok_only=True, title="알림")
            else:
                logger.info("AI confirmation dialog cancelled by user")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"AI event creation failed with exception: {e}", exc_info=True)
            
            # Check if error is related to API key issues
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['api_key_invalid', 'api키', 'api 키', 'permission', 'unauthorized', '401', '403']):
                self.show_api_key_error_with_redirect(f"API 키 관련 오류가 발생했습니다:\n{e}\n\nAPI 키를 다시 확인하거나 새로 발급받아주세요.")
            else:
                self.show_error_message(f"AI 분석 중 오류가 발생했습니다:\n{e}")

    def open_search_dialog(self):
        # with self.data_manager.user_action_priority():  # DISABLED - mutex fixes removed _activity_lock
        if True:
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

    def on_opacity_preview_changed(self, opacity):
        """설정창에서 투명도 미리보기 변경 처리"""
        # 현재 설정창에서 설정 중인 테마 값을 가져와서 적용
        if hasattr(self.active_dialog, 'temp_settings'):
            current_theme = self.active_dialog.temp_settings.get("theme", "dark")
            self.apply_background_opacity(opacity=opacity, theme_name=current_theme)
        else:
            self.apply_background_opacity(opacity=opacity)

    def on_theme_preview_changed(self, theme_name):
        """설정창에서 테마 미리보기 변경 처리"""
        # 현재 설정창에서 설정 중인 투명도 값을 가져와서 적용
        if hasattr(self.active_dialog, 'temp_settings'):
            current_opacity = self.active_dialog.temp_settings.get("window_opacity", 0.95)
            self.apply_background_opacity(opacity=current_opacity, theme_name=theme_name)
        
        # 전체 테마 적용
        self.apply_theme(theme_name)

    def on_start_day_preview_changed(self, start_day):
        """설정창에서 시작요일 미리보기 변경 처리"""
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'apply_preview_settings'):
            # 뷰에 미리보기 설정 적용
            current_widget.apply_preview_settings({'start_day_of_week': start_day})
        else:
            # 임시 설정 변경 방식 (fallback)
            original_start_day = self.settings.get("start_day_of_week", 6)
            self.settings["start_day_of_week"] = start_day
            self.refresh_current_view()
            self.settings["start_day_of_week"] = original_start_day

    def on_hide_weekends_preview_changed(self, hide_weekends):
        """설정창에서 주말표시 미리보기 변경 처리"""
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'apply_preview_settings'):
            # 뷰에 미리보기 설정 적용
            current_widget.apply_preview_settings({'hide_weekends': hide_weekends})
        else:
            # 임시 설정 변경 방식 (fallback)
            original_hide_weekends = self.settings.get("hide_weekends", False)
            self.settings["hide_weekends"] = hide_weekends
            self.refresh_current_view()
            self.settings["hide_weekends"] = original_hide_weekends

    def apply_theme(self, theme_name):
        try:
            stylesheet = load_stylesheet(f'{theme_name}_theme.qss')
            app = QApplication.instance()
            app.setStyleSheet(stylesheet)

            # 설정창 미리보기가 아닌 경우에만 배경 투명도 적용
            # (미리보기는 on_theme_preview_changed에서 처리)
            if not hasattr(self, 'active_dialog') or self.active_dialog is None:
                self.apply_background_opacity(theme_name=theme_name)

            for widget in app.topLevelWidgets():
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()

            self.month_view.refresh()
            self.week_view.refresh()

        except FileNotFoundError:
            print(f"경고: '{theme_name}_theme.qss' 파일을 찾을 수 없습니다.")

    def open_event_editor(self, data):
        if isinstance(data, dict):
            logger.info(f"Event editor requested for editing event: {data.get('summary', 'Unnamed')}")
        elif isinstance(data, (datetime.date, datetime.datetime)):
            logger.info(f"Event editor requested for new event on date: {data}")
        else:
            logger.info(f"Event editor requested with data type: {type(data)}")
        
        if self.active_dialog is not None:
            logger.debug("Event editor blocked: another dialog is already active")
            self.active_dialog.activateWindow()
            return
            
        # 현재 활성화된 뷰의 팝오버 닫기
        current_view = self.stacked_widget.currentWidget()
        if hasattr(current_view, 'current_popover') and current_view.current_popover:
            if current_view.current_popover.isVisible():
                current_view.current_popover.close()
                current_view.current_popover = None
            
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
                    logger.error("Event save failed: No calendar ID available")
                    self.show_error_message("캘린더 목록이 아직 로딩되지 않았습니다. 잠시 후 다시 시도해주세요.")
                    return

                is_recurring = 'recurrence' in event_data.get('body', {})
                event_summary = event_data.get('body', {}).get('summary', 'Unnamed')
                
                if editor.mode == 'new':
                    logger.info(f"Creating new event: '{event_summary}' (recurring: {is_recurring})")
                    QApplication.processEvents()  # UI 반응성 유지
                    self.data_manager.add_event(event_data)
                    QApplication.processEvents()  # UI 반응성 유지
                    logger.info(f"New event creation completed: '{event_summary}'")
                else:
                    logger.info(f"Updating existing event: '{event_summary}' (recurring: {is_recurring})")
                    QApplication.processEvents()  # UI 반응성 유지
                    self.data_manager.update_event(event_data)
                    QApplication.processEvents()  # UI 반응성 유지
                    logger.info(f"Event update completed: '{event_summary}'")

                self.settings['last_selected_calendar_id'] = event_data.get('calendarId')
                save_settings_safe(self.settings)

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
                event_summary = event_to_delete.get('body', {}).get('summary', event_to_delete.get('summary', 'Unnamed'))
                
                logger.info(f"Deleting event: '{event_summary}' (mode: {deletion_mode})")
                QApplication.processEvents()  # UI 반응성 유지
                self.data_manager.delete_event(event_to_delete, deletion_mode=deletion_mode)
                QApplication.processEvents()  # UI 반응성 유지
                logger.info(f"Event deletion completed: '{event_summary}'")

    def show_event_detail(self, event_data):
        """이벤트 상세보기 다이얼로그를 표시합니다."""
        event_title = event_data.get('summary', 'Unknown Event')
        logger.debug(f"Event detail dialog requested for: {event_title}")
        
        if not self.is_interaction_unlocked():
            logger.debug("Event detail dialog blocked due to interaction lock")
            return
            
        try:
            logger.info(f"Opening event detail dialog for: {event_title}")
            
            dialog = SimpleEventDetailDialog(
                event_data=event_data,
                data_manager=self.data_manager,
                main_widget=self,
                parent=None  # Fix segfault by using None parent
            )
            
            # 다이얼로그 표시 (편집은 다이얼로그 내부에서 자체적으로 처리)
            dialog.exec()
                
        except Exception as e:
            logger.error(f"Event detail dialog error: {e}", exc_info=True)
            self.show_error_message(f"이벤트 상세정보를 표시하는 중 오류가 발생했습니다: {str(e)}")

    def show_api_key_error_with_redirect(self, message="AI 일정생성을 하기위해 API키가 필요합니다. API키 생성 사이트로 이동하시겠습니까?", title="API 키 필요"):
        """Show BaseDialog-based error dialog with button to redirect to Gemini API key website"""
        if not self.is_interaction_unlocked():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )
            return True
        
        # Create BaseDialog-based API key dialog
        dialog = APIKeyRequiredDialog(
            parent=None,
            settings=self.settings,
            pos=self._get_dialog_pos(),
            message=message
        )
        
        # Execute dialog and handle result
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            # User clicked "확인" - open API key site
            self.open_gemini_api_site()
    
    def open_gemini_api_site(self):
        """Open Gemini API key issuance website"""
        import webbrowser
        gemini_api_url = "https://aistudio.google.com/app/apikey"
        try:
            webbrowser.open(gemini_api_url)
            logger.info(f"Opened Gemini API key site: {gemini_api_url}")
        except Exception as e:
            logger.error(f"Failed to open Gemini API site: {e}")
            self.show_error_message("브라우저를 열 수 없습니다. 직접 https://aistudio.google.com/app/apikey 를 방문해주세요.")

    def show_error_message(self, message, ok_only=False, title="오류"):
        if not self.is_interaction_unlocked():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Warning if title == "오류" else QSystemTrayIcon.MessageIcon.Information,
                5000
            )
            return True  # 트레이 알림의 경우 항상 True 반환
        else:
            dialog = CustomMessageBox(
                parent=None,
                title=title,
                text=message,
                settings=self.settings,
                pos=self._get_dialog_pos(),
                ok_only=ok_only
            )
            result = dialog.exec()
            return result == QDialog.DialogCode.Accepted

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
            "D-DeskCal",
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
            self.oldPos = event.globalPosition().toPoint() if hasattr(event.globalPosition(), 'toPoint') else event.globalPosition()

    def mouseMoveEvent(self, event):
        if not self.is_interaction_unlocked():
            return
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint() if hasattr(event.globalPosition(), 'toPoint') else event.globalPosition()
            delta = current_pos - self.oldPos
            if self.is_moving:
                self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = current_pos

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
    # Install crash detection system
    crash_detector.install_handlers()
    
    # Single instance check
    single_instance = SingleInstanceApp()
    
    if single_instance.is_already_running():
        print("DCWidget is already running. Exiting...")
        crash_detector.shutdown()
        sys.exit(0)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=ERROR_LOG_FILE,
        filemode='a'
    )
    
    settings = load_settings()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if "user_timezone" not in settings:
        user_timezone = get_timezone_from_ip()
        settings["user_timezone"] = user_timezone
        save_settings_safe(settings)

    selected_theme = settings.get("theme", "dark")
    try:
        stylesheet = load_stylesheet(f'{selected_theme}_theme.qss')
        app.setStyleSheet(stylesheet)
    except FileNotFoundError:
        print(f"경고: '{selected_theme}_theme.qss' 파일을 찾을 수 없습니다.")

    widget = MainWidget(settings)
    widget.show()
    widget.start()
    
    # Setup heartbeat timer for crash detection
    from PyQt6.QtCore import QTimer
    heartbeat_timer = QTimer()
    heartbeat_timer.timeout.connect(crash_detector.heartbeat)
    heartbeat_timer.start(5000)  # Every 5 seconds
    
    # Cleanup single instance lock on exit
    import atexit
    atexit.register(single_instance.cleanup)
    atexit.register(crash_detector.shutdown)
    
    sys.exit(app.exec())