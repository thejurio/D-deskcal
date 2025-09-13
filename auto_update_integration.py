"""
Auto-update integration module for D-deskcal
Provides easy integration with the main UI application
"""

import os
import sys
import logging
from pathlib import Path
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QApplication, QDialog

logger = logging.getLogger(__name__)

try:
    from update_manager import AutoUpdateManager
except ImportError:
    logger.warning("Update manager module not found - auto-update disabled")
    AutoUpdateManager = None

try:
    from custom_update_dialogs import (
        UpdateAvailableDialog, 
        UpdateProgressDialog, 
        UpdateCompleteDialog, 
        UpdateErrorDialog,
        NoUpdateDialog
    )
    from update_dialog_texts import get_update_text
    CUSTOM_DIALOGS_AVAILABLE = True
except ImportError:
    logger.warning("Custom update dialogs not found - using default dialogs")
    CUSTOM_DIALOGS_AVAILABLE = False


class AutoUpdateDialog(QObject):
    """
    사용자 친화적인 자동 업데이트 다이얼로그
    """
    
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.update_manager = None
        self.progress_dialog = None
        self.is_silent_check = False  # silent 모드 플래그 추가
        
        # Get current version
        self.current_version = self._get_current_version()
        
        # Get settings from parent if available
        self.settings = getattr(parent, 'settings', None) if parent else None
        
        if AutoUpdateManager:
            self.update_manager = AutoUpdateManager(self.current_version)
            self._connect_signals()
    
    def _get_current_version(self):
        """현재 버전을 VERSION 파일에서 읽어옵니다."""
        try:
            from resource_path import get_version
            return get_version()
        except Exception:
            return "1.0.0"
    
    def _connect_signals(self):
        """업데이트 매니저 시그널을 연결합니다."""
        if not self.update_manager:
            return
            
        self.update_manager.update_available.connect(self._on_update_available)
        self.update_manager.no_update_available.connect(self._on_no_update)
        self.update_manager.update_error.connect(self._on_update_error)
        self.update_manager.update_checking.connect(self._on_checking_updates)
        
        # 다운로더 시그널
        if hasattr(self.update_manager, 'downloader'):
            downloader = self.update_manager.downloader
            logger.debug("Connecting downloader signals...")
            downloader.download_progress.connect(self._on_download_progress)
            downloader.download_complete.connect(self._on_download_complete)
            downloader.installation_complete.connect(self._on_installation_complete)
            downloader.download_error.connect(self._on_download_error)
            downloader.installation_error.connect(self._on_installation_error)
            logger.debug("Downloader signals connected successfully")
    
    def check_for_updates(self, silent=False):
        """업데이트 확인을 시작합니다."""
        # silent 모드 플래그 저장
        self.is_silent_check = silent
        
        if not self.update_manager:
            if not silent:
                if CUSTOM_DIALOGS_AVAILABLE:
                    dialog = UpdateErrorDialog(
                        get_update_text("auto_update_unavailable"),
                        parent=self.parent,
                        settings=self.settings
                    )
                    dialog.exec()
                else:
                    QMessageBox.information(
                        self.parent,
                        "업데이트 확인",
                        "자동 업데이트 기능을 사용할 수 없습니다.\n수동으로 업데이트를 확인해주세요."
                    )
            return
        
        self.update_manager.check_for_updates(silent)
    
    def _on_checking_updates(self):
        """업데이트 확인 중일 때"""
        pass  # UI에서 필요시 상태 표시
    
    def _on_update_available(self, release_data):
        """업데이트가 있을 때"""
        version = release_data.get('tag_name', '').lstrip('v')
        release_notes = release_data.get('body', '업데이트 정보를 불러올 수 없습니다.')
        
        if CUSTOM_DIALOGS_AVAILABLE:
            dialog = UpdateAvailableDialog(
                release_data, 
                self.current_version,
                parent=self.parent,
                settings=self.settings
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._start_update_download(release_data)
        else:
            # 릴리스 노트를 간략하게 정리
            if len(release_notes) > 300:
                release_notes = release_notes[:300] + "..."
            
            msg = QMessageBox(self.parent)
            msg.setWindowTitle("업데이트 사용 가능")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(f"새로운 버전 v{version}이 사용 가능합니다.")
            msg.setDetailedText(f"현재 버전: {self.current_version}\n새 버전: {version}\n\n릴리스 노트:\n{release_notes}")
            msg.setInformativeText("지금 업데이트하시겠습니까?")
            
            update_button = msg.addButton("업데이트", QMessageBox.ButtonRole.AcceptRole)
            later_button = msg.addButton("나중에", QMessageBox.ButtonRole.RejectRole)
            
            msg.exec()
            
            if msg.clickedButton() == update_button:
                self._start_update_download(release_data)
    
    def _on_no_update(self):
        """업데이트가 없을 때"""
        # silent 모드가 아닐 때만 메시지 표시 (수동 확인 시에만)
        if not self.is_silent_check:
            if CUSTOM_DIALOGS_AVAILABLE:
                dialog = NoUpdateDialog(
                    self.current_version,
                    parent=self.parent,
                    settings=self.settings
                )
                dialog.exec()
            else:
                QMessageBox.information(
                    self.parent,
                    "업데이트 확인",
                    f"현재 최신 버전({self.current_version})을 사용 중입니다."
                )
    
    def _on_update_error(self, error_message):
        """업데이트 확인 실패시"""
        if CUSTOM_DIALOGS_AVAILABLE:
            dialog = UpdateErrorDialog(
                get_update_text("error_message", error=error_message),
                parent=self.parent,
                settings=self.settings
            )
            dialog.exec()
        else:
            QMessageBox.warning(
                self.parent,
                "업데이트 확인 실패",
                f"업데이트를 확인할 수 없습니다:\n{error_message}\n\n"
                "인터넷 연결을 확인하고 다시 시도해주세요."
            )
    
    def _start_update_download(self, release_data):
        """업데이트 다운로드 시작"""
        logger.info(f"Starting update download: {release_data.get('tag_name', 'Unknown')}")
        
        # 테마가 적용된 커스텀 프로그레스 다이얼로그 사용
        self.progress_dialog = UpdateProgressDialog(self.parent)
        self.progress_dialog.show()
        
        # 다운로드 시작 (별도 스레드에서 실행하여 UI 블록 방지)
        logger.info("Starting download and installation process...")
        
        # QTimer를 사용하여 메인 스레드 블록 방지
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, lambda: self.update_manager.download_and_install_update(release_data))
    
    def _on_download_progress(self, progress):
        """다운로드 진행률 업데이트 (0-100%)"""
        logger.debug(f"Download progress: {progress}%")
        if self.progress_dialog and hasattr(self.progress_dialog, 'set_progress'):
            # 다운로드 단계: 0-100 범위 사용
            self.progress_dialog.set_progress(progress)
        else:
            logger.info(f"다운로드 진행률: {progress}%")
    
    def _on_download_complete(self, file_path):
        """다운로드 완료, 설치 시작"""
        logger.info(f"Download completed: {file_path}")
        if self.progress_dialog:
            # 설치 단계로 전환
            if hasattr(self.progress_dialog, 'show_installation_phase'):
                self.progress_dialog.show_installation_phase()
                logger.info("Progress dialog updated to show installation phase")
        else:
            logger.warning("Progress dialog is None in _on_download_complete")
    
    
    def _on_installation_complete(self):
        """설치 완료"""
        logger.info("Installation completed - closing progress dialog")
        if self.progress_dialog:
            # 설치 완료 메시지를 잠시 보여준 후 닫기
            if hasattr(self.progress_dialog, 'set_progress'):
                self.progress_dialog.set_progress(100)  # 완료 표시
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, self.progress_dialog.close)  # 1.5초 후 닫기
        else:
            logger.warning("Progress dialog is None in _on_installation_complete")
        
        user_confirmed = False
        
        if CUSTOM_DIALOGS_AVAILABLE:
            dialog = UpdateCompleteDialog(
                parent=self.parent,
                settings=self.settings
            )
            result = dialog.exec()
            user_confirmed = (result == QDialog.DialogCode.Accepted)
        else:
            msg = QMessageBox(self.parent)
            msg.setWindowTitle("업데이트 완료")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText("업데이트가 완료되었습니다.")
            msg.setInformativeText("업데이트 스크립트가 실행되었습니다.\n프로그램이 자동으로 종료되고 새 버전으로 재시작됩니다.")
            ok_button = msg.addButton("확인", QMessageBox.ButtonRole.AcceptRole)
            msg.exec()
            user_confirmed = (msg.clickedButton() == ok_button)
        
        # 사용자가 확인한 경우에만 프로그램 종료
        if user_confirmed:
            logger.info("User confirmed update completion - shutting down program...")
            
            # 프로그램 종료 (업데이트 스크립트가 재시작함)
            import sys
            sys.exit(0)
        else:
            logger.info("User cancelled update completion dialog")
    
    def _on_download_error(self, error_message):
        """다운로드 실패"""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        if CUSTOM_DIALOGS_AVAILABLE:
            dialog = UpdateErrorDialog(
                get_update_text("download_error_message", error=error_message),
                parent=self.parent,
                settings=self.settings
            )
            dialog.exec()
        else:
            QMessageBox.critical(
                self.parent,
                "업데이트 실패",
                f"업데이트 다운로드에 실패했습니다:\n{error_message}"
            )
    
    def _on_installation_error(self, error_message):
        """설치 실패"""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        if CUSTOM_DIALOGS_AVAILABLE:
            dialog = UpdateErrorDialog(
                get_update_text("install_error_message", error=error_message),
                parent=self.parent,
                settings=self.settings
            )
            dialog.exec()
        else:
            QMessageBox.critical(
                self.parent,
                "설치 실패",
                f"업데이트 설치에 실패했습니다:\n{error_message}"
            )


