import datetime
import os.path
import threading

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from providers.base_provider import BaseCalendarProvider

SCOPES = ["https://www.googleapis.com/auth/calendar"]

class GoogleCalendarProvider(BaseCalendarProvider):
    def __init__(self, settings):
        self.settings = settings
        self._services_lock = threading.Lock()
        self._services_by_thread = {}
        self._calendar_list_cache = None

    def _get_service_for_current_thread(self):
        """현재 스레드에 맞는 독립적인 service 객체를 가져오거나 생성합니다."""
        thread_id = threading.get_ident()
        with self._services_lock:
            if thread_id not in self._services_by_thread:
                self._services_by_thread[thread_id] = self._authenticate()
            return self._services_by_thread[thread_id]

    def _authenticate(self):
        """Google Calendar API와 통신하기 위한 서비스 객체를 생성하고 반환합니다."""
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        
        return build("calendar", "v3", credentials=creds)

    def get_calendar_list(self):
        """사용자의 캘린더 목록 전체를 반환합니다. (메모리 캐시 사용)"""
        # 캘린더 목록은 자주 바뀌지 않으므로, 한 번 가져온 후 캐시하여 사용
        if self._calendar_list_cache is None:
            try:
                service = self._get_service_for_current_thread()
                self._calendar_list_cache = service.calendarList().list().execute().get("items", [])
            except HttpError as e:
                print(f"구글 캘린더 목록을 가져오는 중 오류 발생: {e}")
                return []
        return self._calendar_list_cache

    def get_events(self, start_date, end_date):
        service = self._get_service_for_current_thread()
        if not service: return []

        calendar_list = self.get_calendar_list()
        calendar_ids = [cal['id'] for cal in calendar_list]
        custom_colors = self.settings.get("calendar_colors", {})
        custom_emojis = self.settings.get("calendar_emojis", {})
        calendar_color_map = {cal['id']: cal['backgroundColor'] for cal in calendar_list}

        all_events = []
        time_min = datetime.datetime.combine(start_date, datetime.time.min).isoformat() + 'Z'
        time_max = datetime.datetime.combine(end_date, datetime.time.max).isoformat() + 'Z'

        for cal_id in calendar_ids:
            try:
                events_result = service.events().list(
                    calendarId=cal_id, timeMin=time_min, timeMax=time_max,
                    singleEvents=True, orderBy="startTime"
                ).execute()
                events = events_result.get("items", [])
                
                for event in events:
                    event['calendarId'] = cal_id
                    default_color = calendar_color_map.get(cal_id, '#555555')
                    event['color'] = custom_colors.get(cal_id, default_color)
                    event['emoji'] = custom_emojis.get(cal_id, '')
                
                all_events.extend(events)
            except HttpError as e:
                print(f"캘린더({cal_id})의 이벤트를 가져오는 중 오류 발생: {e}")
                continue
                
        return all_events

    def add_event(self, event_data):
        """새로운 이벤트를 Google Calendar에 추가합니다."""
        try:
            service = self._get_service_for_current_thread()
            calendar_id = event_data['calendarId']
            event_body = event_data['body']
            if 'id' in event_body:
                del event_body['id']
            
            service.events().insert(
                calendarId=calendar_id, 
                body=event_body
            ).execute()
            
            print(f"Google Calendar에 '{event_body.get('summary')}' 일정이 추가되었습니다.")
            return True
        except HttpError as e:
            print(f"Google Calendar 이벤트 추가 중 오류 발생: {e}")
            return False

    def update_event(self, event_data):
        """기존 이벤트를 수정합니다."""
        try:
            service = self._get_service_for_current_thread()
            calendar_id = event_data['calendarId']
            event_body = event_data['body']
            event_id = event_body.get('id')

            if not event_id:
                print("이벤트 ID가 없어 업데이트할 수 없습니다.")
                return False

            service.events().update(
                calendarId=calendar_id, 
                eventId=event_id, 
                body=event_body
            ).execute()
            
            print(f"Google Calendar의 '{event_body.get('summary')}' 일정이 수정되었습니다.")
            return True
        except HttpError as e:
            print(f"Google Calendar 이벤트 수정 중 오류 발생: {e}")
            return False

    def delete_event(self, event_data):
        """기존 이벤트를 삭제합니다."""
        try:
            service = self._get_service_for_current_thread()
            calendar_id = event_data['calendarId']
            event_id = event_data['body'].get('id')

            if not event_id:
                print("이벤트 ID가 없어 삭제할 수 없습니다.")
                return False

            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            print(f"Google Calendar에서 일정이 삭제되었습니다.")
            return True
        except HttpError as e:
            print(f"Google Calendar 이벤트 삭제 중 오류 발생: {e}")
            return False

    def get_calendars(self):
        """Google 캘린더 목록을 가져와 '표준 형식'으로 변환하여 반환합니다."""
        google_calendars = self.get_calendar_list()
        standardized_calendars = []
        for calendar in google_calendars:
            standardized_calendars.append({
                'id': calendar['id'],
                'summary': calendar['summary'],
                'backgroundColor': calendar['backgroundColor'],
                'provider': 'GoogleCalendarProvider'
            })
        return standardized_calendars
