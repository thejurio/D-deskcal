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
    MAX_CACHE_SIZE = 15 # 최대 15개월치 데이터만 캐시에 보관

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self._is_running = True
        self._mutex = QMutex()
        self._task_queue = [] # 처리할 작업 목록 (list)
        self._pending_tasks = set() # 큐에 이미 있는 작업인지 확인 (set)
        self._last_viewed_month = None

    def request_caching_around(self, year, month, direction="none"):
        """
        기존 캐싱 계획을 모두 버리고, 현재 위치를 기준으로 새 계획을 수립하여 큐에 추가합니다.
        """
        with QMutexLocker(self._mutex):
            self._last_viewed_month = (year, month)
            
            # 1. 기존 계획 초기화
            self._task_queue.clear()
            self._pending_tasks.clear()

            # 2. 새로운 작업 순서 생성
            new_tasks = []
            base_date = datetime.date(year, month, 15)

            # 방향성 우선순위에 따라 정렬된 월 목록 생성
            if direction == "forward":
                # 미래 월 -> 과거 월 순
                for i in range(1, 4): new_tasks.append(self._get_month_tuple(base_date, i * 31))
                new_tasks.append((year, month))
                for i in range(-1, -4, -1): new_tasks.append(self._get_month_tuple(base_date, i * 31))
            elif direction == "backward":
                # 과거 월 -> 미래 월 순
                for i in range(-1, -4, -1): new_tasks.append(self._get_month_tuple(base_date, i * 31))
                new_tasks.append((year, month))
                for i in range(1, 4): new_tasks.append(self._get_month_tuple(base_date, i * 31))
            else: # 방향성 없음 (초기 로딩)
                # 가까운 순서대로
                new_tasks.append((year, month))
                for i in range(1, 4):
                    new_tasks.append(self._get_month_tuple(base_date, i * 31))
                    new_tasks.append(self._get_month_tuple(base_date, -i * 31))

            # 3. 캐시되지 않은 작업만 큐에 추가
            for task in new_tasks:
                if task not in self.data_manager.event_cache and task not in self._pending_tasks:
                    self._task_queue.append(task)
                    self._pending_tasks.add(task)
            
            print(f"새로운 캐싱 계획 수립: {year}년 {month}월 주변. 대기열: {len(self._task_queue)}개")

    def _get_month_tuple(self, base_date, days_delta):
        target_date = base_date + datetime.timedelta(days=days_delta)
        return (target_date.year, target_date.month)

    def stop(self):
        self._is_running = False

    def run(self):
        """큐에 있는 작업을 순서대로 처리하고, 캐시 크기를 관리하는 메인 루프."""
        print("지능형 캐싱 매니저(롤링 큐) 스레드가 시작되었습니다.")
        while self._is_running:
            task = None
            with QMutexLocker(self._mutex):
                if self._task_queue:
                    task = self._task_queue.pop(0)
                    self._pending_tasks.remove(task)
            
            if task:
                year, month = task
                print(f"백그라운드 캐싱 수행: {year}년 {month}월")
                events = self.data_manager._fetch_events_from_providers(year, month)
                self.data_manager.event_cache[task] = events
                self.data_manager.data_updated.emit()
                
                self._manage_cache_size() # 캐시 추가 후 크기 관리
                time.sleep(0.5)
            else:
                time.sleep(1)
        
        print("지능형 캐싱 매니저 스레드가 종료되었습니다.")
        self.finished.emit()

    def _manage_cache_size(self):
        """캐시 크기를 확인하고, 최대치를 넘으면 오래된 항목을 제거합니다."""
        with QMutexLocker(self._mutex):
            while len(self.data_manager.event_cache) > self.MAX_CACHE_SIZE:
                if self._last_viewed_month is None: break
                
                # 현재 뷰에서 가장 멀리 떨어진 월을 찾아 제거
                farthest_month = None
                max_distance = -1
                
                y, m = self._last_viewed_month
                for cache_key in self.data_manager.event_cache.keys():
                    dist = abs((cache_key[0] - y) * 12 + (cache_key[1] - m))
                    if dist > max_distance:
                        max_distance = dist
                        farthest_month = cache_key
                
                if farthest_month:
                    print(f"캐시 용량 초과. 가장 오래된 항목 제거: {farthest_month}")
                    del self.data_manager.event_cache[farthest_month]
                else:
                    break # 제거할 항목이 없으면 중단


class DataManager(QObject):
    data_updated = pyqtSignal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.cache_file = "cache.json"
        self.event_cache = {}
        self.load_cache_from_file()
        self.last_requested_month = None
        
        self.providers = []
        self.caching_thread = QThread()
        self.caching_manager = CachingManager(self)
        self.caching_manager.moveToThread(self.caching_thread)

        self.caching_thread.started.connect(self.caching_manager.run)
        self.caching_manager.finished.connect(self.caching_thread.quit)
        self.caching_manager.finished.connect(self.caching_manager.deleteLater)
        self.caching_thread.finished.connect(self.caching_thread.deleteLater)
        
        self.caching_thread.start()

        try:
            google_provider = GoogleCalendarProvider(settings)
            if google_provider.service: self.providers.append(google_provider)
        except Exception as e: print(f"Google Provider 생성 중 오류 발생: {e}")
            
        try:
            local_provider = LocalCalendarProvider(settings)
            self.providers.append(local_provider)
        except Exception as e: print(f"Local Provider 생성 중 오류 발생: {e}")

    def stop_caching_thread(self):
        if self.caching_thread and self.caching_thread.isRunning():
            self.caching_manager.stop()
            self.caching_thread.quit()
            self.caching_thread.wait()

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
        먼저 캐싱 계획을 갱신하고, 그 다음 캐시 유무에 따라 데이터를 반환합니다.
        """
        cache_key = (year, month)
        
        # 1. (항상 실행) 사용자의 현재 위치를 기반으로 캐싱 계획을 새로 수립하도록 요청
        direction = "none"
        if self.last_requested_month:
            if (year, month) > self.last_requested_month:
                direction = "forward"
            elif (year, month) < self.last_requested_month:
                direction = "backward"
        
        self.last_requested_month = cache_key
        self.caching_manager.request_caching_around(year, month, direction)

        # 2. (계획 수립 후) 현재 요청된 월의 데이터를 반환
        if cache_key in self.event_cache:
            return self.event_cache[cache_key]
        else:
            return []

    def sync_month(self, year, month, emit_signal=True):
        events = self._fetch_events_from_providers(year, month)
        self.event_cache[(year, month)] = events
        if emit_signal: self.data_updated.emit()

    def get_all_calendars(self):
        """모든 provider로부터 캘린더 목록을 수집하여 반환합니다."""
        all_calendars = []
        for provider in self.providers:
            if hasattr(provider, 'get_calendars'):
                try:
                    all_calendars.extend(provider.get_calendars())
                except Exception as e:
                    print(f"'{type(provider).__name__}'에서 캘린더 목록을 가져오는 중 오류 발생: {e}")
        return all_calendars

    def load_initial_month(self):
        print("초기 데이터 로딩을 요청합니다...")
        today = datetime.date.today()
        # 앱 시작 시, 현재 월을 기준으로 캐싱 계획 수립 요청
        self.get_events(today.year, today.month)

    def start_progressive_precaching(self):
        # 이 메서드는 이제 load_initial_month에 의해 완전히 대체되었습니다.
        pass
