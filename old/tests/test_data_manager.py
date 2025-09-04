# tests/test_data_manager.py
import unittest
import datetime
import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가하여 모듈을 찾을 수 있도록 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_manager import DataManager
from providers.base_provider import BaseCalendarProvider
from config import LOCAL_CALENDAR_PROVIDER_NAME, GOOGLE_CALENDAR_PROVIDER_NAME

# --- 테스트를 위한 가짜 Provider (Mock Provider) ---

class MockLocalProvider(BaseCalendarProvider):
    """LocalCalendarProvider를 흉내 내는 가짜 클래스"""
    def __init__(self, settings):
        self.events = {}
        self.name = LOCAL_CALENDAR_PROVIDER_NAME

    def get_events(self, start_date, end_date):
        return list(self.events.values())

    def add_event(self, event_data):
        event_id = event_data['body']['id']
        self.events[event_id] = event_data['body']
        return event_data['body']

    def update_event(self, event_data):
        return self.add_event(event_data) # 테스트에서는 add와 동일하게 처리

    def delete_event(self, event_data):
        event_id = event_data.get('body', {}).get('id')
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False

class MockGoogleProvider(BaseCalendarProvider):
    """GoogleCalendarProvider를 흉내 내는 가짜 클래스"""
    def __init__(self, settings):
        self.events = {}
        self.name = GOOGLE_CALENDAR_PROVIDER_NAME
    
    def _get_service_for_current_thread(self): # DataManager가 호출하는 메서드
        return True # 실제 서비스 객체 대신 True를 반환하여 인증 통과

    def get_events(self, start_date, end_date):
        return list(self.events.values())

    def add_event(self, event_data):
        event_id = event_data['body']['id']
        self.events[event_id] = event_data['body']
        return event_data['body']

    def update_event(self, event_data):
        return self.add_event(event_data)

    def delete_event(self, event_data):
        event_id = event_data.get('body', {}).get('id')
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False

# --- DataManager 테스트 케이스 ---

class TestDataManager(unittest.TestCase):
    
    def setUp(self):
        """각 테스트 전에 실행되는 설정 메서드"""
        self.settings = {}
        # start_timer=False, load_cache=False로 설정하여 독립적인 테스트 환경 구성
        self.data_manager = DataManager(self.settings, start_timer=False, load_cache=False)
        
        # 실제 Provider 대신 Mock Provider를 사용하도록 교체
        self.mock_local_provider = MockLocalProvider(self.settings)
        self.mock_google_provider = MockGoogleProvider(self.settings)
        self.data_manager.providers = [self.mock_local_provider, self.mock_google_provider]

    def tearDown(self):
        """각 테스트 후에 실행되는 정리 메서드"""
        # DataManager의 백그라운드 스레드를 정지
        self.data_manager.stop_caching_thread()

    def test_add_local_event(self):
        """로컬 이벤트를 추가했을 때, 로컬 Provider에 전달되고 캐시가 업데이트되는지 테스트"""
        # 1. 테스트용 로컬 이벤트 데이터 준비
        event_data = {
            'provider': LOCAL_CALENDAR_PROVIDER_NAME,
            'body': {
                'id': 'local-123',
                'summary': '로컬 테스트',
                'start': {'date': '2025-08-15'},
                'end': {'date': '2025-08-16'}
            }
        }
        
        # 2. DataManager의 add_event 메서드 실행
        success = self.data_manager.add_event(event_data)
        
        # 3. 검증
        self.assertTrue(success, "이벤트 추가가 성공해야 합니다.")
        # MockLocalProvider에 이벤트가 추가되었는지 확인
        self.assertIn('local-123', self.mock_local_provider.events)
        # DataManager의 캐시에 이벤트가 추가되었는지 확인
        cache_key = (2025, 8)
        self.assertIn(cache_key, self.data_manager.event_cache)
        self.assertEqual(len(self.data_manager.event_cache[cache_key]), 1)
        self.assertEqual(self.data_manager.event_cache[cache_key][0]['summary'], '로컬 테스트')

    def test_add_google_event(self):
        """Google 이벤트를 추가했을 때, Google Provider에 전달되고 캐시가 업데이트되는지 테스트"""
        # 1. 테스트용 구글 이벤트 데이터 준비
        event_data = {
            'provider': GOOGLE_CALENDAR_PROVIDER_NAME,
            'body': {
                'id': 'google-456',
                'summary': '구글 테스트',
                'start': {'dateTime': '2025-09-20T10:00:00Z'},
                'end': {'dateTime': '2025-09-20T11:00:00Z'}
            }
        }

        # 2. DataManager의 add_event 메서드 실행
        success = self.data_manager.add_event(event_data)

        # 3. 검증
        self.assertTrue(success, "이벤트 추가가 성공해야 합니다.")
        # MockGoogleProvider에 이벤트가 추가되었는지 확인
        self.assertIn('google-456', self.mock_google_provider.events)
        # DataManager의 캐시에 이벤트가 추가되었는지 확인
        cache_key = (2025, 9)
        self.assertIn(cache_key, self.data_manager.event_cache)
        self.assertEqual(len(self.data_manager.event_cache[cache_key]), 1)
        self.assertEqual(self.data_manager.event_cache[cache_key][0]['summary'], '구글 테스트')

if __name__ == '__main__':
    unittest.main()
