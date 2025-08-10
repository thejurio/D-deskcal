import sqlite3
import json
import datetime
from dateutil.rrule import rrulestr

from .base_provider import BaseCalendarProvider
from config import (DB_FILE, LOCAL_CALENDAR_ID, LOCAL_CALENDAR_PROVIDER_NAME,
                    DEFAULT_LOCAL_CALENDAR_COLOR)

class LocalCalendarProvider(BaseCalendarProvider):
    def __init__(self, settings, db_connection=None):
        self.settings = settings
        self._connection = db_connection
        self.name = LOCAL_CALENDAR_PROVIDER_NAME
        self._check_and_migrate_db()

    def _get_connection(self):
        if self._connection:
            return self._connection
        return sqlite3.connect(DB_FILE)

    def _check_and_migrate_db(self):
        try:
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
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_start_date ON events (start_date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_end_date ON events (end_date)")
                conn.commit()
        except sqlite3.Error as e:
            print(f"로컬 DB 테이블 초기화 중 오류 발생: {e}")

    def get_events(self, start_date, end_date, data_manager=None):
        final_events = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event_json, rrule FROM events
                    WHERE (rrule IS NULL AND start_date <= ? AND end_date >= ?) OR rrule IS NOT NULL
                """, (end_date.isoformat(), start_date.isoformat()))

                for event_json, rrule_str in cursor.fetchall():
                    event_template = json.loads(event_json)
                    
                    if rrule_str:
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
                            rule = rrulestr(f"RRULE:{rrule_str}", dtstart=start_dt_orig)
                            
                            view_start_dt = datetime.datetime.combine(start_date, datetime.time.min)
                            view_end_dt = datetime.datetime.combine(end_date, datetime.time.max)

                            for occurrence_start in rule.between(view_start_dt, view_end_dt, inc=True):
                                instance_event = json.loads(event_json)
                                occurrence_end = occurrence_start + duration
                                
                                original_id = instance_event['id']
                                occurrence_id_str = occurrence_start.strftime('%Y%m%dT%H%M%S')
                                instance_event['id'] = f"{original_id}_{occurrence_id_str}"
                                instance_event['originalId'] = original_id

                                if 'dateTime' in instance_event['start']:
                                    instance_event['start'] = {'dateTime': occurrence_start.isoformat(), 'timeZone': 'Asia/Seoul'}
                                    instance_event['end'] = {'dateTime': occurrence_end.isoformat(), 'timeZone': 'Asia/Seoul'}
                                else:
                                    instance_event['start'] = {'date': occurrence_start.strftime('%Y-%m-%d')}
                                    instance_event['end'] = {'date': occurrence_end.strftime('%Y-%m-%d')}
                                
                                final_events.append(instance_event)

                        except Exception as e:
                            error_message = f"로컬 반복 규칙 처리 중 오류: {e}, 규칙: '{rrule_str}', 이벤트: {event_template.get('summary')}"
                            if data_manager: data_manager.report_error(error_message)
                            else: print(error_message)
                            continue
                    else:
                        final_events.append(event_template)

                for event in final_events:
                    event['calendarId'] = LOCAL_CALENDAR_ID
                
                return final_events

        except sqlite3.Error as e:
            error_message = f"로컬 이벤트 조회 중 DB 오류가 발생했습니다: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return []

    def add_event(self, event_data, data_manager=None):
        try:
            body = event_data.get('body')
            if not body: return None

            event_id = body.get('id')
            start_date = body.get('start', {}).get('date') or body.get('start', {}).get('dateTime', '')[:10]
            end_date = body.get('end', {}).get('date') or body.get('end', {}).get('dateTime', '')[:10]
            
            rrule_str = None
            if 'recurrence' in body and body['recurrence']:
                rrule_str = body['recurrence'][0].replace('RRULE:', '')

            if not all([event_id, start_date, end_date]): return None

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
            error_message = f"로컬 이벤트 추가 중 오류가 발생했습니다: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return None

    def update_event(self, event_data, data_manager=None):
        return self.add_event(event_data, data_manager)

    def delete_event(self, event_data, data_manager=None):
        try:
            event_id = event_data.get('body', {}).get('id') or event_data.get('id')
            if not event_id:
                error_message = "삭제할 로컬 이벤트의 ID를 찾을 수 없습니다."
                if data_manager: data_manager.report_error(error_message)
                else: print(error_message)
                return False

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"Local Provider: 이벤트 삭제 성공 (ID: {event_id})")
                    return True
                else:
                    # 이미 삭제된 경우일 수 있으므로 사용자에게 오류를 표시하지는 않음
                    print(f"Local Provider: 삭제할 이벤트를 찾지 못함 (ID: {event_id})")
                    return False
        except sqlite3.Error as e:
            error_message = f"로컬 이벤트 삭제 중 DB 오류가 발생했습니다: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return False

    def get_calendars(self):
        return [{
            'id': LOCAL_CALENDAR_ID,
            'summary': '로컬 캘린더',
            'backgroundColor': self.settings.get("local_calendar_color", DEFAULT_LOCAL_CALENDAR_COLOR),
            'provider': LOCAL_CALENDAR_PROVIDER_NAME
        }]

    def search_events(self, query, data_manager=None):
        if not query: return []
        
        search_term = f"%{query}%"
        found_events = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event_json FROM events
                    WHERE event_json LIKE ? OR event_json LIKE ?
                """, (f'%summary":"%{search_term}%', f'%description":"%{search_term}%'))

                for row in cursor.fetchall():
                    event = json.loads(row[0])
                    found_events.append(event)

            for event in found_events:
                event['provider'] = LOCAL_CALENDAR_PROVIDER_NAME
                event['calendarId'] = LOCAL_CALENDAR_ID
            
            return found_events
        except sqlite3.Error as e:
            error_message = f"로컬 이벤트 검색 중 DB 오류가 발생했습니다: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return []