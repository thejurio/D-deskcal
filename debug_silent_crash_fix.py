# Temporary Silent Crash Debug Fix
# 2025-09-08 - Disable hotkey system to test crash fix

# This file contains temporary fixes to isolate the 1-2 minute silent crash issue

import sys
import os

def apply_hotkey_disable():
    """일시적으로 hotkey 시스템 비활성화"""
    
    # 1. hotkey_manager.py를 백업하고 비활성화된 버전으로 교체
    hotkey_file = "hotkey_manager.py"
    
    if os.path.exists(hotkey_file):
        # 백업 생성
        backup_file = f"{hotkey_file}.backup_pre_debug"
        if not os.path.exists(backup_file):
            import shutil
            shutil.copy2(hotkey_file, backup_file)
            print(f"[DEBUG] Hotkey manager backed up to {backup_file}")
        
        # 비활성화된 버전 생성
        safe_hotkey_content = '''# hotkey_manager.py - TEMPORARY DISABLED FOR DEBUG
from PyQt6.QtCore import QObject, pyqtSignal
import logging

logger = logging.getLogger(__name__)

class HotkeyManager(QObject):
    """Temporarily disabled hotkey manager for crash debugging"""
    hotkey_triggered = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        logger.info("HotkeyManager initialized (DISABLED FOR DEBUG)")

    def register_hotkey(self, action_name, hotkey_str):
        logger.debug(f"[DEBUG] Hotkey registration disabled: {action_name} = {hotkey_str}")
        return True

    def start_listener(self):
        logger.info("[DEBUG] Hotkey listener disabled for crash debugging")

    def stop_listener(self):
        logger.debug("[DEBUG] Hotkey stop (already disabled)")

    def cleanup(self):
        logger.debug("[DEBUG] Hotkey cleanup (already disabled)")
'''
        
        with open(hotkey_file, 'w', encoding='utf-8') as f:
            f.write(safe_hotkey_content)
        
        print("[DEBUG] Hotkey system temporarily disabled for crash debugging")
        return True
    
    return False

def restore_hotkey():
    """hotkey 시스템 복구"""
    backup_file = "hotkey_manager.py.backup_pre_debug"
    hotkey_file = "hotkey_manager.py"
    
    if os.path.exists(backup_file):
        import shutil
        shutil.copy2(backup_file, hotkey_file)
        print("[DEBUG] Hotkey system restored from backup")
        return True
    
    return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_hotkey()
    else:
        apply_hotkey_disable()