#!/usr/bin/env python3
"""
이벤트 Provider 불일치 문제 해결 스크립트
Google Calendar 이벤트가 LocalCalendarProvider로 잘못 분류된 문제를 수정
"""

import sqlite3
import json
import datetime
import os

def fix_provider_mismatch():
    """Provider 불일치 문제 수정"""
    print("=" * 60)
    print("FIXING PROVIDER MISMATCH ISSUE")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect("calendar.db")
        cursor = conn.cursor()
        
        # 문제가 있는 이벤트들 찾기
        cursor.execute("SELECT id, event_json FROM events")
        events = cursor.fetchall()
        
        fixed_count = 0
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
            
            # Google Calendar 이벤트인데 LocalCalendarProvider로 설정된 경우
            if has_google_features and current_provider == 'LocalCalendarProvider':
                summary = event_data.get('summary', 'No Title')
                print(f"\nFound mismatched event: {summary}")
                print(f"   ID: {event_id}")
                print(f"   Current Provider: {current_provider}")
                print(f"   Has Google features: {has_google_features}")
                
                # 사용자 선택
                choice = input(f"   Fix this event? [r]emove/[s]kip: ").lower()
                
                if choice == 'r':
                    # 로컬 DB에서 완전 제거 (Google에서 다시 동기화되도록)
                    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                    cursor.execute("DELETE FROM event_exceptions WHERE original_event_id = ?", (event_id,))
                    removed_count += 1
                    print(f"   ✅ Removed from local database")
                else:
                    print(f"   ⏭️ Skipped")
        
        conn.commit()
        conn.close()
        
        print(f"\n🎉 Fix completed!")
        print(f"   - Events removed from local DB: {removed_count}")
        print(f"   - These events will be properly synchronized from Google Calendar")
        
        return removed_count > 0
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")
        return False

def clear_app_caches():
    """애플리케이션 캐시 클리어"""
    print("\n" + "=" * 60)
    print("CLEARING APPLICATION CACHES")
    print("=" * 60)
    
    cache_files = ['cache.json', 'cache_db.json']
    cleared = []
    
    for cache_file in cache_files:
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                cleared.append(cache_file)
                print(f"✅ Cleared: {cache_file}")
            except Exception as e:
                print(f"❌ Failed to clear {cache_file}: {e}")
        else:
            print(f"ℹ️ Not found: {cache_file}")
    
    if cleared:
        print(f"\n🗑️ Cleared {len(cleared)} cache files")
        print("   App will rebuild caches on next startup")
    else:
        print("\n📁 No cache files found to clear")

def verify_fix():
    """수정 사항 검증"""
    print("\n" + "=" * 60)
    print("VERIFYING FIX")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect("calendar.db")
        cursor = conn.cursor()
        
        # 남은 이벤트 확인
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]
        
        # Google 특징이 있지만 LocalProvider인 이벤트 확인
        cursor.execute("SELECT id, event_json FROM events")
        events = cursor.fetchall()
        
        problem_events = 0
        for event_id, event_json_str in events:
            event_data = json.loads(event_json_str)
            
            has_google_features = any([
                'htmlLink' in event_data,
                'etag' in event_data,
                'iCalUID' in event_data,
                event_data.get('kind') == 'calendar#event'
            ])
            
            if has_google_features and event_data.get('provider') == 'LocalCalendarProvider':
                problem_events += 1
        
        conn.close()
        
        print(f"📊 Database status:")
        print(f"   - Total events: {total_events}")
        print(f"   - Problem events remaining: {problem_events}")
        
        if problem_events == 0:
            print("✅ No provider mismatch issues found!")
            return True
        else:
            print("⚠️ Some issues remain - may need manual intervention")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

def create_prevention_patch():
    """향후 문제 예방을 위한 패치 생성"""
    print("\n" + "=" * 60)
    print("CREATING PREVENTION PATCH")
    print("=" * 60)
    
    patch_content = '''# data_manager.py에 추가할 패치
def _validate_event_provider(self, event_data):
    """이벤트의 provider가 올바른지 검증"""
    if not isinstance(event_data, dict):
        return event_data
        
    # Google Calendar 특징 확인
    has_google_features = any([
        'htmlLink' in event_data,
        'etag' in event_data,
        'iCalUID' in event_data,
        event_data.get('kind') == 'calendar#event',
        '@gmail.com' in str(event_data.get('creator', {}))
    ])
    
    # Provider 수정
    if has_google_features:
        event_data['provider'] = 'GoogleCalendarProvider'
        # Google 캘린더 ID로 변경 (필요시)
        if event_data.get('calendarId') == 'local_calendar':
            event_data['calendarId'] = event_data.get('organizer', {}).get('email', 'primary')
    
    return event_data

# add_event, update_event 메서드에서 호출:
# event_data = self._validate_event_provider(event_data)
'''
    
    with open('provider_validation_patch.py', 'w', encoding='utf-8') as f:
        f.write(patch_content)
    
    print("📄 Created provider_validation_patch.py")
    print("   This patch can be integrated into data_manager.py to prevent future issues")

def main():
    """메인 실행 함수"""
    print("Event Provider Mismatch Fix Tool")
    print("Resolving: Google Calendar events misclassified as Local events")
    
    # 현재 디렉토리 확인
    if not os.path.exists("calendar.db"):
        print("❌ calendar.db not found in current directory")
        print(f"   Current directory: {os.getcwd()}")
        return
    
    # 백업 생성
    import shutil
    backup_name = f"calendar_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2("calendar.db", backup_name)
    print(f"[BACKUP] Created backup: {backup_name}")
    
    try:
        # 1. Provider 불일치 수정
        if fix_provider_mismatch():
            
            # 2. 캐시 클리어
            clear_app_caches()
            
            # 3. 수정 사항 검증
            verify_fix()
            
            # 4. 예방 패치 생성
            create_prevention_patch()
            
            print(f"\n🎊 ALL DONE!")
            print(f"   1. Restart the calendar app")
            print(f"   2. Google Calendar events will sync properly")
            print(f"   3. Deletion should work correctly now")
            
        else:
            print(f"\n⚠️ No changes made")
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        # 백업 복원
        if os.path.exists(backup_name):
            shutil.copy2(backup_name, "calendar.db")
            print(f"🔄 Restored from backup: {backup_name}")

if __name__ == "__main__":
    os.chdir(r"C:\dcwidget")
    main()