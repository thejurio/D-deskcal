# tests/test_auth_manager.py
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_manager import AuthManager
from config import TOKEN_FILE

class TestAuthManager(unittest.TestCase):

    def setUp(self):
        """각 테스트 전에 실행됩니다."""
        # 테스트 실행 전에 항상 token.json을 삭제하여 독립적인 환경을 보장합니다.
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.auth_manager = AuthManager()

    def tearDown(self):
        """각 테스트 후에 실행됩니다."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)

    @patch('auth_manager.InstalledAppFlow')
    def test_login_and_logout(self, mock_flow):
        """로그인 및 로그아웃 기능의 정상 동작을 테스트합니다."""
        # --- 1. 로그인 테스트 ---
        
        # 가짜 Credentials 객체 설정
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "fake_token", "refresh_token": "fake_refresh"}'
        
        # 가짜 Flow 객체가 가짜 Credentials를 반환하도록 설정
        # flow.run_local_server()가 mock_creds를 반환하게 됩니다.
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_creds

        # 로그인 실행
        login_success = self.auth_manager.login()

        # 검증
        self.assertTrue(login_success, "로그인이 성공해야 합니다.")
        self.assertTrue(os.path.exists(TOKEN_FILE), "로그인 후 token.json 파일이 생성되어야 합니다.")
        self.assertIsNotNone(self.auth_manager._credentials, "내부 credentials 객체가 설정되어야 합니다.")
        
        # is_logged_in이 True를 반환하는지 확인
        # (MagicMock은 기본적으로 'valid' 속성이 없으므로, 직접 설정해줍니다.)
        self.auth_manager._credentials.valid = True
        self.auth_manager._credentials.refresh_token = True
        self.assertTrue(self.auth_manager.is_logged_in(), "로그인 후 is_logged_in은 True여야 합니다.")

        # --- 2. 로그아웃 테스트 ---
        
        # 로그아웃 실행
        self.auth_manager.logout()

        # 검증
        self.assertFalse(os.path.exists(TOKEN_FILE), "로그아웃 후 token.json 파일이 삭제되어야 합니다.")
        self.assertIsNone(self.auth_manager._credentials, "로그아웃 후 내부 credentials 객체는 None이어야 합니다.")
        self.assertFalse(self.auth_manager.is_logged_in(), "로그아웃 후 is_logged_in은 False여야 합니다.")

    def test_load_credentials(self):
        """기존 token.json 파일로부터 인증 정보를 올바르게 로드하는지 테스트합니다."""
        # 1. 올바른 형식의 가짜 token.json 파일 생성
        fake_token_content = """
        {
            "token": "loaded_token",
            "refresh_token": "loaded_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake_client_id",
            "client_secret": "fake_client_secret",
            "scopes": ["https://www.googleapis.com/auth/calendar"]
        }
        """
        with open(TOKEN_FILE, 'w') as f:
            f.write(fake_token_content)

        # 2. 새로운 AuthManager 인스턴스를 생성하여 로드 로직을 트리거
        new_auth_manager = AuthManager()

        # 3. 검증
        self.assertIsNotNone(new_auth_manager._credentials, "파일로부터 credentials를 로드해야 합니다.")
        self.assertEqual(new_auth_manager._credentials.token, "loaded_token")

if __name__ == '__main__':
    unittest.main()
