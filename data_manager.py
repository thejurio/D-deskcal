# data_manager.py
import datetime
import json
import time
import sqlite3
import logging
from collections import deque, OrderedDict
from contextlib import contextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil import parser as dateutil_parser
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer, QWaitCondition

from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider
from config import (DB_FILE, MAX_CACHE_SIZE, DEFAULT_SYNC_INTERVAL, 
                    GOOGLE_CALENDAR_PROVIDER_NAME, DEFAULT_EVENT_COLOR, DEFAULT_NOTIFICATIONS_ENABLED, 
                    DEFAULT_NOTIFICATION_MINUTES, DEFAULT_ALL_DAY_NOTIFICATION_ENABLED,
                    DEFAULT_ALL_DAY_NOTIFICATION_TIME)

logger = logging.getLogger(__name__)

def get_month_view_dates(year, month, start_day_of_week):
    """월간 뷰에 표시될 모든 날짜(이전/현재/다음 달 포함)의 시작일과 종료일을 반환합니다."""
    first_day_of_month = datetime.date(year, month, 1)
    
    if start_day_of_week == 6: # 일요일 시작
        offset = (first_day_of_month.weekday() + 1) % 7
    else: # 월요일 시작
        offset = first_day_of_month.weekday()
        
    start_date = first_day_of_month - datetime.timedelta(days=offset)
    end_date = start_date + datetime.timedelta(days=41)
    return start_date, end_date

class PriorityTaskQueue:
    def __init__(self):
        # 1: P1 (즉시 실행), 2: P2 (백그라운드 예측), 3: P3 (저우선순위 캐싱)
        self._queues = {1: deque(), 2: deque(), 3: deque()}
        self._pending_tasks = set()
        self._mutex = QMutex()

    def add_task(self, priority, task_data):
        with QMutexLocker(self._mutex):
            if task_data not in self._pending_tasks:
                self._queues[priority].append(task_data)
                self._pending_tasks.add(task_data)
                return True
            return False

    def get_next_task(self):
        with QMutexLocker(self._mutex):
            for p in sorted(self._queues.keys()):
                if self._queues[p]:
                    task_data = self._queues[p].popleft()
                    self._pending_tasks.remove(task_data)
                    return task_data
            return None

    def interrupt_and_add_high_priority(self, task_data):
        with QMutexLocker(self._mutex):
            # P1 큐의 다른 항목들은 제거 (현재 뷰에 집중)
            if self._queues[1]:
                self._pending_tasks -= set(self._queues[1])
                self._queues[1].clear()

            if task_data not in self._pending_tasks:
                self._queues[1].appendleft(task_data) # 최우선으로 추가
                self._pending_tasks.add(task_data)

    def __len__(self):
        with QMutexLocker(self._mutex):
            return len(self._pending_tasks)

