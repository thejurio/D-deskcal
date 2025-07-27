import datetime
import calendar
from PyQt6.QtCore import QObject, pyqtSignal

# 구글 Provider와 로컬 Provider를 모두 임포트합니다.
from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider

class DataManager(QObject):
    data_updated = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.event_cache = {}
        
        self.providers = []
        
        # --- ▼▼▼ 여기가 수정된 핵심입니다 ▼▼▼ ---
        # 1. GoogleCalendarProvider를 리스트에 추가합니다.
        try:
            google_provider = GoogleCalendarProvider(settings)
            if google_provider.service:
                self.providers.append(google_provider)
            else:
                print("Google Provider 초기화 실패: 구글 API에 연결할 수 없습니다.")
        except Exception as e:
            print(f"Google Provider 생성 중 오류 발생: {e}")
            
        # 2. LocalCalendarProvider를 리스트에 추가합니다.
        try:
            local_provider = LocalCalendarProvider(settings)
            self.providers.append(local_provider)
        except Exception as e:
            print(f"Local Provider 생성 중 오류 발생: {e}")
        # --- ▲▲▲ 여기까지가 수정된 핵심입니다 ▲▲▲ ---

    def _fetch_events_from_providers(self, year, month):
        all_events = []
        _, num_days = calendar.monthrange(year, month)
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year, month, num_days)

        for provider in self.providers:
            try:
                provider_events = provider.get_events(start_date, end_date)
                all_events.extend(provider_events)
            except Exception as e:
                print(f"'{type(provider).__name__}'에서 이벤트를 가져오는 중 오류 발생: {e}")
        
        return all_events

    def get_events(self, year, month):
        cache_key = (year, month)
        if cache_key in self.event_cache:
            return self.event_cache[cache_key]
        
        events = self._fetch_events_from_providers(year, month)
        self.event_cache[cache_key] = events
        return events

    def sync_month(self, year, month, emit_signal=True):
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {year}년 {month}월 데이터를 강제 동기화합니다.")
        events = self._fetch_events_from_providers(year, month)
        self.event_cache[(year, month)] = events
        if emit_signal:
            self.data_updated.emit()

    def pre_cache_months(self):
        print("주변 6개월치 데이터 프리캐싱을 시작합니다...")
        today = datetime.date.today()
        for i in range(-3, 4):
            target_date = today + datetime.timedelta(days=i * 30)
            self.get_events(target_date.year, target_date.month)
        print("프리캐싱 완료.")
        self.data_updated.emit()
    
    def get_all_calendars(self):
        """모든 Provider로부터 캘린더 목록을 수집하여 통합된 리스트로 반환합니다."""
        all_calendars = []
        for provider in self.providers:
            if hasattr(provider, 'get_calendars'):
                all_calendars.extend(provider.get_calendars())
        return all_calendars

    def add_event(self, event_data):
        """데이터에 명시된 Provider를 찾아 이벤트 추가를 위임합니다."""
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                # Provider의 add_event가 성공적으로 끝나면 True를 반환합니다.
                if provider.add_event(event_data):
                    # 성공 시, 해당 월의 캐시를 삭제하여 다음번 조회 시 새로 불러오게 합니다.
                    body = event_data['body']
                    start_str = body['start'].get('date') or body['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache:
                        del self.event_cache[cache_key]
                    
                    # UI에 데이터가 변경되었음을 알립니다.
                    self.data_updated.emit()
                break
    
    def update_event(self, event_data):
        """데이터에 명시된 Provider를 찾아 이벤트 수정을 위임합니다."""
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                if provider.update_event(event_data):
                    # 성공 시, 캐시 삭제 및 UI 새로고침
                    body = event_data['body']
                    start_str = body['start'].get('date') or body['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache:
                        del self.event_cache[cache_key]
                    self.data_updated.emit()
                break