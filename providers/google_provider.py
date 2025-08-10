import datetime
import threading

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from providers.base_provider import BaseCalendarProvider
from config import (GOOGLE_CALENDAR_PROVIDER_NAME)

class GoogleCalendarProvider(BaseCalendarProvider):
    def __init__(self, settings, auth_manager):
        self.settings = settings
        self.name = GOOGLE_CALENDAR_PROVIDER_NAME
        self.auth_manager = auth_manager
        self._services_lock = threading.Lock()
        self._services_by_thread = {}
        self._calendar_list_cache = None

    def _get_service_for_current_thread(self):
        """현재 스레드에 맞는 독립적인 service 객체를 가져오거나 생성합니다."""
        thread_id = threading.get_ident()
        with self._services_lock:
            creds = self.auth_manager.get_credentials()
            if not creds:
                return None
            
            if thread_id not in self._services_by_thread:
                self._services_by_thread[thread_id] = build("calendar", "v3", credentials=creds)
            return self._services_by_thread[thread_id]

    def get_calendar_list(self, data_manager=None):
        """사용자의 캘린더 목록 전체를 반환합니다. (메모리 캐시 사용)"""
        if self._calendar_list_cache is None:
            try:
                service = self._get_service_for_current_thread()
                if not service: return [] # 인증 정보가 없으면 조용히 실패
                self._calendar_list_cache = service.calendarList().list().execute().get("items", [])
            except HttpError as e:
                error_message = f"Google 캘린더 목록을 가져오는 중 오류가 발생했습니다: {e}"
                if data_manager:
                    data_manager.report_error(error_message)
                else:
                    print(error_message)
                return []
        return self._calendar_list_cache

    def get_events(self, start_date, end_date, data_manager=None):
        service = self._get_service_for_current_thread()
        if not service:
            if data_manager:
                data_manager.report_error("Google 계정 인증 정보를 찾을 수 없습니다. 설정에서 다시 로그인해주세요.")
            return []

        try:
            # data_manager를 전달하여 오류 보고가 가능하도록 함
            calendar_list = self.get_calendar_list(data_manager=data_manager)
            if not calendar_list:
                if data_manager:
                    data_manager.report_error("Google 캘린더 목록을 가져오는 데 실패했습니다. 인터넷 연결 또는 계정 권한을 확인해주세요.")
                return []
        except Exception as e:
            if data_manager:
                data_manager.report_error(f"Google 캘린더 목록 조회 중 예상치 못한 오류가 발생했습니다: {e}")
            return []

        calendar_ids = [cal['id'] for cal in calendar_list]
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
                    event['provider'] = GOOGLE_CALENDAR_PROVIDER_NAME
                    event['calendarId'] = cal_id
                
                all_events.extend(events)
            except HttpError as e:
                error_message = f"'{cal_id}' 캘린더의 이벤트를 가져오는 중 오류가 발생했습니다.\n\n- 원인: {e.reason}\n- 상태 코드: {e.status_code}"
                if data_manager:
                    data_manager.report_error(error_message)
                else:
                    print(error_message)
                continue
            except Exception as e:
                error_message = f"'{cal_id}' 캘린더 처리 중 예상치 못한 오류: {e}"
                if data_manager:
                    data_manager.report_error(error_message)
                else:
                    print(error_message)
                continue
                
        return all_events

    def add_event(self, event_data, data_manager=None):
        """새로운 이벤트를 Google Calendar에 추가합니다."""
        try:
            service = self._get_service_for_current_thread()
            if not service:
                if data_manager: data_manager.report_error("이벤트를 추가하려면 Google 로그인이 필요합니다.")
                return None

            calendar_id = event_data.get('calendarId')
            event_body = event_data.get('body')

            if not calendar_id or not event_body:
                error_message = "이벤트 추가에 필요한 정보(calendarId, body)가 부족합니다."
                if data_manager: data_manager.report_error(error_message)
                else: print(error_message)
                return None

            if 'id' in event_body:
                del event_body['id']
            
            created_event = service.events().insert(
                calendarId=calendar_id, 
                body=event_body
            ).execute()
            
            created_event['calendarId'] = calendar_id
            
            print(f"Google Calendar에 '{created_event.get('summary')}' 일정이 추가되었습니다.")
            return created_event
        except HttpError as e:
            error_message = f"Google Calendar 이벤트 추가 중 오류 발생: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return None

    def update_event(self, event_data, data_manager=None):
        """기존 이벤트를 수정합니다."""
        try:
            service = self._get_service_for_current_thread()
            if not service:
                if data_manager: data_manager.report_error("이벤트를 수정하려면 Google 로그인이 필요합니다.")
                return None

            calendar_id = event_data.get('calendarId')
            event_body = event_data.get('body')
            event_id = event_body.get('id')

            if not all([calendar_id, event_body, event_id]):
                error_message = "이벤트 수정에 필요한 정보(calendarId, body, eventId)가 부족합니다."
                if data_manager: data_manager.report_error(error_message)
                else: print(error_message)
                return None

            updated_event = service.events().update(
                calendarId=calendar_id, 
                eventId=event_id, 
                body=event_body
            ).execute()
            
            updated_event['calendarId'] = calendar_id
            
            print(f"Google Calendar의 '{updated_event.get('summary')}' 일정이 수정되었습니다.")
            return updated_event
        except HttpError as e:
            error_message = f"Google Calendar 이벤트 수정 중 오류 발생: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return None

    def delete_event(self, event_data, data_manager=None):
        """기존 이벤트를 삭제합니다."""
        try:
            service = self._get_service_for_current_thread()
            if not service:
                if data_manager: data_manager.report_error("이벤트를 삭제하려면 Google 로그인이 필요합니다.")
                return False
            
            event_body = event_data.get('body', event_data)
            calendar_id = event_data.get('calendarId') or event_body.get('calendarId')
            event_id = event_body.get('id')

            if not all([calendar_id, event_id]):
                error_message = "이벤트 삭제에 필요한 정보(calendarId, eventId)가 부족합니다."
                if data_manager: data_manager.report_error(error_message)
                else: print(error_message)
                return False

            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            print(f"Google Calendar에서 ID '{event_id}' 일정이 삭제되었습니다.")
            return True
        except HttpError as e:
            if e.resp.status == 410:
                print(f"이미 삭제된 이벤트입니다 (ID: {event_data.get('id', 'N/A')}). 성공으로 처리합니다.")
                return True
            
            error_message = f"Google Calendar 이벤트 삭제 중 오류 발생: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
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
                'provider': GOOGLE_CALENDAR_PROVIDER_NAME
            })
        return standardized_calendars

    def search_events(self, query, data_manager=None):
        """Google 서버에 직접 쿼리하여 모든 캘린더에서 이벤트를 검색합니다."""
        if not query:
            return []

        service = self._get_service_for_current_thread()
        if not service:
            if data_manager: data_manager.report_error("이벤트를 검색하려면 Google 로그인이 필요합니다.")
            return []

        calendar_list = self.get_calendar_list(data_manager=data_manager)
        
        all_found_events = []
        for calendar in calendar_list:
            cal_id = calendar['id']
            try:
                events_result = service.events().list(
                    calendarId=cal_id,
                    q=query,
                    singleEvents=True,
                    orderBy="startTime"
                ).execute()
                
                events = events_result.get("items", [])
                for event in events:
                    event['provider'] = GOOGLE_CALENDAR_PROVIDER_NAME
                    event['calendarId'] = cal_id
                
                all_found_events.extend(events)
            except HttpError as e:
                error_message = f"캘린더({cal_id}) 검색 중 오류 발생: {e}"
                if data_manager: data_manager.report_error(error_message)
                else: print(error_message)
                continue
        
        return all_found_events