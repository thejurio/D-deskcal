# tests/test_settings_manager.py
import unittest
import os
import json
import sys

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from settings_manager import save_settings, load_settings
from config import SETTINGS_FILE

class TestSettingsManager(unittest.TestCase):

    def setUp(self):
        """테스트 실행 전, 기존 설정 파일이 있다면 삭제합니다."""
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)

    def tearDown(self):
        """테스트 실행 후, 생성된 설정 파일을 삭제합니다."""
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)

    def test_save_and_load_settings(self):
        """설정을 저장하고 다시 불러오는 기능이 정상 동작하는지 테스트합니다."""
        # 1. 테스트용 설정 데이터 준비
        test_settings = {
            "window_opacity": 0.85,
            "selected_calendars": ["cal1", "cal2"],
            "sync_interval_minutes": 15
        }

        # 2. 설정 저장 함수 호출
        save_settings(test_settings)

        # 3. 파일이 실제로 생성되었는지 확인
        self.assertTrue(os.path.exists(SETTINGS_FILE))

        # 4. 설정 불러오기 함수 호출
        loaded_settings = load_settings()

        # 5. 저장된 데이터와 불러온 데이터가 일치하는지 검증
        self.assertEqual(loaded_settings, test_settings)

    def test_load_settings_no_file(self):
        """설정 파일이 없을 때, 빈 딕셔너리를 반환하는지 테스트합니다."""
        # 파일이 없는 상태에서 바로 로드 함수 호출
        loaded_settings = load_settings()
        
        # 빈 딕셔너리가 반환되는지 확인
        self.assertEqual(loaded_settings, {})

    def test_load_settings_corrupted_file(self):
        """설정 파일이 손상되었을 때(JSON 형식이 아닐 때), 빈 딕셔너리를 반환하는지 테스트합니다."""
        # 손상된 내용으로 파일 생성
        with open(SETTINGS_FILE, 'w') as f:
            f.write("this is not a valid json")
            
        # 로드 함수 호출
        loaded_settings = load_settings()
        
        # 빈 딕셔너리가 반환되는지 확인
        self.assertEqual(loaded_settings, {})

if __name__ == '__main__':
    unittest.main()
