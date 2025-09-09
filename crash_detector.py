# Crash Detection System
# 2025-09-08 - 실시간 crash 감지 및 분석

import sys
import signal
import traceback
import threading
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class CrashDetector:
    def __init__(self):
        self.start_time = time.time()
        self.last_heartbeat = time.time()
        self.heartbeat_thread = None
        self.is_running = True
        
    def install_handlers(self):
        """크래시 감지 핸들러 설치"""
        
        # Python 예외 처리
        sys.excepthook = self.handle_exception
        
        # 시스템 시그널 처리 (Unix/Linux style, Windows에서는 제한적)
        try:
            signal.signal(signal.SIGINT, self.handle_signal)
            signal.signal(signal.SIGTERM, self.handle_signal) 
            if hasattr(signal, 'SIGSEGV'):
                signal.signal(signal.SIGSEGV, self.handle_signal)
        except (AttributeError, OSError):
            pass  # Windows에서는 일부 시그널이 지원되지 않음
            
        # Heartbeat 모니터링 시작
        self.start_heartbeat_monitor()
        
        logger.info("[CRASH DETECTOR] Crash detection system installed")
    
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """처리되지 않은 예외 감지"""
        runtime = time.time() - self.start_time
        
        crash_info = f"""
================== CRASH DETECTED ==================
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Runtime: {runtime:.2f} seconds
Exception Type: {exc_type.__name__}
Exception Value: {exc_value}

Traceback:
{''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}
================== END CRASH INFO ==================
"""
        
        print(crash_info)
        logger.critical(crash_info)
        
        # 크래시 정보를 파일로 저장
        with open(f"crash_report_{int(time.time())}.log", "w", encoding="utf-8") as f:
            f.write(crash_info)
        
        # 기본 예외 처리기 호출
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def handle_signal(self, signum, frame):
        """시스템 시그널 감지"""
        runtime = time.time() - self.start_time
        
        signal_info = f"""
================== SIGNAL DETECTED ==================
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Runtime: {runtime:.2f} seconds
Signal: {signum}
Frame: {frame}

Stack trace:
{''.join(traceback.format_stack(frame))}
================== END SIGNAL INFO ==================
"""
        
        print(signal_info)
        logger.critical(signal_info)
        
        # 시그널 정보를 파일로 저장
        with open(f"signal_report_{int(time.time())}.log", "w", encoding="utf-8") as f:
            f.write(signal_info)
    
    def heartbeat(self):
        """애플리케이션이 살아있음을 알리는 heartbeat"""
        self.last_heartbeat = time.time()
        
    def start_heartbeat_monitor(self):
        """Heartbeat 모니터링 스레드 시작"""
        def monitor():
            logger.info("[CRASH DETECTOR] Heartbeat monitor started")
            while self.is_running:
                time.sleep(10)  # 10초마다 체크
                current_time = time.time()
                time_since_heartbeat = current_time - self.last_heartbeat
                runtime = current_time - self.start_time
                
                if time_since_heartbeat > 30:  # 30초 이상 heartbeat 없음
                    warning_msg = f"[CRASH DETECTOR] WARNING: No heartbeat for {time_since_heartbeat:.1f}s (Runtime: {runtime:.1f}s)"
                    print(warning_msg)
                    logger.warning(warning_msg)
                else:
                    status_msg = f"[CRASH DETECTOR] OK: Runtime {runtime:.1f}s, Last heartbeat {time_since_heartbeat:.1f}s ago"
                    print(status_msg)
                    logger.info(status_msg)
        
        self.heartbeat_thread = threading.Thread(target=monitor, daemon=True)
        self.heartbeat_thread.start()
    
    def shutdown(self):
        """크래시 감지기 종료"""
        self.is_running = False
        runtime = time.time() - self.start_time
        shutdown_msg = f"[CRASH DETECTOR] Shutdown after {runtime:.2f} seconds"
        print(shutdown_msg)
        logger.info(shutdown_msg)

# 전역 crash detector 인스턴스
crash_detector = CrashDetector()