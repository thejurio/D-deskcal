import datetime
import calendar
import json
import os
import time
from contextlib import contextmanager
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer, QWaitCondition

from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider

class CachingManager(QObject):
    finished = pyqtSignal()
    MAX_CACHE_SIZE = 7

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self._is_running = True
        self._mutex = QMutex()
        self._task_queue = []
        self._pending_tasks = set()
        self._last_viewed_month = None
        self._activity_lock = QMutex()
        self._pause_requested = False
        self._resume_condition = QWaitCondition()

    def request_caching_around(self, year, month, direction="none"):
        with QMutexLocker(self._mutex):
            self._last_viewed_month = (year, month)
            self._task_queue = [t for t in self._task_queue if t[0] == "FULL_SYNC"]
            self._pending_tasks = {t for t in self._pending_tasks if t[0] == "FULL_SYNC"}
            new_tasks = []
            base_date = datetime.date(year, month, 15)
            task_configs = []
            if direction == "forward":
                for i in range(1, 4): task_configs.append(i * 31)
                task_configs.append(0)
                for i in range(-1, -4, -1): task_configs.append(i * 31)
            elif direction == "backward":
                for i in range(-1, -4, -1): task_configs.append(i * 31)
                task_configs.append(0)
                for i in range(1, 4): task_configs.append(i * 31)
            else:
                task_configs.append(0)
                for i in range(1, 4):
                    task_configs.append(i * 31)
                    task_configs.append(-i * 31)
            for days in task_configs:
                new_tasks.append(self._get_month_tuple(base_date, days))
            for task_type, task_data in new_tasks:
                if task_data not in self.data_manager.event_cache and ('month', task_data) not in self._pending_tasks:
                    self._task_queue.append(('month', task_data))
                    self._pending_tasks.add(('month', task_data))
            print(f"새로운 캐싱 계획 수립: {year}년 {month}월 주변. 대기열: {len(self._task_queue)}개")

    def request_full_sync(self):
        with QMutexLocker(self._mutex):
            if ("FULL_SYNC", None) not in self._pending_tasks:
                self._task_queue.insert(0, ("FULL_SYNC", None))
                self._pending_tasks.add(("FULL_SYNC", None))
                print("백그라운드 전체 동기화 요청됨.")

    def _get_month_tuple(self, base_date, days_delta):
        target_date = base_date + datetime.timedelta(days=days_delta)
        return ('month', (target_date.year, target_date.month))

    def stop(self):
        self._is_running = False
        self.resume_sync()

    def run(self):
        print("지능형 캐싱 매니저 스레드가 시작되었습니다.")
        while self._is_running:
            task_type, task_data = None, None
            with QMutexLocker(self._mutex):
                if self._task_queue:
                    task_type, task_data = self._task_queue.pop(0)
                    self._pending_tasks.remove((task_type, task_data))
            if task_type == "month":
                self._wait_if_paused()
                if not self._is_running: break
                year, month = task_data
                print(f"백그라운드 캐싱 수행: {year}년 {month}월")
                events = self.data_manager._fetch_events_from_providers(year, month)
                if events is not None:
                    self.data_manager.event_cache[task_data] = events
                    self.data_manager.data_updated.emit(year, month)
                    self._manage_cache_size()
                time.sleep(0.5)
            elif task_type == "FULL_SYNC":
                self._perform_full_sync()
            else:
                time.sleep(1)
        print("지능형 캐싱 매니저 스레드가 종료되었습니다.")
        self.finished.emit()

    def _perform_full_sync(self):
        print("백그라운드 전체 동기화 시작...")
        with QMutexLocker(self._mutex):
            cached_months = list(self.data_manager.event_cache.keys())
            if not cached_months: return
            if self._last_viewed_month:
                y, m = self._last_viewed_month
                cached_months.sort(key=lambda t: abs((t[0] - y) * 12 + (t[1] - m)))
        for year, month in cached_months:
            self._wait_if_paused()
            if not self._is_running: break
            print(f"동기화 중: {year}년 {month}월")
            events = self.data_manager._fetch_events_from_providers(year, month)
            if events is not None:
                self.data_manager.event_cache[(year, month)] = events
                self.data_manager.data_updated.emit(year, month)
            time.sleep(0.2)
        if self._is_running:
            print("자동 동기화 완료.")

    def _manage_cache_size(self):
        with QMutexLocker(self._mutex):
            while len(self.data_manager.event_cache) > self.MAX_CACHE_SIZE:
                if self._last_viewed_month is None: break
                farthest_month = max(self.data_manager.event_cache.keys(), 
                                     key=lambda t: abs((t[0] - self._last_viewed_month[0]) * 12 + (t[1] - self._last_viewed_month[1])))
                if farthest_month:
                    print(f"캐시 용량 초과. 가장 먼 항목 제거: {farthest_month}")
                    del self.data_manager.event_cache[farthest_month]
                else: break

    def pause_sync(self):
        self._activity_lock.lock()
        self._pause_requested = True
        print("백그라운드 작업 일시정지 요청됨.")

    def resume_sync(self):
        if self._pause_requested:
            self._pause_requested = False
            self._activity_lock.unlock()
            self._resume_condition.wakeAll()
            print("백그라운드 작업 재개됨.")

    def _wait_if_paused(self):
        locker = QMutexLocker(self._activity_lock)
        while self._pause_requested:
            print("사용자 활동으로 인해 백그라운드 작업 대기 중...")
            self._resume_condition.wait(self._activity_lock)
        locker.unlock()

