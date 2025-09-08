#!/usr/bin/env python3
"""
상세한 로깅을 통한 로컬 일정 생성 문제 디버깅
"""
import sys
import datetime
import logging

# DEBUG 레벨 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('local_event_debug.log', mode='w', encoding='utf-8')
    ]
)

from PyQt6.QtWidgets import QApplication

def test_local_event_with_debug_logging():
    """로컬 일정 생성을 상세 로깅과 함께 테스트"""
    
    # QApplication 필요
    app = QApplication(sys.argv)
    
    print("=== 로컬 일정 생성 디버깅 시작 ===")
    print("DEBUG 레벨 로깅이 활성화되었습니다.")
    print("로그는 콘솔과 'local_event_debug.log' 파일에 저장됩니다.\n")
    
    try:
        # 필요한 모듈 import (로그와 함께)
        print("1. 필요한 모듈들을 import 중...")
        from settings_manager import load_settings
        from data_manager import DataManager
        from auth_manager import AuthManager
        print("   [OK] 모든 모듈 import 완료\n")
        
        # 설정 로드
        print("2. 설정 로드 중...")
        settings = load_settings()
        print("   [OK] 설정 로드 완료\n")
        
        # AuthManager와 DataManager 초기화
        print("3. DataManager 초기화 중...")
        auth_manager = AuthManager()
        data_manager = DataManager(settings, auth_manager)
        print("   [OK] DataManager 초기화 완료\n")
        
        # 현재 날짜로 테스트 이벤트 생성
        today = datetime.date.today()
        test_event_data = {
            'provider': 'local',
            'calendarId': 'local_calendar',
            'body': {
                'id': f'debug_test_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'summary': '[DEBUG] 로컬 일정 생성 문제 디버깅',
                'description': '이 이벤트는 로깅을 통한 문제 진단용입니다.',
                'start': {
                    'date': today.isoformat()
                },
                'end': {
                    'date': (today + datetime.timedelta(days=1)).isoformat()
                }
            }
        }
        
        print("4. 테스트 이벤트 생성 중...")
        print(f"   이벤트: {test_event_data['body']['summary']}")
        print(f"   날짜: {today}")
        print(f"   ID: {test_event_data['body']['id']}\n")
        
        # 이벤트 추가 전 캐시 상태
        print("5. 이벤트 추가 전 캐시 확인...")
        events_before = data_manager.get_events(today.year, today.month)
        print(f"   추가 전 캐시 이벤트 수: {len(events_before)}\n")
        
        # 이벤트 추가 실행
        print("6. 이벤트 추가 실행...")
        print("   (상세한 로그를 확인하세요)\n")
        
        result = data_manager.add_event(test_event_data)
        
        print(f"7. add_event 결과: {result}")
        if result:
            print("   [OK] add_event 성공 반환")
        else:
            print("   [FAIL] add_event 실패 반환")
        print()
        
        # 이벤트 추가 직후 캐시 확인
        print("8. 이벤트 추가 직후 캐시 확인...")
        events_after = data_manager.get_events(today.year, today.month)
        print(f"   추가 후 캐시 이벤트 수: {len(events_after)}")
        
        # 디버그 이벤트 찾기
        debug_event = None
        for event in events_after:
            if '[DEBUG]' in event.get('summary', ''):
                debug_event = event
                print(f"   [OK] 디버그 이벤트 발견: {event.get('id')}")
                print(f"     제목: {event.get('summary')}")
                print(f"     동기화 상태: {event.get('_sync_state', 'unknown')}")
                print(f"     제공자: {event.get('provider', 'unknown')}")
                break
        
        if not debug_event:
            print("   [FAIL] 디버그 이벤트가 캐시에서 발견되지 않음!")
        print()
        
        # 백그라운드 동기화 대기
        print("9. 백그라운드 동기화 대기 (5초)...")
        import time
        time.sleep(5)
        print()
        
        # 동기화 후 캐시 재확인
        print("10. 동기화 후 캐시 재확인...")
        events_after_sync = data_manager.get_events(today.year, today.month)
        print(f"    동기화 후 캐시 이벤트 수: {len(events_after_sync)}")
        
        sync_debug_event = None
        for event in events_after_sync:
            if '[DEBUG]' in event.get('summary', ''):
                sync_debug_event = event
                print(f"    [OK] 동기화 후 디버그 이벤트: {event.get('id')}")
                print(f"      동기화 상태: {event.get('_sync_state', 'unknown')}")
                break
        
        if not sync_debug_event:
            print("    [FAIL] 동기화 후 디버그 이벤트 사라짐!")
        print()
        
        # 강제 새로고침 테스트
        print("11. 강제 새로고침 테스트...")
        data_manager.force_sync_month(today.year, today.month)
        time.sleep(3)
        
        events_after_force_sync = data_manager.get_events(today.year, today.month)
        print(f"    강제 새로고침 후 이벤트 수: {len(events_after_force_sync)}")
        
        force_sync_debug_event = None
        for event in events_after_force_sync:
            if '[DEBUG]' in event.get('summary', ''):
                force_sync_debug_event = event
                print(f"    [OK] 강제 새로고침 후 디버그 이벤트: {event.get('id')}")
                break
        
        if not force_sync_debug_event:
            print("    [FAIL] 강제 새로고침 후 디버그 이벤트 사라짐!")
            print("    [DEBUG] 이것이 문제의 핵심일 가능성이 높습니다!")
        print()
        
        print("=== 디버깅 완료 ===")
        print("자세한 로그는 'local_event_debug.log' 파일에서 확인하세요.")
        
    except Exception as e:
        print(f"디버깅 중 오류 발생: {e}")
        logging.exception("Debug script error")
    
    finally:
        app.quit()

if __name__ == "__main__":
    test_local_event_with_debug_logging()