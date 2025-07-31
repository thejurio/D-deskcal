import sqlite3
import json
import datetime
from dateutil.rrule import rrulestr

from .base_provider import BaseCalendarProvider
from config import (DB_FILE, LOCAL_CALENDAR_ID, LOCAL_CALENDAR_PROVIDER_NAME,
                    DEFAULT_LOCAL_CALENDAR_COLOR, DEFAULT_LOCAL_CALENDAR_EMOJI)

class LocalCalendarProvider(BaseCalendarProvider):
    def __init__(self, settings, db_connection=None):
        self.settings = settings
        self._connection = db_connection
        self.name = LOCAL_CALENDAR_PROVIDER_NAME
        # DB 연결을 먼저 확인하고 마이그레이션을 수행합니다.
        self._check_and_migrate_db()

    def _get_connection(self):
        """DB 연결을 반환하거나, 없을 경우 새로 생성합니다."""
        if self._connection:
            return self._connection
        return sqlite3.connect(DB_FILE)

    def _check_and_migrate_db(self):
        """DB 스키마를 확인하고 필요 시 'rrule' 컬럼을 추가합니다."""
        try:
            # 테이블이 없는 경우를 대비해 먼저 init을 호출
            self._init_db_table() 
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(events)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'rrule' not in columns:
                    print("데이터베이스 스키마 마이그레이션: 'rrule' 컬럼을 추가합니다.")
                    cursor.execute("ALTER TABLE events ADD COLUMN rrule TEXT")
                    conn.commit()
        except sqlite3.Error as e:
            print(f"DB 마이그레이션 중 오류 발생: {e}")


    def _init_db_table(self):
        """데이터베이스 테이블과 인덱스를 생성합니다. (없을 경우에만)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        rrule TEXT,
                        event_json TEXT NOT NULL
                    )
                """)
                # 날짜 검색 성능 향상을 위한 인덱스 추가
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_start_date ON events (start_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_end_date ON events (end_date)")
                conn.commit()
        except sqlite3.Error as e:
            print(f"로컬 DB 테이블 초기화 중 오류 발생: {e}")

    # providers/local_provider.py 파일입니다.

    def get_events(self, start_date, end_date, data_manager=None):
        """특정 기간 사이의 로컬 이벤트를 반환합니다. (반복 일정 포함)"""
        final_events = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 1. 기간 내의 일반 이벤트 + 모든 반복 이벤트 가져오기
                # 반복 이벤트는 시작일과 상관없이 모두 가져와서 규칙을 확인해야 함
                cursor.execute("""
                    SELECT event_json, rrule FROM events
                    WHERE (rrule IS NULL AND start_date <= ? AND end_date >= ?) OR rrule IS NOT NULL
                """, (end_date.isoformat(), start_date.isoformat()))

                for event_json, rrule_str in cursor.fetchall():
                    event_template = json.loads(event_json)
                    
                    if rrule_str:
                        # 2. 반복 이벤트 처리
                        try:
                            start_str = event_template['start'].get('dateTime', event_template['start'].get('date'))
                            end_str = event_template['end'].get('dateTime', event_template['end'].get('date'))
                            
                            is_all_day = 'date' in event_template['start']

                            if is_all_day:
                                start_dt_orig = datetime.datetime.fromisoformat(start_str)
                                end_dt_orig = datetime.datetime.fromisoformat(end_str)
                            else:
                                start_dt_orig = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                                end_dt_orig = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                            
                            duration = end_dt_orig - start_dt_orig

                            # rrulestr에 dtstart를 반드시 datetime 객체로 전달해야 함
                            rule = rrulestr(f"RRULE:{rrule_str}", dtstart=start_dt_orig)
                            
                            # 3. 기간 내의 반복 인스턴스 생성
                            view_start_dt = datetime.datetime.combine(start_date, datetime.time.min)
                            view_end_dt = datetime.datetime.combine(end_date, datetime.time.max)

                            for occurrence_start in rule.between(view_start_dt, view_end_dt, inc=True):
                                instance_event = json.loads(event_json) # 원본 복사
                                occurrence_end = occurrence_start + duration
                                
                                # --- ▼▼▼ [수정] 반복 인스턴스에 고유 ID 부여 ▼▼▼ ---
                                original_id = instance_event['id']
                                occurrence_id_str = occurrence_start.strftime('%Y%m%dT%H%M%S')
                                instance_event['id'] = f"{original_id}_{occurrence_id_str}"
                                instance_event['originalId'] = original_id # 원본 ID도 저장
                                # --- ▲▲▲ 여기까지 수정 ▲▲▲ ---

                                if 'dateTime' in instance_event['start']:
                                    instance_event['start'] = {'dateTime': occurrence_start.isoformat(), 'timeZone': 'Asia/Seoul'}
                                    instance_event['end'] = {'dateTime': occurrence_end.isoformat(), 'timeZone': 'Asia/Seoul'}
                                else: # 종일 일정
                                    instance_event['start'] = {'date': occurrence_start.strftime('%Y-%m-%d')}
                                    instance_event['end'] = {'date': occurrence_end.strftime('%Y-%m-%d')}
                                
                                final_events.append(instance_event)

                        except Exception as e:
                            print(f"반복 규칙 처리 중 오류 발생: {e}, 규칙: '{rrule_str}', 이벤트: {event_template.get('summary')}")
                            # 오류가 발생한 반복 일정은 건너뛰고, 원본 이벤트만 추가 (선택적)
                            # final_events.append(event_template) 
                            continue
                    else:
                        # 일반 이벤트는 그냥 추가
                        final_events.append(event_template)

                # 모든 이벤트에 공통 속성(calendarId) 추가
                for event in final_events:
                    event['calendarId'] = LOCAL_CALENDAR_ID
                
                return final_events

        except sqlite3.Error as e:
            print(f"로컬 이벤트 조회 중 오류 발생: {e}")
            return []

    def add_event(self, event_data):
        """새로운 로컬 이벤트를 DB에 추가하고, 추가된 이벤트 객체를 반환합니다."""
        try:
            body = event_data.get('body')
            if not body:
                return None

            event_id = body.get('id')
            start_date = body.get('start', {}).get('date') or body.get('start', {}).get('dateTime', '')[:10]
            end_date = body.get('end', {}).get('date') or body.get('end', {}).get('dateTime', '')[:10]
            
            # --- ▼▼▼ RRULE 데이터 추출 ▼▼▼ ---
            rrule_str = None
            if 'recurrence' in body and body['recurrence']:
                # Google API는 ["RRULE:..."] 형식이므로, 첫 번째 항목을 사용하고 접두사를 제거합니다.
                rrule_str = body['recurrence'][0].replace('RRULE:', '')
            # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

            if not all([event_id, start_date, end_date]):
                return None

            body['provider'] = LOCAL_CALENDAR_PROVIDER_NAME
            body['calendarId'] = LOCAL_CALENDAR_ID

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO events (id, start_date, end_date, rrule, event_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (event_id, start_date, end_date, rrule_str, json.dumps(body)))
                conn.commit()
            
            return body
        except (sqlite3.Error, KeyError) as e:
            print(f"로컬 이벤트 추가 중 오류 발생: {e}")
            return None

    def update_event(self, event_data):
        return self.add_event(event_data)

    def delete_event(self, event_data):
        """기존 로컬 이벤트를 삭제합니다."""
        try:
            event_id = event_data.get('body', {}).get('id') or event_data.get('id')
            if not event_id:
                print("삭제할 이벤트의 ID를 찾을 수 없습니다.")
                return False

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"Local Provider: 이벤트 삭제 성공 (ID: {event_id})")
                    return True
                else:
                    print(f"Local Provider: 삭제할 이벤트를 찾지 못함 (ID: {event_id})")
                    return False
        except sqlite3.Error as e:
            print(f"로컬 이벤트 삭제 중 오류 발생: {e}")
            return False

    def get_calendars(self):
        """'로컬 캘린더' 자체에 대한 정보를 표준 형식으로 반환합니다."""
        return [{
            'id': LOCAL_CALENDAR_ID,  # 로컬 캘린더를 위한 고유 ID
            'summary': '로컬 캘린더',
            # 설정에 저장된 색상 또는 기본 색상을 사용합니다.
            'backgroundColor': self.settings.get("local_calendar_color", DEFAULT_LOCAL_CALENDAR_COLOR),
            'provider': LOCAL_CALENDAR_PROVIDER_NAME
        }]

    def search_events(self, query):
        """로컬 DB에서 제목 또는 설명에 query가 포함된 이벤트를 검색합니다."""
        if not query:
            return []
        
        search_term = f"%{query}%"
        found_events = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # json_extract를 사용하고 싶지만, 모든 sqlite 버전에 내장되어 있지 않으므로 LIKE를 사용합니다.
                cursor.execute("""
                    SELECT event_json FROM events
                    WHERE event_json LIKE ? OR event_json LIKE ?
                """, (f'%summary":"%{search_term}%', f'%description":"%{search_term}%'))

                for row in cursor.fetchall():
                    event = json.loads(row[0])
                    # 반복 이벤트는 현재 구현에서는 검색 결과에 원본만 포함합니다.
                    # (모든 인스턴스를 생성하여 검색하는 것은 매우 비효율적일 수 있음)
                    found_events.append(event)

            # 공통 속성 추가
            for event in found_events:
                event['provider'] = LOCAL_CALENDAR_PROVIDER_NAME
                event['calendarId'] = LOCAL_CALENDAR_ID
            
            return found_events
        except sqlite3.Error as e:
            print(f"로컬 이벤트 검색 중 오류 발생: {e}")
            return []