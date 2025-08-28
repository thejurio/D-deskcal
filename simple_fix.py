#!/usr/bin/env python3
"""
간단한 이벤트 Provider 불일치 문제 해결 스크립트
"""

import sqlite3
import json
import datetime
import os
import shutil

def main():
    """메인 실행 함수"""
    print("Event Provider Mismatch Fix Tool")
    print("Resolving: Google Calendar events misclassified as Local events")
    
    # 현재 디렉토리 확인
    if not os.path.exists("calendar.db"):
        print("[ERROR] calendar.db not found in current directory")
        print(f"   Current directory: {os.getcwd()}")
        return
    
    # 백업 생성
    backup_name = f"calendar_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2("calendar.db", backup_name)
    print(f"[BACKUP] Created backup: {backup_name}")
    
    try:
        conn = sqlite3.connect("calendar.db")
        cursor = conn.cursor()
        
        # 문제가 있는 이벤트들 찾기
        cursor.execute("SELECT id, event_json FROM events")
        events = cursor.fetchall()
        
        removed_count = 0
        
        for event_id, event_json_str in events:
            event_data = json.loads(event_json_str)
            
            # Google Calendar 특징 확인
            has_google_features = any([
                'htmlLink' in event_data,
                'etag' in event_data,
                'creator' in event_data and 'gmail.com' in str(event_data.get('creator', {})),
                'iCalUID' in event_data,
                event_data.get('kind') == 'calendar#event'
            ])
            
            current_provider = event_data.get('provider', '')
            summary = event_data.get('summary', 'No Title')
            
            # Google Calendar 이벤트인데 LocalCalendarProvider로 설정된 경우
            if has_google_features and current_provider == 'LocalCalendarProvider':
                print(f"Found mismatched event: {summary}")
                print(f"   ID: {event_id}")
                
                # 특정 문제 이벤트 자동 제거
                if "계절학기" in summary or "보고서 수합" in summary:
                    # 로컬 DB에서 완전 제거 (Google에서 다시 동기화되도록)
                    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                    cursor.execute("DELETE FROM event_exceptions WHERE original_event_id = ?", (event_id,))
                    removed_count += 1
                    print(f"   [AUTO-REMOVED] Removed from local database")
                else:
                    print(f"   [INFO] Found but not auto-removing: {summary}")
        
        conn.commit()
        conn.close()
        
        print(f"[SUCCESS] Fix completed!")
        print(f"   - Events removed from local DB: {removed_count}")
        print(f"   - These events will be properly synchronized from Google Calendar")
        
        # 캐시 클리어
        cache_files = ['cache.json', 'cache_db.json']
        for cache_file in cache_files:
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                    print(f"[CLEARED] Cleared: {cache_file}")
                except Exception as e:
                    print(f"[ERROR] Failed to clear {cache_file}: {e}")
        
        if removed_count > 0:
            print(f"[COMPLETE] ALL DONE!")
            print(f"   1. Restart the calendar app")
            print(f"   2. Google Calendar events will sync properly")
            print(f"   3. Deletion should work correctly now")
        else:
            print(f"[INFO] No problematic events found to remove")
            
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        # 백업 복원
        if os.path.exists(backup_name):
            shutil.copy2(backup_name, "calendar.db")
            print(f"[RESTORE] Restored from backup: {backup_name}")

if __name__ == "__main__":
    os.chdir(r"C:\dcwidget")
    main()