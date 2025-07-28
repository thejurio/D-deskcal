import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PyQt6.QtCore import QObject, pyqtSignal, QThread

# --- 설정 ---
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar'
]
# --- ---

class LoginWorker(QObject):
    """백그라운드 스레드에서 동기적인 로그인 작업을 처리하는 작업자"""
    finished = pyqtSignal(object) # object는 Credentials 객체 또는 None

    def run(self):
        """로그인 절차를 실행하고 결과를 finished 신호로 보냅니다."""
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            self.finished.emit(creds)
        except Exception as e:
            print(f"로그인 절차 중 오류 발생: {e}")
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
