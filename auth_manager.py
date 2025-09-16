import os
import sys
import webbrowser
import subprocess
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# --- 설정 ---
from config import TOKEN_FILE, CREDENTIALS_FILE
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar'
]
# --- ---

def open_browser_fallback(url):
    """Windows에서 기본 브라우저 열기 - 다중 fallback 방식"""
    try:
        # 방법 1: os.startfile() - Windows 전용 최우선
        os.startfile(url)
        print("os.startfile()로 브라우저 열기 성공")
        return True
    except Exception as e1:
        print(f"os.startfile() 실패: {e1}")
        try:
            # 방법 2: cmd start 명령어
            subprocess.run(['cmd', '/c', 'start', '', url], check=False, shell=True)
            print("cmd start로 브라우저 열기 성공")
            return True
        except Exception as e2:
            print(f"cmd start 실패: {e2}")
            try:
                # 방법 3: webbrowser.open()
                webbrowser.open(url)
                print("webbrowser.open()으로 브라우저 열기 성공")
                return True
            except Exception as e3:
                print(f"webbrowser.open() 실패: {e3}")
                print(f"브라우저 열기 실패. 수동으로 브라우저에서 다음 주소를 열어주세요: {url}")
                return False

class LoginWorker(QObject):
    """백그라운드 스레드에서 동기적인 로그인 작업을 처리하는 작업자"""
    finished = pyqtSignal(object) # object는 Credentials 객체 또는 None

    def run(self):
        """로그인 절차를 실행하고 결과를 finished 신호로 보냅니다."""
        print("로그인 절차 시작...")
        print(f"credentials 파일 경로: {CREDENTIALS_FILE}")

        # Enhanced credential file search with detailed logging
        if os.path.exists(CREDENTIALS_FILE):
            print("✅ credentials.json 파일 발견됨")
            try:
                with open(CREDENTIALS_FILE, 'r') as f:
                    content = f.read()
                    print(f"📄 credentials.json 크기: {len(content)} bytes")
            except Exception as e:
                print(f"❌ credentials.json 읽기 실패: {e}")
        else:
            print("❌ credentials.json 파일을 찾을 수 없음!")

            # Enhanced debugging info
            print(f"🔍 현재 작업 디렉토리: {os.getcwd()}")

            # Check all possible locations
            print("🔍 가능한 위치들 확인:")

            if hasattr(sys, '_MEIPASS'):
                meipass_path = os.path.join(sys._MEIPASS, "credentials.json")
                print(f"  1. MEIPASS: {meipass_path} - {'✅' if os.path.exists(meipass_path) else '❌'}")

            env_path = os.environ.get('GOOGLE_CREDENTIALS_PATH')
            if env_path:
                print(f"  2. ENV VAR: {env_path} - {'✅' if os.path.exists(env_path) else '❌'}")
            else:
                print("  2. ENV VAR: GOOGLE_CREDENTIALS_PATH 설정되지 않음")

            from config import get_data_dir, get_app_dir
            user_path = os.path.join(get_data_dir(), "credentials.json")
            dev_path = os.path.join(get_app_dir(), "credentials.json")

            print(f"  3. USER DIR: {user_path} - {'✅' if os.path.exists(user_path) else '❌'}")
            print(f"  4. APP DIR: {dev_path} - {'✅' if os.path.exists(dev_path) else '❌'}")

            print("💡 해결방법:")
            print("  - 빌드된 실행파일: credentials.json이 번들에 포함되어야 함")
            print("  - 개발환경: 프로젝트 루트에 credentials.json 파일 필요")
            print("  - 사용자설치: GOOGLE_CREDENTIALS_PATH 환경변수 설정")

            self.finished.emit(None)
            return

        try:
            # PyInstaller 환경 감지
            is_pyinstaller = hasattr(sys, '_MEIPASS')
            if is_pyinstaller:
                print("PyInstaller 환경에서 로그인 시작...")
            else:
                print("개발 환경에서 로그인 시작...")
            
            print("OAuth flow 생성 완료, 로컬 서버 시작 중...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            
            # run_local_server를 사용하되 브라우저 열기만 커스터마이징
            if is_pyinstaller:
                print("PyInstaller 환경: 사용자 정의 브라우저 열기 사용")
                # run_local_server에서 원래 webbrowser.open을 대체
                original_webbrowser_open = webbrowser.open
                webbrowser.open = open_browser_fallback
                try:
                    creds = flow.run_local_server(port=0, open_browser=True)
                finally:
                    # webbrowser.open 복원
                    webbrowser.open = original_webbrowser_open
            else:
                # 개발 환경에서는 기본 브라우저 열기 사용
                print("개발 환경: 기본 브라우저 열기 사용")
                creds = flow.run_local_server(port=0, open_browser=True)
            
            print("로그인 성공!")
            self.finished.emit(creds)
        except Exception as e:
            print(f"로그인 절차 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()  # 상세한 오류 정보 출력
            self.finished.emit(None)


class AuthManager(QObject):
    auth_state_changed = pyqtSignal()
    login_started = pyqtSignal()
    login_finished = pyqtSignal(bool) # 성공 여부를 bool 값으로 전달

    def __init__(self):
        super().__init__()
        self._credentials = None
        self.login_thread = None
        self.login_worker = None
        self.load_credentials()

    def __del__(self):
        """AuthManager 객체 소멸 시, 실행 중인 스레드를 안전하게 종료합니다."""
        if self.login_thread and self.login_thread.isRunning():
            self.login_thread.quit()
            self.login_thread.wait()

    def load_credentials(self):
        if os.path.exists(TOKEN_FILE):
            try:
                self._credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception as e:
                print(f"인증 정보 로드 실패: {e}")
                self._credentials = None

    def get_credentials(self):
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                with open(TOKEN_FILE, "w") as token:
                    token.write(self._credentials.to_json())
            except Exception as e:
                print(f"토큰 갱신 실패: {e}")
                self.logout()
                return None
        return self._credentials

    def is_logged_in(self):
        creds = self.get_credentials()
        return creds and creds.valid

    def login(self):
        """로그인 절차를 백그라운드 스레드에서 시작합니다."""
        self.login_started.emit()
        
        self.login_thread = QThread()
        self.login_worker = LoginWorker()
        self.login_worker.moveToThread(self.login_thread)

        self.login_thread.started.connect(self.login_worker.run)
        self.login_worker.finished.connect(self.on_login_finished)
        
        self.login_thread.start()

    def on_login_finished(self, creds):
        """로그인 스레드가 완료되면 호출됩니다."""
        if creds:
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            self._credentials = creds
            self.auth_state_changed.emit()
            self.login_finished.emit(True)
            print("로그인 성공! 이벤트 데이터 새로고침을 요청합니다...")
        else:
            self.login_finished.emit(False)

        # 스레드 정리
        self.login_thread.quit()
        self.login_thread.wait()
        self.login_thread = None
        self.login_worker = None

    def logout(self):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self._credentials = None
        self.auth_state_changed.emit()

    def get_user_info(self):
        creds = self.get_credentials()
        if not creds:
            return None
        try:
            service = build("oauth2", "v2", credentials=creds)
            user_info = service.userinfo().get().execute()
            return user_info
        except Exception as e:
            print(f"사용자 정보 조회 실패: {e}")
            return None
