# data_manager.py
import datetime
import calendar
import json
import os
import time
import sqlite3
from contextlib import contextmanager
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer, QWaitCondition

from auth_manager import AuthManager # AuthManager 임포트
from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider
from config import (DB_FILE, MAX_CACHE_SIZE, DEFAULT_SYNC_INTERVAL, 
                    GOOGLE_CALENDAR_PROVIDER_NAME, LOCAL_CALENDAR_PROVIDER_NAME,
                    DEFAULT_EVENT_COLOR)
# ... (CachingManager 클래스는 변경 없음) ...
class CachingManager(QObject):
    finished = pyqtSignal()
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
                    self.data_manager.event_cache[(year, month)] = events
                    self.data_manager._save_month_to_cache_db(year, month, events)
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
                self.data_manager._save_month_to_cache_db(year, month, events)
                self.data_manager.data_updated.emit(year, month)
            time.sleep(0.2)
        if self._is_running:
            print("자동 동기화 완료.")

    def _manage_cache_size(self):
        with QMutexLocker(self._mutex):
            today = datetime.date.today()
            current_month = (today.year, today.month)
            prev_month_date = today.replace(day=1) - datetime.timedelta(days=1)
            prev_month = (prev_month_date.year, prev_month_date.month)
            next_month_date = (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            next_month = (next_month_date.year, next_month_date.month)
            
            protected_months = {current_month, prev_month, next_month}
            
            while len(self.data_manager.event_cache) > MAX_CACHE_SIZE:
                if self._last_viewed_month is None: break
                
                candidates = {
                    month: abs((month[0] - self._last_viewed_month[0]) * 12 + (month[1] - self._last_viewed_month[1]))
                    for month in self.data_manager.event_cache.keys() if month not in protected_months
                }
                if not candidates: break
                farthest_month = max(candidates, key=candidates.get)
                print(f"월간 캐시 용량 초과. 가장 먼 항목 제거: {farthest_month}")
                del self.data_manager.event_cache[farthest_month]
                self.data_manager._remove_month_from_cache_db(farthest_month[0], farthest_month[1])

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
    calendar_list_changed = pyqtSignal()
    event_completion_changed = pyqtSignal() # 완료 상태 변경 시그널 추가

    def get_color_for_calendar(self, cal_id):
        """특정 캘린더 ID에 대한 현재 색상 설정을 빠르게 반환합니다."""
        custom_colors = self.settings.get("calendar_colors", {})
        if cal_id in custom_colors:
            return custom_colors[cal_id]

        if not hasattr(self, '_default_color_map_cache') or self._default_color_map_cache is None:
            all_calendars = self.get_all_calendars() # 캐시된 목록을 사용하므로 빠름
            self._default_color_map_cache = {cal['id']: cal.get('backgroundColor', DEFAULT_EVENT_COLOR) for cal in all_calendars}
        
        return self._default_color_map_cache.get(cal_id, DEFAULT_EVENT_COLOR)

    def __init__(self, settings, start_timer=True, load_cache=True):
        super().__init__()
        self.settings = settings
        self.auth_manager = AuthManager()
        self.auth_manager.auth_state_changed.connect(self.on_auth_state_changed)

        self.event_cache = {}
        self.completed_event_ids = set() 
        
        # ▼▼▼ [수정] 캐시 변수 2개 추가 ▼▼▼
        self.calendar_list_cache = None
        self._default_color_map_cache = None
        # ▲▲▲ 여기까지 수정 ▲▲▲

        if load_cache:
            self._init_cache_db()
            self._load_cache_from_db()
            self._init_completed_events_db()
            self._load_completed_event_ids()
        
        self.last_requested_month = None
        self.providers = []
        self.caching_thread = QThread()
        self.caching_manager = CachingManager(self)
        self.caching_manager.moveToThread(self.caching_thread)
        self.caching_thread.started.connect(self.caching_manager.run)
        self.caching_thread.finished.connect(self.caching_thread.quit)
        self.caching_manager.finished.connect(self.caching_manager.deleteLater)
        self.caching_thread.finished.connect(self.caching_thread.deleteLater)
        self.caching_thread.start()
        
        if start_timer:
            self.sync_timer = QTimer(self)
            self.sync_timer.timeout.connect(self.request_full_sync)
            self.update_sync_timer()
        
        self.setup_providers()


    def _init_completed_events_db(self):
        """완료된 이벤트 ID 저장을 위한 DB 테이블을 생성합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS completed_events (
                        event_id TEXT PRIMARY KEY
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"완료 이벤트 DB 테이블 초기화 중 오류 발생: {e}")

    def _load_completed_event_ids(self):
        """DB에서 완료된 이벤트 ID 목록을 로드하여 집합에 저장합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event_id FROM completed_events")
                self.completed_event_ids = {row[0] for row in cursor.fetchall()}
            print(f"DB에서 {len(self.completed_event_ids)}개의 완료된 이벤트 상태를 로드했습니다.")
        except sqlite3.Error as e:
            print(f"DB에서 완료 이벤트 로드 중 오류 발생: {e}")

    def is_event_completed(self, event_id):
        """주어진 이벤트 ID가 완료되었는지 확인합니다."""
        return event_id in self.completed_event_ids

    def mark_event_as_completed(self, event_id):
        """이벤트를 완료 상태로 표시하고 DB에 저장합니다."""
        if event_id in self.completed_event_ids:
            return
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO completed_events (event_id) VALUES (?)", (event_id,))
                conn.commit()
            self.completed_event_ids.add(event_id)
            self.event_completion_changed.emit() # UI 즉시 갱신
            print(f"이벤트 {event_id}를 완료 처리했습니다.")
        except sqlite3.Error as e:
            print(f"이벤트 완료 처리 중 DB 오류 발생: {e}")

    def unmark_event_as_completed(self, event_id):
        """이벤트의 완료 상태를 해제하고 DB에서 삭제합니다."""
        if event_id not in self.completed_event_ids:
            return
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM completed_events WHERE event_id = ?", (event_id,))
                conn.commit()
            self.completed_event_ids.discard(event_id)
            self.event_completion_changed.emit() # UI 즉시 갱신
            print(f"이벤트 {event_id}를 진행 중으로 변경했습니다.")
        except sqlite3.Error as e:
            print(f"이벤트 진행 중 처리 중 DB 오류 발생: {e}")


    def _init_cache_db(self):
        """캐시 저장을 위한 DB 테이블을 생성합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS event_cache (
                        year INTEGER NOT NULL,
                        month INTEGER NOT NULL,
                        events_json TEXT NOT NULL,
                        PRIMARY KEY (year, month)
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"캐시 DB 테이블 초기화 중 오류 발생: {e}")

    def setup_providers(self):
        """인증 상태에 따라 Provider 목록을 설정합니다."""
        self.providers = []
        # Google Provider는 로그인 상태일 때만 추가
        if self.auth_manager.is_logged_in():
            try:
                google_provider = GoogleCalendarProvider(self.settings, self.auth_manager)
                self.providers.append(google_provider)
            except Exception as e:
                print(f"Google Provider 생성 중 오류 발생: {e}")
        
        # Local Provider는 항상 추가
        try:
            local_provider = LocalCalendarProvider(self.settings)
            self.providers.append(local_provider)
        except Exception as e:
            print(f"Local Provider 생성 중 오류 발생: {e}")

    def on_auth_state_changed(self):
        """로그인/로그아웃 시 호출됩니다."""
        print("인증 상태 변경 감지. Provider를 재설정하고 데이터를 새로고침합니다.")
        self.setup_providers()
        
        # ▼▼▼ [수정] 캐시 초기화 2줄 추가 ▼▼▼
        self.calendar_list_cache = None
        if hasattr(self, '_default_color_map_cache'):
            del self._default_color_map_cache
        # ▲▲▲ 여기까지 수정 ▲▲▲

        self.calendar_list_changed.emit()
        
        # 메모리와 DB의 모든 캐시를 삭제
        self.event_cache.clear()
        self.clear_all_cache_db()

        # 현재 보고 있는 달의 데이터를 새로고침
        if self.last_requested_month:
            year, month = self.last_requested_month
            self.get_events(year, month) # 데이터 다시 요청
        self.request_full_sync() # 전체 동기화도 요청

    def update_sync_timer(self):
        interval_minutes = self.settings.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL)
        if interval_minutes > 0:
            self.sync_timer.start(interval_minutes * 60 * 1000)
            print(f"자동 동기화 타이머가 설정되었습니다. 주기: {interval_minutes}분")
        else:
            self.sync_timer.stop()
            print("자동 동기화가 비활성화되었습니다.")

    def request_full_sync(self):
        self.caching_manager.request_full_sync()

    def notify_date_changed(self, new_date, direction="none"):
        """UI에서 날짜 변경이 있을 때 호출되어 슬라이딩 캐시를 유발합니다."""
        self.last_requested_month = (new_date.year, new_date.month)
        self.caching_manager.request_caching_around(new_date.year, new_date.month, direction)

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

    def _load_cache_from_db(self):
        """DB에서 월간 이벤트 캐시를 로드합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT year, month, events_json FROM event_cache")
                for year, month, events_json in cursor.fetchall():
                    self.event_cache[(year, month)] = json.loads(events_json)
            print(f"DB에서 {len(self.event_cache)}개의 월간 캐시를 로드했습니다.")
        except sqlite3.Error as e:
            print(f"DB에서 캐시 로드 중 오류 발생: {e}")

    def _save_month_to_cache_db(self, year, month, events):
        """특정 월의 이벤트 캐시를 DB에 저장(덮어쓰기)합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO event_cache (year, month, events_json)
                    VALUES (?, ?, ?)
                """, (year, month, json.dumps(events)))
                conn.commit()
        except sqlite3.Error as e:
            print(f"DB에 월간 캐시 저장 중 오류 발생: {e}")

    def _remove_month_from_cache_db(self, year, month):
        """특정 월의 캐시를 DB에서 삭제합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM event_cache WHERE year = ? AND month = ?", (year, month))
                conn.commit()
        except sqlite3.Error as e:
            print(f"DB에서 월간 캐시 삭제 중 오류 발생: {e}")

    def clear_all_cache_db(self):
        """DB의 모든 캐시를 삭제합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM event_cache")
                conn.commit()
            print("DB의 모든 이벤트 캐시를 삭제했습니다.")
        except sqlite3.Error as e:
            print(f"DB 캐시 전체 삭제 중 오류 발생: {e}")

    def _fetch_events_from_providers(self, year, month):
        all_events = []
        _, num_days = calendar.monthrange(year, month)
        start_date, end_date = datetime.date(year, month, 1), datetime.date(year, month, num_days)
        
        # --- ▼▼▼ [추가] 색상 적용을 위한 정보 미리 준비 ▼▼▼ ---
        all_calendars = self.get_all_calendars()
        custom_colors = self.settings.get("calendar_colors", {})
        default_color_map = {cal['id']: cal.get('backgroundColor', DEFAULT_EVENT_COLOR) for cal in all_calendars}
        # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

        for provider in self.providers:
            try:
                events = provider.get_events(start_date, end_date)
                if events is not None:
                    # --- ▼▼▼ [추가] 가져온 이벤트에 즉시 색상 적용 ▼▼▼ ---
                    for event in events:
                        cal_id = event.get('calendarId')
                        if cal_id:
                            default_color = default_color_map.get(cal_id, DEFAULT_EVENT_COLOR)
                            event['color'] = custom_colors.get(cal_id, default_color)
                    # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---
                    all_events.extend(events)
            except Exception as e:
                print(f"'{type(provider).__name__}' 이벤트 조회 오류: {e}")
        return all_events

    def force_sync_month(self, year, month):
        """
        캐시를 무시하고 특정 월의 데이터를 즉시 동기화한 후 UI를 업데이트합니다.
        """
        print(f"현재 보이는 월({year}년 {month}월)을 강제로 즉시 동기화합니다...")
        
        # 1. Provider로부터 최신 데이터 가져오기
        events = self._fetch_events_from_providers(year, month)
        
        if events is not None:
            # 2. 메모리 캐시와 DB 캐시 업데이트
            self.event_cache[(year, month)] = events
            self._save_month_to_cache_db(year, month, events)
            
            # 3. UI에 데이터가 변경되었음을 즉시 알림
            self.data_updated.emit(year, month)
            print("강제 동기화 완료. UI 업데이트 신호를 보냈습니다.")
        else:
            print("강제 동기화 실패: Provider로부터 데이터를 가져오지 못했습니다.")

    def get_events(self, year, month):
        cache_key = (year, month)
        direction = "none"
        if self.last_requested_month:
            if (year, month) > self.last_requested_month: direction = "forward"
            elif (year, month) < self.last_requested_month: direction = "backward"
        self.last_requested_month = cache_key
        
        if cache_key not in self.event_cache:
            self.caching_manager.request_caching_around(year, month, direction)

        return self.event_cache.get(cache_key, [])

    def get_events_for_period(self, start_date, end_date):
        """주어진 기간(start_date, end_date 포함)에 걸친 모든 이벤트를 반환합니다."""
        all_events = []
        
        # 기간에 포함되는 모든 월을 찾습니다.
        months_to_check = set()
        current_date = start_date
        while current_date <= end_date:
            months_to_check.add((current_date.year, current_date.month))
            # 다음 달로 이동
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)

        # 각 월의 이벤트를 가져와서 기간에 포함되는지 확인합니다.
        for year, month in months_to_check:
            monthly_events = self.get_events(year, month)
            for event in monthly_events:
                try:
                    start_info = event.get('start', {})
                    end_info = event.get('end', {})
                    
                    start_str = start_info.get('date') or start_info.get('dateTime', '')[:10]
                    # Google Calendar 종일 일정의 end.date는 실제 종료일 + 1일이므로 -1일 해줍니다.
                    end_str = end_info.get('date') or end_info.get('dateTime', '')[:10]
                    
                    event_start_date = datetime.date.fromisoformat(start_str)
                    event_end_date = datetime.date.fromisoformat(end_str)
                    if 'date' in end_info:
                        event_end_date -= datetime.timedelta(days=1)

                    # 이벤트 기간이 주어진 기간과 겹치는지 확인
                    if not (event_end_date < start_date or event_start_date > end_date):
                        all_events.append(event)
                except (ValueError, TypeError) as e:
                    print(f"이벤트 날짜 파싱 오류: {e}, 이벤트: {event.get('summary')}")
                    continue
        
        # 중복 제거 (다른 월에서 동일 이벤트가 포함될 수 있음)
        unique_events = {e['id']: e for e in all_events}.values()
        return list(unique_events)

    def get_all_calendars(self):
        if self.calendar_list_cache is not None:
            return self.calendar_list_cache

        all_calendars = []
        for provider in self.providers:
            if hasattr(provider, 'get_calendars'):
                try:
                    all_calendars.extend(provider.get_calendars())
                except Exception as e:
                    print(f"'{type(provider).__name__}'에서 캘린더 목록을 가져오는 중 오류 발생: {e}")
        
        self.calendar_list_cache = all_calendars
        return all_calendars


    def add_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                new_event = provider.add_event(event_data)
                if new_event:
                    if 'provider' not in new_event:
                        new_event['provider'] = provider_name

                    # --- ▼▼▼ [추가] 색상 적용 로직 중앙화 ▼▼▼ ---
                    cal_id = new_event.get('calendarId')
                    if cal_id:
                        all_calendars = self.get_all_calendars()
                        cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
                        default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
                        
                        new_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
                        # 이모지는 여기서 처리하지 않음 (필요 시 추가)
                    # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

                    start_str = new_event['start'].get('date') or new_event['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    
                    if cache_key in self.event_cache:
                        self.event_cache[cache_key].append(new_event)
                    else:
                        self.event_cache[cache_key] = [new_event]
                    
                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False
    
    def update_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                updated_event = provider.update_event(event_data)
                if updated_event:
                    if 'provider' not in updated_event:
                        updated_event['provider'] = provider_name

                    # --- ▼▼▼ [추가] 색상 적용 로직 중앙화 ▼▼▼ ---
                    cal_id = updated_event.get('calendarId')
                    if cal_id:
                        all_calendars = self.get_all_calendars()
                        cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
                        default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR

                        updated_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
                        # 이모지는 여기서 처리하지 않음 (필요 시 추가)
                    # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

                    start_str = updated_event['start'].get('date') or updated_event['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    
                    if cache_key in self.event_cache:
                        event_id = updated_event.get('id')
                        self.event_cache[cache_key] = [
                            event for event in self.event_cache[cache_key] if event.get('id') != event_id
                        ]
                        self.event_cache[cache_key].append(updated_event)
                    else:
                        self.event_cache[cache_key] = [updated_event]

                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False

    def delete_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                if provider.delete_event(event_data):
                    event_body = event_data.get('body', event_data)
                    event_id_to_delete = event_body.get('id')
                    
                    # 완료 목록에서도 삭제
                    self.unmark_event_as_completed(event_id_to_delete)

                    start_str = event_body['start'].get('date') or event_body['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)

                    if cache_key in self.event_cache:
                        self.event_cache[cache_key] = [
                            event for event in self.event_cache[cache_key] if event.get('id') != event_id_to_delete
                        ]

                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False

    def load_initial_month(self):
        print("초기 데이터 로딩을 요청합니다...")
        today = datetime.date.today()
        self.get_events(today.year, today.month)

    def search_events(self, query):
        """모든 Provider에서 이벤트를 검색하고 결과를 통합하여 반환합니다."""
        all_results = []
        for provider in self.providers:
            try:
                results = provider.search_events(query)
                if results:
                    all_results.extend(results)
            except Exception as e:
                print(f"'{type(provider).__name__}' 이벤트 검색 오류: {e}")
        
        # ID를 기준으로 중복 제거
        unique_results = list({event['id']: event for event in all_results}.values())
        
        # 중앙에서 색상 적용
        self._apply_colors_to_events(unique_results)

        # 시작 시간 순으로 정렬
        def get_start_time(event):
            start = event.get('start', {})
            return start.get('dateTime') or start.get('date')
        unique_results.sort(key=get_start_time)
        
        return unique_results