class CachingManager(QObject):
    finished = pyqtSignal()
    # [수정] CachingManager는 이제 동기화 상태를 직접 알리지 않음. DataManager가 관리.

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self._is_running = True
        self._mutex = QMutex()
        self._task_queue = PriorityTaskQueue()
        self._last_viewed_month = None
        self._activity_lock = QMutex()
        self._pause_requested = False
        self._resume_condition = QWaitCondition()

    def request_caching_around(self, year, month):
        with QMutexLocker(self._mutex):
            self._last_viewed_month = (year, month)
            current_month_task = ('month', (year, month))

            # 1. 현재 월을 P1(최우선)으로 설정하고, 다른 P1 작업은 모두 취소
            self._task_queue.interrupt_and_add_high_priority(current_month_task)
            logger.info(f"P1 작업 설정: {year}년 {month}월 즉시 동기화")

            # 2. 주변 월을 P2, P3 우선순위로 추가
            base_date = datetime.date(year, month, 15)
            # P2: M-1, M+1
            for days in [-31, 31]:
                task_data = self._get_month_tuple(base_date, days)
                if task_data[1] not in self.data_manager.event_cache:
                    self._task_queue.add_task(2, task_data)
            # P3: M-2, M+2
            for days in [-62, 62]:
                task_data = self._get_month_tuple(base_date, days)
                if task_data[1] not in self.data_manager.event_cache:
                    self._task_queue.add_task(3, task_data)

            logger.info(f"새로운 캐싱 계획 수립: {year}년 {month}월 주변. 대기열: {len(self._task_queue)}개")

    def request_current_month_sync(self):
        with QMutexLocker(self._mutex):
            if self._last_viewed_month:
                # 자동 동기화는 P2 우선순위로 처리하여 사용자 요청에 방해되지 않도록 함
                task_data = ("month", self._last_viewed_month)
                self._task_queue.add_task(2, task_data)
                logger.info(f"자동 동기화 요청됨 (P2): {self._last_viewed_month}")

    def _get_month_tuple(self, base_date, days_delta):
        target_date = base_date + datetime.timedelta(days=days_delta)
        return ('month', (target_date.year, target_date.month))

    def stop(self):
        self._is_running = False
        self.resume_sync()

    def run(self):
        logger.info("지능형 캐싱 매니저 스레드가 시작되었습니다.")
        while self._is_running:
            task_data = self._task_queue.get_next_task()

            if task_data:
                self._wait_if_paused()
                if not self._is_running: break

                task_type, (year, month) = task_data
                
                is_p1_task = (year, month) == self._last_viewed_month
                action_text = "P1 동기화" if is_p1_task else "백그라운드 캐싱"
                logger.info(f"{action_text} 수행: {year}년 {month}월")

                # DataManager를 통해 동기화 상태 알림
                self.data_manager.set_sync_state(True, year, month)

                events = self.data_manager._fetch_events_from_providers(year, month)
                
                # 작업이 중단되지 않았을 경우에만 캐시 업데이트
                if self._is_running:
                    if events is not None:
                        self.data_manager.event_cache[(year, month)] = events
                        self.data_manager._save_month_to_cache_db(year, month, events)
                        self.data_manager.data_updated.emit(year, month)
                        if not is_p1_task:
                            self._manage_cache_size()
                    
                    # DataManager를 통해 동기화 상태 알림
                    self.data_manager.set_sync_state(False, year, month)

                time.sleep(0.2 if is_p1_task else 0.5)
            else:
                time.sleep(1)
        logger.info("지능형 캐싱 매니저 스레드가 종료되었습니다.")
        self.finished.emit()

    def _manage_cache_size(self):
        with QMutexLocker(self._mutex):
            today = datetime.date.today()
            current_month = (today.year, today.month)

            protected_months = {current_month}
            if self._last_viewed_month:
                protected_months.add(self._last_viewed_month)

            base_date = today.replace(day=15)
            for i in range(1, 3): # 현재 기준 M+-2 보호
                protected_months.add((base_date + datetime.timedelta(days=i*31)).timetuple()[:2])
                protected_months.add((base_date - datetime.timedelta(days=i*31)).timetuple()[:2])

            while len(self.data_manager.event_cache) > MAX_CACHE_SIZE:
                if self._last_viewed_month is None: break

                candidates = {
                    month: abs((month[0] - self._last_viewed_month[0]) * 12 + (month[1] - self._last_viewed_month[1]))
                    for month in self.data_manager.event_cache.keys() if month not in protected_months
                }
                if not candidates: break

                farthest_month = max(candidates, key=candidates.get)
                logger.info(f"월간 캐시 용량 초과. 가장 먼 항목 제거: {farthest_month}")
                del self.data_manager.event_cache[farthest_month]
                self.data_manager._remove_month_from_cache_db(farthest_month[0], farthest_month[1])

    def pause_sync(self):
        self._activity_lock.lock()
        self._pause_requested = True
        logger.info("백그라운드 작업 일시정지 요청됨.")

    def resume_sync(self):
        if self._pause_requested:
            self._pause_requested = False
            self._activity_lock.unlock()
            self._resume_condition.wakeAll()
            logger.info("백그라운드 작업 재개됨.")

    def _wait_if_paused(self):
        locker = QMutexLocker(self._activity_lock)
        while self._pause_requested:
            logger.info("사용자 활동으로 인해 백그라운드 작업 대기 중...")
            self._resume_condition.wait(self._activity_lock)
        locker.unlock()

class CalendarListFetcher(QObject):
    calendars_fetched = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, providers):
        super().__init__()
        self.providers = providers
        self._is_running = True

    def run(self):
        logger.info("캘린더 목록 비동기 로더 스레드 시작...")
        all_calendars = []
        for provider in self.providers:
            if not self._is_running: break
            if hasattr(provider, 'get_calendars'):
                try:
                    all_calendars.extend(provider.get_calendars())
                except Exception as e:
                    logger.error(f"'{type(provider).__name__}'에서 캘린더 목록을 가져오는 중 오류 발생", exc_info=True)
        
        if self._is_running:
            self.calendars_fetched.emit(all_calendars)
        
        self.finished.emit()
        logger.info("캘린더 목록 비동기 로더 스레드 종료.")

    def stop(self):
        self._is_running = False

