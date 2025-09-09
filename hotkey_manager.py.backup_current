# Safe Hotkey Manager - PyQt6 QShortcut based implementation
# 2025-09-08 - Safe alternative to keyboard library for crash prevention

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import QApplication
import logging

logger = logging.getLogger(__name__)

class HotkeyManager(QObject):
    """
    PyQt6 QShortcut을 사용한 안전한 단축키 관리자
    cross-thread signal emission 문제를 피하기 위해 QShortcut 사용
    """
    hotkey_triggered = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.shortcuts = {}  # 단축키 저장
        logger.info("HotkeyManager initialized successfully (SAFE VERSION)")

    def _format_hotkey_for_qshortcut(self, hotkey_str):
        """
        "Ctrl + Shift + F1" 형태를 QKeySequence가 이해하는 형태로 변환
        """
        if not hotkey_str:
            return None
        
        logger.debug(f"Formatting hotkey string for QShortcut: '{hotkey_str}'")
        try:
            # QKeySequence는 "Ctrl+Shift+F1" 형태를 이해함
            formatted = hotkey_str.replace(" ", "")
            # 키 이름 정규화
            formatted = formatted.replace("ctrl", "Ctrl")
            formatted = formatted.replace("shift", "Shift")
            formatted = formatted.replace("alt", "Alt")
            
            logger.debug(f"Formatted hotkey: '{formatted}'")
            return formatted
        except Exception as e:
            logger.error(f"Error formatting hotkey '{hotkey_str}': {e}")
            return None

    def register_hotkey(self, action_name, hotkey_str):
        """
        단축키를 등록합니다 (QShortcut 사용)
        """
        if not hotkey_str:
            logger.warning(f"Empty hotkey string provided for action: {action_name}")
            return False

        try:
            formatted_hotkey = self._format_hotkey_for_qshortcut(hotkey_str)
            if not formatted_hotkey:
                logger.error(f"Failed to format hotkey for action '{action_name}': {hotkey_str}")
                return False

            # 기존 단축키가 있으면 제거
            if action_name in self.shortcuts:
                self.shortcuts[action_name].setEnabled(False)
                del self.shortcuts[action_name]

            # QApplication 인스턴스가 있는지 확인
            app = QApplication.instance()
            if not app:
                logger.error("No QApplication instance found, cannot register shortcuts")
                return False

            # QShortcut 생성 (앱 전역에서 작동)
            shortcut = QShortcut(QKeySequence(formatted_hotkey), app.activeWindow() or app)
            
            # 안전한 시그널 연결 (이미 메인 스레드에서 실행됨)
            shortcut.activated.connect(lambda: self.hotkey_triggered.emit(action_name))
            
            # 전역 컨텍스트로 설정 (가능하면)
            shortcut.setContext(shortcut.ApplicationShortcut if hasattr(shortcut, 'ApplicationShortcut') else shortcut.WidgetShortcut)
            
            self.shortcuts[action_name] = shortcut
            logger.info(f"Successfully registered safe hotkey: {action_name} = {hotkey_str}")
            return True

        except Exception as e:
            logger.error(f"Failed to register hotkey for '{action_name}' with key '{hotkey_str}': {e}")
            return False

    def start_listener(self):
        """
        QShortcut 기반에서는 별도의 리스너 시작이 불필요
        """
        logger.info("Hotkey listener started (QShortcut-based, no separate thread needed)")

    def stop_listener(self):
        """
        모든 단축키 비활성화
        """
        logger.info("Stopping hotkey listener...")
        try:
            for action_name, shortcut in self.shortcuts.items():
                shortcut.setEnabled(False)
                logger.debug(f"Disabled shortcut for action: {action_name}")
            logger.info("All hotkeys successfully disabled")
        except Exception as e:
            logger.error(f"Error stopping hotkey listener: {e}")

    def cleanup(self):
        """
        정리 작업
        """
        logger.info("Cleaning up hotkey manager...")
        try:
            for action_name, shortcut in self.shortcuts.items():
                shortcut.setEnabled(False)
                shortcut.deleteLater()
            self.shortcuts.clear()
            logger.info("Hotkey manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during hotkey cleanup: {e}")

    def register_and_start(self):
        """
        설정에서 단축키를 읽어와 등록하고 시작
        """
        logger.info("Starting hotkey registration and listener...")
        
        try:
            # 설정에서 단축키 정보 읽기
            hotkey_settings = self.settings.get('hotkeys', {})
            if not hotkey_settings:
                logger.warning("No hotkey settings found in configuration")
                return True

            success_count = 0
            for action_name, hotkey_str in hotkey_settings.items():
                if self.register_hotkey(action_name, hotkey_str):
                    success_count += 1

            self.start_listener()
            
            logger.info(f"Hotkey registration completed: {success_count}/{len(hotkey_settings)} shortcuts registered successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to register and start hotkeys: {e}")
            return False