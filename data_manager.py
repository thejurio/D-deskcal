import datetime
import calendar
import json
import os
import time
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker

from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider

# --- ▼▼▼ 1. PreCacheWorker를 CachingManager로 교체하고 기능을 확장합니다. ▼▼▼ ---
class CachingManager(QObject):
    finished = pyqtSignal()

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self._is_running = True
        self._queue = []
        self._mutex = QMutex()

    def add_to_queue(self, tasks):
        """작업 큐에 새로운 월(튜플) 목록을 추가합니다."""
        with QMutexLocker(self._mutex):
            for task in tasks:
                if task not in self._queue:
                    self._queue.append(task)
    
    def stop(self):
        """작업 루프를 안전하게 종료시킵니다."""
        self._is_running = False

    def run(self):
        """큐에 작업이 있으면 계속해서 처리하는 메인 루프입니다."""
        print("백그라운드 캐싱 매니저 스레드가 시작되었습니다.")
        while self._is_running:
            task = None
            with QMutexLocker(self._mutex):
                if self._queue:
                    task = self._queue.pop(0)
            
            if task:
                year, month = task
                print(f"백그라운드 캐싱: {year}년 {month}월")
                # 캐시에 이미 데이터가 있는지 다시 한번 확인 후, 없으면 네트워크 요청
                if (year, month) not in self.data_manager.event_cache:
                    events = self.data_manager._fetch_events_from_providers(year, month)
                    self.data_manager.event_cache[(year, month)] = events
                    self.data_manager.data_updated.emit() # 데이터 준비 완료 신호 전송
                    # API에 부담을 주지 않기 위해 작업 사이에 짧은 텀을 둡니다.
                    time.sleep(0.5) 
            else:
                # 큐가 비어있으면 잠시 대기합니다.
                time.sleep(1)
        
        print("백그라운드 캐싱 매니저 스레드가 종료되었습니다.")
        self.finished.emit()
# --- ▲▲▲ 여기까지 CachingManager 변경 ▲▲▲ ---


class DataManager(QObject):
    data_updated = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.cache_file = "cache.json"
        self.event_cache = {}
        self.load_cache_from_file()
        
        self.providers = []
        # --- ▼▼▼ 2. CachingManager를 생성하고 스레드를 시작시키는 로직으로 변경합니다. ▼▼▼ ---
        self.caching_thread = QThread()
        self.caching_manager = CachingManager(self)
        self.caching_manager.moveToThread(self.caching_thread)

        self.caching_thread.started.connect(self.caching_manager.run)
        self.caching_manager.finished.connect(self.caching_thread.quit)
        self.caching_manager.finished.connect(self.caching_manager.deleteLater)
        self.caching_thread.finished.connect(self.caching_thread.deleteLater)
        
        self.caching_thread.start()
        # --- ▲▲▲ 여기까지 스레드 시작 로직 변경 ▲▲▲ ---

        try:
            google_provider = GoogleCalendarProvider(settings)
            if google_provider.service: self.providers.append(google_provider)
        except Exception as e: print(f"Google Provider 생성 중 오류 발생: {e}")
            
        try:
            local_provider = LocalCalendarProvider(settings)
            self.providers.append(local_provider)
        except Exception as e: print(f"Local Provider 생성 중 오류 발생: {e}")

    def stop_caching_thread(self):
        """프로그램 종료 시 캐싱 스레드를 안전하게 종료시킵니다."""
        if self.caching_thread and self.caching_thread.isRunning():
            self.caching_manager.stop()
            self.caching_thread.quit()
            self.caching_thread.wait() # 스레드가 완전히 끝날 때까지 대기

    # ... (load_cache_from_file, save_cache_to_file, _fetch_events_from_providers, get_events, sync_month 메서드는 기존과 동일) ...
    def load_cache_from_file(self):
        if not os.path.exists(self.cache_file): return
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                loaded_cache = json.load(f)
                self.event_cache = {tuple(map(int, k.split('-'))): v for k, v in loaded_cache.items()}
        except Exception as e:
            print(f"캐시 파일 읽기 오류: {e}")
            self.event_cache = {}

    def save_cache_to_file(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                cache_to_save = {f"{k[0]}-{k[1]}": v for k, v in self.event_cache.items()}
                json.dump(cache_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"캐시 파일 저장 오류: {e}")

    def _fetch_events_from_providers(self, year, month):
        all_events = []
        _, num_days = calendar.monthrange(year, month)
        start_date, end_date = datetime.date(year, month, 1), datetime.date(year, month, num_days)
        for provider in self.providers:
            try:
                all_events.extend(provider.get_events(start_date, end_date))
            except Exception as e:
                print(f"'{type(provider).__name__}' 이벤트 조회 오류: {e}")
        return all_events

    def get_events(self, year, month):
        """
        UI에서 호출하는 기본 이벤트 요청 메서드.
        캐시가 있으면 즉시 반환, 없으면 빈 리스트를 반환하고 백그라운드 로딩을 요청.
        """
        cache_key = (year, month)
        if cache_key in self.event_cache:
            return self.event_cache[cache_key]
        
        # 캐시에 없으면, 백그라운드 로딩을 요청하고 일단 빈 리스트를 반환
        self.caching_manager.add_to_queue([(year, month)])
        return []

    def sync_month(self, year, month, emit_signal=True):
        events = self._fetch_events_from_providers(year, month)
        self.event_cache[(year, month)] = events
        if emit_signal: self.data_updated.emit()

    def load_initial_month(self):
        """
        앱 시작 시 현재 달 데이터를 로딩하는 메서드.
        캐시에 없으면 백그라운드 로딩을 요청하고, 있으면 UI 업데이트 신호를 보냄.
        """
        print("현재 달 데이터를 우선 로딩합니다...")
        today = datetime.date.today()
        
        # get_events를 호출하여 캐시 확인 및 로딩 요청
        events = self.get_events(today.year, today.month)
        
        # 만약 캐시에 이미 데이터가 있었다면(events가 비어있지 않다면), 즉시 UI 업데이트
        if events:
            self.data_updated.emit()
        print("현재 달 로딩 완료.")

    def start_progressive_precaching(self):
        """점진적 프리캐싱 작업을 캐싱 매니저의 큐에 추가합니다."""
        print("점진적 프리캐싱 작업을 큐에 추가합니다.")
        today = datetime.date.today()
        tasks_to_add = []
        for i in range(1, 4): # n±1, n±2, n±3 순서
            # n+i
            future_date = today + datetime.timedelta(days=i * 30)
            tasks_to_add.append((future_date.year, future_date.month))
            # n-i
            past_date = today - datetime.timedelta(days=i * 30)
            tasks_to_add.append((past_date.year, past_date.month))
        
        self.caching_manager.add_to_queue(tasks_to_add)
    # --- ▲▲▲ 여기까지 메서드 수정 ▲▲▲ ---

    # ... (get_all_calendars, add_event, update_event 메서드는 기존과 동일) ...
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