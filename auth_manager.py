import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PyQt6.QtCore import QObject, pyqtSignal

# --- 설정 ---
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'
# ▼▼▼ [수정 1] userinfo.email과 openid 스코프 추가 ▼▼▼
SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/calendar'
]
# --- ---

class AuthManager(QObject):
    auth_state_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._credentials = None
        self.load_credentials()

    def load_credentials(self):
        if os.path.exists(TOKEN_FILE):
            try:
                self._credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception as e:
                print(f"인증 정보 로드 실패: {e}")
                self._credentials = None

    def get_credentials(self):
        """유효한 인증 정보를 반환합니다. (필요 시 갱신)"""
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
        try:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

            self._credentials = creds
            self.auth_state_changed.emit()
            return True
        except Exception as e:
            print(f"로그인 절차 중 오류 발생: {e}")
            return False

    def logout(self):
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self._credentials = None
        self.auth_state_changed.emit()

    def get_user_info(self):
        """로그인된 사용자의 정보를 반환합니다."""
        # ▼▼▼ [수정 2] 올바른 인증 정보로 API 호출 ▼▼▼
        creds = self.get_credentials()
        if not creds:
            print("사용자 정보 조회 실패: 유효한 인증 정보 없음")
            return None

        try:
            # build 함수에 creds를 전달하여 인증된 서비스 객체 생성
            service = build("oauth2", "v2", credentials=creds)
            user_info = service.userinfo().get().execute()
            return user_info
        except Exception as e:
            print(f"사용자 정보 조회 실패: {e}")
            return None