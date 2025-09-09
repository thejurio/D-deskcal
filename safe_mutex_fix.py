# Safe Mutex Pattern Fix for Silent Crash
# 2025-09-08 - Fix QMutex corruption and memory access violations

import sys
import os
import shutil

def apply_safe_mutex_fix():
    """data_manager.py의 위험한 mutex 패턴을 안전한 버전으로 교체"""
    
    print("[SAFE MUTEX FIX] Starting mutex corruption fix...")
    
    data_manager_file = "data_manager.py"
    backup_file = f"{data_manager_file}.backup_mutex_fix"
    
    if os.path.exists(data_manager_file):
        # 백업 생성
        if not os.path.exists(backup_file):
            shutil.copy2(data_manager_file, backup_file)
            print(f"[SAFE MUTEX FIX] Data manager backed up to {backup_file}")
        
        # 파일 읽기
        with open(data_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 위험한 _ensure_mutex_valid 호출들을 안전한 버전으로 교체
        safe_content = content.replace(
            'self._ensure_mutex_valid()',
            '# self._ensure_mutex_valid()  # DISABLED - dangerous runtime mutex recreation'
        ).replace(
            'def _ensure_mutex_valid(self):',
            'def _ensure_mutex_valid_DISABLED(self):'
        ).replace(
            '"""mutex가 유효한지 확인하고 필요시 재초기화"""',
            '"""DISABLED - mutex runtime recreation was causing memory corruption"""'
        ).replace(
            'if not hasattr(self, \'_mutex\') or not isinstance(self._mutex, QMutex):',
            '# DISABLED - was causing memory corruption and crashes'
        ).replace(
            'self._mutex = QMutex()',
            '# self._mutex = QMutex()  # DISABLED - dangerous runtime recreation'
        )
        
        # 추가 안전 조치: moveToThread 패턴도 임시 비활성화
        safe_content = safe_content.replace(
            'self.caching_manager.moveToThread(self.caching_thread)',
            '# self.caching_manager.moveToThread(self.caching_thread)  # DISABLED FOR CRASH FIX'
        ).replace(
            'self.caching_thread.start()',
            '# self.caching_thread.start()  # DISABLED FOR CRASH FIX'
        ).replace(
            'self.calendar_fetcher.moveToThread(self.calendar_fetch_thread)',
            '# self.calendar_fetcher.moveToThread(self.calendar_fetch_thread)  # DISABLED FOR CRASH FIX'
        ).replace(
            'self.calendar_fetch_thread.start()',
            '# self.calendar_fetch_thread.start()  # DISABLED FOR CRASH FIX'
        )
        
        # 수정된 내용 저장
        with open(data_manager_file, 'w', encoding='utf-8') as f:
            f.write(safe_content)
        
        print("[SAFE MUTEX FIX] Dangerous mutex patterns disabled")
        print("[SAFE MUTEX FIX] moveToThread patterns disabled for crash prevention")
        return True
    
    return False

def restore_original():
    """원본 복구"""
    backup_file = "data_manager.py.backup_mutex_fix"
    data_manager_file = "data_manager.py"
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, data_manager_file)
        print("[SAFE MUTEX FIX] Original data_manager.py restored")
        return True
    
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_original()
    else:
        apply_safe_mutex_fix()