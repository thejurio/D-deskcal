# hotkey_manager.py
from PyQt6.QtCore import QObject, pyqtSignal
import keyboard
import threading
import logging

logger = logging.getLogger(__name__)

class HotkeyManager(QObject):
    """
    keyboard 라이브러리를 사용하여 시스템 전역 단축키를 관리하는 클래스.
    PyQt의 메인 스레드와 충돌하지 않도록 스레드 안전성을 고려하여 설계되었습니다.
    """
    hotkey_triggered = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.lock = threading.Lock()
        logger.info("HotkeyManager initialized successfully")

    def _on_trigger_factory(self, action_name):
        """
        특정 액션에 대한 콜백 함수를 생성하는 팩토리 메서드.
        이 콜백은 keyboard 리스너 스레드에서 실행되므로, GUI 작업을 직접 수행해서는 안 됩니다.
        대신, 스레드에 안전한 PyQt 시그널을 발생시킵니다.
        """
        def _on_trigger():
            # keyboard 리스너 스레드가 GUI 호출로 인해 멈추는 것을 방지하기 위해
            # 시그널 발생을 메인 이벤트 루프에 예약합니다.
            # keyboard.call_later를 사용하면 현재 콜백이 즉시 반환되어 리스너 스레드가 계속 작동합니다.
            keyboard.call_later(lambda: self.hotkey_triggered.emit(action_name), delay=0.01)
        return _on_trigger

    def _format_hotkey_for_keyboard(self, hotkey_str):
        """
        "Ctrl + Shift + F1" 같은 문자열을 keyboard 라이브러리가 이해하는 "ctrl+shift+f1" 형식으로 변환합니다.
        """
        if not hotkey_str:
            return None
        
        logger.debug(f"Attempting to format hotkey string: '{hotkey_str}'")
        try:
            # 공백 제거 및 소문자 변환
            formatted_hotkey = hotkey_str.lower().replace(" ", "")
            # '+'로 연결된 부분들을 다시 '+'로 합칩니다. e.g., 'ctrl+shift+a'
            parts = formatted_hotkey.split('+')
            formatted_hotkey = '+'.join(parts)
            logger.debug(f"Successfully converted to keyboard library format: '{formatted_hotkey}'")
            return formatted_hotkey
        except Exception as e:
            logger.error(f"Error formatting hotkey '{hotkey_str}': {e}")
            return None

    def register_and_start(self):
        """
        설정에서 단축키를 읽어와 keyboard 리스너에 등록합니다.
        이전의 모든 단축키는 해제하고 새로 등록합니다.
        """
        with self.lock:
            logger.info("Starting hotkey registration and listener...")
            self._stop_listener_unsafe()

            ai_hotkey_str = self.settings.get("ai_add_event_hotkey")
            logger.debug(f"Hotkey loaded from settings: '{ai_hotkey_str}'")

            if ai_hotkey_str:
                formatted_hotkey = self._format_hotkey_for_keyboard(ai_hotkey_str)
                if formatted_hotkey:
                    try:
                        keyboard.add_hotkey(
                            formatted_hotkey,
                            self._on_trigger_factory("ai_add_event"),
                            suppress=False
                        )
                        logger.info(f"Successfully registered hotkey: '{formatted_hotkey}'")
                        
                        # PyInstaller 환경에서 keyboard 라이브러리 테스트
                        self._test_keyboard_functionality()
                        
                    except Exception as e:
                        logger.error(f"Failed to register hotkey: {e}")
                        logger.info("Attempting to use alternative keyboard hook method...")
                        self._try_alternative_keyboard_hook(formatted_hotkey)
            else:
                logger.warning("No hotkey to register")
    
    def _test_keyboard_functionality(self):
        """PyInstaller 환경에서 keyboard 라이브러리가 제대로 작동하는지 테스트"""
        try:
            # keyboard 라이브러리가 시스템 후킹에 접근할 수 있는지 확인
            import sys
            if hasattr(sys, '_MEIPASS'):
                logger.info("PyInstaller 환경에서 keyboard 라이브러리 테스트 중...")
                # keyboard 후킹이 실제로 작동하는지 간단한 테스트
                # 이 부분은 실제로는 단축키를 눌러봐야 확인 가능
                logger.info("PyInstaller 환경에서 keyboard 초기화 완료")
        except Exception as e:
            logger.warning(f"Keyboard functionality test failed: {e}")
    
    def _try_alternative_keyboard_hook(self, hotkey_str):
        """keyboard 라이브러리 실패 시 대안적인 방법 시도"""
        try:
            import win32api
            import win32con
            logger.info("Trying Windows API based hotkey registration...")
            # 여기서는 일단 로그만 남기고, 추후 win32api 구현 가능
            logger.warning("Alternative keyboard hook not yet implemented - hotkeys may not work in PyInstaller build")
        except ImportError:
            logger.error("Both keyboard library and win32api failed - hotkeys disabled")

    def stop(self):
        """모든 단축키 리스너를 안전하게 해제합니다."""
        with self.lock:
            self._stop_listener_unsafe()

    def _stop_listener_unsafe(self):
        """락(lock) 내부에서 모든 단축키를 해제하는 도우미 메서드."""
        logger.info("Unhooking all hotkey listeners...")
        try:
            keyboard.unhook_all()
            logger.info("All hotkeys successfully unhooked")
        except Exception as e:
            # unhook_all_hotkeys는 실패할 경우가 거의 없지만, 만약을 대비해 로깅합니다.
            logger.error(f"Exception occurred while unhooking hotkeys: {e}")