class DataManager(QObject):
    data_updated = pyqtSignal(int, int)
    calendar_list_changed = pyqtSignal()
    event_completion_changed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    notification_triggered = pyqtSignal(str, str)
    # [수정] is_syncing 상태, 년, 월 정보를 함께 전달
    sync_state_changed = pyqtSignal(bool, int, int) 

    def __init__(self, settings, auth_manager, start_timer=True, load_cache=True):
        super().__init__()
        self.settings = settings
        self.auth_manager = auth_manager
        self.auth_manager.auth_state_changed.connect(self.on_auth_state_changed)

        # [수정] is_syncing을 월별로 관리하는 딕셔너리로 변경
        self.syncing_months = {}
        self.event_cache = {}
        self.completed_event_ids = set()
        self.notified_event_ids = set()
        
        self.calendar_list_cache = None
        self._default_color_map_cache = None
        
        # [삭제] ImmediateSyncWorker 관련 멤버 변수 삭제
        
        self.calendar_fetch_thread = None
        self.calendar_fetcher = None

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
            self.update_sync_timer()

            self.notification_timer = QTimer(self)
            self.notification_timer.timeout.connect(self._check_for_notifications)
            self.notification_timer.start(60 * 1000)
        
        self.setup_providers()

    # [추가] CachingManager가 호출할 동기화 상태 설정 메서드
    def set_sync_state(self, is_syncing, year, month):
        self.syncing_months[(year, month)] = is_syncing
        self.sync_state_changed.emit(is_syncing, year, month)

    def is_month_syncing(self, year, month):
        return self.syncing_months.get((year, month), False)

    def report_error(self, message):
        self.error_occurred.emit(message)

    def get_color_for_calendar(self, cal_id):
        custom_colors = self.settings.get("calendar_colors", {})
        if cal_id in custom_colors:
            return custom_colors[cal_id]

        if not hasattr(self, '_default_color_map_cache') or self._default_color_map_cache is None:
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            self._default_color_map_cache = {cal['id']: cal.get('backgroundColor', DEFAULT_EVENT_COLOR) for cal in all_calendars}
        
        return self._default_color_map_cache.get(cal_id, DEFAULT_EVENT_COLOR)

    def _init_completed_events_db(self):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS completed_events (event_id TEXT PRIMARY KEY)")
                conn.commit()
        except sqlite3.Error as e:
            msg = "완료 이벤트 데이터베이스를 초기화하는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def _load_completed_event_ids(self):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event_id FROM completed_events")
                self.completed_event_ids = {row[0] for row in cursor.fetchall()}
            logger.info(f"DB에서 {len(self.completed_event_ids)}개의 완료된 이벤트 상태를 로드했습니다.")
        except sqlite3.Error as e:
            msg = "완료 이벤트 상태를 불러오는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def is_event_completed(self, event_id):
        return event_id in self.completed_event_ids

    def mark_event_as_completed(self, event_id):
        if event_id in self.completed_event_ids: return
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO completed_events (event_id) VALUES (?)", (event_id,))
                conn.commit()
            self.completed_event_ids.add(event_id)
            self.event_completion_changed.emit()
            logger.info(f"이벤트 {event_id}를 완료 처리했습니다.")
        except sqlite3.Error as e:
            msg = f"이벤트({event_id})를 완료 처리하는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def unmark_event_as_completed(self, event_id):
        if event_id not in self.completed_event_ids: return
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM completed_events WHERE event_id = ?", (event_id,))
                conn.commit()
            self.completed_event_ids.discard(event_id)
            self.event_completion_changed.emit()
            logger.info(f"이벤트 {event_id}를 진행 중으로 변경했습니다.")
        except sqlite3.Error as e:
            msg = f"이벤트({event_id})를 진행 중으로 변경하는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def _init_cache_db(self):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS event_cache (year INTEGER NOT NULL, month INTEGER NOT NULL, events_json TEXT NOT NULL, PRIMARY KEY (year, month))")
                conn.commit()
        except sqlite3.Error as e:
            msg = "캐시 데이터베이스를 초기화하는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def setup_providers(self):
        self.providers = []
        if self.auth_manager.is_logged_in():
            try:
                google_provider = GoogleCalendarProvider(self.settings, self.auth_manager)
                self.providers.append(google_provider)
            except Exception as e:
                logger.error("Google Provider 생성 중 오류 발생", exc_info=True)
        try:
            local_provider = LocalCalendarProvider(self.settings)
            self.providers.append(local_provider)
        except Exception as e:
            logger.error("Local Provider 생성 중 오류 발생", exc_info=True)

    def on_auth_state_changed(self):
        logger.info("인증 상태 변경 감지. Provider를 재설정하고 데이터를 새로고침합니다.")
        
        is_logging_out = not self.auth_manager.is_logged_in()
        
        self.setup_providers()
        self.calendar_list_cache = None
        self._default_color_map_cache = None
        
        if is_logging_out:
            logger.info("로그아웃 감지. Google 캘린더 관련 캐시를 삭제합니다.")
            for month_key, events in list(self.event_cache.items()):
                google_events = [e for e in events if e.get('provider') == GOOGLE_CALENDAR_PROVIDER_NAME]
                if google_events:
                    remaining_events = [e for e in events if e.get('provider') != GOOGLE_CALENDAR_PROVIDER_NAME]
                    self.event_cache[month_key] = remaining_events
                    self._save_month_to_cache_db(month_key[0], month_key[1], remaining_events)
            
        self.get_all_calendars(fetch_if_empty=True)
        
        self.calendar_list_changed.emit()
        if self.last_requested_month:
            year, month = self.last_requested_month
            self.data_updated.emit(year, month)
        else:
            today = datetime.date.today()
            self.data_updated.emit(today.year, today.month)

    def update_sync_timer(self):
        interval_minutes = self.settings.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL)
        if interval_minutes > 0:
            self.sync_timer.start(interval_minutes * 60 * 1000)
            logger.info(f"자동 동기화 타이머가 설정되었습니다. 주기: {interval_minutes}분")
        else:
            self.sync_timer.stop()
            logger.info("자동 동기화가 비활성화되었습니다.")

    def request_current_month_sync(self):
        self.caching_manager.request_current_month_sync()

    def notify_date_changed(self, new_date):
        self.last_requested_month = (new_date.year, new_date.month)
        self.caching_manager.request_caching_around(new_date.year, new_date.month)

    def stop_caching_thread(self):
        if hasattr(self, 'notification_timer'):
            self.notification_timer.stop()
        # [삭제] ImmediateSyncWorker 스레드 중지 로직 삭제
        if self.caching_thread is not None and self.caching_thread.isRunning():
            self.caching_manager.stop()
            self.caching_thread.quit()
            self.caching_thread.wait()
        if self.calendar_fetch_thread is not None and self.calendar_fetch_thread.isRunning():
            self.calendar_fetcher.stop()
            self.calendar_fetch_thread.quit()
            self.calendar_fetch_thread.wait()

    @contextmanager
    def user_action_priority(self):
        self.caching_manager.pause_sync()
        try:
            yield
        finally:
            self.caching_manager.resume_sync()

    def _load_cache_from_db(self):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT year, month, events_json FROM event_cache")
                for year, month, events_json in cursor.fetchall():
                    self.event_cache[(year, month)] = json.loads(events_json)
            logger.info(f"DB에서 {len(self.event_cache)}개의 월간 캐시를 로드했습니다.")
        except sqlite3.Error as e:
            msg = "데이터베이스에서 캐시를 불러오는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def _save_month_to_cache_db(self, year, month, events):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO event_cache (year, month, events_json) VALUES (?, ?, ?)", (year, month, json.dumps(events)))
                conn.commit()
        except sqlite3.Error as e:
            logger.error("DB에 월간 캐시 저장 중 오류 발생", exc_info=True)

    def _remove_month_from_cache_db(self, year, month):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM event_cache WHERE year = ? AND month = ?", (year, month))
                conn.commit()
        except sqlite3.Error as e:
            logger.error("DB에서 월간 캐시 삭제 중 오류 발생", exc_info=True)

    def _fetch_events_from_providers(self, year, month):
        all_events = []
        start_day_of_week = self.settings.get("start_day_of_week", 6)
        start_date, end_date = get_month_view_dates(year, month, start_day_of_week)
        
        all_calendars = self.get_all_calendars(fetch_if_empty=False)
        custom_colors = self.settings.get("calendar_colors", {})
        default_color_map = {cal['id']: cal.get('backgroundColor', DEFAULT_EVENT_COLOR) for cal in all_calendars}
        for provider in self.providers:
            try:
                # data_manager 자신을 provider에 넘겨주어 오류 보고가 가능하도록 함
                events = provider.get_events(start_date, end_date, self)
                if events is not None:
                    for event in events:
                        cal_id = event.get('calendarId')
                        if cal_id:
                            default_color = default_color_map.get(cal_id, DEFAULT_EVENT_COLOR)
                            event['color'] = custom_colors.get(cal_id, default_color)
                    all_events.extend(events)
            except Exception as e:
                msg = f"'{type(provider).__name__}'에서 이벤트를 가져오는 중 오류가 발생했습니다."
                logger.error(msg, exc_info=True)
                self.report_error(f"{msg}\n{e}")
        return all_events

    # [삭제] _run_immediate_sync, _on_immediate_sync_finished, _on_immediate_data_fetched 메서드 삭제

    def get_events(self, year, month):
        cache_key = (year, month)
        self.last_requested_month = cache_key
        
        # UI에 날짜 변경 알림 (P1 작업 요청)
        self.notify_date_changed(datetime.date(year, month, 1))
        
        # 캐시된 데이터가 있으면 즉시 반환
        return self.event_cache.get(cache_key, [])

    def force_sync_month(self, year, month):
        logger.info(f"현재 보이는 월({year}년 {month}월)을 강제로 즉시 동기화합니다...")
        self.caching_manager.request_caching_around(year, month)

    def get_events_for_period(self, start_date, end_date):
        all_events = []
        months_to_check = set()
        current_date = start_date
        while current_date <= end_date:
            months_to_check.add((current_date.year, current_date.month))
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
        for year, month in months_to_check:
            # [수정] get_events는 이제 비동기 요청만 트리거하므로, 직접 캐시를 확인
            monthly_events = self.event_cache.get((year, month), [])
            for event in monthly_events:
                try:
                    start_info = event.get('start', {})
                    end_info = event.get('end', {})
                    start_str = start_info.get('date') or start_info.get('dateTime', '')[:10]
                    end_str = end_info.get('date') or end_info.get('dateTime', '')[:10]
                    event_start_date = datetime.date.fromisoformat(start_str)
                    event_end_date = datetime.date.fromisoformat(end_str)
                    if 'date' in end_info:
                        event_end_date -= datetime.timedelta(days=1)
                    if not (event_end_date < start_date or event_start_date > end_date):
                        all_events.append(event)
                except (ValueError, TypeError) as e:
                    logger.warning(f"이벤트 날짜 파싱 오류: {e}, 이벤트: {event.get('summary')}")
                    continue
        unique_events = {e['id']: e for e in all_events}.values()
        return list(unique_events)

    def get_all_calendars(self, fetch_if_empty=True):
        if self.calendar_list_cache is not None:
            return self.calendar_list_cache

        if fetch_if_empty:
            self._fetch_calendars_async()
        
        return []

    def _fetch_calendars_async(self):
        if self.calendar_fetch_thread and self.calendar_fetch_thread.isRunning():
            return

        self.calendar_fetch_thread = QThread()
        self.calendar_fetcher = CalendarListFetcher(self.providers)
        self.calendar_fetcher.moveToThread(self.calendar_fetch_thread)

        self.calendar_fetcher.calendars_fetched.connect(self._on_calendars_fetched)
        self.calendar_fetch_thread.started.connect(self.calendar_fetcher.run)
        
        self.calendar_fetcher.finished.connect(self._on_calendar_thread_finished)
        
        self.calendar_fetch_thread.start()

    def _on_calendar_thread_finished(self):
        if self.calendar_fetch_thread is None: return
            
        self.calendar_fetch_thread.quit()
        if self.calendar_fetch_thread.isRunning():
            self.calendar_fetch_thread.wait()
            
        self.calendar_fetcher.deleteLater()
        self.calendar_fetch_thread.deleteLater()
        self.calendar_fetch_thread = None
        self.calendar_fetcher = None
        logger.info("캘린더 목록 스레드 정리 완료.")

    def _on_calendars_fetched(self, calendars):
        logger.info(f"{len(calendars)}개의 캘린더 목록을 비동기적으로 수신했습니다.")
        self.calendar_list_cache = calendars
        self._default_color_map_cache = None
        self.calendar_list_changed.emit()

    def add_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                new_event = provider.add_event(event_data, self)
                if new_event:
                    if 'provider' not in new_event: new_event['provider'] = provider_name
                    cal_id = new_event.get('calendarId')
                    if cal_id:
                        all_calendars = self.get_all_calendars(fetch_if_empty=False)
                        cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
                        default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
                        new_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
                    start_str = new_event['start'].get('date') or new_event['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    # P1 동기화 요청
                    self.force_sync_month(event_date.year, event_date.month)
                    return True
        return False
    
    def update_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                updated_event = provider.update_event(event_data, self)
                if updated_event:
                    if 'provider' not in updated_event: updated_event['provider'] = provider_name
                    cal_id = updated_event.get('calendarId')
                    if cal_id:
                        all_calendars = self.get_all_calendars(fetch_if_empty=False)
                        cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
                        default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
                        updated_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
                    start_str = updated_event['start'].get('date') or updated_event['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    # P1 동기화 요청
                    self.force_sync_month(event_date.year, event_date.month)
                    return True
        return False

    # In class DataManager, modify the delete_event method
    def delete_event(self, event_data, deletion_mode='all'):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                # Pass the deletion_mode to the provider
                if provider.delete_event(event_data, data_manager=self, deletion_mode=deletion_mode):
                    event_body = event_data.get('body', event_data)
                    event_id_to_delete = event_body.get('id')
                    self.unmark_event_as_completed(event_id_to_delete)

                    # For future and all deletions, we may need to sync more than one month,
                    # but for simplicity, we'll stick to syncing the start month for now.
                    start_str = event_body['start'].get('date') or event_body['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)

                    self.force_sync_month(event_date.year, event_date.month)
                    return True
        return False

    def load_initial_month(self):
        logger.info("초기 데이터 로딩을 요청합니다...")
        self.get_all_calendars(fetch_if_empty=True)
        today = datetime.date.today()
        self.get_events(today.year, today.month)

    def _apply_colors_to_events(self, events):
        if not events: return
        all_calendars = self.get_all_calendars(fetch_if_empty=False)
        custom_colors = self.settings.get("calendar_colors", {})
        default_color_map = {cal['id']: cal.get('backgroundColor', DEFAULT_EVENT_COLOR) for cal in all_calendars}
        for event in events:
            cal_id = event.get('calendarId')
            if cal_id:
                default_color = default_color_map.get(cal_id, DEFAULT_EVENT_COLOR)
                event['color'] = custom_colors.get(cal_id, default_color)

    def search_events(self, query):
        all_results = []
        for provider in self.providers:
            try:
                results = provider.search_events(query, self)
                if results:
                    all_results.extend(results)
            except Exception as e:
                msg = f"'{type(provider).__name__}'에서 이벤트를 검색하는 중 오류가 발생했습니다."
                logger.error(msg, exc_info=True)
                self.report_error(f"{msg}\n{e}")
        unique_results = list({event['id']: event for event in all_results}.values())
        self._apply_colors_to_events(unique_results)
        def get_start_time(event):
            start = event.get('start', {})
            return start.get('dateTime') or start.get('date')
        unique_results.sort(key=get_start_time)
        return unique_results

    def _check_for_notifications(self):
        if not self.settings.get("notifications_enabled", DEFAULT_NOTIFICATIONS_ENABLED):
            return

        minutes_before = self.settings.get("notification_minutes", DEFAULT_NOTIFICATION_MINUTES)
        now = datetime.datetime.now().astimezone()
        notification_start_time = now
        notification_end_time = now + datetime.timedelta(minutes=minutes_before)

        today = datetime.date.today()
        events_to_check = []
        
        current_month_events = self.event_cache.get((today.year, today.month), [])
        events_to_check.extend(current_month_events)
        
        next_month_date = today.replace(day=28) + datetime.timedelta(days=4)
        next_month_events = self.event_cache.get((next_month_date.year, next_month_date.month), [])
        events_to_check.extend(next_month_events)

        if self.settings.get("all_day_notification_enabled", DEFAULT_ALL_DAY_NOTIFICATION_ENABLED):
            notification_time_str = self.settings.get("all_day_notification_time", DEFAULT_ALL_DAY_NOTIFICATION_TIME)
            hour, minute = map(int, notification_time_str.split(':'))
            notification_time_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            today_str = today.strftime('%Y-%m-%d')
            all_day_events_today = [
                e for e in current_month_events 
                if e.get('start', {}).get('date') == today_str
            ]

            if now >= notification_time_today:
                for event in all_day_events_today:
                    notification_id = f"{event.get('id')}_{today_str}"
                    if notification_id not in self.notified_event_ids:
                        summary = event.get('summary', '제목 없음')
                        message = f"오늘 '{summary}' 일정이 있습니다."
                        self.notification_triggered.emit("일정 알림", message)
                        self.notified_event_ids.add(notification_id)

        for event in events_to_check:
            event_id = event.get('id')
            if event_id in self.notified_event_ids:
                continue

            start_info = event.get('start', {})
            start_time_str = start_info.get('dateTime')
            
            if not start_time_str:
                continue

            try:
                if start_time_str.endswith('Z'):
                    start_time_str = start_time_str[:-1] + '+00:00'

                event_start_time = datetime.datetime.fromisoformat(start_time_str)
                if event_start_time.tzinfo is None:
                    event_start_time = event_start_time.astimezone()

                if notification_start_time <= event_start_time < notification_end_time:
                    summary = event.get('summary', '제목 없음')
                    
                    time_diff = event_start_time - now
                    minutes_remaining = int(time_diff.total_seconds() / 60)
                    
                    if minutes_remaining > 0:
                        message = f"{minutes_remaining}분 후에 '{summary}' 일정이 시작됩니다."
                    else:
                        message = f"지금 '{summary}' 일정이 시작됩니다."

                    self.notification_triggered.emit("일정 알림", message)
                    self.notified_event_ids.add(event_id)
                    
                    if len(self.notified_event_ids) > 100:
                         self.notified_event_ids.clear()

            except ValueError:
                continue

    def get_provider_by_name(self, name):
        return next((p for p in self.providers if p.name == name), None)

    def get_classified_events_for_week(self, start_of_week):
        hide_weekends = self.settings.get("hide_weekends", False)
        num_days = 5 if hide_weekends else 7
        
        week_events = self.get_events_for_period(start_of_week, start_of_week + datetime.timedelta(days=num_days-1))
        selected_ids = self.settings.get("selected_calendars", [])
        filtered_events = [event for event in week_events if event.get('calendarId') in selected_ids]

        try:
            user_tz = ZoneInfo(self.settings.get("user_timezone", "UTC"))
        except ZoneInfoNotFoundError:
            user_tz = ZoneInfo("UTC")

        time_events, all_day_events = [], []
        for e in filtered_events:
            try:
                start_str = e['start'].get('dateTime', e['start'].get('date'))
                end_str = e['end'].get('dateTime', e['end'].get('date'))

                if 'dateTime' in e['start']:
                    aware_start_dt = dateutil_parser.isoparse(start_str)
                    aware_end_dt = dateutil_parser.isoparse(end_str)
                    e['start']['local_dt'] = aware_start_dt.astimezone(user_tz)
                    e['end']['local_dt'] = aware_end_dt.astimezone(user_tz)
                else: # 종일 이벤트
                    naive_start_dt = datetime.datetime.fromisoformat(start_str)
                    naive_end_dt = datetime.datetime.fromisoformat(end_str)
                    e['start']['local_dt'] = naive_start_dt.replace(tzinfo=user_tz) if naive_start_dt.tzinfo is None else naive_start_dt
                    e['end']['local_dt'] = naive_end_dt.replace(tzinfo=user_tz) if naive_end_dt.tzinfo is None else naive_end_dt

                if hide_weekends and e['start']['local_dt'].weekday() >= 5:
                    continue

                is_all_day_native = 'date' in e['start']
                duration = e['end']['local_dt'] - e['start']['local_dt']
                is_multi_day = duration.total_seconds() >= 86400
                is_exactly_24h_midnight = duration.total_seconds() == 86400 and e['start']['local_dt'].time() == datetime.time(0, 0)

                if is_all_day_native or (is_multi_day and not is_exactly_24h_midnight):
                    all_day_events.append(e)
                elif 'dateTime' in e['start']:
                    time_events.append(e)
            except (ValueError, TypeError) as err:
                logger.warning(f"주간 뷰 이벤트 시간 파싱 오류: {err}, 이벤트: {e.get('summary')}")
                continue
        
        return time_events, all_day_events

    def get_events_for_agenda(self, start_date, days=30):
        """
        [수정됨] 여러 날에 걸친 일정을 각 날짜에 맞게 포함하도록 로직을 개선합니다.
        """
        agenda_end_date = start_date + datetime.timedelta(days=days)
        
        # 시작일 30일 전부터 조회하여, 현재 뷰에 걸쳐있는 긴 일정을 놓치지 않도록 함
        search_start_date = start_date - datetime.timedelta(days=30)
        events_in_period = self.get_events_for_period(search_start_date, agenda_end_date)

        # 날짜별로 이벤트를 담을 OrderedDict 생성
        agenda = OrderedDict()
        for i in range(days):
            current_day = start_date + datetime.timedelta(days=i)
            agenda[current_day] = []

        for event in events_in_period:
            try:
                start_info = event.get('start', {})
                end_info = event.get('end', {})

                start_str = start_info.get('dateTime', start_info.get('date'))
                end_str = end_info.get('dateTime', end_info.get('date'))

                # Z를 +00:00으로 변환하여 fromisoformat 호환성 확보
                if start_str.endswith('Z'): start_str = start_str[:-1] + '+00:00'
                if end_str.endswith('Z'): end_str = end_str[:-1] + '+00:00'
                
                start_dt = datetime.datetime.fromisoformat(start_str)
                end_dt = datetime.datetime.fromisoformat(end_str)

                # 종일 이벤트의 경우, end_date가 다음 날 0시로 되어 있으므로 하루를 빼서 실제 종료일로 맞춤
                if 'date' in start_info:
                    end_dt -= datetime.timedelta(days=1)

                # 안건 뷰의 각 날짜를 순회하며 이벤트가 해당 날짜에 포함되는지 확인
                for day in agenda.keys():
                    day_dt_start = datetime.datetime.combine(day, datetime.time.min).astimezone()
                    day_dt_end = datetime.datetime.combine(day, datetime.time.max).astimezone()
                    
                    # 타임존 정보가 없는 경우, 시스템 기본값으로 설정
                    if start_dt.tzinfo is None: start_dt = start_dt.astimezone()
                    if end_dt.tzinfo is None: end_dt = end_dt.astimezone()

                    # 이벤트 기간이 현재 날짜와 겹치는지 확인
                    if start_dt <= day_dt_end and end_dt >= day_dt_start:
                        # 위젯에서 현재 날짜를 알 수 있도록 'agenda_display_date' 추가
                        event_copy = event.copy()
                        event_copy['agenda_display_date'] = day
                        agenda[day].append(event_copy)

            except (ValueError, TypeError) as e:
                # logger.warning(f"안건 뷰 날짜 파싱 오류: {e}, 이벤트: {event.get('summary')}")
                continue
        
        # 각 날짜별로 이벤트를 시간순으로 정렬
        for day, events in agenda.items():
            events.sort(key=lambda e: e['start'].get('dateTime', e['start'].get('date')))

        # 이벤트가 없는 날짜는 제거
        return OrderedDict((day, events) for day, events in agenda.items() if events)

    def get_events_for_period(self, start_date, end_date):
        all_events = []
        months_to_check = set()
        current_date = start_date
        while current_date <= end_date:
            months_to_check.add((current_date.year, current_date.month))
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)
        for year, month in months_to_check:
            # [수정] get_events는 이제 비동기 요청만 트리거하므로, 직접 캐시를 확인
            monthly_events = self.event_cache.get((year, month), [])
            for event in monthly_events:
                try:
                    start_info = event.get('start', {})
                    end_info = event.get('end', {})
                    start_str = start_info.get('date') or start_info.get('dateTime', '')[:10]
                    end_str = end_info.get('date') or end_info.get('dateTime', '')[:10]
                    event_start_date = datetime.date.fromisoformat(start_str)
                    event_end_date = datetime.date.fromisoformat(end_str)
                    if 'date' in end_info:
                        event_end_date -= datetime.timedelta(days=1)
                    if not (event_end_date < start_date or event_start_date > end_date):
                        all_events.append(event)
                except (ValueError, TypeError) as e:
                    print(f"이벤트 날짜 파싱 오류: {e}, 이벤트: {event.get('summary')}")
                    continue
        unique_events = {e['id']: e for e in all_events}.values()
        return list(unique_events)

    def get_all_calendars(self, fetch_if_empty=True):
        if self.calendar_list_cache is not None:
            return self.calendar_list_cache

        if fetch_if_empty:
            self._fetch_calendars_async()
        
        return []

    def _fetch_calendars_async(self):
        if self.calendar_fetch_thread and self.calendar_fetch_thread.isRunning():
            return

        self.calendar_fetch_thread = QThread()
        self.calendar_fetcher = CalendarListFetcher(self.providers)
        self.calendar_fetcher.moveToThread(self.calendar_fetch_thread)

        self.calendar_fetcher.calendars_fetched.connect(self._on_calendars_fetched)
        self.calendar_fetch_thread.started.connect(self.calendar_fetcher.run)
        
        self.calendar_fetcher.finished.connect(self._on_calendar_thread_finished)
        
        self.calendar_fetch_thread.start()

    def _on_calendar_thread_finished(self):
        if self.calendar_fetch_thread is None: return
            
        self.calendar_fetch_thread.quit()
        if self.calendar_fetch_thread.isRunning():
            self.calendar_fetch_thread.wait()
            
        self.calendar_fetcher.deleteLater()
        self.calendar_fetch_thread.deleteLater()
        self.calendar_fetch_thread = None
        self.calendar_fetcher = None
        print("캘린더 목록 스레드 정리 완료.")

    def _on_calendars_fetched(self, calendars):
        print(f"{len(calendars)}개의 캘린더 목록을 비동기적으로 수신했습니다.")
        self.calendar_list_cache = calendars
        self._default_color_map_cache = None
        self.calendar_list_changed.emit()

    def add_event(self, event_data):
        provider_name = event_data.get('provider')
        for provider in self.providers:
            if provider.name == provider_name:
                new_event = provider.add_event(event_data, self)
                if new_event:
                    if 'provider' not in new_event: new_event['provider'] = provider_name
                    cal_id = new_event.get('calendarId')
                    if cal_id:
                        all_calendars = self.get_all_calendars(fetch_if_empty=False)
                        cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
                        default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
                        new_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
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
                updated_event = provider.update_event(event_data, self)
                if updated_event:
                    if 'provider' not in updated_event: updated_event['provider'] = provider_name
                    cal_id = updated_event.get('calendarId')
                    if cal_id:
                        all_calendars = self.get_all_calendars(fetch_if_empty=False)
                        cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
                        default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
                        updated_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
                    start_str = updated_event['start'].get('date') or updated_event['start'].get('dateTime')[:10]
                    event_date = datetime.date.fromisoformat(start_str)
                    cache_key = (event_date.year, event_date.month)
                    if cache_key in self.event_cache:
                        event_id = updated_event.get('id')
                        self.event_cache[cache_key] = [e for e in self.event_cache[cache_key] if e.get('id') != event_id]
                        self.event_cache[cache_key].append(updated_event)
                    else:
                        self.event_cache[cache_key] = [updated_event]
                    self.data_updated.emit(event_date.year, event_date.month)
                    return True
        return False

# data_manager.py 파일의 DataManager 클래스 내부

# ▼▼▼ [핵심 수정] 이 함수를 찾아서 아래 코드로 교체합니다. ▼▼▼
    
    # ▲▲▲ 여기까지 교체 ▲▲▲

    def load_initial_month(self):
        print("초기 데이터 로딩을 요청합니다...")
        self.get_all_calendars(fetch_if_empty=True)
        today = datetime.date.today()
        self.get_events(today.year, today.month)

    def _apply_colors_to_events(self, events):
        if not events: return
        all_calendars = self.get_all_calendars(fetch_if_empty=False)
        custom_colors = self.settings.get("calendar_colors", {})
        default_color_map = {cal['id']: cal.get('backgroundColor', DEFAULT_EVENT_COLOR) for cal in all_calendars}
        for event in events:
            cal_id = event.get('calendarId')
            if cal_id:
                default_color = default_color_map.get(cal_id, DEFAULT_EVENT_COLOR)
                event['color'] = custom_colors.get(cal_id, default_color)

    def search_events(self, query):
        all_results = []
        for provider in self.providers:
            try:
                results = provider.search_events(query, self)
                if results:
                    all_results.extend(results)
            except Exception as e:
                print(f"'{type(provider).__name__}' 이벤트 검색 오류: {e}")
        unique_results = list({event['id']: event for event in all_results}.values())
        self._apply_colors_to_events(unique_results)
        def get_start_time(event):
            start = event.get('start', {})
            return start.get('dateTime') or start.get('date')
        unique_results.sort(key=get_start_time)
        return unique_results

    def _check_for_notifications(self):
        if not self.settings.get("notifications_enabled", DEFAULT_NOTIFICATIONS_ENABLED):
            return

        minutes_before = self.settings.get("notification_minutes", DEFAULT_NOTIFICATION_MINUTES)
        now = datetime.datetime.now().astimezone()
        notification_start_time = now
        notification_end_time = now + datetime.timedelta(minutes=minutes_before)

        today = datetime.date.today()
        events_to_check = []
        
        current_month_events = self.event_cache.get((today.year, today.month), [])
        events_to_check.extend(current_month_events)
        
        next_month_date = today.replace(day=28) + datetime.timedelta(days=4)
        next_month_events = self.event_cache.get((next_month_date.year, next_month_date.month), [])
        events_to_check.extend(next_month_events)

        if self.settings.get("all_day_notification_enabled", DEFAULT_ALL_DAY_NOTIFICATION_ENABLED):
            notification_time_str = self.settings.get("all_day_notification_time", DEFAULT_ALL_DAY_NOTIFICATION_TIME)
            hour, minute = map(int, notification_time_str.split(':'))
            notification_time_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            today_str = today.strftime('%Y-%m-%d')
            all_day_events_today = [
                e for e in current_month_events 
                if e.get('start', {}).get('date') == today_str
            ]

            if now >= notification_time_today:
                for event in all_day_events_today:
                    notification_id = f"{event.get('id')}_{today_str}"
                    if notification_id not in self.notified_event_ids:
                        summary = event.get('summary', '제목 없음')
                        message = f"오늘 '{summary}' 일정이 있습니다."
                        self.notification_triggered.emit("일정 알림", message)
                        self.notified_event_ids.add(notification_id)

        for event in events_to_check:
            event_id = event.get('id')
            if event_id in self.notified_event_ids:
                continue

            start_info = event.get('start', {})
            start_time_str = start_info.get('dateTime')
            
            if not start_time_str:
                continue

            try:
                if start_time_str.endswith('Z'):
                    start_time_str = start_time_str[:-1] + '+00:00'

                event_start_time = datetime.datetime.fromisoformat(start_time_str)
                if event_start_time.tzinfo is None:
                    event_start_time = event_start_time.astimezone()

                if notification_start_time <= event_start_time < notification_end_time:
                    summary = event.get('summary', '제목 없음')
                    
                    time_diff = event_start_time - now
                    minutes_remaining = int(time_diff.total_seconds() / 60)
                    
                    if minutes_remaining > 0:
                        message = f"{minutes_remaining}분 후에 '{summary}' 일정이 시작됩니다."
                    else:
                        message = f"지금 '{summary}' 일정이 시작됩니다."

                    self.notification_triggered.emit("일정 알림", message)
                    self.notified_event_ids.add(event_id)
                    
                    if len(self.notified_event_ids) > 100:
                         self.notified_event_ids.clear()

            except ValueError:
                continue