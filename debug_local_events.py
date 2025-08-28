#!/usr/bin/env python3
"""
로컬 캘린더 이벤트 삭제 문제 디버깅 도구
8월 29일 "학습도약 계절학기 보고서 수합" 일정이 삭제되지 않는 문제 분석
"""

import sqlite3
import json
import datetime
from dateutil.rrule import rrulestr

def debug_database_state():
    """데이터베이스 현재 상태 확인"""
    print("=" * 60)
    print("DATABASE STATE ANALYSIS")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect("calendar.db")
        cursor = conn.cursor()
        
        # 1. 테이블 구조 확인
        print("\n1. TABLE STRUCTURE:")
        cursor.execute("PRAGMA table_info(events)")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
            
        # 2. 모든 이벤트 조회
        print("\n2. ALL EVENTS IN DATABASE:")
        cursor.execute("SELECT id, start_date, end_date, rrule, event_json FROM events")
        events = cursor.fetchall()
        
        target_found = False
        for i, (event_id, start_date, end_date, rrule, event_json) in enumerate(events):
            event_data = json.loads(event_json)
            summary = event_data.get('summary', 'No Title')
            
            # 목표 이벤트 찾기
            if "학습도약" in summary or "계절학기" in summary or "보고서" in summary:
                target_found = True
                print(f"\n   *** TARGET EVENT FOUND ***")
                print(f"   Event #{i+1}: {summary}")
                print(f"   ID: {event_id}")
                print(f"   Start: {start_date}")
                print(f"   End: {end_date}")
                print(f"   RRULE: {rrule}")
                print(f"   Event JSON: {json.dumps(event_data, indent=2, ensure_ascii=False)}")
            else:
                print(f"   Event #{i+1}: {summary} (ID: {event_id})")
        
        if not target_found:
            print("   *** TARGET EVENT NOT FOUND IN DATABASE ***")
            
        # 3. 예외 테이블 확인
        print("\n3. EVENT EXCEPTIONS:")
        cursor.execute("SELECT * FROM event_exceptions")
        exceptions = cursor.fetchall()
        if exceptions:
            for exc in exceptions:
                print(f"   Exception: {exc}")
        else:
            print("   No exceptions found")
            
        conn.close()
        return target_found, events
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False, []

def analyze_caching_issue():
    """캐싱 시스템의 문제점 분석"""
    print("\n" + "=" * 60)
    print("CACHING SYSTEM ANALYSIS")
    print("=" * 60)
    
    # 캐시 파일들 확인
    import os
    
    cache_files = []
    for file in ['cache.json', 'calendar.db']:
        if os.path.exists(file):
            stat = os.stat(file)
            cache_files.append({
                'file': file,
                'size': stat.st_size,
                'modified': datetime.datetime.fromtimestamp(stat.st_mtime)
            })
    
    print("Cache files:")
    for cache_file in cache_files:
        print(f"   {cache_file['file']}: {cache_file['size']} bytes, modified {cache_file['modified']}")

def simulate_deletion_process(event_id=None):
    """삭제 프로세스 시뮬레이션"""
    print("\n" + "=" * 60)
    print("DELETION PROCESS SIMULATION")
    print("=" * 60)
    
    if not event_id:
        # 목표 이벤트 ID 찾기
        try:
            conn = sqlite3.connect("calendar.db")
            cursor = conn.cursor()
            cursor.execute("SELECT id, event_json FROM events")
            
            for db_id, event_json in cursor.fetchall():
                event_data = json.loads(event_json)
                summary = event_data.get('summary', '')
                if "학습도약" in summary or "계절학기" in summary:
                    event_id = db_id
                    break
            conn.close()
            
        except sqlite3.Error:
            pass
    
    if not event_id:
        print("Target event not found for simulation")
        return
    
    print(f"Simulating deletion for event ID: {event_id}")
    
    # 삭제 시뮬레이션
    try:
        conn = sqlite3.connect("calendar.db")
        cursor = conn.cursor()
        
        # 삭제 전 상태
        cursor.execute("SELECT COUNT(*) FROM events WHERE id = ?", (event_id,))
        before_count = cursor.fetchone()[0]
        print(f"Events with ID {event_id} before deletion: {before_count}")
        
        # 삭제 실행 (실제로는 하지 않음, 시뮬레이션만)
        print("Would execute: DELETE FROM events WHERE id = ?")
        print("Would execute: DELETE FROM event_exceptions WHERE original_event_id = ?")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Simulation error: {e}")

def check_data_manager_cache():
    """DataManager의 캐시 상태 확인 (파일 기반)"""
    print("\n" + "=" * 60)
    print("DATA MANAGER CACHE ANALYSIS")
    print("=" * 60)
    
    try:
        # cache.json 파일 확인
        if os.path.exists("cache.json"):
            with open("cache.json", "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                
            print("Cache.json contents:")
            for key, events in cache_data.items():
                if isinstance(events, list):
                    target_events = []
                    for event in events:
                        if isinstance(event, dict):
                            summary = event.get('summary', '')
                            if "학습도약" in summary or "계절학기" in summary:
                                target_events.append(event)
                    
                    if target_events:
                        print(f"   Month {key}: Found {len(target_events)} target events")
                        for event in target_events:
                            print(f"     - {event.get('summary')} (ID: {event.get('id')})")
                    else:
                        print(f"   Month {key}: {len(events)} events (no target events)")
        else:
            print("No cache.json file found")
            
    except Exception as e:
        print(f"Cache analysis error: {e}")

def generate_fix_suggestions():
    """문제 해결 방안 제안"""
    print("\n" + "=" * 60)
    print("PROBLEM ANALYSIS & FIX SUGGESTIONS")
    print("=" * 60)
    
    print("Potential causes identified:")
    print("1. EVENT RESURRECTION via caching:")
    print("   - Event deleted from DB but remains in cache.json")
    print("   - Cache gets reloaded and overwrites DB deletion")
    print()
    print("2. SYNC INTERFERENCE:")
    print("   - Background sync thread restores deleted events")
    print("   - Cache manager conflicts with deletion operations")
    print()
    print("3. RRULE MISINTERPRETATION:")
    print("   - Non-recurring event treated as recurring")
    print("   - Deletion logic confusion between instance vs master event")
    print()
    
    print("Recommended fixes:")
    print("1. Clear all caches after deletion")
    print("2. Add proper cache invalidation")
    print("3. Improve deletion transaction integrity")
    print("4. Add deletion verification step")

def main():
    """메인 디버그 실행"""
    print("Local Calendar Event Deletion Debugger")
    print("Analyzing: '학습도약 계절학기 보고서 수합' event deletion issue")
    print("Date: August 29, 2025")
    
    # 1. 데이터베이스 상태 분석
    target_found, events = debug_database_state()
    
    # 2. 캐싱 시스템 분석
    analyze_caching_issue()
    
    # 3. 캐시 파일 분석
    check_data_manager_cache()
    
    # 4. 삭제 프로세스 시뮬레이션
    simulate_deletion_process()
    
    # 5. 해결 방안 제안
    generate_fix_suggestions()
    
    print(f"\nDebug analysis complete. Found {len(events)} total events in database.")
    print("Check the output above for detailed analysis.")

if __name__ == "__main__":
    import os
    os.chdir(r"C:\dcwidget")  # 작업 디렉토리 설정
    main()