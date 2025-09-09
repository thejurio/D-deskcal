# Complete Mutex Fix for Silent Crash
# 2025-09-08 - Fix all QMutex and QMutexLocker usage patterns

import sys
import os
import shutil

def apply_complete_mutex_fix():
    """QMutex와 QMutexLocker 사용을 모두 안전하게 비활성화"""
    
    print("[COMPLETE MUTEX FIX] Starting complete mutex elimination...")
    
    data_manager_file = "data_manager.py"
    backup_file = f"{data_manager_file}.backup_complete_fix"
    
    if os.path.exists(data_manager_file):
        # 백업 생성
        if not os.path.exists(backup_file):
            shutil.copy2(data_manager_file, backup_file)
            print(f"[COMPLETE MUTEX FIX] Data manager backed up to {backup_file}")
        
        # 파일 읽기
        with open(data_manager_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 모든 QMutexLocker 사용을 안전한 버전으로 교체
        safe_content = content.replace(
            'with QMutexLocker(self._mutex):',
            '# with QMutexLocker(self._mutex):  # DISABLED - was causing crashes\\nif True:'
        ).replace(
            'with QMutexLocker(self._activity_lock):',
            '# with QMutexLocker(self._activity_lock):  # DISABLED - was causing crashes\\nif True:'
        ).replace(
            'from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QMutexLocker, QTimer, QEventLoop',
            'from PyQt6.QtCore import QObject, pyqtSignal, QThread, QTimer, QEventLoop  # QMutex, QMutexLocker DISABLED'
        ).replace(
            'self._mutex = QMutex()',
            '# self._mutex = QMutex()  # DISABLED - dangerous pattern'
        ).replace(
            'self._activity_lock = QMutex()',
            '# self._activity_lock = QMutex()  # DISABLED - dangerous pattern'
        )
        
        # 추가 안전 조치
        lines = safe_content.split('\\n')
        safe_lines = []
        
        for line in lines:
            # QMutex 초기화 라인들 모두 비활성화
            if 'QMutex()' in line and not line.strip().startswith('#'):
                safe_lines.append(f'        # {line.strip()}  # DISABLED FOR CRASH FIX')
            else:
                safe_lines.append(line)
        
        safe_content = '\\n'.join(safe_lines)
        
        # 수정된 내용 저장
        with open(data_manager_file, 'w', encoding='utf-8') as f:
            f.write(safe_content)
        
        print("[COMPLETE MUTEX FIX] All QMutex and QMutexLocker usage disabled")
        return True
    
    return False

def restore_original():
    """원본 복구"""
    backup_file = "data_manager.py.backup_complete_fix"
    data_manager_file = "data_manager.py"
    
    if os.path.exists(backup_file):
        shutil.copy2(backup_file, data_manager_file)
        print("[COMPLETE MUTEX FIX] Original data_manager.py restored")
        return True
    
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_original()
    else:
        apply_complete_mutex_fix()