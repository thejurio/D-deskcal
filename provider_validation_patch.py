"""
Provider 검증 및 수정 패치
data_manager.py에 통합할 수 있는 코드
"""

def _validate_event_provider(self, event_data):
    """
    이벤트의 provider가 올바른지 검증하고 수정
    Google Calendar 이벤트가 LocalCalendarProvider로 잘못 분류되는 것을 방지
    """
    if not isinstance(event_data, dict):
        return event_data
        
    # Google Calendar 특징 확인
    has_google_features = any([
        'htmlLink' in event_data,
        'etag' in event_data,
        'iCalUID' in event_data,
        event_data.get('kind') == 'calendar#event',
        '@gmail.com' in str(event_data.get('creator', {})),
        '@gmail.com' in str(event_data.get('organizer', {}))
    ])
    
    current_provider = event_data.get('provider', '')
    
    # Google 특징이 있는데 LocalCalendarProvider로 설정된 경우 수정
    if has_google_features and current_provider == 'LocalCalendarProvider':
        print(f"[FIX] Correcting provider for event: {event_data.get('summary', 'No Title')}")
        event_data['provider'] = 'GoogleCalendarProvider'
        
        # 캘린더 ID도 Google 형식으로 수정
        if event_data.get('calendarId') == 'local_calendar':
            # 원래 Google Calendar ID 복원
            organizer_email = event_data.get('organizer', {}).get('email', 'primary')
            event_data['calendarId'] = organizer_email
    
    # 진짜 로컬 이벤트는 LocalCalendarProvider로 유지
    elif not has_google_features and current_provider != 'LocalCalendarProvider':
        # 로컬에서 생성된 이벤트인지 확인
        if event_data.get('id', '').startswith('temp_') or 'local' in event_data.get('calendarId', ''):
            event_data['provider'] = 'LocalCalendarProvider'
            event_data['calendarId'] = 'local_calendar'
    
    return event_data

# data_manager.py의 add_event 메서드에서 사용:
# event_data = self._validate_event_provider(event_data)

# data_manager.py의 update_event 메서드에서 사용:
# event_data = self._validate_event_provider(event_data)

def _clean_orphaned_events(self):
    """
    데이터베이스에서 잘못된 provider를 가진 이벤트를 정리
    """
    try:
        import sqlite3
        import json
        
        conn = sqlite3.connect("calendar.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, event_json FROM events")
        events = cursor.fetchall()
        
        cleaned_count = 0
        
        for event_id, event_json_str in events:
            event_data = json.loads(event_json_str)
            
            # Google 특징이 있는데 LocalCalendarProvider인 경우
            has_google_features = any([
                'htmlLink' in event_data,
                'etag' in event_data,
                'iCalUID' in event_data,
                event_data.get('kind') == 'calendar#event'
            ])
            
            if has_google_features and event_data.get('provider') == 'LocalCalendarProvider':
                # 로컬 DB에서 제거 (Google에서 다시 동기화됨)
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                cursor.execute("DELETE FROM event_exceptions WHERE original_event_id = ?", (event_id,))
                cleaned_count += 1
                print(f"[CLEANUP] Removed misclassified event: {event_data.get('summary', event_id)}")
        
        if cleaned_count > 0:
            conn.commit()
            print(f"[CLEANUP] Cleaned {cleaned_count} misclassified events")
        
        conn.close()
        
    except Exception as e:
        print(f"[CLEANUP ERROR] Failed to clean orphaned events: {e}")

# 애플리케이션 시작 시 호출:
# self._clean_orphaned_events()