# tests/test_google_provider.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import datetime

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.google_provider import GoogleCalendarProvider
from config import GOOGLE_CALENDAR_PROVIDER_NAME, DEFAULT_EVENT_COLOR

class TestGoogleCalendarProvider(unittest.TestCase):

    def setUp(self):
        self.settings = {
            "calendar_colors": {"cal_1": "#ff0000"},
            "calendar_emojis": {"cal_1": "🚀"}
        }
        # 가짜 AuthManager 객체를 만듭니다.
        self.mock_auth_manager = MagicMock()
        self.provider = GoogleCalendarProvider(self.settings, self.mock_auth_manager)

    @patch('providers.google_provider.build')
    def test_get_calendars(self, mock_build):
        """get_calendars가 API 응답을 표준 형식으로 올바르게 변환하는지 테스트합니다."""
        # 1. Google API가 반환할 가짜 캘린더 목록 데이터
        mock_api_response = {
            "items": [
                {"id": "cal_1", "summary": "테스트 캘린더 1", "backgroundColor": "#aabbcc"},
                {"id": "cal_2", "summary": "테스트 캘린더 2", "backgroundColor": "#ddeeff"},
            ]
        }
        
        # 2. 가짜 서비스 객체 설정
        # build('calendar', 'v3', ...).calendarList().list().execute()가
        # 위에서 정의한 가짜 데이터를 반환하도록 설정합니다.
        mock_service = MagicMock()
        mock_service.calendarList().list().execute.return_value = mock_api_response
        mock_build.return_value = mock_service
        
        # 3. 테스트 대상 함수 호출
        calendars = self.provider.get_calendars()

        # 4. 검증
        self.assertEqual(len(calendars), 2)
        self.assertEqual(calendars[0]['id'], 'cal_1')
        self.assertEqual(calendars[0]['summary'], '테스트 캘린더 1')
        self.assertEqual(calendars[0]['provider'], GOOGLE_CALENDAR_PROVIDER_NAME)
        # 설정에 저장된 색상이 기본 색상보다 우선하는지 확인
        self.assertEqual(calendars[0]['backgroundColor'], '#aabbcc') # get_calendars는 API의 색상을 그대로 반환

    @patch('providers.google_provider.build')
    def test_get_events(self, mock_build):
        """get_events가 API 응답에 provider, color, emoji 정보를 올바르게 추가하는지 테스트합니다."""
        # 1. get_events 내부에서 get_calendar_list를 호출하므로, 이에 대한 가짜 응답도 필요합니다.
        mock_calendar_list_response = {
            "items": [
                {"id": "cal_1", "summary": "테스트 캘린더 1", "backgroundColor": "#aabbcc"},
            ]
        }
        
        # 2. Google API가 반환할 가짜 이벤트 목록 데이터
        mock_events_response = {
            "items": [
                {
                    "id": "event_1", 
                    "summary": "중요한 회의",
                    "start": {"dateTime": "2025-01-01T10:00:00Z"},
                    "end": {"dateTime": "2025-01-01T11:00:00Z"}
                }
            ]
        }

        # 3. 가짜 서비스 객체 설정
        mock_service = MagicMock()
        mock_service.calendarList().list().execute.return_value = mock_calendar_list_response
        mock_service.events().list().execute.return_value = mock_events_response
        mock_build.return_value = mock_service

        # 4. 테스트 대상 함수 호출 (datetime.date 객체 사용)
        start_date = datetime.date(2025, 1, 1)
        end_date = datetime.date(2025, 1, 31)
        events = self.provider.get_events(start_date, end_date)

        # 5. 검증
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['id'], 'event_1')
        self.assertEqual(event['provider'], GOOGLE_CALENDAR_PROVIDER_NAME)
        self.assertEqual(event['calendarId'], 'cal_1')
        # 설정에 저장된 커스텀 색상과 이모지가 올바르게 적용되었는지 확인
        self.assertEqual(event['color'], '#ff0000')
        self.assertEqual(event['emoji'], '🚀')

if __name__ == '__main__':
    unittest.main()
