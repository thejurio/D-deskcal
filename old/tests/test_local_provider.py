import unittest
import sqlite3
import json
import datetime
import os

# 테스트 대상 모듈을 import하기 위해 경로를 추가합니다.
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.local_provider import LocalCalendarProvider
from config import LOCAL_CALENDAR_ID, LOCAL_CALENDAR_PROVIDER_NAME

class TestLocalCalendarProvider(unittest.TestCase):

    def setUp(self):
        """각 테스트 메소드 실행 전에 호출됩니다."""
        # :memory:를 사용하여 실제 파일이 아닌 인메모리 DB를 사용합니다.
        self.db_connection = sqlite3.connect(":memory:")
        
        # 테스트용 Provider를 생성하고, 인메모리 DB 연결을 주입합니다.
        self.settings = {} # 테스트용 빈 설정
        self.provider = LocalCalendarProvider(self.settings, db_connection=self.db_connection)
        
        # 테스트용 DB에 테이블 생성
        self.provider._init_db_table()

        # 테스트용 샘플 이벤트 데이터
        self.sample_event_body = {
            'id': 'test-event-123',
            'summary': '테스트 이벤트',
            'start': {'date': '2025-08-15'},
            'end': {'date': '2025-08-16'}
        }
        self.sample_event_data = {
            'calendarId': LOCAL_CALENDAR_ID,
            'provider': LOCAL_CALENDAR_PROVIDER_NAME,
            'body': self.sample_event_body
        }


    def tearDown(self):
        """각 테스트 메소드 실행 후에 호출됩니다."""
        # 인메모리 DB 연결을 닫습니다.
        self.db_connection.close()

    def test_add_and_get_event(self):
        """이벤트 추가 및 조회 기능을 테스트합니다."""
        # 1. 이벤트 추가
        added_event = self.provider.add_event(self.sample_event_data)
        self.assertIsNotNone(added_event, "이벤트 추가가 실패했습니다.")
        self.assertEqual(added_event['id'], self.sample_event_body['id'])

        # 2. 추가된 이벤트 조회
        start_date = datetime.date(2025, 8, 1)
        end_date = datetime.date(2025, 8, 31)
        events = self.provider.get_events(start_date, end_date)
        
        self.assertEqual(len(events), 1, "이벤트가 정확히 1개 조회되어야 합니다.")
        retrieved_event = events[0]
        self.assertEqual(retrieved_event['summary'], self.sample_event_body['summary'])
        self.assertEqual(retrieved_event['id'], self.sample_event_body['id'])

    def test_delete_event(self):
        """이벤트 삭제 기능을 테스트합니다."""
        # 1. 먼저 이벤트를 추가합니다.
        self.provider.add_event(self.sample_event_data)

        # 2. 추가된 것을 확인합니다.
        start_date = datetime.date(2025, 8, 1)
        end_date = datetime.date(2025, 8, 31)
        events = self.provider.get_events(start_date, end_date)
        self.assertEqual(len(events), 1)

        # 3. 이벤트를 삭제합니다.
        delete_success = self.provider.delete_event(self.sample_event_data)
        self.assertTrue(delete_success, "이벤트 삭제에 실패했습니다.")

        # 4. 삭제 후 이벤트가 없는 것을 확인합니다.
        events_after_delete = self.provider.get_events(start_date, end_date)
        self.assertEqual(len(events_after_delete), 0, "이벤트 삭제 후에는 아무것도 조회되지 않아야 합니다.")

    def test_update_event(self):
        """이벤트 수정 기능을 테스트합니다."""
        # 1. 이벤트를 추가합니다.
        self.provider.add_event(self.sample_event_data)

        # 2. 수정할 데이터를 준비합니다.
        updated_summary = "수정된 테스트 이벤트"
        updated_event_body = self.sample_event_body.copy()
        updated_event_body['summary'] = updated_summary
        update_data = {
            'calendarId': LOCAL_CALENDAR_ID,
            'provider': LOCAL_CALENDAR_PROVIDER_NAME,
            'body': updated_event_body
        }

        # 3. 이벤트를 수정합니다.
        self.provider.update_event(update_data)

        # 4. 수정된 내용이 올바르게 반영되었는지 확인합니다.
        start_date = datetime.date(2025, 8, 1)
        end_date = datetime.date(2025, 8, 31)
        events = self.provider.get_events(start_date, end_date)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['summary'], updated_summary)

if __name__ == '__main__':
    unittest.main()
