import datetime
import calendar
import json
import os
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider

class PreCacheWorker(QObject):
    finished = pyqtSignal()
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
    def run(self):
        print("백그라운드 프리캐싱 스레드를 시작합니다...")
        today = datetime.date.today()
        for i in list(range(-3, 0)) + list(range(1, 4)):
            target_date = today + datetime.timedelta(days=i * 30)
            self.data_manager.get_events(target_date.year, target_date.month)
        print("백그라운드 프리캐싱 완료.")
        self.finished.emit()

class DataManager(QObject):
    data_updated = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.cache_file = "cache.json" # 캐시 파일 이름 정의
        self.event_cache = {}
        
        # --- ▼▼▼ 여기가 수정된 핵심입니다 (캐시 불러오기) ▼▼▼ ---
        self.load_cache_from_file() # 프로그램 시작 시 캐시 파일 불러오기
        
        self.providers = []
        self.thread = None
        self.worker = None
        
        try:
            google_provider = GoogleCalendarProvider(settings)
            if google_provider.service: self.providers.append(google_provider)
            else: print("Google Provider 초기화 실패: 구글 API에 연결할 수 없습니다.")
        except Exception as e:
            print(f"Google Provider 생성 중 오류 발생: {e}")
            
        try:
            local_provider = LocalCalendarProvider(settings)
            self.providers.append(local_provider)
        except Exception as e:
            print(f"Local Provider 생성 중 오류 발생: {e}")

    # --- ▼▼▼ 2개의 새로운 메서드를 추가합니다. (캐시 저장/불러오기) ▼▼▼ ---
    def load_cache_from_file(self):
        """프로그램 시작 시 파일에서 캐시를 불러옵니다."""
        if not os.path.exists(self.cache_file):
            print("캐시 파일이 존재하지 않습니다.")
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                # JSON의 문자열 키(예: "2025-07")를 다시 파이썬 튜플 키(예: (2025, 7))로 변환합니다.
                loaded_cache = json.load(f)
                self.event_cache = {tuple(map(int, k.split('-'))): v for k, v in loaded_cache.items()}
                print(f"'{self.cache_file}'에서 캐시를 성공적으로 불러왔습니다.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"캐시 파일('.cache.json')을 읽는 중 오류 발생: {e}")
            self.event_cache = {} # 문제가 있는 경우 캐시를 초기화합니다.

    def save_cache_to_file(self):
        """프로그램 종료 시 현재 캐시를 파일에 저장합니다."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                # 파이썬 튜플 키는 JSON에 저장할 수 없으므로 "년도-월" 형태의 문자열로 변환합니다.
                cache_to_save = {f"{k[0]}-{k[1]}": v for k, v in self.event_cache.items()}
                json.dump(cache_to_save, f, ensure_ascii=False, indent=4)
                print(f"현재 캐시를 '{self.cache_file}'에 성공적으로 저장했습니다.")
        except Exception as e:
            print(f"캐시를 파일에 저장하는 중 오류 발생: {e}")
            
    # --- ▲▲▲ 여기까지 새로운 메서드 추가 ▲▲▲ ---

    def _fetch_events_from_providers(self, year, month):
        # ... (이하 다른 메서드들은 기존과 동일) ...
        all_events = []
        _, num_days = calendar.monthrange(year, month)
        start_date, end_date = datetime.date(year, month, 1), datetime.date(year, month, num_days)
        for provider in self.providers:
            try:
                all_events.extend(provider.get_events(start_date, end_date))
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
        if emit_signal: self.data_updated.emit()

    def load_initial_month(self):
        print("현재 달 데이터를 우선 로딩합니다...")
        today = datetime.date.today()
        # 캐시가 이미 있으면 즉시 UI에 표시하고, 백그라운드에서 업데이트 확인
        if (today.year, today.month) in self.event_cache:
            self.data_updated.emit()
            print("기존 캐시로 현재 달을 표시합니다.")
            self.sync_month(today.year, today.month, emit_signal=True) # 백그라운드에서 조용히 업데이트
        else:
            self.sync_month(today.year, today.month, emit_signal=True)
        print("현재 달 로딩 완료.")

    def start_background_precaching(self):
        self.thread = QThread()
        self.worker = PreCacheWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
    
    def get_all_calendars(self):
        all_calendars = []
        for provider in self.providers:
            if hasattr(provider, 'get_calendars'):
                all_calendars.extend(provider.get_calendars())
        return all_calendars

    def add_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                if provider.add_event(event_data):
                    body = event_data['body']
                    start_str = body['start'].get('date') or body['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache: del self.event_cache[cache_key]
                    self.data_updated.emit()
                break
    
    def update_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                if provider.update_event(event_data):
                    body = event_data['body']
                    start_str = body['start'].get('date') or body['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache: del self.event_cache[cache_key]
                    self.data_updated.emit()
                break