# Aggressive Silent Crash Debug Fix
# 2025-09-08 - Disable threading and mutex systems entirely

import sys
import os
import shutil

def disable_threading_systems():
    """모든 스레딩 및 뮤텍스 시스템 일시 비활성화"""
    
    print("[AGGRESSIVE DEBUG] Starting aggressive crash debugging...")
    
    # 1. data_manager.py에서 모든 스레딩 비활성화
    data_manager_file = "data_manager.py"
    backup_file = f"{data_manager_file}.backup_aggressive"
    
    if os.path.exists(data_manager_file):
        if not os.path.exists(backup_file):
            shutil.copy2(data_manager_file, backup_file)
            print(f"[DEBUG] Data manager backed up to {backup_file}")
        
        # data_manager.py 읽기
        with open(data_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 위험한 패턴들을 안전한 버전으로 교체
        safe_content = content.replace(
            'self._mutex = QMutex()',
            '# self._mutex = QMutex()  # DISABLED FOR DEBUG'
        ).replace(
            'self._activity_lock = QMutex()',
            '# self._activity_lock = QMutex()  # DISABLED FOR DEBUG'
        ).replace(
            'with QMutexLocker(self._mutex):',
            '# with QMutexLocker(self._mutex):  # DISABLED FOR DEBUG\nif True:'
        ).replace(
            'with QMutexLocker(self._activity_lock):',
            '# with QMutexLocker(self._activity_lock):  # DISABLED FOR DEBUG\nif True:'
        ).replace(
            'self._ensure_mutex_valid()',
            '# self._ensure_mutex_valid()  # DISABLED FOR DEBUG'
        ).replace(
            'self.caching_manager.moveToThread(self.caching_thread)',
            '# self.caching_manager.moveToThread(self.caching_thread)  # DISABLED FOR DEBUG'
        ).replace(
            'self.caching_thread.start()',
            '# self.caching_thread.start()  # DISABLED FOR DEBUG'
        ).replace(
            'self.calendar_fetcher.moveToThread(self.calendar_fetch_thread)',
            '# self.calendar_fetcher.moveToThread(self.calendar_fetch_thread)  # DISABLED FOR DEBUG'
        ).replace(
            'self.calendar_fetch_thread.start()',
            '# self.calendar_fetch_thread.start()  # DISABLED FOR DEBUG'
        )
        
        # 수정된 내용 저장
        with open(data_manager_file, 'w', encoding='utf-8') as f:
            f.write(safe_content)
        
        print("[AGGRESSIVE DEBUG] All threading and mutex systems disabled")
        return True
    
    return False

def restore_threading_systems():
    """스레딩 시스템 복구"""
    backup_file = "data_manager.py.backup_aggressive"
    data_manager_file = "data_manager.py"
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, data_manager_file)
        print("[DEBUG] Threading systems restored from backup")
        return True
    
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_threading_systems()
    else:
        disable_threading_systems()