class AutoUpdateChecker:
    """
    주기적 자동 업데이트 확인을 위한 클래스
    """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.update_dialog = AutoUpdateDialog(main_window)
        self.timer = QTimer()
        self.timer.timeout.connect(self._periodic_check)
        
        # 24시간마다 자동 체크 (86400000 ms)
        self.check_interval = 24 * 60 * 60 * 1000
    
    def start_periodic_check(self):
        """주기적 업데이트 확인 시작"""
        # 시작 5초 후 첫 번째 체크 (자동이므로 silent=True)
        QTimer.singleShot(5000, lambda: self.update_dialog.check_for_updates(silent=True))
        
        # 그 후 24시간마다 체크
        self.timer.start(self.check_interval)
    
    def stop_periodic_check(self):
        """주기적 업데이트 확인 중지"""
        self.timer.stop()
    
    def _periodic_check(self):
        """주기적 업데이트 확인 (무음)"""
        self.update_dialog.check_for_updates(silent=True)
    
    def manual_check(self):
        """수동 업데이트 확인"""
        self.update_dialog.check_for_updates(silent=False)


def integrate_auto_update(main_window):
    """
    메인 윈도우에 자동 업데이트 기능을 통합합니다.
    
    사용법:
        from auto_update_integration import integrate_auto_update
        
        class MainWindow(QMainWindow):
            def __init__(self):
                super().__init__()
                # ... 기존 초기화 코드 ...
                
                # 자동 업데이트 통합
                self.auto_updater = integrate_auto_update(self)
        
        # 메뉴에 수동 업데이트 확인 추가하려면:
        # self.auto_updater.manual_check()
    """
    
    updater = AutoUpdateChecker(main_window)
    updater.start_periodic_check()
    return updater


# 사용 예시를 위한 함수
def add_update_menu_action(menu, auto_updater):
    """
    메뉴에 '업데이트 확인' 항목을 추가합니다.
    
    사용법:
        # 메인 윈도우에서
        help_menu = self.menuBar().addMenu("도움말")
        add_update_menu_action(help_menu, self.auto_updater)
    """
    from PyQt6.QtGui import QAction
    
    update_action = QAction("업데이트 확인", menu.parent())
    update_action.triggered.connect(auto_updater.manual_check)
    menu.addAction(update_action)
    
    return update_action