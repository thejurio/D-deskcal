# update_manager.py
import requests
import os
import sys
import subprocess
import tempfile
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer
from PyQt6.QtWidgets import QProgressDialog, QMessageBox

# GitHub 저장소 정보
GITHUB_REPO = "thejurio/D-deskcal" 

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
            headers = {
                'User-Agent': 'D-DeskCal/1.1.7 (Windows Desktop Calendar Application)',
                'Accept': 'application/vnd.github.v3+json',
                'Cache-Control': 'max-age=3600'  # 1시간 캐시
            }
            # SSL 인증서 검증 및 타임아웃 설정
            response = requests.get(
                api_url, 
                timeout=10, 
                headers=headers, 
                verify=True,  # SSL 인증서 검증
                allow_redirects=True
            )
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
        try:
            new_parts = list(map(int, new_version.split('.')))
            current_parts = list(map(int, current_version.split('.')))
            
            # 버전 자릿수를 맞추기 위해 0으로 채움
            max_len = max(len(new_parts), len(current_parts))
            new_parts.extend([0] * (max_len - len(new_parts)))
            current_parts.extend([0] * (max_len - len(current_parts)))

            return new_parts > current_parts
        except (ValueError, AttributeError):
            return False


class UpdateDownloader(QObject):
    """
    업데이트 파일을 다운로드하고 설치를 관리합니다.
    """
    download_progress = pyqtSignal(int)  # progress percentage
    download_complete = pyqtSignal(str)  # downloaded_file_path
    download_error = pyqtSignal(str)
    installation_complete = pyqtSignal()
    installation_error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.download_url = None
        self.temp_dir = None
        self.installer_filename = None
        
    def download_update(self, release_data):
        """GitHub 릴리스에서 업데이트 파일을 다운로드합니다."""
        try:
            # 설치 파일 찾기 (.exe 인스톨러 파일)
            assets = release_data.get('assets', [])
            installer_asset = None
            
            # portable.zip 파일 우선 찾기 (GitHub Actions 빌드 결과물)
            for asset in assets:
                if asset['name'].endswith('-portable.zip'):
                    installer_asset = asset
                    break
            
            # portable이 없으면 installer.zip 파일 찾기 (하위 호환성)
            if not installer_asset:
                for asset in assets:
                    if asset['name'].endswith('-installer.zip'):
                        installer_asset = asset
                        break
            
            # 그래도 없으면 .exe 파일 찾기
            if not installer_asset:
                for asset in assets:
                    if asset['name'].endswith('-installer.exe'):
                        installer_asset = asset
                        break
            
            if not installer_asset:
                self.download_error.emit("설치 파일(.exe 또는 .zip)을 찾을 수 없습니다.")
                return
            
            self.download_url = installer_asset['browser_download_url']
            self.installer_filename = installer_asset['name']  # 실제 파일명 저장
            
            # 임시 디렉토리 생성
            self.temp_dir = tempfile.mkdtemp(prefix='D-deskcal-update-')
            
            # 파일 다운로드
            self._download_file()
            
        except Exception as e:
            self.download_error.emit(f"다운로드 준비 중 오류 발생: {e}")
    
    def _download_file(self):
        """실제 파일 다운로드를 수행합니다."""
        try:
            response = requests.get(self.download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # 실제 파일명 사용 (예: D-deskcal-v1.1.7-installer.exe)
            file_path = Path(self.temp_dir) / self.installer_filename
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.download_progress.emit(progress)
            
            self.download_complete.emit(str(file_path))
            
        except Exception as e:
            self.download_error.emit(f"다운로드 중 오류 발생: {e}")
    
    def install_update(self, downloaded_file):
        """다운로드된 업데이트를 설치합니다."""
        try:
            downloaded_path = Path(downloaded_file)
            
            # .exe 인스톨러인지 .zip 파일인지 확인
            if downloaded_path.suffix.lower() == '.exe':
                # .exe 인스톨러 실행
                self._run_installer(downloaded_file)
            else:
                # 기존 ZIP 파일 처리 (하위 호환성)
                self._install_from_zip(downloaded_file)
            
            self.installation_complete.emit()
            
        except Exception as e:
            self.installation_error.emit(f"설치 중 오류 발생: {e}")
    
    def _run_installer(self, installer_path):
        """인스톨러(.exe) 파일을 실행합니다."""
        try:
            print(f"인스톨러 실행: {installer_path}")
            
            from PyQt6.QtWidgets import QMessageBox
            from PyQt6.QtCore import QTimer
            
            # 사용자에게 알림 후 인스톨러 실행
            msg = QMessageBox()
            msg.setWindowTitle("업데이트 설치")
            msg.setText("업데이트가 다운로드되었습니다.\n\n인스톨러가 실행됩니다. 설치를 진행해주세요.\n설치 완료 후 D-DeskCal이 자동으로 시작됩니다.")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # 일반 모드로 인스톨러 실행 (사용자가 직접 조작)
            subprocess.Popen([str(installer_path)])
            
            # 잠시 후 현재 앱 종료
            QTimer.singleShot(2000, sys.exit)
            
        except Exception as e:
            raise Exception(f"인스톨러 실행 실패: {e}")
    
    def _install_from_zip(self, zip_file):
        """ZIP 파일에서 업데이트를 설치합니다. (하위 호환성)"""
        try:
            # 기존 ZIP 압축 해제 로직
            extract_dir = Path(self.temp_dir) / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 현재 실행 파일의 경로
            if getattr(sys, 'frozen', False):
                current_exe_dir = Path(sys.executable).parent
            else:
                current_exe_dir = Path.cwd()
            
            print(f"추출 디렉토리: {extract_dir}")
            print(f"현재 실행 디렉토리: {current_exe_dir}")
            
            # 추출된 파일 내용 확인
            print("추출된 파일 목록:")
            for item in extract_dir.rglob("*"):
                if item.is_file():
                    print(f"  {item.relative_to(extract_dir)}")
            
            # 업데이트 스크립트 생성 및 실행
            self._create_update_script(extract_dir, current_exe_dir)
            
        except Exception as e:
            raise Exception(f"ZIP 파일 설치 실패: {e}")
    
    def _create_update_script(self, source_dir, target_dir):
        """업데이트 설치를 위한 배치 스크립트를 생성합니다."""
        script_path = Path(self.temp_dir) / "update.bat"
        
        # 현재 실행 파일명 결정
        if getattr(sys, 'frozen', False):
            current_exe = Path(sys.executable).name
        else:
            current_exe = "D-deskcal.exe"
        
        script_content = f'''@echo off
echo D-deskcal 업데이트 설치 중...
echo 로그 파일: {target_dir}\\update_log.txt
echo.

REM 로그 파일 생성
echo 업데이트 시작: %date% %time% > "{target_dir}\\update_log.txt"
echo 소스 디렉토리: {source_dir} >> "{target_dir}\\update_log.txt"
echo 타겟 디렉토리: {target_dir} >> "{target_dir}\\update_log.txt"

echo 프로그램 종료를 기다리는 중...
timeout /t 5 /nobreak >nul

echo 현재 실행 파일 정보: >> "{target_dir}\\update_log.txt"
dir "{target_dir}\\{current_exe}" >> "{target_dir}\\update_log.txt" 2>&1

echo 기존 파일 백업 중...
if exist "{target_dir}\\backup" rmdir /s /q "{target_dir}\\backup" 2>nul
mkdir "{target_dir}\\backup" 2>nul
if exist "{target_dir}\\{current_exe}" (
    copy "{target_dir}\\{current_exe}" "{target_dir}\\backup\\" /y >nul 2>&1
    echo 기존 실행 파일 백업 완료 >> "{target_dir}\\update_log.txt"
)

echo 새 파일 설치 중...
echo 소스 디렉토리 내용: >> "{target_dir}\\update_log.txt"
dir "{source_dir}" /s >> "{target_dir}\\update_log.txt"
echo.

REM 추출된 파일 구조에서 실행 파일 찾기
if exist "{source_dir}\\D-deskcal.exe" (
    echo 직접 경로에서 실행 파일 발견
    echo 직접 경로에서 실행 파일 발견 >> "{target_dir}\\update_log.txt"
    copy "{source_dir}\\D-deskcal.exe" "{target_dir}\\" /y
    if %errorlevel% equ 0 (
        echo 실행 파일 복사 성공 >> "{target_dir}\\update_log.txt"
    ) else (
        echo 실행 파일 복사 실패: %errorlevel% >> "{target_dir}\\update_log.txt"
    )
    if exist "{source_dir}\\_internal" xcopy "{source_dir}\\_internal" "{target_dir}\\_internal\\" /e /y /q
) else if exist "{source_dir}\\D-deskcal\\D-deskcal.exe" (
    echo D-deskcal 폴더에서 실행 파일 발견
    echo D-deskcal 폴더에서 실행 파일 발견 >> "{target_dir}\\update_log.txt"
    copy "{source_dir}\\D-deskcal\\D-deskcal.exe" "{target_dir}\\" /y
    if %errorlevel% equ 0 (
        echo 실행 파일 복사 성공 >> "{target_dir}\\update_log.txt"
    ) else (
        echo 실행 파일 복사 실패: %errorlevel% >> "{target_dir}\\update_log.txt"
    )
    if exist "{source_dir}\\D-deskcal\\_internal" xcopy "{source_dir}\\D-deskcal\\_internal" "{target_dir}\\_internal\\" /e /y /q
) else (
    echo 실행 파일을 찾을 수 없습니다!
    echo 실행 파일을 찾을 수 없음 >> "{target_dir}\\update_log.txt"
    echo 사용 가능한 파일: >> "{target_dir}\\update_log.txt"
    dir "{source_dir}" /s /b >> "{target_dir}\\update_log.txt"
    pause
    goto :end
)

echo 업데이트 후 파일 정보: >> "{target_dir}\\update_log.txt"
dir "{target_dir}\\{current_exe}" >> "{target_dir}\\update_log.txt" 2>&1

echo 업데이트 완료!
echo D-deskcal을 다시 시작합니다...
timeout /t 2 /nobreak >nul

start "" "{target_dir}\\{current_exe}"

echo 임시 파일 정리 중...
timeout /t 3 /nobreak >nul
rmdir /s /q "{self.temp_dir}" 2>nul

echo 업데이트 완료: %date% %time% >> "{target_dir}\\update_log.txt"

:end
exit
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # 스크립트 실행
        subprocess.Popen([str(script_path)], shell=True)
    
    def cleanup(self):
        """임시 파일들을 정리합니다."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)


class AutoUpdateManager(QObject):
    """
    통합된 자동 업데이트 관리자
    """
    update_available = pyqtSignal(dict)  # release_data
    update_checking = pyqtSignal()
    no_update_available = pyqtSignal()
    update_error = pyqtSignal(str)
    
    def __init__(self, current_version, parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.checker = UpdateManager(current_version)
        self.downloader = UpdateDownloader()
        
        # 시그널 연결
        self.checker.update_available.connect(self._on_update_available)
        self.checker.up_to_date.connect(self.no_update_available.emit)
        self.checker.error_occurred.connect(self.update_error.emit)
    
    def check_for_updates(self, silent=False):
        """업데이트 확인을 시작합니다."""
        if not silent:
            self.update_checking.emit()
        
        # GitHub API에서 릴리스 정보 가져오기
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            latest_version = release_data.get("tag_name", "").lstrip('v')
            
            if self.checker._is_newer(latest_version, self.current_version):
                self.update_available.emit(release_data)
            else:
                self.no_update_available.emit()
                
        except Exception as e:
            self.update_error.emit(f"업데이트 확인 실패: {e}")
    
    def _on_update_available(self, version, download_url):
        """업데이트가 있을 때 호출됩니다."""
        # 이 메서드는 새로운 구조에서 사용되지 않습니다.
        pass
    
    def download_and_install_update(self, release_data):
        """업데이트를 다운로드하고 설치합니다."""
        print(f"업데이트 다운로드 시작: {release_data.get('tag_name', 'Unknown')}")
        
        # 다운로드 완료 시 자동 설치 연결 (중복 연결 방지)
        try:
            self.downloader.download_complete.disconnect()
        except TypeError:
            pass  # 연결이 없으면 무시
            
        self.downloader.download_complete.connect(
            self.downloader.install_update
        )
        
        # 다운로드 시작
        self.downloader.download_update(release_data)

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
