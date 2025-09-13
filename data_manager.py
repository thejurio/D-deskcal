# data_manager.py
import datetime
import json
import time
import sqlite3
import threading
import uuid
import logging
import calendar
from collections import deque, OrderedDict
from contextlib import contextmanager
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer, QWaitCondition, QThreadPool, QRunnable

from providers.google_provider import GoogleCalendarProvider
from providers.local_provider import LocalCalendarProvider
from config import (DB_FILE, MAX_CACHE_SIZE, DEFAULT_SYNC_INTERVAL, 
                    GOOGLE_CALENDAR_PROVIDER_NAME, DEFAULT_EVENT_COLOR, DEFAULT_NOTIFICATIONS_ENABLED, 
                    DEFAULT_NOTIFICATION_MINUTES, DEFAULT_ALL_DAY_NOTIFICATION_ENABLED,
                    DEFAULT_ALL_DAY_NOTIFICATION_TIME)

logger = logging.getLogger(__name__)

def safe_json_dumps(obj):
    """Safely convert objects to JSON, handling datetime objects"""
    def json_serializer(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.isoformat()
        elif hasattr(obj, 'zone') and hasattr(obj.zone, 'zone'):  # Handle timezone info
            return str(obj)
        raise TypeError(f"Object {obj} of type {type(obj)} is not JSON serializable")
    
    try:
        return json.dumps(obj, default=json_serializer, ensure_ascii=False)
    except Exception as e:
        logger.error(f"JSON 직렬화 실패: {e}, object: {type(obj)}")
        return json.dumps({"error": "serialization_failed", "type": str(type(obj))})

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

class DistanceBasedTaskQueue:
    """거리별 작업 분배 시스템"""
    
    def __init__(self):
        # 거리별 큐: 0(현재월), 1(인접월) - 3개월 윈도우용
        self._queues = {i: deque() for i in range(2)}
        self._pending_tasks = set()
        # Python threading.Lock으로 QMutex 대체 (안전한 스레드 동기화)
        self._lock = threading.Lock()
        # 각 거리별 워커의 활성 작업 추적
        self._active_tasks = {i: None for i in range(2)}
        # 최근 완료된 작업 추적 (중복 방지)
        self._recently_completed = {}
        # 완료 추적 유지 시간 (초)
        self._completion_cooldown = 30

    def _ensure_mutex_valid_DISABLED(self):
        """DISABLED - mutex runtime recreation was causing memory corruption"""
        # DISABLED - was causing memory corruption and crashes
            # # self._mutex = QMutex()  # DISABLED - dangerous pattern  # DISABLED - dangerous runtime recreation

    def add_task(self, distance, task_data):
        """거리 기반으로 작업 추가"""
        with self._lock:
            # 최근 완료된 작업인지 확인 (쿨다운 체크)
            import time
            current_time = time.time()
            if task_data in self._recently_completed:
                time_since_completion = current_time - self._recently_completed[task_data]
                if time_since_completion < self._completion_cooldown:
                    logger.debug(f"[캐시 DEBUG] 작업 쿨다운 중 - 스킵: {task_data} (완료 후 {time_since_completion:.1f}초)")
                    return False
            
            # 거리 범위 제한 (0-1) - 3개월 윈도우용
            distance = min(max(distance, 0), 1)
            
            # 이미 pending이지만 더 가까운 거리일 때 갱신
            for d in sorted(self._queues.keys()):
                if task_data in self._queues[d] and distance < d:
                    self._queues[d].remove(task_data)
                    self._queues[distance].append(task_data)
                    logger.info(f"[캐시 DEBUG] 작업 거리 갱신: {task_data} 거리{d}→{distance}")
                    return True
                    
            # 새 작업 추가
            if task_data not in self._pending_tasks:
                self._queues[distance].append(task_data)
                self._pending_tasks.add(task_data)
                logger.info(f"[캐시 DEBUG] 거리{distance} 작업 추가: {task_data}")
                return True
            return False

    def get_next_task_for_distance(self, distance):
        """특정 거리의 워커가 다음 작업 가져오기"""
        with self._lock:
            if distance in self._queues and self._queues[distance]:
                task_data = self._queues[distance].popleft()
                self._pending_tasks.discard(task_data)
                self._active_tasks[distance] = task_data
                return task_data
            return None

    def mark_task_completed(self, distance, task_data):
        """작업 완료 처리"""
        with self._lock:
            if self._active_tasks.get(distance) == task_data:
                self._active_tasks[distance] = None
                logger.info(f"[캐시 DEBUG] 거리{distance} 작업 완료: {task_data}")
            
            # 완료 시간 기록 (중복 방지용)
            import time
            self._recently_completed[task_data] = time.time()
            logger.debug(f"[캐시 DEBUG] 작업 완료 기록: {task_data} (30초 쿨다운 적용)")
            
            # 오래된 완료 기록 정리
            self._cleanup_old_completions()

    def interrupt_and_add_current_month(self, task_data):
        """현재 월은 모든 작업을 중단하고 최우선 처리 (개선된 버전)"""
        with self._lock:
            # 쿨다운 체크 - 현재월도 중복 요청 방지
            import time
            current_time = time.time()
            if task_data in self._recently_completed:
                time_since_completion = current_time - self._recently_completed[task_data]
                if time_since_completion < self._completion_cooldown:
                    logger.debug(f"[캐시 DEBUG] 현재월 작업 쿨다운 중 - 스킵: {task_data} (완료 후 {time_since_completion:.1f}초)")
                    return False
            
            # 1. idle 워커가 있다면 우선 활용 (중단 불필요)
            if self._active_tasks[0] is None:  # 거리0 워커가 idle
                self._queues[0].clear()
                self._queues[0].append(task_data)
                self._pending_tasks.add(task_data)
                logger.info(f"[캐시 DEBUG] 현재월 idle 워커 즉시 할당: {task_data}")
                return True
            
            # 2. 다른 idle 워커가 있다면 활용
            idle_workers = self.get_idle_workers()
            if idle_workers:
                # 가장 가까운 idle 워커 선택 (거리 0에 가장 가까운)
                optimal_worker = min(idle_workers)
                self._queues[optimal_worker].append(task_data)
                self._pending_tasks.add(task_data)
                logger.info(f"[캐시 DEBUG] 현재월 다른 idle 워커 활용: 거리{optimal_worker} → {task_data}")
                return True
            
            # 3. 모든 워커가 busy일 때만 중단 로직 실행
            # 가장 먼 거리 워커를 중단
            farthest_worker = self.get_farthest_busy_worker()
            if farthest_worker is not None and farthest_worker > 0:  # 거리0이 아닌 워커만 중단
                old_task = self._active_tasks[farthest_worker]
                if old_task:
                    self._pending_tasks.discard(old_task)
                    logger.info(f"[캐시 DEBUG] 현재월을 위해 거리{farthest_worker} 워커 중단: {old_task}")
                
                # 중단된 워커에 현재월 할당
                self._queues[farthest_worker].clear()
                self._queues[farthest_worker].append(task_data)
                self._pending_tasks.add(task_data)
                self._active_tasks[farthest_worker] = None
                logger.info(f"[캐시 DEBUG] 현재월 작업을 거리{farthest_worker} 워커에 할당: {task_data}")
                return True
            
            # 4. 마지막 수단: 거리0 워커 중단 (기존 로직)
            old_task = self._active_tasks[0]
            if old_task:
                self._pending_tasks.discard(old_task)
                logger.info(f"[캐시 DEBUG] 현재월 작업 중단: {old_task}")
            
            self._queues[0].clear()
            self._queues[0].append(task_data)
            self._pending_tasks.add(task_data)
            self._active_tasks[0] = None
            logger.info(f"[캐시 DEBUG] 현재월 최우선 작업 설정: {task_data}")
            return True

    def clear_orphaned_pending(self):
        """큐에는 없지만 pending 상태인 고아 작업들 정리"""
        # self._ensure_mutex_valid()  # DISABLED - dangerous runtime mutex recreation
        # with QMutexLocker(self._mutex):  # DISABLED - was causing crashes
        if True:
            all_queued_tasks = set()
            for queue in self._queues.values():
                all_queued_tasks.update(queue)
            
            orphaned_tasks = self._pending_tasks - all_queued_tasks
            orphaned_count = len(orphaned_tasks)
            self._pending_tasks -= orphaned_tasks
            
            if orphaned_count > 0:
                logger.info(f"[캐시 DEBUG] 고아 작업 {orphaned_count}개 정리됨")
            return orphaned_count

    def _cleanup_old_completions(self):
        """오래된 완료 기록 정리"""
        import time
        current_time = time.time()
        expired_keys = []
        
        for task_data, completion_time in self._recently_completed.items():
            if current_time - completion_time > self._completion_cooldown:
                expired_keys.append(task_data)
        
        for key in expired_keys:
            del self._recently_completed[key]
        
        if expired_keys:
            logger.debug(f"[캐시 DEBUG] 만료된 완료 기록 {len(expired_keys)}개 정리됨")

    def get_queue_status(self):
        """각 거리별 큐 상태 반환 (디버그용)"""
        # self._ensure_mutex_valid()  # DISABLED - dangerous runtime mutex recreation
        # with QMutexLocker(self._mutex):  # DISABLED - was causing crashes
        if True:
            status = {}
            for distance, queue in self._queues.items():
                status[distance] = {
                    'queued': len(queue),
                    'active': self._active_tasks[distance] is not None,
                    'active_task': self._active_tasks[distance]
                }
            return status

    def get_idle_workers(self):
        """현재 idle 상태인 워커들의 거리 목록 반환"""
        # 락이 이미 획득된 상태에서 호출될 수 있으므로 락 사용하지 않음
        idle_workers = []
        for distance in range(2):  # 0~1 거리
            if self._active_tasks[distance] is None:
                idle_workers.append(distance)
        logger.debug(f"[캐시 DEBUG] Idle 워커들: {idle_workers}")
        return idle_workers
    
    def find_optimal_idle_worker(self, target_distance):
        """가장 적합한 idle 워커 찾기 (거리 기준)"""
        idle_workers = self.get_idle_workers()
        if not idle_workers:
            return None
        
        # 타겟 거리와 가장 가까운 idle 워커 선택
        optimal_worker = min(idle_workers, key=lambda d: abs(d - target_distance))
        logger.info(f"[캐시 DEBUG] 최적 idle 워커 선택: 거리{optimal_worker} (타겟 거리{target_distance})")
        return optimal_worker
    
    def get_farthest_busy_worker(self):
        """가장 먼 거리에서 작업 중인 워커 찾기"""
        # 락이 이미 획득된 상태에서 호출될 수 있으므로 락 사용하지 않음
        busy_workers = []
        for distance in range(2):  # 0~1 거리
            if self._active_tasks[distance] is not None:
                busy_workers.append(distance)
        
        if not busy_workers:
            return None
        
        # 가장 먼 거리 워커 반환
        farthest_worker = max(busy_workers)
        logger.debug(f"[캐시 DEBUG] 가장 먼 busy 워커: 거리{farthest_worker}")
        return farthest_worker
    
    def add_task_with_smart_assignment(self, distance, task_data):
        """개선된 스마트 작업 할당"""
        with self._lock:
            # 1. 쿨다운 체크
            import time
            current_time = time.time()
            if task_data in self._recently_completed:
                time_since_completion = current_time - self._recently_completed[task_data]
                if time_since_completion < self._completion_cooldown:
                    logger.debug(f"[캐시 DEBUG] 작업 쿨다운 중 - 스킵: {task_data} (완료 후 {time_since_completion:.1f}초)")
                    return False
            
            # 2. idle 워커 우선 활용 (가장 중요한 개선점)
            optimal_idle_worker = self.find_optimal_idle_worker(distance)
            if optimal_idle_worker is not None:
                # idle 워커에 즉시 할당
                actual_distance = optimal_idle_worker
                self._queues[actual_distance].append(task_data)
                self._pending_tasks.add(task_data)
                logger.info(f"[캐시 DEBUG] idle 워커 즉시 할당: 거리{actual_distance} → {task_data}")
                return True
            
            # 3. 모든 워커가 busy일 때 기존 로직 사용
            # 거리 범위 제한 (0-3)
            distance = min(max(distance, 0), 3)
            
            # 이미 pending이지만 더 가까운 거리일 때 갱신
            for d in sorted(self._queues.keys()):
                if task_data in self._queues[d] and distance < d:
                    self._queues[d].remove(task_data)
                    self._queues[distance].append(task_data)
                    logger.info(f"[캐시 DEBUG] 작업 거리 갱신: {task_data} 거리{d}→{distance}")
                    return True
            
            # 새 작업 추가
            if task_data not in self._pending_tasks:
                self._queues[distance].append(task_data)
                self._pending_tasks.add(task_data)
                logger.info(f"[캐시 DEBUG] 새 작업 추가: 거리{distance} → {task_data}")
                return True
            
            logger.debug(f"[캐시 DEBUG] 작업 이미 존재: {task_data}")
            return False

    def __len__(self):
        # self._ensure_mutex_valid()  # DISABLED - dangerous runtime mutex recreation
        # with QMutexLocker(self._mutex):  # DISABLED - was causing crashes\n        # if True:
            return len(self._pending_tasks)

class DistanceWorker(QObject):
    """개별 워커 스레드 - 특정 거리의 작업 담당"""
    finished = pyqtSignal()
    
    def __init__(self, distance, task_queue, data_manager):
        super().__init__()
        self.distance = distance
        self.task_queue = task_queue
        self.data_manager = data_manager
        self._is_running = True
        
        # 거리별 워커 이름 설정
        if distance == 0:
            self.name = "현재월"
        else:
            self.name = f"거리{distance}"
            
        logger.info(f"[캐시 DEBUG] {self.name} 워커 초기화됨")

    def stop(self):
        """워커 중지"""
        self._is_running = False
        logger.info(f"[캐시 DEBUG] {self.name} 워커 중지 요청됨")

    def run(self):
        """워커의 메인 실행 루프"""
        logger.info(f"[캐시 DEBUG] {self.name} 워커 시작")
        
        while self._is_running:
            # 1. 할당된 거리의 작업 가져오기
            task_data = self.task_queue.get_next_task_for_distance(self.distance)
            
            if task_data:
                try:
                    task_type, (year, month) = task_data
                    logger.info(f"[캐시 DEBUG] {self.name} 워커 작업 시작: {year}년 {month}월")
                    
                    # 2. 동기화 상태 알림 (UI 스피너 표시)
                    self.data_manager.set_sync_state(True, year, month)
                    
                    # 3. 실제 API 호출
                    events = self.data_manager._fetch_events_from_providers(year, month)
                    
                    if events is not None and self._is_running:
                        # 4. 캐시에 저장
                        self.data_manager._merge_events_preserving_temp(year, month, events)
                        self.data_manager._save_month_to_cache_db(year, month, events)
                        
                        # 5. UI 업데이트 신호 발송
                        self.data_manager.data_updated.emit(year, month)
                        
                        logger.info(f"[캐시 DEBUG] {self.name} 워커 작업 완료: {year}년 {month}월 ({len(events)}개 이벤트)")
                    
                    # 6. 작업 완료 처리
                    self.data_manager.set_sync_state(False, year, month)
                    self.task_queue.mark_task_completed(self.distance, task_data)
                    
                except Exception as e:
                    logger.error(f"[캐시 DEBUG] {self.name} 워커 작업 오류: {e}", exc_info=True)
                    # 오류 시에도 동기화 상태 해제
                    try:
                        task_type, (year, month) = task_data
                        self.data_manager.set_sync_state(False, year, month)
                    except:
                        pass
            else:
                # 작업이 없으면 잠시 대기
                time.sleep(0.1)
        
        logger.info(f"[캐시 DEBUG] {self.name} 워커 종료됨")
        self.finished.emit()


class DistanceBasedCachingManager(QObject):
    """7개 워커 기반 거리별 병렬 캐싱 시스템 총괄 관리자"""
    finished = pyqtSignal()

    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self._is_running = True
        # # self._mutex = QMutex()  # DISABLED - dangerous pattern  # DISABLED - dangerous runtime recreation
        
        # 거리별 작업 큐
        self._task_queue = DistanceBasedTaskQueue()
        self._last_viewed_month = None
        
        # 7개 워커와 스레드 관리
        self._workers = {}
        self._worker_threads = {}
        
        # 일시정지 관리
        # self._activity_lock = QMutex()  # DISABLED - dangerous pattern
        self._pause_requested = False
        self._resume_condition = QWaitCondition()
        
        # 7개 워커 초기화 (거리 0~6)
        self._init_workers()
        
        logger.info("[캐시 DEBUG] DistanceBasedCachingManager 초기화 완료 (7개 워커)")

    def _ensure_mutex_valid_DISABLED(self):
        """DISABLED - mutex runtime recreation was causing memory corruption"""
        # DISABLED - was causing memory corruption and crashes
            # # self._mutex = QMutex()  # DISABLED - dangerous pattern  # DISABLED - dangerous runtime recreation

    def _init_workers(self):
        """2개 거리별 워커 초기화 (3개월 윈도우: 현재월 + ±1개월)"""
        for distance in range(2):
            # 워커 생성
            worker = DistanceWorker(distance, self._task_queue, self.data_manager)
            self._workers[distance] = worker
            
            # 스레드 생성 및 연결
            thread = QThread()
            self._worker_threads[distance] = thread
            
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            
            # 스레드 시작
            thread.start()
            
            logger.info(f"[캐시 DEBUG] 거리{distance} 워커 스레드 시작됨")

    def request_caching_around(self, year, month, skip_current=False):
        """거리별 병렬 캐싱 요청"""
        # self._ensure_mutex_valid()  # DISABLED - dangerous runtime mutex recreation
        # with QMutexLocker(self._mutex):  # DISABLED - was causing crashes  # DISABLED FOR CRASH FIX
        if True:
            # 🚀 중복 요청 방지: 같은 월에 대한 요청이 이미 처리 중이면 스킵
            current_request = (year, month)
            if hasattr(self, '_last_cache_request') and self._last_cache_request == current_request:
                # 100ms 쿨다운 체크
                current_time = time.time()
                if hasattr(self, '_last_request_time'):
                    time_diff = current_time - self._last_request_time
                    if time_diff < 0.1:  # 100ms 쿨다운
                        logger.debug(f"[캐시 DEBUG] 중복 요청 방지: {year}년 {month}월 (쿨다운 {time_diff:.3f}s)")
                        return
            
            self._last_cache_request = current_request
            self._last_request_time = time.time()
            self._last_viewed_month = (year, month)
            
            logger.info(f"[캐시 DEBUG] 병렬 캐싱 요청: {year}년 {month}월 중심")
            
            # 현재 월 처리 (skip_current가 False인 경우에만)
            if not skip_current:
                current_month_task = ('month', (year, month))
                if self._task_queue.interrupt_and_add_current_month(current_month_task):
                    logger.info(f"[캐시 DEBUG] 현재월 최우선 처리: {year}년 {month}월")
                else:
                    logger.info(f"[캐시 DEBUG] 현재월 쿨다운으로 스킵: {year}년 {month}월")

            # 1. 슬라이딩 윈도우 계산 (3개월: ±1개월)
            window_months = self._calculate_sliding_window(year, month, 1)
            
            # 2. 이미 캐시되지 않은 월들만 필터링
            cached_months = set(self.data_manager.event_cache.keys())
            target_months = [m for m in window_months if m not in cached_months]
            
            # 3. 현재월을 이미 처리했다면 target_months에서 제외
            if not skip_current:
                current_month_key = (year, month)
                if current_month_key in target_months:
                    target_months.remove(current_month_key)
                    logger.debug(f"[캐시 DEBUG] 현재월 중복 제거: {year}년 {month}월")
            
            logger.info(f"[캐시 DEBUG] 윈도우 {len(window_months)}개월, 미캐시 {len(target_months)}개월")
            
            # 3. 거리별 작업 분산
            distance_assignments = {}
            for target_month in target_months:
                # 거리 계산 (절대값) - 3개월 윈도우 기준
                distance = abs((target_month[0] - year) * 12 + (target_month[1] - month))
                worker_distance = min(distance, 1)  # 최대 거리 1 (±1개월)
                
                if worker_distance not in distance_assignments:
                    distance_assignments[worker_distance] = []
                distance_assignments[worker_distance].append(target_month)

            # 4. 각 거리별 워커에 작업 할당
            total_assigned = 0
            for distance, months in distance_assignments.items():
                for target_month in months:
                    task_data = ('month', target_month)
                    added = self._task_queue.add_task_with_smart_assignment(distance, task_data)
                    
                    if added:
                        total_assigned += 1
                        logger.info(f"[캐시 DEBUG] 거리{distance} 워커 할당: {target_month}")

            logger.info(f"[캐시 DEBUG] 총 {total_assigned}개 작업이 2개 워커에 분산 할당됨")
            
            # 5. 고아 작업 정리
            orphaned_count = self._task_queue.clear_orphaned_pending()
            if orphaned_count > 0:
                logger.info(f"[캐시 DEBUG] {orphaned_count}개 고아 작업 정리됨")

    def request_current_month_sync(self):
        """현재 월 동기화 요청"""
        # self._ensure_mutex_valid()  # DISABLED - dangerous runtime mutex recreation
        # with QMutexLocker(self._mutex):  # DISABLED - was causing crashes
        if True:
            if self._last_viewed_month:
                task_data = ("month", self._last_viewed_month)
                # 현재 월은 항상 거리 0으로 처리
                self._task_queue.add_task(0, task_data)
                logger.info(f"[캐시 DEBUG] 현재월 동기화 요청: {self._last_viewed_month}")

    def stop(self):
        """모든 워커 중지"""
        logger.info("[캐시 DEBUG] 모든 워커 중지 요청")
        self._is_running = False
        
        # 모든 워커 중지
        for worker in self._workers.values():
            worker.stop()
        
        self.resume_sync()  # 일시정지 상태 해제
        
        # 모든 워커 종료 대기
        for thread in self._worker_threads.values():
            if thread.isRunning():
                thread.quit()
                thread.wait(3000)  # 3초 대기
        
        logger.info("[캐시 DEBUG] 모든 워커 중지 완료")
        self.finished.emit()

    def _calculate_sliding_window(self, center_year, center_month, radius):
        """중심 월 기준으로 ±radius 개월의 슬라이딩 윈도우 계산 (중심월 포함)"""
        months = []
        center_date = datetime.date(center_year, center_month, 1)
        
        for i in range(-radius, radius + 1):
            # 중심월도 포함하여 7개월 윈도우 구성 (±3개월)
            target_date = center_date + relativedelta(months=i)
            months.append((target_date.year, target_date.month))
        
        return months

    def pause_sync(self):
        """모든 워커 일시정지"""
        # _activity_lock disabled for safety - using simple flag instead
        self._pause_requested = True
        logger.info("[캐시 DEBUG] 모든 워커 일시정지 요청")

    def resume_sync(self):
        """모든 워커 재개"""
        if self._pause_requested:
            self._pause_requested = False
            # _activity_lock and _resume_condition disabled for safety - using simple flag instead
            logger.info("[캐시 DEBUG] 모든 워커 재개됨")

    def get_queue_status(self):
        """큐 상태 조회 (디버그용)"""
        return self._task_queue.get_queue_status()

    def get_worker_status(self):
        """워커 상태 조회 (디버그용)"""
        status = {}
        for distance, thread in self._worker_threads.items():
            status[distance] = {
                'thread_running': thread.isRunning(),
                'worker_name': self._workers[distance].name
            }
        return status

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
        
        # [추가] 로컬-퍼스트 삭제 추적: 백그라운드 삭제 중인 이벤트 ID 추적
        self.pending_deletion_ids = set()  # 현재 삭제 중인 이벤트 ID들
        self.batch_deletion_mode = False  # 배치 삭제 모드 플래그
        
        self.calendar_list_cache = None
        self._default_color_map_cache = None
        
        # [삭제] ImmediateSyncWorker 관련 멤버 변수 삭제
        
        # 캐시 윈도우 변화 추적
        self.last_cache_window = set()  # 마지막 캐시 윈도우
        self.current_view_month = None  # 사용자가 현재 보고 있는 월
        
        self.calendar_fetch_thread = None
        self.calendar_fetcher = None

        if load_cache:
            # 새로운 분리된 데이터베이스 시스템 초기화
            self._init_separated_db_system()
            self._load_cache_from_db()
            self._init_completed_events_db()
            self._load_completed_event_ids()
        
        self.last_requested_month = None
        self.providers = []
        # DistanceBasedCachingManager는 자체적으로 7개 워커 스레드를 관리
        self.caching_manager = DistanceBasedCachingManager(self)
        
        if start_timer:
            self.sync_timer = QTimer(self)
            self.update_sync_timer()

            self.notification_timer = QTimer(self)
            self.notification_timer.timeout.connect(self._check_for_notifications)
            self.notification_timer.start(60 * 1000)
            
            # 스마트 실시간 업데이트 타이머 (조건부 실행으로 성능 최적화)
            self.smart_update_timer = QTimer(self)
            self.smart_update_timer.timeout.connect(self._smart_realtime_update)
            self.smart_update_timer.start(3 * 1000)  # 3초마다 체크
            self.last_update_time = time.time()
            logger.info("스마트 실시간 업데이트 타이머 시작됨: 3초 간격")
        
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

    def _init_separated_db_system(self):
        """새로운 분리된 데이터베이스 시스템 초기화 및 마이그레이션"""
        try:
            from db_manager import get_db_manager
            db_manager = get_db_manager()
            
            # 데이터베이스 초기화 및 마이그레이션 수행
            # db_manager의 __init__에서 자동으로 _init_databases()와 migrate_existing_data()가 호출됨
            logger.info("분리된 데이터베이스 시스템이 초기화되었습니다.")
            
            # 초기화 후 즉시 캐시 정리 수행 (오늘 날짜 기준)
            deleted_count = db_manager.cleanup_old_cache()
            if deleted_count > 0:
                logger.info(f"초기화 시 캐시 정리: {deleted_count}개 엔트리 삭제됨")
                
        except Exception as e:
            msg = "분리된 데이터베이스 시스템 초기화 중 오류가 발생했습니다."
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
        
        # 색상 맵 캐시만 초기화 (캘린더 목록은 동기적으로 다시 생성됨)
        self._default_color_map_cache = None
        
        if is_logging_out:
            logger.info("로그아웃 감지. Google 캘린더 관련 캐시를 삭제합니다.")
            for month_key, events in list(self.event_cache.items()):
                google_events = [e for e in events if e.get('provider') == GOOGLE_CALENDAR_PROVIDER_NAME]
                if google_events:
                    remaining_events = [e for e in events if e.get('provider') != GOOGLE_CALENDAR_PROVIDER_NAME]
                    self.event_cache[month_key] = remaining_events
                    self._save_month_to_cache_db(month_key[0], month_key[1], remaining_events)
        
        # 로그인 후 캘린더 목록과 현재 월 데이터를 동기적으로 새로고침
        if not is_logging_out and self.auth_manager.is_logged_in():
            logger.info("로그인 완료 후 캘린더 목록과 이벤트 데이터 새로고침 시작...")
            
            # 캘린더 목록을 먼저 새로고침 (동기적으로)
            self._fetch_calendars_async()
            
            # 현재 월 캐시 삭제 후 강제 동기화
            if self.last_requested_month:
                year, month = self.last_requested_month
                self.event_cache.pop((year, month), None)
                logger.info(f"로그인 후 현재 월 캐시 삭제 및 강제 동기화: {year}년 {month}월")
                
                # QTimer를 사용해 캘린더 목록 로딩 완료 후 이벤트 동기화
                from PyQt6.QtCore import QTimer
                def delayed_sync():
                    logger.info(f"로그인 후 지연된 이벤트 동기화 시작: {year}년 {month}월")
                    # 로그인 후 확실한 업데이트를 위해 즉시 UI 업데이트 신호 발송
                    self.data_updated.emit(year, month)
                    # 그리고 백그라운드에서 최신 데이터 동기화
                    self.force_sync_month(year, month)
                
                QTimer.singleShot(500, delayed_sync)  # 500ms 후 실행 (더 여유있게)
            else:
                today = datetime.date.today()
                self.event_cache.pop((today.year, today.month), None)
                logger.info(f"로그인 후 오늘 날짜 캐시 삭제 및 강제 동기화: {today.year}년 {today.month}월")
                
                # QTimer를 사용해 캘린더 목록 로딩 완료 후 이벤트 동기화
                from PyQt6.QtCore import QTimer
                def delayed_sync():
                    logger.info(f"로그인 후 지연된 이벤트 동기화 시작: {today.year}년 {today.month}월")
                    # 로그인 후 확실한 업데이트를 위해 즉시 UI 업데이트 신호 발송
                    self.data_updated.emit(today.year, today.month)
                    # 그리고 백그라운드에서 최신 데이터 동기화
                    self.force_sync_month(today.year, today.month)
                
                QTimer.singleShot(500, delayed_sync)  # 500ms 후 실행 (더 여유있게)
        elif self.last_requested_month:
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

    def _smart_realtime_update(self):
        """스마트 실시간 업데이트 - 조건부로만 실행하여 성능 최적화"""
        current_time = time.time()
        
        # 조건 1: 로그인되어 있을 때만
        if not self.auth_manager.is_logged_in():
            return
            
        # 조건 2: 마지막 업데이트로부터 충분한 시간이 지났을 때만
        if current_time - self.last_update_time < 5:  # 5초 미만이면 스킵 (실시간성 우선)
            return
            
        # 조건 3: 현재 동기화 중인 월이 없을 때만
        if self.last_requested_month:
            year, month = self.last_requested_month
            if self.is_month_syncing(year, month):
                logger.debug(f"스마트 업데이트 스킵: {year}년 {month}월 동기화 중")
                return
        else:
            today = datetime.date.today()
            year, month = today.year, today.month
            if self.is_month_syncing(year, month):
                logger.debug(f"스마트 업데이트 스킵: {year}년 {month}월 동기화 중")
                return
                
        # 실제 백그라운드 동기화 실행 (UI 업데이트는 완료 시 자동 발생)
        logger.debug(f"스마트 실시간 업데이트 실행: {year}년 {month}월")
        self.force_sync_month(year, month)
        self.last_update_time = current_time

    def notify_date_changed(self, new_date):
        self.last_requested_month = (new_date.year, new_date.month)
        self.caching_manager.request_caching_around(new_date.year, new_date.month)

    def stop_caching_thread(self):
        """🛑 완전한 종료: 모든 스레드와 백그라운드 작업 정리"""
        logger.info("🛑 [SHUTDOWN] DCWidget 종료 프로세스 시작...")
        
        try:
            # 1. 타이머들 중지
            if hasattr(self, 'notification_timer'):
                self.notification_timer.stop()
                logger.info("📱 알림 타이머 중지됨")
            
            if hasattr(self, 'smart_update_timer'):
                self.smart_update_timer.stop()
                logger.info("⚡ 스마트 업데이트 타이머 중지됨")
            
            # 2. DistanceBasedCachingManager 중지 (4개 워커 스레드)
            if hasattr(self, 'caching_manager') and self.caching_manager:
                logger.info("🔄 캐싱 매니저 중지 중...")
                self.caching_manager.stop()
                logger.info("✅ 캐싱 매니저 중지 완료")
            
            # 3. 캘린더 페치 스레드 중지
            if hasattr(self, 'calendar_fetch_thread') and self.calendar_fetch_thread is not None:
                if self.calendar_fetch_thread.isRunning():
                    logger.info("📅 캘린더 페치 스레드 중지 중...")
                    if hasattr(self, 'calendar_fetcher'):
                        self.calendar_fetcher.stop()
                    self.calendar_fetch_thread.quit()
                    if not self.calendar_fetch_thread.wait(3000):  # 3초 대기
                        logger.warning("⚠️ 캘린더 페치 스레드 강제 종료")
                        self.calendar_fetch_thread.terminate()
                    logger.info("✅ 캘린더 페치 스레드 중지 완료")
            
            # 4. QThreadPool 작업들 대기 및 종료
            logger.info("🧵 QThreadPool 작업 대기 중...")
            thread_pool = QThreadPool.globalInstance()
            thread_pool.waitForDone(5000)  # 5초 대기
            if thread_pool.activeThreadCount() > 0:
                logger.warning(f"⚠️ {thread_pool.activeThreadCount()}개 스레드가 여전히 활성 상태")
            else:
                logger.info("✅ 모든 QThreadPool 작업 완료")
            
            # 5. Provider들 정리
            if hasattr(self, 'providers'):
                for provider in self.providers:
                    if hasattr(provider, 'cleanup'):
                        try:
                            provider.cleanup()
                        except Exception as e:
                            logger.warning(f"⚠️ Provider 정리 중 오류: {e}")
                logger.info("✅ Provider들 정리 완료")
            
            logger.info("🎉 [SHUTDOWN] DCWidget 종료 프로세스 완료!")
            
        except Exception as e:
            logger.error(f"❌ [SHUTDOWN] 종료 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

    @contextmanager
    def user_action_priority(self):
        self.caching_manager.pause_sync()
        try:
            yield
        finally:
            self.caching_manager.resume_sync()

    def _load_cache_from_db(self):
        try:
            # 새로운 분리된 캐시 데이터베이스 사용
            from db_manager import get_db_manager
            db_manager = get_db_manager()
            
            with db_manager.get_cache_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT year, month, events_json FROM event_cache")
                for year, month, events_json in cursor.fetchall():
                    self.event_cache[(year, month)] = json.loads(events_json)
            logger.info(f"캐시 DB에서 {len(self.event_cache)}개의 월간 캐시를 로드했습니다.")
            # 시작 시 메모리-DB 캐시 동기화 확인
            self._sync_memory_cache_with_db()
        except sqlite3.Error as e:
            msg = "캐시 데이터베이스에서 캐시를 불러오는 중 오류가 발생했습니다."
            logger.error(msg, exc_info=True)
            self.report_error(f"{msg}\n{e}")

    def _save_month_to_cache_db(self, year, month, events):
        try:
            # 새로운 분리된 캐시 데이터베이스 사용
            from db_manager import get_db_manager
            db_manager = get_db_manager()
            
            with db_manager.get_cache_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO event_cache (year, month, events_json, cached_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (year, month, safe_json_dumps(events)))
                conn.commit()
            
            # 캐시 정리는 사용자의 월 이동 시에만 수행 (UI에서 트리거)
            
        except sqlite3.Error as e:
            logger.error("캐시 DB에 월간 캐시 저장 중 오류 발생", exc_info=True)

    def _remove_month_from_cache_db(self, year, month):
        try:
            # 새로운 분리된 캐시 데이터베이스 사용
            from db_manager import get_db_manager
            db_manager = get_db_manager()
            
            with db_manager.get_cache_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM event_cache WHERE year = ? AND month = ?", (year, month))
                conn.commit()
        except sqlite3.Error as e:
            logger.error("캐시 DB에서 월간 캐시 삭제 중 오류 발생", exc_info=True)
    
    def _schedule_cache_cleanup(self, center_year=None, center_month=None):
        """캐시 정리를 백그라운드에서 수행 (윈도우 변화시에만)"""
        try:
            # 기본값: 오늘 날짜 사용
            if center_year is None or center_month is None:
                import datetime
                today = datetime.date.today()
                center_year, center_month = today.year, today.month
            
            # 캐시 윈도우 변화 확인
            window_changed, current_window = self._check_cache_window_changed(center_year, center_month)
            
            # 변화가 없으면 정리하지 않음
            if not window_changed:
                logger.debug(f"[캐시 정리] 윈도우 변화 없음 - 정리 스킵")
                return
            
            import threading
            
            def cleanup_task():
                try:
                    from db_manager import get_db_manager
                    db_manager = get_db_manager()
                    
                    # 윈도우 변화가 있을 때만 정리 실행
                    deleted_count = db_manager.cleanup_old_cache(center_year, center_month)
                    if deleted_count > 0:
                        logger.info(f"[캐시 정리] 윈도우 변화로 인한 정리: {deleted_count}개 엔트리 삭제됨")
                        # DB 캐시 정리 후 메모리 캐시와 동기화
                        self._sync_memory_cache_with_db()
                    else:
                        logger.info(f"[캐시 정리] 윈도우 변화 있으나 삭제할 항목 없음")
                        
                except Exception as e:
                    logger.error(f"백그라운드 캐시 정리 실패: {e}")
            
            # 백그라운드 스레드에서 실행 (UI 블로킹 방지)
            cleanup_thread = threading.Thread(target=cleanup_task, daemon=True, name="CacheCleanup")
            cleanup_thread.start()
            
        except Exception as e:
            logger.error(f"캐시 정리 스케줄링 실패: {e}")

    def _sync_memory_cache_with_db(self):
        """메모리 캐시를 DB 캐시와 동기화"""
        try:
            from db_manager import get_db_manager
            db_manager = get_db_manager()
            
            # DB에서 현재 캐시된 월 정보 가져오기
            with db_manager.get_cache_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT year, month FROM event_cache")
                db_cached_months = set((row[0], row[1]) for row in cursor.fetchall())
            
            # 메모리 캐시에서 DB에 없는 항목 제거
            memory_months = set(self.event_cache.keys())
            to_remove = memory_months - db_cached_months
            
            removed_count = 0
            for year, month in to_remove:
                if (year, month) in self.event_cache:
                    del self.event_cache[(year, month)]
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"[캐시 동기화] 메모리에서 {removed_count}개 항목 제거: {[f'{y}-{m:02d}' for y, m in to_remove]}")
            
            logger.debug(f"[캐시 동기화] DB 캐시: {len(db_cached_months)}개, 메모리 캐시: {len(self.event_cache)}개")
            
        except Exception as e:
            logger.error(f"메모리-DB 캐시 동기화 실패: {e}")

    def _check_cache_window_changed(self, center_year, center_month):
        """캐시 윈도우가 변경되었는지 확인"""
        import datetime
        
        # 오늘 날짜
        today = datetime.date.today()
        today_key = (today.year, today.month)
        
        # 현재 윈도우 계산 (7개월: 중심월 ±3개월)
        current_window = set(self._calculate_sliding_window(center_year, center_month, 3))
        
        # 오늘 날짜가 윈도우에 없으면 강제로 추가 (항상 보호)
        if today_key not in current_window:
            current_window.add(today_key)
            logger.info(f"[캐시 윈도우] 오늘 날짜 {today.year}-{today.month:02d} 강제 추가 (영구 보호)")
        
        # 윈도우 변화 확인
        window_changed = current_window != self.last_cache_window
        
        if window_changed:
            # 변화 로그
            added = current_window - self.last_cache_window
            removed = self.last_cache_window - current_window
            
            if added:
                added_str = [f"{y}-{m:02d}" for y, m in sorted(added)]
                logger.info(f"[캐시 윈도우] 추가된 월: {', '.join(added_str)}")
            
            if removed:
                removed_str = [f"{y}-{m:02d}" for y, m in sorted(removed)]
                logger.info(f"[캐시 윈도우] 제거된 월: {', '.join(removed_str)}")
            
            # 윈도우 업데이트
            self.last_cache_window = current_window.copy()
            logger.info(f"[캐시 윈도우] 변화 감지: 중심월 {center_year}-{center_month:02d}, 총 {len(current_window)}개월")
        else:
            logger.debug(f"[캐시 윈도우] 변화 없음: 중심월 {center_year}-{center_month:02d}")
        
        return window_changed, current_window

    def _calculate_sliding_window(self, center_year, center_month, radius):
        """중심 월 기준으로 ±radius 개월의 슬라이딩 윈도우 계산 (중심월 포함)"""
        from dateutil.relativedelta import relativedelta
        
        months = []
        center_date = datetime.date(center_year, center_month, 1)
        
        for i in range(-radius, radius + 1):
            # 중심월도 포함하여 윈도우 구성
            target_date = center_date + relativedelta(months=i)
            months.append((target_date.year, target_date.month))
        
        return months

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
                    filtered_events = []
                    for event in events:
                        event_id = event.get('id')
                        
                        # [추가] 삭제 대기 중인 이벤트는 provider에서 가져와도 무시
                        if event_id in self.pending_deletion_ids:
                            logger.debug(f"Filtered out pending deletion event: {event_id}")
                            continue
                        
                        # 반복일정인 경우 마스터 ID도 확인
                        recurring_event_id = event.get('recurringEventId')
                        if recurring_event_id and recurring_event_id in self.pending_deletion_ids:
                            logger.debug(f"Filtered out recurring instance of pending deletion: {recurring_event_id}")
                            continue
                        
                        cal_id = event.get('calendarId')
                        if cal_id:
                            default_color = default_color_map.get(cal_id, DEFAULT_EVENT_COLOR)
                            event['color'] = custom_colors.get(cal_id, default_color)
                        filtered_events.append(event)
                    
                    all_events.extend(filtered_events)
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
                        # [추가] 삭제 대기 중인 이벤트는 제외
                        event_id = event.get('id')
                        if event_id not in self.pending_deletion_ids:
                            all_events.append(event)
                        else:
                            logger.info(f"[DELETE DEBUG] Filtered out pending deletion event: {event_id}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"이벤트 날짜 파싱 오류: {e}, 이벤트: {event.get('summary')}")
                    continue
        unique_events = {e['id']: e for e in all_events}.values()
        return list(unique_events)

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
        """Enhanced Local-first event addition with recurring events support"""
        provider_name = event_data.get('provider')
        logger.info(f"Enhanced Local-first add_event 시작: provider={provider_name}")
        
        # Provider 존재 확인
        found_provider = None
        for provider in self.providers:
            if provider.name == provider_name:
                found_provider = provider
                break
        
        if not found_provider:
            logger.warning(f"Provider '{provider_name}' not found. Available providers: {[p.name for p in self.providers]}")
            return False
        
        # 반복 일정 확인 및 처리
        event_body = event_data.get('body', {})
        recurrence = event_body.get('recurrence', [])
        
        if recurrence and len(recurrence) > 0:
            # 반복 일정의 Local-First 처리
            return self._add_recurring_event_local_first(event_data, recurrence[0])
        else:
            # 단일 이벤트의 기존 Local-First 처리
            return self._add_single_event_local_first(event_data)
        
    def _add_single_event_local_first(self, event_data):
        """단일 이벤트의 Local-First 추가 (기존 로직)"""
        # 1. 즉시 optimistic event 생성
        optimistic_event = self._create_optimistic_event(event_data)
        logger.info(f"Single optimistic event 생성: id={optimistic_event.get('id')}")
        
        # 2. 즉시 로컬 캐시 업데이트
        event_date = self._get_event_date(optimistic_event)
        self._update_cache_immediately(optimistic_event, event_date)
        logger.info(f"로컬 캐시 업데이트 완료: {event_date}")
        
        # 3. 즉시 UI 업데이트 발신
        self.data_updated.emit(event_date.year, event_date.month)
        logger.info(f"UI 업데이트 시그널 발신: {event_date.year}-{event_date.month}")
        
        # 4. 백그라운드에서 원격 동기화
        self._queue_remote_add_event(event_data, optimistic_event)
        
        return True
    
    def _add_recurring_event_local_first(self, event_data, rrule_string):
        """반복 일정의 Local-First 추가 - 모든 인스턴스 즉시 생성"""
        try:
            from rrule_parser import RRuleParser
            from dateutil import parser as dateutil_parser
            
            event_body = event_data.get('body', {})
            
            # 시작 날짜 파싱
            start_info = event_body.get('start', {})
            if 'dateTime' in start_info:
                start_datetime = dateutil_parser.parse(start_info['dateTime'])
            elif 'date' in start_info:
                date_str = start_info['date']
                start_datetime = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            else:
                logger.error("Invalid start datetime in recurring event")
                return False
            
            # RRULE 파싱하여 모든 반복 날짜 계산
            rrule_parser = RRuleParser()
            recurring_dates = rrule_parser.parse_google_rrule(
                rrule_string, start_datetime, max_instances=50
            )
            
            logger.info(f"Recurring event: generated {len(recurring_dates)} instances")
            
            # 모든 반복 인스턴스 생성 및 즉시 캐시에 추가
            affected_months = set()
            instances_added = 0
            
            # 모든 인스턴스에서 사용할 공통 base_id 생성
            import uuid
            base_id = event_body.get('id', 'unknown')
            if base_id == 'unknown':
                base_id = uuid.uuid4().hex[:8]
            
            logger.info(f"[RECURRING CREATE] Using common base_id: {base_id} for {len(recurring_dates)} instances")
            
            for i, recurring_date in enumerate(recurring_dates):
                # 반복 인스턴스 생성 (공통 base_id 사용)
                instance = self._create_recurring_instance(event_body, recurring_date, i, base_id)
                
                # Optimistic 이벤트로 변환
                optimistic_instance = self._create_optimistic_event_from_instance(event_data, instance)
                
                # 캐시에 추가 (중복 방지)
                instance_date = self._get_event_date(optimistic_instance)
                if instance_date:
                    cache_key = (instance_date.year, instance_date.month)
                    affected_months.add(cache_key)
                    
                    if cache_key not in self.event_cache:
                        self.event_cache[cache_key] = []
                    
                    # 중복 체크: 동일한 ID의 이벤트가 이미 존재하는지 확인
                    instance_id = optimistic_instance.get('id')
                    existing_event = next((e for e in self.event_cache[cache_key] if e.get('id') == instance_id), None)
                    
                    if not existing_event:
                        self.event_cache[cache_key].append(optimistic_instance)
                        instances_added += 1
                    else:
                        logger.warning(f"Duplicate recurring instance prevented: {instance_id}")
            
            # 영향받는 모든 월에 대해 중복 정리 및 UI 업데이트
            for year, month in affected_months:
                cache_key = (year, month)
                self._cleanup_duplicate_events(cache_key)
                self.data_updated.emit(year, month)
                logger.info(f"UI 업데이트 시그널 발신: {year}-{month}")
            
            # 백그라운드에서 원격 동기화 (첫 번째 인스턴스 사용)
            if instances_added > 0:
                # 첫 번째 생성된 인스턴스를 가져와서 원격 동기화에 사용
                first_instance = None
                for cache_key, events in self.event_cache.items():
                    for event in events:
                        if (event.get('_is_recurring_instance') and 
                            event.get('_instance_index') == 0 and
                            event.get('_sync_state') == 'pending'):
                            first_instance = event
                            break
                    if first_instance:
                        break
                
                if first_instance:
                    # 반복일정임을 표시하여 특별한 처리
                    first_instance['_is_recurring_master'] = True
                    self._queue_remote_add_recurring_event(event_data, first_instance)
            
            logger.info(f"Successfully added {instances_added} recurring instances to cache")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add recurring event: {e}")
            return False
    
    def _create_recurring_instance(self, base_event, recurring_date, index, base_id=None):
        """기본 이벤트에서 반복 인스턴스 생성"""
        import uuid
        
        instance = base_event.copy()
        
        # 고유 ID 생성 (안전하게) - base_id가 제공되지 않은 경우에만 생성
        if base_id is None:
            base_id = base_event.get('id', 'unknown')
            if base_id == 'unknown':
                base_id = uuid.uuid4().hex[:8]
        instance['id'] = f"temp_recurring_{base_id}_{index}"
        
        # 원본 시작/종료 시간 파싱
        original_start = self._parse_event_datetime(base_event.get('start', {}))
        original_end = self._parse_event_datetime(base_event.get('end', {}))
        
        if original_start and original_end:
            # 이벤트 지속 시간 계산
            duration = original_end - original_start
            
            # 새로운 시작/종료 시간 계산
            new_start = recurring_date.replace(
                hour=original_start.hour,
                minute=original_start.minute,
                second=original_start.second,
                microsecond=original_start.microsecond
            )
            new_end = new_start + duration
            
            # 시작/종료 시간 설정
            instance['start'] = self._format_event_datetime(new_start, base_event.get('start', {}))
            instance['end'] = self._format_event_datetime(new_end, base_event.get('end', {}))
        
        # 반복 정보 설정
        instance['_is_recurring_instance'] = True
        instance['_instance_index'] = index
        instance['_master_event_id'] = base_id
        
        return instance
    
    def _parse_event_datetime(self, datetime_obj):
        """이벤트의 날짜/시간 파싱"""
        try:
            from dateutil import parser as dateutil_parser
            if 'dateTime' in datetime_obj:
                return dateutil_parser.parse(datetime_obj['dateTime'])
            elif 'date' in datetime_obj:
                date_str = datetime_obj['date']
                return datetime.datetime.strptime(date_str, '%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Failed to parse event datetime: {e}")
        return None
    
    def _format_event_datetime(self, dt, original_format):
        """날짜/시간을 이벤트 형식으로 포맷팅"""
        if 'dateTime' in original_format:
            # 시간 포함 형식
            return {
                'dateTime': dt.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': original_format.get('timeZone', 'Asia/Seoul')
            }
        else:
            # 날짜만 형식 (종일 이벤트)
            return {
                'date': dt.strftime('%Y-%m-%d')
            }
    
    def _create_optimistic_event_from_instance(self, event_data, instance):
        """반복 인스턴스에서 Optimistic 이벤트 생성"""
        import uuid
        
        optimistic_event = instance.copy()
        
        # ID가 없는 경우 안전하게 생성
        if 'id' not in optimistic_event or not optimistic_event['id']:
            base_id = event_data.get('body', {}).get('id', 'unknown')
            index = optimistic_event.get('_instance_index', 0)
            optimistic_event['id'] = f"temp_recurring_{base_id}_{index}"
        
        # 기본 설정들
        optimistic_event['calendarId'] = event_data.get('calendarId')
        optimistic_event['provider'] = event_data.get('provider')
        optimistic_event['_sync_state'] = 'pending'
        
        # 색상 설정
        cal_id = optimistic_event.get('calendarId')
        if cal_id:
            target_color = self._get_calendar_color(cal_id)
            if target_color:
                optimistic_event['color'] = target_color
        
        return optimistic_event
        
    def _create_optimistic_event(self, event_data):
        """즉시 UI 업데이트를 위한 임시 이벤트 생성"""
        import uuid
        
        event_body = event_data.get('body', {})
        optimistic_event = event_body.copy()
        
        # 임시 ID 생성 (실제 API ID로 나중에 교체됨)
        if 'id' not in optimistic_event:
            optimistic_event['id'] = f"temp_{uuid.uuid4().hex[:8]}"
        
        # 필수 필드들 설정
        optimistic_event['calendarId'] = event_data.get('calendarId')
        optimistic_event['provider'] = event_data.get('provider')
        optimistic_event['_sync_state'] = 'pending'  # 동기화 상태 추가
        
        # 색상 정보 설정
        cal_id = optimistic_event.get('calendarId')
        if cal_id:
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
            default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
            optimistic_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
        
        return optimistic_event
    
    def _get_event_date(self, event):
        """이벤트의 날짜 추출"""
        start_str = event['start'].get('date') or event['start'].get('dateTime')[:10]
        return datetime.date.fromisoformat(start_str)
    
    def _update_cache_immediately(self, event, event_date):
        """즉시 로컬 캐시 업데이트"""
        cache_key = (event_date.year, event_date.month)
        if cache_key in self.event_cache:
            self.event_cache[cache_key].append(event)
        else:
            self.event_cache[cache_key] = [event]
    
    def _queue_remote_add_event(self, event_data, optimistic_event):
        """백그라운드에서 원격 동기화 실행"""
        class RemoteAddTask(QRunnable):
            def __init__(self, data_manager, event_data, optimistic_event):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.optimistic_event = optimistic_event
                
            def run(self):
                provider_name = self.event_data.get('provider')
                temp_id = self.optimistic_event.get('id')
                
                # ID가 없으면 동기화를 건너뛰고 로그만 출력
                if not temp_id:
                    logger.warning(f"Optimistic event has no ID, skipping remote sync")
                    return
                
                for provider in self.data_manager.providers:
                    if provider.name == provider_name:
                        try:
                            logger.info(f"원격 API 호출 시작: provider={provider_name}, temp_id={temp_id}")
                            # 실제 원격 API 호출
                            real_event = provider.add_event(self.event_data, self.data_manager)
                            if real_event:
                                logger.info(f"원격 API 호출 성공: real_id={real_event.get('id')}")
                                # 성공: 임시 이벤트를 실제 이벤트로 교체
                                self.data_manager._replace_optimistic_event(temp_id, real_event, provider_name)
                            else:
                                logger.warning(f"원격 API 호출 실패: provider.add_event returned None")
                                # 실패: 동기화 실패 상태로 마크
                                self.data_manager._mark_event_sync_failed(temp_id, "원격 추가 실패")
                        except Exception as e:
                            logger.error(f"원격 이벤트 추가 예외 발생: {e}")
                            self.data_manager._mark_event_sync_failed(temp_id, str(e))
                        break
        
        # 백그라운드 스레드에서 실행
        task = RemoteAddTask(self, event_data, optimistic_event)
        QThreadPool.globalInstance().start(task)
    
    def _queue_remote_add_recurring_event(self, event_data, first_instance):
        """반복일정 전용 백그라운드 원격 동기화"""
        class RemoteRecurringAddTask(QRunnable):
            def __init__(self, data_manager, event_data, first_instance):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.first_instance = first_instance
                
            def run(self):
                provider_name = self.event_data.get('provider')
                temp_id = self.first_instance.get('id')
                
                if not temp_id:
                    logger.warning(f"Recurring event has no ID, skipping remote sync")
                    return
                
                for provider in self.data_manager.providers:
                    if provider.name == provider_name:
                        try:
                            logger.info(f"원격 반복일정 API 호출 시작: provider={provider_name}, temp_id={temp_id}")
                            # 실제 원격 API 호출
                            real_event = provider.add_event(self.event_data, self.data_manager)
                            if real_event:
                                logger.debug(f"Recurring sync API call success: real_id={real_event.get('id')}")
                                logger.info(f"원격 반복일정 API 호출 성공: real_id={real_event.get('id')}")
                                logger.debug("Calling _replace_optimistic_recurring_events")
                                # 성공: 모든 반복 인스턴스를 실제 이벤트 기반으로 교체
                                self.data_manager._replace_optimistic_recurring_events(temp_id, real_event, provider_name)
                                logger.debug("_replace_optimistic_recurring_events completed")
                            else:
                                logger.warning(f"원격 반복일정 API 호출 실패: provider.add_event returned None")
                                # 실패: 동기화 실패 상태로 마크
                                self.data_manager._mark_recurring_events_sync_failed(temp_id, "원격 추가 실패")
                        except Exception as e:
                            logger.error(f"원격 반복일정 추가 예외 발생: {e}")
                            self.data_manager._mark_recurring_events_sync_failed(temp_id, str(e))
                        break
        
        # 백그라운드 스레드에서 실행
        task = RemoteRecurringAddTask(self, event_data, first_instance)
        QThreadPool.globalInstance().start(task)
    
    def _replace_optimistic_event(self, temp_id, real_event, provider_name):
        """임시 이벤트를 실제 이벤트로 교체"""
        logger.info(f"임시 이벤트 교체 시작: temp_id={temp_id}, real_id={real_event.get('id')}")
        
        if 'provider' not in real_event:
            real_event['provider'] = provider_name
        
        # 색상 정보 추가
        cal_id = real_event.get('calendarId')
        if cal_id:
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
            default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
            real_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
        
        real_event['_sync_state'] = 'synced'
        
        # 캐시에서 임시 이벤트 찾아서 교체
        event_date = self._get_event_date(real_event)
        cache_key = (event_date.year, event_date.month)
        
        found_and_replaced = False
        if cache_key in self.event_cache:
            events = self.event_cache[cache_key]
            for i, event in enumerate(events):
                if event.get('id') == temp_id:
                    events[i] = real_event
                    found_and_replaced = True
                    logger.info(f"임시 이벤트 교체 완료: {temp_id} -> {real_event.get('id')}")
                    break
        
        if not found_and_replaced:
            logger.warning(f"임시 이벤트를 찾을 수 없음: temp_id={temp_id}, cache_key={cache_key}")
            # 임시 이벤트를 찾을 수 없는 경우 새로 추가
            if cache_key in self.event_cache:
                self.event_cache[cache_key].append(real_event)
            else:
                self.event_cache[cache_key] = [real_event]
            logger.info(f"실제 이벤트를 새로 추가함: {real_event.get('id')}")
        
        # UI 업데이트
        self.data_updated.emit(event_date.year, event_date.month)
    
    def _replace_optimistic_recurring_events(self, temp_id, real_master_event, provider_name):
        """모든 반복 인스턴스를 실제 이벤트 기반으로 교체"""
        logger.info(f"[REPLACE DEBUG] 반복일정 교체 시작: temp_id={temp_id}, real_id={real_master_event.get('id')}")
        
        # 마스터 이벤트 ID 추출 (temp_recurring_BASE_INDEX에서 BASE 부분)
        master_event_id = self._extract_master_event_id(temp_id)
        logger.info(f"[REPLACE DEBUG] Extracted master_event_id: {master_event_id}")
        
        # 실제 이벤트에서 반복 정보 추출하여 새로운 인스턴스 생성 필요
        # 하지만 Google은 단일 마스터 이벤트만 반환하므로, 
        # 임시 인스턴스들을 실제 이벤트 정보로 업데이트해야 함
        
        affected_months = set()
        instances_replaced = 0
        
        for cache_key, events in self.event_cache.items():
            updated_events = []
            logger.info(f"[REPLACE DEBUG] Checking cache_key {cache_key} with {len(events)} events")
            
            for event in events:
                event_id = event.get('id', 'NO_ID')
                is_related = self._is_related_recurring_event(event, master_event_id)
                logger.debug(f"[REPLACE DEBUG] Event {event_id}: is_related={is_related}")
                
                if is_related:
                    # 임시 인스턴스를 실제 정보로 업데이트
                    logger.info(f"[REPLACE DEBUG] Updating temp event: {event_id}")
                    updated_event = self._update_recurring_instance_with_real_data(event, real_master_event, provider_name)
                    updated_events.append(updated_event)
                    instances_replaced += 1
                    affected_months.add(cache_key)
                else:
                    updated_events.append(event)
            
            self.event_cache[cache_key] = updated_events
        
        # 영향받는 모든 월에 대해 한 번에 UI 업데이트 (배치 처리)
        if affected_months:
            # 모든 월을 동시에 업데이트 (깜빡임 방지)
            from PyQt6.QtCore import QTimer
            def update_all_affected_months():
                for year, month in affected_months:
                    self.data_updated.emit(year, month)
                logger.info(f"[REPLACE DEBUG] UI updated for all affected months: {list(affected_months)}")
            
            QTimer.singleShot(10, update_all_affected_months)  # 더 짧은 지연으로 빠른 업데이트
        
        logger.info(f"[REPLACE DEBUG] 반복일정 교체 완료: {instances_replaced}개 인스턴스 업데이트")
        logger.info(f"[REPLACE DEBUG] Affected months: {affected_months}")
        
        # 교체 후 캐시 상태 확인
        for cache_key in affected_months:
            events_in_cache = len(self.event_cache.get(cache_key, []))
            logger.debug(f"[REPLACE DEBUG] After replacement, cache {cache_key} has {events_in_cache} events")
    
    def _update_recurring_instance_with_real_data(self, temp_instance, real_master_event, provider_name):
        """임시 반복 인스턴스를 실제 이벤트 데이터로 업데이트"""
        updated_instance = temp_instance.copy()
        
        # 임시 ID를 실제 Google 인스턴스 ID 형태로 변경
        temp_id = temp_instance.get('id', '')
        master_id = real_master_event.get('id')
        
        # Google Calendar 인스턴스 ID 형태로 변경
        if temp_id.startswith('temp_recurring_') and master_id:
            # 인스턴스의 시작 시간을 기반으로 Google 형태의 ID 생성
            start_time = temp_instance.get('start', {})
            if start_time.get('dateTime'):
                # 날짜시간에서 Google 형식으로 변환 (예: 20250803T080000Z)
                import datetime
                try:
                    dt = datetime.datetime.fromisoformat(start_time['dateTime'].replace('Z', '+00:00'))
                    time_suffix = dt.strftime('%Y%m%dT%H%M%SZ')
                    updated_instance['id'] = f"{master_id}_{time_suffix}"
                    logger.debug(f"[UPDATE DEBUG] Changed temp ID {temp_id} to real ID {updated_instance['id']}")
                except:
                    # 시간 파싱 실패 시 마스터 ID만 사용
                    updated_instance['id'] = master_id
                    logger.debug(f"[UPDATE DEBUG] Time parse failed, using master ID: {master_id}")
            else:
                # 전일 이벤트인 경우
                updated_instance['id'] = master_id
        
        # 실제 이벤트의 정보로 업데이트 (시간은 유지)
        updated_instance.update({
            'provider': provider_name,
            '_sync_state': 'synced',
            'summary': real_master_event.get('summary', updated_instance.get('summary')),
            'description': real_master_event.get('description', updated_instance.get('description')),
            'location': real_master_event.get('location', updated_instance.get('location')),
        })
        
        # 색상 정보 추가
        cal_id = real_master_event.get('calendarId')
        if cal_id:
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
            default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
            updated_instance['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
        
        # 실제 Google 이벤트와의 연결 정보 추가
        updated_instance['_google_master_id'] = real_master_event.get('id')
        updated_instance['recurringEventId'] = real_master_event.get('id')  # Google 형식에 맞게 추가
        
        return updated_instance
    
    def _mark_recurring_events_sync_failed(self, temp_id, error_msg):
        """모든 반복 인스턴스의 동기화 실패 마크"""
        logger.warning(f"반복일정 동기화 실패: temp_id={temp_id}, error={error_msg}")
        
        master_event_id = self._extract_master_event_id(temp_id)
        affected_months = set()
        
        for cache_key, events in self.event_cache.items():
            for event in events:
                if self._is_related_recurring_event(event, master_event_id):
                    event['_sync_state'] = 'failed'
                    event['_sync_error'] = error_msg
                    affected_months.add(cache_key)
        
        # 영향받는 모든 월에 대해 UI 업데이트
        for year, month in affected_months:
            self.data_updated.emit(year, month)
    
    def _mark_event_sync_failed(self, temp_id, error_msg):
        """이벤트 동기화 실패 마크"""
        logger.warning(f"이벤트 동기화 실패: temp_id={temp_id}, error={error_msg}")
        
        # 모든 캐시에서 해당 이벤트 찾아서 실패 상태로 마크
        found_event = False
        for cache_key, events in self.event_cache.items():
            for event in events:
                if event.get('id') == temp_id:
                    event['_sync_state'] = 'failed'
                    event['_sync_error'] = error_msg
                    found_event = True
                    logger.info(f"임시 이벤트 실패 상태로 마크: {temp_id}")
                    # UI 업데이트하여 실패 상태 표시
                    year, month = cache_key
                    self.data_updated.emit(year, month)
                    return
        
        if not found_event:
            logger.error(f"실패 마크할 임시 이벤트를 찾을 수 없음: temp_id={temp_id}")
    
    def _merge_events_preserving_temp(self, year, month, new_events):
        """임시 이벤트를 보존하면서 새로운 이벤트로 캐시 업데이트 (반복일정 중복 방지)"""
        cache_key = (year, month)
        existing_events = self.event_cache.get(cache_key, [])
        
        # 기존 캐시에서 임시 이벤트와 실패한 이벤트 찾기
        temp_events = []
        synced_temp_events = []  # 이미 동기화된 임시 이벤트들
        
        for event in existing_events:
            event_id = event.get('id', '')
            sync_state = event.get('_sync_state')
            
            # 임시 이벤트이거나 동기화 실패한 이벤트는 구분하여 처리
            if 'temp_' in event_id:
                if sync_state == 'synced':
                    synced_temp_events.append(event)
                elif sync_state in ['pending', 'failed']:
                    temp_events.append(event)
        
        # 새로운 이벤트 중에서 이미 존재하는 것과 중복되지 않는 것만 추가
        unique_new_events = []
        
        for new_event in new_events:
            is_duplicate = False
            google_id = new_event.get('id')
            
            # [추가] 삭제 대기 중인 이벤트는 캐시에 추가하지 않음
            if google_id in self.pending_deletion_ids:
                logger.info(f"[DELETE DEBUG] Blocked pending deletion event from cache: {google_id}")
                continue
                
            # 반복 이벤트의 경우 마스터 ID도 확인
            recurring_event_id = new_event.get('recurringEventId')
            if recurring_event_id and recurring_event_id in self.pending_deletion_ids:
                logger.info(f"[DELETE DEBUG] Blocked recurring instance of pending deletion master: {recurring_event_id}")
                continue
            
            # 1. 이미 동기화된 임시 이벤트와 중복 확인 (Google Master ID로)
            for synced_event in synced_temp_events:
                if synced_event.get('_google_master_id') == google_id:
                    is_duplicate = True
                    logger.debug(f"중복 방지: Google 이벤트 {google_id}는 이미 동기화된 임시 이벤트 존재")
                    break
            
            # 2. 새로운 이벤트들 간의 중복 확인
            if not is_duplicate:
                for existing_new in unique_new_events:
                    if self._is_duplicate_event(new_event, existing_new):
                        is_duplicate = True
                        logger.debug(f"중복 방지: 새로운 이벤트들 간 중복 발견")
                        break
            
            # 3. 반복일정의 경우 제목, 시간 기반 중복 확인 (임시 이벤트와)
            if not is_duplicate and new_event.get('recurringEventId'):
                for temp_event in temp_events:
                    if self._is_same_recurring_event(new_event, temp_event):
                        is_duplicate = True
                        logger.debug(f"중복 방지: 반복일정 매칭됨 (임시) - {new_event.get('summary')}")
                        break
            
            # 4. 반복일정의 경우 이미 동기화된 이벤트와의 중복 확인
            if not is_duplicate and new_event.get('recurringEventId'):
                new_event_id = new_event.get('id')
                new_recurring_id = new_event.get('recurringEventId')
                
                for synced_event in synced_temp_events:
                    # 동일한 마스터 이벤트에서 나온 인스턴스인지 확인
                    synced_master_id = synced_event.get('_google_master_id')
                    synced_event_id = synced_event.get('id', '')
                    
                    if (synced_master_id == new_recurring_id or 
                        synced_event_id == new_event_id or
                        self._is_same_recurring_event(new_event, synced_event)):
                        is_duplicate = True
                        logger.debug(f"[MERGE DEBUG] 중복 방지: 이미 동기화된 반복일정과 매칭됨 - {new_event.get('summary')}")
                        break
            
            if not is_duplicate:
                unique_new_events.append(new_event)
        
        # 모든 이벤트 합치기: 고유한 새 이벤트 + 동기화된 임시 이벤트 + 보존할 임시 이벤트
        merged_events = unique_new_events + synced_temp_events + temp_events
        
        # 캐시 업데이트
        self.event_cache[cache_key] = merged_events
        logger.info(f"캐시 병합 완료: {year}-{month}, 전체={len(merged_events)}개 "
                   f"(새이벤트={len(unique_new_events)}, 동기화완료={len(synced_temp_events)}, 임시보존={len(temp_events)})")
    
    def _is_duplicate_event(self, event1, event2):
        """두 이벤트가 중복인지 확인"""
        # ID가 동일한 경우
        if event1.get('id') == event2.get('id'):
            return True
        
        # 제목, 시작시간, 종료시간이 모두 동일한 경우
        if (event1.get('summary') == event2.get('summary') and
            event1.get('start') == event2.get('start') and
            event1.get('end') == event2.get('end')):
            return True
            
        return False
    
    def _is_same_recurring_event(self, google_event, temp_event):
        """Google 이벤트와 임시 반복 이벤트가 같은 이벤트인지 확인"""
        # 1. 제목이 같고
        if google_event.get('summary') != temp_event.get('summary'):
            return False
        
        # 2. 시간이 비슷하고 (반복일정의 각 인스턴스)
        google_start = google_event.get('start', {})
        temp_start = temp_event.get('start', {})
        
        # 시작 시간 비교 (날짜는 다를 수 있지만 시간은 같아야 함)
        google_time = google_start.get('dateTime', google_start.get('date', ''))
        temp_time = temp_start.get('dateTime', temp_start.get('date', ''))
        
        if google_time and temp_time:
            try:
                # 시간 부분만 비교 (HH:MM)
                google_time_part = google_time.split('T')[1][:5] if 'T' in google_time else ''
                temp_time_part = temp_time.split('T')[1][:5] if 'T' in temp_time else ''
                
                if google_time_part == temp_time_part:
                    return True
            except:
                pass
        
        return False

    # Local-first delete_event method
    def delete_event(self, event_data, deletion_mode='all'):
        """Enhanced Local-first event deletion with recurring events support"""
        logger.info("delete_event called")
        event_body = event_data.get('body', event_data)
        event_id = event_body.get('id')
        
        logger.info(f"Deleting event: {event_id}, mode: {deletion_mode}")
        logger.info(f"[DELETE DEBUG] Enhanced Local-first delete_event: id={event_id}, mode={deletion_mode}")
        logger.info(f"[DELETE DEBUG] Event data: {event_data}")
        logger.info(f"[DELETE DEBUG] Event body keys: {list(event_body.keys())}")
        
        # 반복 일정인지 확인
        is_recurring = self._is_recurring_event(event_id)
        logger.info(f"[DELETE DEBUG] Is recurring: {is_recurring}")
        
        if is_recurring and deletion_mode == 'all':
            # 반복 일정 전체 삭제
            return self._delete_all_recurring_instances(event_data)
        elif is_recurring and deletion_mode in ['instance', 'future']:
            # 반복 일정 부분 삭제 - 추후 구현
            logger.warning(f"Recurring partial deletion ({deletion_mode}) not fully implemented yet")
            return self._delete_single_event_local_first(event_data, deletion_mode)
        else:
            # 단일 이벤트 삭제
            return self._delete_single_event_local_first(event_data, deletion_mode)
    
    def _delete_single_event_local_first(self, event_data, deletion_mode):
        """단일 이벤트의 Local-First 삭제 (기존 로직)"""
        event_body = event_data.get('body', event_data)
        event_id = event_body.get('id')
        
        # 1. 즉시 로컬 캐시에서 이벤트 찾기 및 백업
        deleted_event, cache_key = self._find_and_backup_event(event_id)
        if not deleted_event:
            logger.warning(f"Event {event_id} not found in cache")
            return False
        
        # 2. 즉시 로컬 캐시에서 이벤트 제거
        self._remove_event_from_cache(event_id)
        
        # 3. 즉시 완료 상태 정리
        self.unmark_event_as_completed(event_id)
        
        # 4. [추가] 삭제 대기 목록에 추가
        self.pending_deletion_ids.add(event_id)
        logger.info(f"[DELETE DEBUG] Added single event to pending deletion: {event_id}")
        
        # 5. 즉시 UI 업데이트
        year, month = cache_key
        self.data_updated.emit(year, month)
        
        # 6. 백그라운드에서 원격 동기화
        self._queue_remote_delete_event(event_data, deleted_event, deletion_mode)
        
        return True
    
    def _delete_all_recurring_instances(self, event_data):
        """반복 일정의 모든 인스턴스 즉시 삭제"""
        try:
            # [추가] 배치 삭제 모드 시작 - UI refresh 차단
            self.batch_deletion_mode = True
            logger.debug("Batch deletion mode started")
            logger.info(f"[DELETE DEBUG] Batch deletion mode started")
            
            event_body = event_data.get('body', event_data)
            event_id = event_body.get('id')
            
            logger.info(f"[DELETE DEBUG] _delete_all_recurring_instances called")
            logger.info(f"[DELETE DEBUG] Original event_id: {event_id}")
            logger.info(f"[DELETE DEBUG] Event body: {event_body}")
            
            # 마스터 이벤트 ID 추출
            master_event_id = self._extract_master_event_id(event_id)
            logger.info(f"[DELETE DEBUG] Extracted master_event_id: {master_event_id}")
            
            logger.info(f"Deleting all recurring instances for master_id: {master_event_id}")
            
            # 모든 캐시에서 관련 반복 인스턴스 찾기 및 삭제
            affected_months = set()
            instances_deleted = 0
            deleted_event_ids = []  # 삭제된 이벤트 ID 추적
            
            for cache_key, events in self.event_cache.items():
                # 삭제할 이벤트들 찾기
                events_to_remove = []
                logger.debug(f"Checking cache_key {cache_key} with {len(events)} events")
                logger.info(f"[DELETE DEBUG] Checking cache_key {cache_key} with {len(events)} events")
                
                for i, event in enumerate(events):
                    event_id = event.get('id', 'NO_ID')
                    sync_state = event.get('_sync_state', 'NO_STATE')
                    google_master_id = event.get('_google_master_id', 'NO_GOOGLE_ID')
                    
                    logger.info(f"[DELETE DEBUG] Event {i}: id={event_id}, sync_state={sync_state}, google_master_id={google_master_id}")
                    
                    is_related = self._is_related_recurring_event(event, master_event_id)
                    if is_related:
                        events_to_remove.append(event)
                        deleted_event_ids.append(event_id)  # 삭제된 ID 기록
                        # 완료 상태도 정리
                        self.unmark_event_as_completed(event.get('id'))
                        logger.debug(f"Found recurring instance to delete: {event.get('id')}")
                        logger.debug(f"Event summary: {event.get('summary', 'NO_SUMMARY')}")
                        logger.info(f"[DELETE DEBUG] Found recurring instance to delete: {event.get('id')}")
                        logger.info(f"[DELETE DEBUG] Event summary: {event.get('summary', 'NO_SUMMARY')}")
                    else:
                        logger.debug(f"Event {event_id} not related to master {master_event_id}")
                        logger.debug(f"[DELETE DEBUG] Event {event_id} not related to master {master_event_id}")
                
                # 이벤트 삭제 (안전한 방식으로)
                if events_to_remove:
                    original_count = len(events)
                    # 새로운 리스트로 교체 (안전한 삭제)
                    remaining_events = []
                    for event in events:
                        if event not in events_to_remove:
                            remaining_events.append(event)
                    
                    self.event_cache[cache_key] = remaining_events
                    deleted_count = original_count - len(remaining_events)
                    instances_deleted += deleted_count
                    affected_months.add(cache_key)
                    
                    logger.debug(f"Deleted {deleted_count} events from cache_key {cache_key}")
                    logger.info(f"Deleted {deleted_count} events from cache_key {cache_key}")
            
            # [추가] 삭제된 이벤트 ID들을 pending deletion으로 추가
            # 마스터 ID와 모든 인스턴스 ID 포함
            self.pending_deletion_ids.add(master_event_id)
            for deleted_id in deleted_event_ids:
                self.pending_deletion_ids.add(deleted_id)
            logger.info(f"[DELETE DEBUG] Added to pending deletion: master={master_event_id}, instances={deleted_event_ids}")
            
            # 영향받는 모든 월에 대해 동시에 UI 업데이트 (지연 없이 한번에)
            if affected_months:
                # QTimer를 사용해 다음 이벤트 루프에서 모든 UI 업데이트를 한번에 처리
                from PyQt6.QtCore import QTimer
                for year, month in affected_months:
                    QTimer.singleShot(0, lambda y=year, m=month: self.data_updated.emit(y, m))
                logger.info(f"UI 업데이트 시그널 발신 (동시): {list(affected_months)}")
            
            # 백그라운드에서 실제 삭제 처리
            logger.info(f"[DELETE DEBUG] Queuing remote delete for event_data: {event_data}")
            logger.info(f"[DELETE DEBUG] Queuing remote delete for event_body: {event_body}")
            self._queue_remote_delete_event(event_data, event_body, 'all')
            
            logger.info(f"Successfully deleted {instances_deleted} recurring instances from cache")
            return instances_deleted > 0
            
        except Exception as e:
            logger.error(f"Failed to delete recurring event: {e}")
            # [추가] 오류 시에도 배치 삭제 모드 해제
            self.batch_deletion_mode = False
            return False
    
    def _is_recurring_event(self, event_id):
        """이벤트가 반복 일정인지 확인"""
        if not event_id:
            return False
        
        # 임시 ID 패턴 확인
        if event_id.startswith('temp_recurring_'):
            return True
        
        # 캐시에서 이벤트 찾아서 반복 정보 확인
        for cache_key, events in self.event_cache.items():
            for event in events:
                if event.get('id') == event_id:
                    return (event.get('_is_recurring_instance', False) or 
                           'recurrence' in event or
                           event.get('recurringEventId') is not None)
        
        return False
    
    def _extract_master_event_id(self, event_id):
        """이벤트 ID에서 마스터 이벤트 ID 추출"""
        if event_id and event_id.startswith('temp_recurring_'):
            # temp_recurring_base_id_index에서 base_id 추출
            parts = event_id.split('_')
            if len(parts) >= 3:
                return '_'.join(parts[2:-1])  # 마지막 인덱스 제외
        
        # Google 반복일정 패턴 처리 (masterid_timestamp 형태)
        if event_id and '_' in event_id and event_id.split('_')[-1].endswith('Z'):
            # 타임스탬프 부분을 제거하여 마스터 ID 추출
            master_id = event_id.rsplit('_', 1)[0]
            logger.debug(f"Master event ID extracted: {event_id} -> {master_id}")
            return master_id
        
        return event_id
    
    def _is_related_recurring_event(self, event, master_event_id):
        """이벤트가 특정 마스터 이벤트의 인스턴스인지 확인 (강화된 버전)"""
        event_id = event.get('id', '')
        
        # 1. 직접적인 마스터 이벤트 ID 매치
        if event.get('_master_event_id') == master_event_id:
            return True
        
        # 2. 동일한 ID (마스터 이벤트 자체)
        if event.get('id') == master_event_id:
            return True
        
        # 3. 임시 반복 ID 패턴 매치
        if event_id.startswith('temp_recurring_'):
            # temp_recurring_BASE_INDEX 형태에서 BASE 부분 추출
            parts = event_id.split('_')
            if len(parts) >= 3:
                # 마지막 부분(인덱스) 제외하고 base 부분 추출
                event_base_id = '_'.join(parts[2:-1])
                if event_base_id == master_event_id:
                    return True
                # 부분 매치도 확인 (안전장치)
                if master_event_id in event_base_id:
                    return True
        
        # 4. Google 반복일정 패턴 확인 (masterid_timestamp 형태)
        if '_' in event_id and event_id.split('_')[-1].endswith('Z'):
            # Google 인스턴스 ID에서 마스터 ID 추출
            event_master_id = event_id.rsplit('_', 1)[0]
            if event_master_id == master_event_id:
                return True
                
        # 5. recurringEventId 확인
        if event.get('recurringEventId') == master_event_id:
            return True
        
        # 6. 반복 이벤트 특성 확인
        if event.get('_is_recurring_instance') and master_event_id in str(event_id):
            return True
            
        return False
    
    def _cleanup_duplicate_events(self, cache_key):
        """특정 캐시 키에서 중복 이벤트 정리"""
        if cache_key not in self.event_cache:
            return
            
        events = self.event_cache[cache_key]
        seen_ids = set()
        unique_events = []
        
        for event in events:
            event_id = event.get('id')
            if event_id and event_id not in seen_ids:
                seen_ids.add(event_id)
                unique_events.append(event)
            elif event_id:
                logger.warning(f"Removed duplicate event: {event_id}")
        
        if len(unique_events) != len(events):
            self.event_cache[cache_key] = unique_events
            logger.info(f"Cleaned up {len(events) - len(unique_events)} duplicate events in {cache_key}")
    
    def _remove_event_from_cache(self, event_id):
        """캐시에서 이벤트 제거"""
        for cache_key, events in self.event_cache.items():
            self.event_cache[cache_key] = [e for e in events if e.get('id') != event_id]
    
    def _queue_remote_delete_event(self, event_data, deleted_event, deletion_mode):
        """백그라운드에서 원격 삭제 동기화"""
        class RemoteDeleteTask(QRunnable):
            def __init__(self, data_manager, event_data, deleted_event, deletion_mode):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.deleted_event = deleted_event
                self.deletion_mode = deletion_mode
                
            def run(self):
                provider_name = self.event_data.get('provider')
                event_id = self.deleted_event.get('id', 'NO_ID')
                
                logger.info(f"[DELETE DEBUG] RemoteDeleteTask.run() called")
                logger.info(f"[DELETE DEBUG] Provider: {provider_name}")
                logger.info(f"[DELETE DEBUG] Event ID for deletion: {event_id}")
                logger.info(f"[DELETE DEBUG] Deleted event data: {self.deleted_event}")
                logger.info(f"[DELETE DEBUG] Event data for provider: {self.event_data}")
                logger.info(f"[DELETE DEBUG] Deletion mode: {self.deletion_mode}")
                
                # 임시 ID 체크
                if event_id.startswith('temp_'):
                    logger.warning(f"[DELETE DEBUG] PROBLEM: Trying to delete with temporary ID: {event_id}")
                    # 실제 Google ID 찾기 시도
                    google_id = self.deleted_event.get('_google_master_id')
                    if google_id:
                        logger.info(f"[DELETE DEBUG] Found linked Google ID: {google_id}")
                        # 실제 Google ID로 이벤트 데이터 업데이트
                        updated_event_data = self.event_data.copy()
                        updated_event_data['body'] = self.deleted_event.copy()
                        updated_event_data['body']['id'] = google_id
                        logger.info(f"[DELETE DEBUG] Updated event data for deletion: {updated_event_data}")
                    else:
                        logger.error(f"[DELETE DEBUG] No Google ID found for temp event: {event_id}")
                        return
                
                for provider in self.data_manager.providers:
                    if provider.name == provider_name:
                        try:
                            # 실제 원격 API 호출
                            success = provider.delete_event(updated_event_data if 'updated_event_data' in locals() else self.event_data, 
                                                           data_manager=self.data_manager, deletion_mode=self.deletion_mode)
                            if success:
                                # 성공: 삭제 확인 및 pending deletion에서 제거
                                logger.info(f"이벤트 {event_id} 원격 삭제 성공")
                                
                                # 반복일정 전체 삭제인 경우 모든 관련 인스턴스를 한번에 제거
                                # Google 반복일정 패턴: masterid_timestamp 형태
                                has_timestamp_suffix = '_' in event_id and event_id.split('_')[-1].endswith('Z')
                                is_recurring = (event_id.startswith('temp_recurring_') or 
                                              self.deleted_event.get('recurringEventId') or
                                              has_timestamp_suffix)  # Google recurring event pattern
                                
                                logger.debug(f"Checking recurring status: mode={self.deletion_mode}, is_recurring={is_recurring}")
                                logger.debug(f"Event ID pattern: {event_id}")
                                logger.debug(f"Deleted event recurringEventId: {self.deleted_event.get('recurringEventId')}")
                                logger.debug(f"Has timestamp suffix: {has_timestamp_suffix}")
                                
                                if self.deletion_mode == 'all' and is_recurring:
                                    logger.debug("Calling _remove_all_recurring_from_pending_deletion")
                                    self.data_manager._remove_all_recurring_from_pending_deletion(event_id, self.deleted_event)
                                else:
                                    logger.debug("Calling _remove_from_pending_deletion (single)")
                                    self.data_manager._remove_from_pending_deletion(event_id)
                            else:
                                # 실패: 이벤트를 캐시에 복원
                                self.data_manager._restore_deleted_event(self.deleted_event, "원격 삭제 실패")
                        except Exception as e:
                            logger.error(f"원격 이벤트 삭제 실패: {e}")
                            self.data_manager._restore_deleted_event(self.deleted_event, str(e))
                        break
        
        # 백그라운드 스레드에서 실행
        task = RemoteDeleteTask(self, event_data, deleted_event, deletion_mode)
        QThreadPool.globalInstance().start(task)
    
    def _restore_deleted_event(self, deleted_event, error_msg):
        """삭제 실패 시 이벤트 복원"""
        event_id = deleted_event.get('id')
        event_summary = deleted_event.get('summary', 'No summary')
        print(f"DEBUG: _restore_deleted_event called for event: {event_summary} (ID: {event_id})")
        print(f"DEBUG: Error: {error_msg}")
        
        deleted_event['_sync_state'] = 'failed'
        deleted_event['_sync_error'] = error_msg
        
        # [추가] 삭제 실패 시 pending deletion에서 제거
        self._remove_from_pending_deletion(event_id)
        
        # 이벤트 날짜로 적절한 캐시에 복원
        event_date = self._get_event_date(deleted_event)
        cache_key = (event_date.year, event_date.month)
        
        if cache_key in self.event_cache:
            self.event_cache[cache_key].append(deleted_event)
        else:
            self.event_cache[cache_key] = [deleted_event]
        
        # UI 업데이트하여 복원된 이벤트 표시
        self.data_updated.emit(event_date.year, event_date.month)
    
    def _remove_from_pending_deletion(self, event_id):
        """삭제 대기 목록에서 이벤트 ID 제거"""
        if event_id in self.pending_deletion_ids:
            self.pending_deletion_ids.remove(event_id)
            logger.info(f"[DELETE DEBUG] Removed {event_id} from pending deletion")
        
        # 마스터 ID 관련 모든 ID들도 제거 (반복 이벤트 대응)
        if event_id.startswith('temp_recurring_'):
            master_id = self._extract_master_event_id(event_id)
            self.pending_deletion_ids.discard(master_id)
            
            # 관련된 모든 인스턴스 ID들도 제거
            to_remove = []
            for pending_id in self.pending_deletion_ids:
                if (pending_id.startswith('temp_recurring_') and 
                    self._extract_master_event_id(pending_id) == master_id):
                    to_remove.append(pending_id)
            
            for remove_id in to_remove:
                self.pending_deletion_ids.discard(remove_id)
            
            logger.info(f"[DELETE DEBUG] Removed master {master_id} and {len(to_remove)} related instances from pending deletion")
    
    def _remove_all_recurring_from_pending_deletion(self, event_id, deleted_event):
        """반복일정의 모든 인스턴스를 한번에 pending deletion에서 제거하고 UI 업데이트"""
        logger.info(f"[DELETE DEBUG] _remove_all_recurring_from_pending_deletion called with batch_mode: {self.batch_deletion_mode}")
        
        try:
            # 마스터 이벤트 ID 추출
            if event_id.startswith('temp_recurring_'):
                master_id = self._extract_master_event_id(event_id)
            else:
                # Google ID인 경우 - recurringEventId 또는 timestamp 제거하여 master ID 추출
                master_id = deleted_event.get('recurringEventId')
                if not master_id:
                    # Google 반복일정 인스턴스 ID에서 마스터 ID 추출 (timestamp 부분 제거)
                    if '_' in event_id and event_id.split('_')[-1].endswith('Z'):
                        master_id = event_id.rsplit('_', 1)[0]  # 마지막 _timestamp 부분 제거
                    else:
                        master_id = event_id
            
            logger.info(f"[DELETE DEBUG] _remove_all_recurring_from_pending_deletion: master_id={master_id}")
            
            # 제거될 모든 ID들 수집
            removed_ids = []
            affected_months = set()
            
            # 마스터 ID 제거
            if master_id in self.pending_deletion_ids:
                self.pending_deletion_ids.remove(master_id)
                removed_ids.append(master_id)
            
            # 관련된 모든 인스턴스 ID들 제거
            to_remove = []
            for pending_id in list(self.pending_deletion_ids):  # 복사본으로 안전한 순회
                if (pending_id.startswith('temp_recurring_') and 
                    self._extract_master_event_id(pending_id) == master_id):
                    to_remove.append(pending_id)
                    
                    # 해당 이벤트가 어느 월에 속하는지 확인
                    for cache_key, events in self.event_cache.items():
                        for event in events:
                            if event.get('id') == pending_id:
                                affected_months.add(cache_key)
                                break
            
            # 실제 제거
            for remove_id in to_remove:
                self.pending_deletion_ids.discard(remove_id)
                removed_ids.append(remove_id)
            
            logger.info(f"[DELETE DEBUG] Removed all recurring instances: master={master_id}, instances={len(to_remove)}")
            logger.info(f"[DELETE DEBUG] Total removed IDs: {removed_ids}")
            logger.info(f"[DELETE DEBUG] Affected months: {affected_months}")
            
        finally:
            # 배치 삭제 모드 비활성화
            logger.info(f"[DELETE DEBUG] Disabling batch deletion mode")
            self.batch_deletion_mode = False
            
            # 영향받는 모든 월에 대해 동시에 UI 업데이트 (100ms 지연으로 Google API 삭제와 동기화)
            from PyQt6.QtCore import QTimer
            if affected_months:
                def update_all_months():
                    logger.info(f"[DELETE DEBUG] Final UI update after Google deletion completed")
                    for year, month in affected_months:
                        self.data_updated.emit(year, month)
                    logger.info(f"[DELETE DEBUG] UI 업데이트 완료 (모든 인스턴스 동시): {list(affected_months)}")
                
                QTimer.singleShot(100, update_all_months)

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
                        # [추가] 삭제 대기 중인 이벤트는 제외
                        event_id = event.get('id')
                        if event_id not in self.pending_deletion_ids:
                            all_events.append(event)
                        else:
                            logger.info(f"[DELETE DEBUG] Filtered out pending deletion event: {event_id}")
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
        # [IMPROVED] Direct synchronous execution to avoid threading issues
        logger.info("캘린더 목록 동기 로딩 시작...")
        all_calendars = []
        for provider in self.providers:
            if hasattr(provider, 'get_calendars'):
                try:
                    calendars = provider.get_calendars()
                    all_calendars.extend(calendars)
                    logger.info(f"'{type(provider).__name__}'에서 {len(calendars)}개 캘린더 로딩 완료")
                except Exception as e:
                    logger.error(f"'{type(provider).__name__}'에서 캘린더 목록을 가져오는 중 오류 발생", exc_info=True)
        
        self.calendar_list_cache = all_calendars
        logger.info(f"총 {len(all_calendars)}개 캘린더 로딩 완료")
        
        # UI 업데이트 신호 발송
        logger.info("calendar_list_changed 신호 발송 시작...")
        self.calendar_list_changed.emit()
        logger.info("calendar_list_changed 신호 발송 완료")

    def _on_calendar_thread_finished(self):
        if self.calendar_fetch_thread is None: return
            
        self.calendar_fetch_thread.quit()
        if self.calendar_fetch_thread.isRunning():
            self.calendar_fetch_thread.wait()
            
        self.calendar_fetcher.deleteLater()
        self.calendar_fetch_thread.deleteLater()
        self.calendar_fetch_thread = None
        self.calendar_fetcher = None
        logger.info("Calendar list thread cleanup completed")

    def _on_calendars_fetched(self, calendars):
        logger.info(f"Received {len(calendars)} calendars asynchronously")
        self.calendar_list_cache = calendars
        self._default_color_map_cache = None
        self.calendar_list_changed.emit()

    
    def update_event(self, event_data):
        """Local-first event update: UI 즉시 업데이트 → 백그라운드 동기화 (반복 일정 포함)"""
        # Check for recurrence change first
        recurrence_change_mode = event_data.get('recurrence_change_mode')
        if recurrence_change_mode:
            return self._handle_recurrence_change(event_data)
        
        # Check if calendar has changed (move operation needed)
        original_calendar_id = event_data.get('originalCalendarId')
        original_provider = event_data.get('originalProvider')
        new_calendar_id = event_data.get('calendarId')
        new_provider = event_data.get('provider')
        
        # If calendar changed, perform enhanced move operation for better UX
        if (original_calendar_id and original_provider and 
            (original_calendar_id != new_calendar_id or original_provider != new_provider)):
            
            return self._move_event_between_calendars_atomically(event_data)
        
        # Local-first update with recurring event support
        event_body = event_data.get('body', {})
        event_id = event_body.get('id')
        
        # Check if this is a recurring event
        is_recurring = self._is_recurring_event(event_id)
        
        if is_recurring:
            return self._update_recurring_event_local_first(event_data)
        else:
            return self._update_single_event_local_first(event_data)
        
    def _update_single_event_local_first(self, event_data):
        """단일 이벤트의 Local-first 업데이트"""
        event_body = event_data.get('body', {})
        event_id = event_body.get('id')
        
        # 1. 즉시 로컬 캐시에서 기존 이벤트 찾기 및 백업
        original_event, cache_key = self._find_and_backup_event(event_id)
        if not original_event:
            return False  # 이벤트를 찾을 수 없음
        
        # 2. 즉시 optimistic 업데이트 적용
        updated_event = self._create_optimistic_updated_event(original_event, event_data)
        self._replace_event_in_cache(event_id, updated_event, cache_key)
        
        # 3. 즉시 UI 업데이트
        year, month = cache_key
        self.data_updated.emit(year, month)
        
        # 4. 백그라운드에서 원격 동기화
        self._queue_remote_update_event(event_data, updated_event, original_event)
        
        return True
    
    def _update_recurring_event_local_first(self, event_data):
        """반복 일정의 Local-first 업데이트 - 모든 인스턴스 즉시 업데이트"""
        try:
            event_body = event_data.get('body', {})
            event_id = event_body.get('id')
            
            # 마스터 이벤트 ID 추출
            master_event_id = event_id
            if event_id and event_id.startswith('temp_recurring_'):
                # 임시 ID에서 마스터 ID 추출
                parts = event_id.split('_')
                if len(parts) >= 3:
                    master_event_id = '_'.join(parts[2:-1])  # 마지막 인덱스 제외
            
            # 모든 캐시에서 관련 반복 인스턴스 찾기 및 업데이트
            affected_months = set()
            instances_updated = 0
            original_instances = []  # 롤백용
            
            for cache_key, events in self.event_cache.items():
                # 업데이트할 이벤트들 찾기
                events_to_update = []
                for i, event in enumerate(events):
                    if (event.get('_master_event_id') == master_event_id or
                        event.get('id') == master_event_id or
                        (event.get('id', '').startswith('temp_recurring_') and 
                         master_event_id in event.get('id', ''))):
                        events_to_update.append((i, event))
                
                # 이벤트 업데이트
                if events_to_update:
                    for i, original_event in events_to_update:
                        # 백업본 저장 (롤백용)
                        original_instances.append((cache_key, i, original_event.copy()))
                        
                        # Optimistic 업데이트 적용
                        updated_event = self._create_optimistic_updated_event(original_event, event_data)
                        # 반복 이벤트 특성 유지
                        updated_event['_is_recurring_instance'] = original_event.get('_is_recurring_instance', True)
                        updated_event['_instance_index'] = original_event.get('_instance_index', 0)
                        updated_event['_master_event_id'] = original_event.get('_master_event_id', master_event_id)
                        
                        events[i] = updated_event
                        instances_updated += 1
                    
                    affected_months.add(cache_key)
            
            # 영향받는 모든 월에 대해 UI 업데이트
            for year, month in affected_months:
                self.data_updated.emit(year, month)
            
            # 백그라운드에서 실제 Google Calendar 업데이트
            self._queue_remote_recurring_update(event_data, original_instances)
            
            print(f"[RECURRING UPDATE] Updated {instances_updated} recurring instances in cache")
            return instances_updated > 0
            
        except Exception as e:
            print(f"[RECURRING UPDATE ERROR] Failed to update recurring event: {e}")
            return False
    
    def _find_and_backup_event(self, event_id):
        """이벤트 ID로 캐시에서 이벤트 찾기 및 백업"""
        for cache_key, events in self.event_cache.items():
            for event in events:
                if event.get('id') == event_id:
                    # 백업본 생성 (롤백용)
                    backup_event = event.copy()
                    return backup_event, cache_key
        return None, None
    
    def _create_optimistic_updated_event(self, original_event, event_data):
        """기존 이벤트를 업데이트된 내용으로 즉시 수정"""
        updated_event = original_event.copy()
        
        # 새로운 데이터로 업데이트
        event_body = event_data.get('body', {})
        updated_event.update(event_body)
        
        # 메타 정보 추가
        updated_event['calendarId'] = event_data.get('calendarId')
        updated_event['provider'] = event_data.get('provider')
        updated_event['_sync_state'] = 'pending'
        
        # 색상 정보 재설정
        cal_id = updated_event.get('calendarId')
        if cal_id:
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
            default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
            updated_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
        
        return updated_event
    
    def _replace_event_in_cache(self, event_id, updated_event, cache_key):
        """캐시에서 이벤트 교체"""
        if cache_key in self.event_cache:
            events = self.event_cache[cache_key]
            for i, event in enumerate(events):
                if event.get('id') == event_id:
                    events[i] = updated_event
                    break
    
    def _queue_remote_update_event(self, event_data, updated_event, original_event):
        """백그라운드에서 원격 업데이트 동기화"""
        class RemoteUpdateTask(QRunnable):
            def __init__(self, data_manager, event_data, updated_event, original_event):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.updated_event = updated_event
                self.original_event = original_event
                
            def run(self):
                provider_name = self.event_data.get('provider')
                event_id = self.updated_event['id']
                
                for provider in self.data_manager.providers:
                    if provider.name == provider_name:
                        try:
                            # 실제 원격 API 호출
                            real_updated_event = provider.update_event(self.event_data, self.data_manager)
                            if real_updated_event:
                                # 성공: 동기화 상태 업데이트
                                self.data_manager._mark_event_sync_success(event_id, real_updated_event, provider_name)
                            else:
                                # 실패: 원본 이벤트로 롤백
                                self.data_manager._rollback_failed_update(event_id, self.original_event, "원격 업데이트 실패")
                        except Exception as e:
                            logger.error(f"원격 이벤트 업데이트 실패: {e}")
                            self.data_manager._rollback_failed_update(event_id, self.original_event, str(e))
                        break
        
        # 백그라운드 스레드에서 실행
        task = RemoteUpdateTask(self, event_data, updated_event, original_event)
        QThreadPool.globalInstance().start(task)
    
    def _handle_recurrence_change(self, event_data):
        """반복 규칙 변경 처리"""
        recurrence_change_mode = event_data.get('recurrence_change_mode')
        recurrence_change_option = event_data.get('recurrence_change_option', 'all')
        event_body = event_data.get('body', {})
        event_id = event_body.get('id')
        
        logger.info(f"반복 규칙 변경 처리: mode={recurrence_change_mode}, option={recurrence_change_option}, id={event_id}")
        
        if recurrence_change_mode == "single_to_recurring":
            return self._convert_single_to_recurring(event_data)
        elif recurrence_change_mode == "recurring_to_single":
            return self._convert_recurring_to_single(event_data, recurrence_change_option)
        elif recurrence_change_mode == "modify_recurrence":
            return self._modify_recurrence_rule(event_data, recurrence_change_option)
        else:
            logger.error(f"알 수 없는 반복 규칙 변경 모드: {recurrence_change_mode}")
            return False
    
    def _convert_single_to_recurring(self, event_data):
        """단일 일정을 반복 일정으로 변환"""
        try:
            event_body = event_data.get('body', {})
            event_id = event_body.get('id')
            
            # 1. 기존 단일 일정 찾기 및 삭제
            original_event, cache_key = self._find_and_backup_event(event_id)
            if not original_event:
                logger.error(f"변환할 단일 일정을 찾을 수 없음: {event_id}")
                return False
            
            # 기존 일정을 캐시에서 제거
            if cache_key and cache_key in self.event_cache:
                self.event_cache[cache_key] = [e for e in self.event_cache[cache_key] if e.get('id') != event_id]
            
            # 2. 새로운 반복 일정으로 업데이트
            updated_event = self._create_optimistic_updated_event(original_event, event_data)
            
            # 3. 반복 일정 인스턴스들 생성 및 캐시에 추가
            self._generate_recurring_instances_for_cache(updated_event)
            
            # 4. UI 업데이트
            if cache_key:
                year, month = cache_key
                self.data_updated.emit(year, month)
            
            # 5. 백그라운드 동기화
            self._queue_remote_recurrence_conversion(event_data, original_event, "single_to_recurring")
            
            logger.info(f"단일 → 반복 일정 변환 완료: {event_id}")
            return True
            
        except Exception as e:
            logger.error(f"단일 → 반복 일정 변환 실패: {e}")
            return False
    
    def _convert_recurring_to_single(self, event_data, option):
        """반복 일정을 단일 일정으로 변환"""
        try:
            event_body = event_data.get('body', {})
            event_id = event_body.get('id')
            
            if option == "instance":
                # 이 인스턴스만 단일 일정으로 변환
                return self._convert_single_instance_to_single(event_data)
            elif option == "future":
                # 이후 모든 인스턴스를 단일 일정으로 변환 (반복 종료)
                return self._convert_future_instances_to_single(event_data)
            elif option == "all":
                # 모든 반복을 삭제하고 하나의 단일 일정으로 변환
                return self._convert_all_recurring_to_single(event_data)
            else:
                logger.error(f"알 수 없는 변환 옵션: {option}")
                return False
                
        except Exception as e:
            logger.error(f"반복 → 단일 일정 변환 실패: {e}")
            return False
    
    def _modify_recurrence_rule(self, event_data, option):
        """반복 규칙 수정"""
        try:
            event_body = event_data.get('body', {})
            event_id = event_body.get('id')
            original_rrule = event_data.get('original_rrule')
            new_rrule = event_body.get('recurrence', [None])[0] if event_body.get('recurrence') else None
            
            if option == "future":
                # 이후 모든 일정의 반복 규칙 변경
                return self._modify_future_recurrence(event_data, original_rrule, new_rrule)
            elif option == "all":
                # 모든 반복 일정의 규칙 변경
                return self._modify_all_recurrence(event_data, original_rrule, new_rrule)
            else:
                logger.error(f"알 수 없는 수정 옵션: {option}")
                return False
                
        except Exception as e:
            logger.error(f"반복 규칙 수정 실패: {e}")
            return False
    
    def _convert_single_instance_to_single(self, event_data):
        """단일 인스턴스만 일반 일정으로 변환 (반복에서 제외)"""
        # 이는 예외 처리와 동일한 로직 (반복에서 해당 날짜 제외)
        event_body = event_data.get('body', {})
        event_id = event_body.get('id')
        
        # 예외 날짜로 추가
        original_id = event_id.split('_')[0] if '_' in event_id else event_id
        start_str = event_body.get('start', {}).get('dateTime') or event_body.get('start', {}).get('date')
        
        if start_str:
            try:
                import datetime
                if 'T' in start_str:
                    exception_date = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00')).isoformat()
                else:
                    exception_date = start_str
                    
                # 로컬 제공자에 예외 추가
                for provider in self.providers:
                    if provider.name == LOCAL_CALENDAR_PROVIDER_NAME:
                        with provider._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT OR IGNORE INTO event_exceptions (original_event_id, exception_date) VALUES (?, ?)",
                                (original_id, exception_date)
                            )
                            conn.commit()
                        break
                
                # 새로운 단일 일정 생성
                event_body['id'] = str(uuid.uuid4())  # 새로운 ID
                event_body.pop('recurrence', None)  # 반복 제거
                
                # 캐시에 단일 일정으로 추가
                updated_event = self._create_optimistic_updated_event({}, event_data)
                self._add_event_to_cache(updated_event)
                
                return True
                
            except Exception as e:
                logger.error(f"인스턴스 변환 실패: {e}")
                return False
        
        return False
    
    def _generate_recurring_instances_for_cache(self, master_event):
        """마스터 이벤트로부터 반복 인스턴스들을 생성하여 캐시에 추가"""
        # 이는 기존 캐싱 로직을 활용하여 반복 인스턴스들 생성
        try:
            import datetime
            from dateutil.rrule import rrulestr
            
            recurrence = master_event.get('recurrence', [])
            if not recurrence:
                return
            
            rrule_str = recurrence[0]
            start_str = master_event.get('start', {}).get('dateTime') or master_event.get('start', {}).get('date')
            
            if not start_str:
                return
            
            # 현재 보이는 달들의 범위에서 인스턴스 생성
            current_date = datetime.date.today()
            for month_offset in range(-3, 4):  # 현재 기준 ±3개월
                target_date = current_date.replace(day=1)
                if month_offset != 0:
                    year = target_date.year
                    month = target_date.month + month_offset
                    while month <= 0:
                        month += 12
                        year -= 1
                    while month > 12:
                        month -= 12
                        year += 1
                    target_date = target_date.replace(year=year, month=month)
                
                # 해당 월의 인스턴스들 생성
                month_start = target_date
                if target_date.month == 12:
                    month_end = target_date.replace(year=target_date.year+1, month=1, day=1) - datetime.timedelta(days=1)
                else:
                    month_end = target_date.replace(month=target_date.month+1, day=1) - datetime.timedelta(days=1)
                
                # RRULE 파싱하여 인스턴스 생성 (local_provider 로직 활용)
                for provider in self.providers:
                    if provider.name == LOCAL_CALENDAR_PROVIDER_NAME:
                        instances = provider.get_events(month_start, month_end, self)
                        recurring_instances = [e for e in instances if e.get('id', '').startswith(master_event['id'])]
                        
                        cache_key = (target_date.year, target_date.month)
                        if cache_key not in self.event_cache:
                            self.event_cache[cache_key] = []
                        
                        # 기존 인스턴스 제거 후 새로운 인스턴스 추가
                        self.event_cache[cache_key] = [e for e in self.event_cache[cache_key] 
                                                     if not e.get('id', '').startswith(master_event['id'])]
                        self.event_cache[cache_key].extend(recurring_instances)
                        break
                        
        except Exception as e:
            logger.error(f"반복 인스턴스 생성 실패: {e}")
    
    def _queue_remote_recurrence_conversion(self, event_data, original_event, conversion_type):
        """백그라운드에서 반복 규칙 변환 동기화"""
        class RecurrenceConversionTask(QRunnable):
            def __init__(self, data_manager, event_data, original_event, conversion_type):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.original_event = original_event
                self.conversion_type = conversion_type
                
            def run(self):
                provider_name = self.event_data.get('provider')
                
                for provider in self.data_manager.providers:
                    if provider.name == provider_name:
                        try:
                            if self.conversion_type == "single_to_recurring":
                                # 기존 단일 일정 삭제 후 새로운 반복 일정 추가
                                provider.delete_event({'body': self.original_event}, self.data_manager)
                                result = provider.add_event(self.event_data, self.data_manager)
                            else:
                                # 기타 변환 타입들
                                result = provider.update_event(self.event_data, self.data_manager)
                            
                            if result:
                                logger.info(f"반복 규칙 변환 원격 동기화 성공: {self.conversion_type}")
                            else:
                                logger.error(f"반복 규칙 변환 원격 동기화 실패: {self.conversion_type}")
                                
                        except Exception as e:
                            logger.error(f"반복 규칙 변환 원격 동기화 오류: {e}")
                        break
        
        task = RecurrenceConversionTask(self, event_data, original_event, conversion_type)
        QThreadPool.globalInstance().start(task)
    
    def _queue_remote_recurring_update(self, event_data, original_instances):
        """백그라운드에서 반복 일정 원격 업데이트"""
        class RemoteRecurringUpdateTask(QRunnable):
            def __init__(self, data_manager, event_data, original_instances):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.original_instances = original_instances
            
            def run(self):
                try:
                    # 실제 Google Calendar 업데이트 처리
                    provider_name = self.event_data.get('provider')
                    for provider in self.data_manager.providers:
                        if provider.name == provider_name:
                            # 마스터 이벤트 업데이트 (Google이 반복 확장 처리)
                            real_updated_event = provider.update_event(self.event_data, self.data_manager)
                            if real_updated_event:
                                # 성공: 모든 인스턴스의 동기화 상태 업데이트
                                self.data_manager._mark_recurring_sync_success(self.event_data, real_updated_event)
                            else:
                                # 실패: 모든 인스턴스를 원본으로 롤백
                                self.data_manager._rollback_failed_recurring_update(self.original_instances, "원격 업데이트 실패")
                            break
                except Exception as e:
                    print(f"[REMOTE RECURRING UPDATE ERROR] {e}")
                    self.data_manager._rollback_failed_recurring_update(self.original_instances, str(e))
        
        task = RemoteRecurringUpdateTask(self, event_data, original_instances)
        QThreadPool.globalInstance().start(task)
    
    def _mark_recurring_sync_success(self, event_data, real_event):
        """반복 일정 동기화 성공 처리"""
        event_body = event_data.get('body', {})
        master_event_id = event_body.get('id')
        
        # 마스터 이벤트 ID 추출
        if master_event_id and master_event_id.startswith('temp_recurring_'):
            parts = master_event_id.split('_')
            if len(parts) >= 3:
                master_event_id = '_'.join(parts[2:-1])
        
        # 모든 관련 인스턴스의 동기화 상태 업데이트
        affected_months = set()
        for cache_key, events in self.event_cache.items():
            for event in events:
                if (event.get('_master_event_id') == master_event_id or
                    event.get('id') == master_event_id or
                    (event.get('id', '').startswith('temp_recurring_') and 
                     master_event_id in event.get('id', ''))):
                    event['_sync_state'] = 'synced'
                    affected_months.add(cache_key)
        
        # 영향받는 모든 월에 대해 UI 업데이트
        for year, month in affected_months:
            self.data_updated.emit(year, month)
        
        print(f"[RECURRING SYNC SUCCESS] Updated sync status for recurring event {master_event_id}")
    
    def _rollback_failed_recurring_update(self, original_instances, error_msg):
        """반복 일정 업데이트 실패 시 롤백"""
        affected_months = set()
        
        for cache_key, index, original_event in original_instances:
            if cache_key in self.event_cache:
                # 실패 상태 표시
                original_event['_sync_state'] = 'failed'
                original_event['_sync_error'] = error_msg
                
                # 원본 이벤트로 복원
                self.event_cache[cache_key][index] = original_event
                affected_months.add(cache_key)
        
        # 영향받는 모든 월에 대해 UI 업데이트 (롤백 상태 표시)
        for year, month in affected_months:
            self.data_updated.emit(year, month)
        
        print(f"[RECURRING UPDATE ROLLBACK] Rolled back {len(original_instances)} instances due to: {error_msg}")
    
    def _mark_event_sync_success(self, event_id, real_event, provider_name):
        """이벤트 동기화 성공 처리"""
        if 'provider' not in real_event:
            real_event['provider'] = provider_name
        
        # 색상 정보 추가
        cal_id = real_event.get('calendarId')
        if cal_id:
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            cal_info = next((c for c in all_calendars if c['id'] == cal_id), None)
            default_color = cal_info.get('backgroundColor') if cal_info else DEFAULT_EVENT_COLOR
            real_event['color'] = self.settings.get("calendar_colors", {}).get(cal_id, default_color)
        
        real_event['_sync_state'] = 'synced'
        
        # 캐시에서 이벤트 교체
        for cache_key, events in self.event_cache.items():
            for i, event in enumerate(events):
                if event.get('id') == event_id:
                    events[i] = real_event
                    # UI 업데이트
                    year, month = cache_key
                    self.data_updated.emit(year, month)
                    return
    
    def _rollback_failed_update(self, event_id, original_event, error_msg):
        """업데이트 실패 시 롤백"""
        original_event['_sync_state'] = 'failed'
        original_event['_sync_error'] = error_msg
        
        # 캐시에서 원본 이벤트로 복원
        for cache_key, events in self.event_cache.items():
            for i, event in enumerate(events):
                if event.get('id') == event_id:
                    events[i] = original_event
                    # UI 업데이트하여 롤백 상태 표시
                    year, month = cache_key
                    self.data_updated.emit(year, month)
                    return
    

    def load_initial_month(self):
        logger.info("Requesting initial data loading...")
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
    
    # Enhanced Calendar Move Methods
    def _move_event_between_calendars_atomically(self, event_data):
        """
        Enhanced Local-First 캘린더 간 이벤트 이동
        UI 즉시 반영 (원자적) → 백그라운드 처리 → 실패시 롤백
        """
        original_calendar_id = event_data.get('originalCalendarId')
        original_provider = event_data.get('originalProvider')
        new_calendar_id = event_data.get('calendarId')
        new_provider = event_data.get('provider')
        event_id = event_data.get('body', {}).get('id')
        
        print(f"DEBUG: Atomically moving event {event_id} from {original_provider}:{original_calendar_id} to {new_provider}:{new_calendar_id}")
        
        # 1. 즉시 캐시에서 이벤트를 원자적으로 이동 (중간 상태 없음)
        success = self._move_event_in_cache_atomically(
            event_id, 
            original_calendar_id, 
            original_provider,
            new_calendar_id, 
            new_provider,
            event_data.get('body', {})
        )
        
        if not success:
            print(f"DEBUG: Failed to find event {event_id} in cache for atomic move")
            return False
        
        # 2. 즉시 UI 업데이트
        self._emit_data_updated_for_affected_months(event_data)
        
        # 3. 백그라운드에서 실제 캘린더 간 이동 처리
        self._queue_remote_calendar_move(event_data, original_calendar_id, original_provider)
        
        return True

    def _move_event_in_cache_atomically(self, event_id, from_cal_id, from_provider, to_cal_id, to_provider, event_body):
        """
        캐시에서 이벤트를 원자적으로 이동 (사용자가 중간 과정을 보지 않음)
        """
        # 원본 이벤트 찾기
        original_event = None
        source_cache_key = None
        
        for cache_key, events in self.event_cache.items():
            for event in events:
                if (event.get('id') == event_id and 
                    event.get('calendarId') == from_cal_id and
                    event.get('provider') == from_provider):
                    original_event = event.copy()
                    source_cache_key = cache_key
                    break
            if original_event:
                break
        
        if not original_event:
            print(f"DEBUG: Could not find event {event_id} in cache for atomic move")
            return False
        
        # 새로운 이벤트 데이터 생성
        moved_event = original_event.copy()
        moved_event.update(event_body)
        moved_event['calendarId'] = to_cal_id
        moved_event['provider'] = to_provider
        moved_event['_move_state'] = 'moving'  # 이동 중 상태 표시
        moved_event['_original_location'] = {
            'calendarId': from_cal_id,
            'provider': from_provider
        }
        
        # [NEW] 즉시 타겟 캘린더 색상으로 변경 (시각적 즉시 변화)
        target_color = self._get_calendar_color(to_cal_id)
        if target_color:
            moved_event['color'] = target_color
            print(f"DEBUG: Event color changed immediately to {target_color} for calendar {to_cal_id}")
        
        # 원자적 이동: 기존 제거 + 새 위치 추가 (한 번에 처리)
        try:
            # 1. 원본 제거
            if source_cache_key in self.event_cache:
                self.event_cache[source_cache_key] = [
                    e for e in self.event_cache[source_cache_key] 
                    if not (e.get('id') == event_id and 
                           e.get('calendarId') == from_cal_id and
                           e.get('provider') == from_provider)
                ]
            
            # 2. 새 위치에 추가
            target_cache_key = self._determine_cache_key_for_event(moved_event)
            if target_cache_key not in self.event_cache:
                self.event_cache[target_cache_key] = []
            self.event_cache[target_cache_key].append(moved_event)
            
            print(f"DEBUG: Event {event_id} moved atomically in cache from {from_cal_id} to {to_cal_id}")
            return True
            
        except Exception as e:
            print(f"DEBUG: Failed to move event atomically: {e}")
            return False
    
    def _determine_cache_key_for_event(self, event):
        """이벤트에 적합한 캐시 키 결정"""
        start_info = event.get('start', {})
        start_date_str = start_info.get('dateTime') or start_info.get('date', '')
        
        if start_date_str:
            try:
                if 'T' in start_date_str:
                    date_part = start_date_str.split('T')[0]
                else:
                    date_part = start_date_str[:10]
                    
                event_date = datetime.datetime.fromisoformat(date_part).date()
                return (event_date.year, event_date.month)
            except:
                pass
        
        # 기본값: 현재 월
        today = datetime.date.today()
        return (today.year, today.month)
    
    def _get_calendar_color(self, calendar_id):
        """캘린더 ID에 해당하는 색상 반환"""
        try:
            # 1. 사용자 설정 색상 확인
            custom_colors = self.settings.get("calendar_colors", {})
            if calendar_id in custom_colors:
                return custom_colors[calendar_id]
            
            # 2. 캘린더 기본 색상 확인
            all_calendars = self.get_all_calendars(fetch_if_empty=False)
            cal_info = next((c for c in all_calendars if c['id'] == calendar_id), None)
            if cal_info and cal_info.get('backgroundColor'):
                return cal_info['backgroundColor']
            
            # 3. 기본 색상 반환
            return DEFAULT_EVENT_COLOR
            
        except Exception as e:
            print(f"DEBUG: Error getting calendar color for {calendar_id}: {e}")
            return DEFAULT_EVENT_COLOR
    
    def _emit_data_updated_for_affected_months(self, event_data):
        """영향받는 모든 월에 대해 UI 업데이트 신호 발송"""
        # 원본 위치 업데이트
        try:
            original_event = {'start': event_data.get('body', {}).get('start', {})}
            original_cache_key = self._determine_cache_key_for_event(original_event)
            year, month = original_cache_key
            self.data_updated.emit(year, month)
        except:
            pass
        
        # 새 위치 업데이트  
        try:
            new_cache_key = self._determine_cache_key_for_event(event_data.get('body', {}))
            year, month = new_cache_key
            self.data_updated.emit(year, month)
        except:
            pass
    
    def _queue_remote_calendar_move(self, event_data, original_calendar_id, original_provider):
        """
        백그라운드에서 실제 캘린더 간 이동 처리
        """
        class RemoteMoveTask(QRunnable):
            def __init__(self, data_manager, event_data, original_calendar_id, original_provider):
                super().__init__()
                self.data_manager = data_manager
                self.event_data = event_data
                self.original_calendar_id = original_calendar_id
                self.original_provider = original_provider
                
            def run(self):
                event_id = self.event_data.get('body', {}).get('id')
                
                try:
                    print(f"DEBUG: Starting remote calendar move for event {event_id}")
                    
                    # [FIX] 1. 먼저 원본 캘린더에서 삭제 (중복 방지)
                    original_event_data = {
                        'calendarId': self.original_calendar_id,
                        'provider': self.original_provider,
                        'body': self.event_data.get('body', {})
                    }
                    
                    delete_success = self.data_manager._delete_event_remote_only(original_event_data)
                    
                    if not delete_success:
                        print(f"WARNING: Failed to delete original event {event_id}")
                        # 삭제 실패 시에도 계속 진행 (이미 캐시에서는 이동됨)
                    
                    # 2. 새 캘린더에 추가
                    new_event_data = self.event_data.copy()
                    new_event_data.pop('originalCalendarId', None)
                    new_event_data.pop('originalProvider', None)
                    
                    # 백그라운드에서 실제 추가 (캐시 업데이트 없이)
                    add_success = self.data_manager._add_event_remote_only(new_event_data)
                    
                    if not add_success:
                        print(f"ERROR: Failed to add event to new calendar after deletion")
                        # 이 경우는 롤백이 필요함
                        raise Exception("Failed to add event to new calendar")
                    
                    # 3. 성공: 이동 상태 클리어
                    self.data_manager._clear_move_state(event_id)
                    print(f"DEBUG: Successfully moved event {event_id} between calendars")
                    
                except Exception as e:
                    print(f"DEBUG: Remote calendar move failed for event {event_id}: {e}")
                    # 4. 실패: 롤백
                    self.data_manager._rollback_calendar_move(
                        event_id, 
                        self.original_calendar_id, 
                        self.original_provider,
                        self.event_data.get('calendarId'),
                        self.event_data.get('provider')
                    )
                    # 에러 메시지 표시
                    self.data_manager.error_occurred.emit(f"캘린더 이동 실패: {str(e)}")
        
        # 백그라운드에서 실행
        task = RemoteMoveTask(self, event_data, original_calendar_id, original_provider)
        QThreadPool.globalInstance().start(task)
    
    def _add_event_remote_only(self, event_data):
        """원격에만 이벤트 추가 (캐시 업데이트 없이)"""
        try:
            provider_name = event_data.get('provider')
            for provider in self.providers:
                if provider.name == provider_name:
                    # [FIX] data_manager를 None으로 전달하여 캐시 업데이트 방지
                    result = provider.add_event(event_data, None)
                    return result is not None
            return False
        except Exception as e:
            print(f"DEBUG: _add_event_remote_only failed: {e}")
            return False
    
    def _delete_event_remote_only(self, event_data):
        """원격에만 이벤트 삭제 (캐시 업데이트 없이)"""
        try:
            provider_name = event_data.get('provider')
            for provider in self.providers:
                if provider.name == provider_name:
                    # [FIX] data_manager를 None으로 전달하여 캐시 업데이트 방지
                    result = provider.delete_event(event_data, None)
                    return result
            return False
        except Exception as e:
            print(f"DEBUG: _delete_event_remote_only failed: {e}")
            return False
    
    def _clear_move_state(self, event_id):
        """이벤트의 이동 상태 클리어"""
        for cache_key, events in self.event_cache.items():
            for event in events:
                if event.get('id') == event_id:
                    event.pop('_move_state', None)
                    event.pop('_original_location', None)
                    # UI 업데이트
                    year, month = cache_key
                    self.data_updated.emit(year, month)
                    break
    
    def _rollback_calendar_move(self, event_id, original_cal_id, original_provider, failed_cal_id, failed_provider):
        """캘린더 이동 실패 시 롤백"""
        print(f"DEBUG: Rolling back calendar move for event {event_id}")
        
        # 실패한 위치에서 이벤트 찾기
        for cache_key, events in self.event_cache.items():
            for i, event in enumerate(events):
                if (event.get('id') == event_id and 
                    event.get('calendarId') == failed_cal_id):
                    
                    # 원본 위치 정보 복원
                    original_location = event.get('_original_location', {})
                    rolled_back_event = event.copy()
                    rolled_back_event['calendarId'] = original_location.get('calendarId', original_cal_id)
                    rolled_back_event['provider'] = original_location.get('provider', original_provider)
                    rolled_back_event['_move_state'] = 'failed'
                    rolled_back_event.pop('_original_location', None)
                    
                    # 실패한 위치에서 제거
                    events.pop(i)
                    
                    # 원본 위치로 복원
                    original_cache_key = self._determine_cache_key_for_event(rolled_back_event)
                    if original_cache_key not in self.event_cache:
                        self.event_cache[original_cache_key] = []
                    self.event_cache[original_cache_key].append(rolled_back_event)
                    
                    # UI 업데이트
                    self.data_updated.emit(original_cache_key[0], original_cache_key[1])
                    if cache_key != original_cache_key:
                        self.data_updated.emit(cache_key[0], cache_key[1])
                    
                    print(f"DEBUG: Event {event_id} rolled back to original calendar {original_cal_id}")
                    return
        
        print(f"DEBUG: Could not find event {event_id} for rollback")