class DataManager(QObject):
    data_updated = pyqtSignal(int, int)

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
        self.caching_thread.finished.connect(self.caching_thread.quit)
        self.caching_thread.finished.connect(self.caching_manager.deleteLater)
        self.caching_thread.finished.connect(self.caching_thread.deleteLater)
        self.caching_thread.start()
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.request_full_sync)
        self.update_sync_timer()
        try:
            self.google_provider = GoogleCalendarProvider(settings)
            if self.google_provider._get_service_for_current_thread():
                 self.providers.append(self.google_provider)
        except Exception as e: print(f"Google Provider 생성 중 오류 발생: {e}")
        try:
            local_provider = LocalCalendarProvider(settings)
            self.providers.append(local_provider)
        except Exception as e: print(f"Local Provider 생성 중 오류 발생: {e}")

    def update_sync_timer(self):
        interval_minutes = self.settings.get("sync_interval_minutes", 5)
        if interval_minutes > 0:
            self.sync_timer.start(interval_minutes * 60 * 1000)
            print(f"자동 동기화 타이머가 설정되었습니다. 주기: {interval_minutes}분")
        else:
            self.sync_timer.stop()
            print("자동 동기화가 비활성화되었습니다.")

    def request_full_sync(self):
        self.caching_manager.request_full_sync()

    def stop_caching_thread(self):
        if self.caching_thread and self.caching_thread.isRunning():
            self.caching_manager.stop()
            self.caching_thread.quit()
            self.caching_thread.wait()

    @contextmanager
    def user_action_priority(self):
        self.caching_manager.pause_sync()
        try:
            yield
        finally:
            self.caching_manager.resume_sync()

    def load_cache_from_file(self):
        if not os.path.exists(self.cache_file): return
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.event_cache = {tuple(map(int, k.split('-'))): v for k, v in json.load(f).items()}
        except Exception as e: print(f"캐시 파일 읽기 오류: {e}")

    def save_cache_to_file(self):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({f"{k[0]}-{k[1]}": v for k, v in self.event_cache.items()}, f, ensure_ascii=False, indent=4)
        except Exception as e: print(f"캐시 파일 저장 오류: {e}")

    def _fetch_events_from_providers(self, year, month):
        all_events = []
        _, num_days = calendar.monthrange(year, month)
        start_date, end_date = datetime.date(year, month, 1), datetime.date(year, month, num_days)
        for provider in self.providers:
            try:
                events = provider.get_events(start_date, end_date)
                if events is not None: all_events.extend(events)
            except Exception as e:
                print(f"'{type(provider).__name__}' 이벤트 조회 오류: {e}")
        return all_events

    def get_events(self, year, month):
        cache_key = (year, month)
        direction = "none"
        if self.last_requested_month:
            if (year, month) > self.last_requested_month: direction = "forward"
            elif (year, month) < self.last_requested_month: direction = "backward"
        self.last_requested_month = cache_key
        self.caching_manager.request_caching_around(year, month, direction)
        return self.event_cache.get(cache_key, [])

    def get_all_calendars(self):
        all_calendars = []
        for provider in self.providers:
            if hasattr(provider, 'get_calendars'):
                try:
                    all_calendars.extend(provider.get_calendars())
                except Exception as e:
                    print(f"'{type(provider).__name__}'에서 캘린더 목록을 가져오는 중 오류 발생: {e}")
        return all_calendars

    def add_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                if provider.add_event(event_data):
                    start_str = event_data['body']['start'].get('date') or event_data['body']['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache: del self.event_cache[cache_key]
                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False
    
    def update_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                if provider.update_event(event_data):
                    start_str = event_data['body']['start'].get('date') or event_data['body']['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache: del self.event_cache[cache_key]
                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False

    def delete_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if type(provider).__name__ == provider_name:
                if provider.delete_event(event_data):
                    start_str = event_data['body']['start'].get('date') or event_data['body']['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache: del self.event_cache[cache_key]
                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False

    def load_initial_month(self):
        print("초기 데이터 로딩을 요청합니다...")
        today = datetime.date.today()
        self.get_events(today.year, today.month)
