# update_manager.py
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# GitHub 저장소 정보 (실제 주소로 변경 필요)
GITHUB_REPO = "DC-Widget/DC-Widget" 

class UpdateManager(QObject):
    """
    백그라운드에서 업데이트를 확인하고 결과를 시그널로 알립니다.
    """
    update_available = pyqtSignal(str, str)  # new_version, download_url
    error_occurred = pyqtSignal(str)
    up_to_date = pyqtSignal()

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def check_for_updates(self):
        """GitHub API를 통해 최신 릴리스 정보를 가져와 버전을 비교합니다."""
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            latest_release = response.json()
            latest_version = latest_release.get("tag_name", "").lstrip('v')
            download_url = latest_release.get("html_url")

            if not latest_version or not download_url:
                self.error_occurred.emit("릴리스 정보를 가져오는 데 실패했습니다.")
                return

            # 버전 비교 (간단한 문자열 비교, 추후 더 정교한 비교 로직으로 개선 가능)
            if self._is_newer(latest_version, self.current_version):
                self.update_available.emit(latest_version, download_url)
            else:
                self.up_to_date.emit()

        except requests.RequestException as e:
            self.error_occurred.emit(f"업데이트 확인 중 네트워크 오류가 발생했습니다: {e}")
        except Exception as e:
            self.error_occurred.emit(f"업데이트 확인 중 알 수 없는 오류가 발생했습니다: {e}")

    def _is_newer(self, new_version, current_version):
        """버전 문자열을 비교하여 새로운 버전인지 확인합니다. (예: '1.2.0' > '1.1.10')"""
        new_parts = list(map(int, new_version.split('.')))
        current_parts = list(map(int, current_version.split('.')))
        
        # 버전 자릿수를 맞추기 위해 0으로 채움
        max_len = max(len(new_parts), len(current_parts))
        new_parts.extend([0] * (max_len - len(new_parts)))
        current_parts.extend([0] * (max_len - len(current_parts)))

        return new_parts > current_parts

def run_update_check(current_version, update_callback, error_callback, no_update_callback):
    """
    백그라운드 스레드에서 업데이트 검사를 실행하고 콜백을 통해 결과를 전달합니다.
    """
    thread = QThread()
    worker = UpdateManager(current_version)
    
    worker.moveToThread(thread)
    
    worker.update_available.connect(update_callback)
    worker.error_occurred.connect(error_callback)
    worker.up_to_date.connect(no_update_callback)
    
    thread.started.connect(worker.check_for_updates)
    thread.finished.connect(thread.deleteLater)
    
    # 작업 완료 후 스레드가 스스로 종료되도록 연결
    worker.update_available.connect(thread.quit)
    worker.error_occurred.connect(thread.quit)
    worker.up_to_date.connect(thread.quit)
    
    thread.start()
    
    # 스레드가 메모리에서 해제되지 않도록 참조를 유지
    return thread
