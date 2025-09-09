# local_provider.py 파일의 모든 내용을 이 코드로 교체하세요.

import sqlite3
import json
import datetime
import logging
from dateutil.rrule import rrulestr
from datetime import timezone

from .base_provider import BaseCalendarProvider
from config import (LOCAL_CALENDAR_ID, LOCAL_CALENDAR_PROVIDER_NAME,
                    DEFAULT_LOCAL_CALENDAR_COLOR)
from db_manager import get_db_manager

logger = logging.getLogger(__name__)

def safe_json_dumps(obj):
    """Safely convert objects to JSON, handling datetime objects"""
    def json_serializer(obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.isoformat()
        elif hasattr(obj, 'zone') and hasattr(obj.zone, 'zone'):  # Handle timezone info
            return str(obj)
        raise TypeError(f"Object {obj} of type {type(obj)} is not JSON serializable")
    
    try:
        return json.dumps(obj, default=json_serializer, ensure_ascii=False)
    except Exception as e:
        logger.error(f"JSON 직렬화 실패: {e}, object: {type(obj)}")
        return json.dumps({"error": "serialization_failed", "type": str(type(obj))})

class LocalCalendarProvider(BaseCalendarProvider):
    def __init__(self, settings, db_connection=None):
        self.settings = settings
        self._connection = db_connection
        self.name = LOCAL_CALENDAR_PROVIDER_NAME
        self.db_manager = get_db_manager()
        # Migrate existing data if needed
        self.db_manager.migrate_existing_data()

    def _get_connection(self):
        if self._connection:
            return self._connection
        # Return a context manager for database operations
        return self.db_manager.get_local_connection()

    def get_events(self, start_date, end_date, data_manager=None):
        final_events = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT original_event_id, exception_date FROM event_exceptions")
                exceptions = {org_id: set() for org_id, _ in cursor.fetchall()}
                cursor.execute("SELECT original_event_id, exception_date FROM event_exceptions")
                for org_id, ex_date_str in cursor.fetchall():
                    exceptions[org_id].add(ex_date_str)

                cursor.execute("""
                    SELECT event_json, rrule FROM local_events
                    WHERE (rrule IS NULL AND start_date <= ? AND end_date >= ?) OR rrule IS NOT NULL
                """, (end_date.isoformat(), start_date.isoformat()))

                for event_json, rrule_str in cursor.fetchall():
                    event_template = json.loads(event_json)
                    if rrule_str:
                        try:
                            start_str = event_template['start'].get('dateTime', event_template['start'].get('date'))
                            end_str = event_template['end'].get('dateTime', event_template['end'].get('date'))
                            is_all_day = 'date' in event_template['start']
                            
                            aware_start = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                            aware_end = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                            duration = aware_end - aware_start
                            
                            # RRULE 파싱을 위해 naive datetime 사용 (시간대 문제 해결)
                            dtstart_for_rule = aware_start.replace(tzinfo=None)
                            
                            # RRULE 문자열에서 UNTIL 값을 naive로 변환
                            modified_rrule = self._convert_rrule_until_to_naive(rrule_str, aware_start.tzinfo)
                            
                            rule = rrulestr(f"RRULE:{modified_rrule}", dtstart=dtstart_for_rule)
                            view_start_dt = datetime.datetime.combine(start_date, datetime.time.min)
                            view_end_dt = datetime.datetime.combine(end_date, datetime.time.max)

                            for occurrence_start_naive in rule.between(view_start_dt, view_end_dt, inc=True):
                                original_tz = aware_start.tzinfo
                                occurrence_start = occurrence_start_naive.replace(tzinfo=original_tz) if original_tz else occurrence_start_naive
                                
                                original_id_check = event_template['id']
                                if original_id_check in exceptions and occurrence_start.isoformat() in exceptions[original_id_check]:
                                    continue
                                    
                                instance_event = json.loads(event_json)
                                occurrence_end = occurrence_start + duration
                                occurrence_id_str = occurrence_start.strftime('%Y%m%dT%H%M%S')
                                instance_event['id'] = f"{event_template['id']}_{occurrence_id_str}"
                                instance_event['originalId'] = event_template['id']

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
            rrule_str = body.get('recurrence', [None])[0].replace('RRULE:', '') if 'recurrence' in body and body['recurrence'] else None
            if not all([event_id, start_date, end_date]): return None
            body['provider'] = LOCAL_CALENDAR_PROVIDER_NAME
            body['calendarId'] = LOCAL_CALENDAR_ID
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO local_events (id, start_date, end_date, rrule, event_json) VALUES (?, ?, ?, ?, ?)",
                               (event_id, start_date, end_date, rrule_str, safe_json_dumps(body)))
                conn.commit()
            return body
        except (sqlite3.Error, KeyError) as e:
            error_message = f"로컬 이벤트 추가 중 오류가 발생했습니다: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return None

    def update_event(self, event_data, data_manager=None):
        return self.add_event(event_data, data_manager)

    def delete_event(self, event_data, data_manager=None, deletion_mode='all'):
        try:
            event_body = event_data.get('body', event_data)
            event_summary = event_body.get('summary', 'No summary')
            print(f"DEBUG: LocalProvider.delete_event called for: {event_summary}")
            print(f"DEBUG: deletion_mode: {deletion_mode}")
            
            instance_id = event_body.get('id')
            print(f"DEBUG: instance_id: {instance_id}")
            if not instance_id: 
                print("DEBUG: No instance_id found")
                return False
            original_id = instance_id.split('_')[0]
            print(f"DEBUG: original_id: {original_id}")
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if deletion_mode == 'all':
                    print(f"DEBUG: Deleting all instances of event {original_id}")
                    cursor.execute("DELETE FROM local_events WHERE id = ?", (original_id,))
                    deleted_count = cursor.rowcount
                    print(f"DEBUG: Deleted {deleted_count} events from local_events table")
                    cursor.execute("DELETE FROM event_exceptions WHERE original_event_id = ?", (original_id,))
                    exceptions_deleted = cursor.rowcount
                    print(f"DEBUG: Deleted {exceptions_deleted} exceptions")
                elif deletion_mode == 'instance':
                    start_str = event_body['start'].get('dateTime') or event_body['start'].get('date')
                    aware_start = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    cursor.execute("INSERT OR IGNORE INTO event_exceptions (original_event_id, exception_date) VALUES (?, ?)",
                                   (original_id, aware_start.isoformat()))
                elif deletion_mode == 'future':
                    cursor.execute("SELECT rrule FROM local_events WHERE id = ?", (original_id,))
                    result = cursor.fetchone()
                    if not result: return False
                    rrule_str = result[0]
                    start_str = event_body['start'].get('dateTime') or event_body['start'].get('date')
                    aware_start = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    naive_start = aware_start.replace(tzinfo=None)
                    until_dt_naive = naive_start - datetime.timedelta(days=1)
                    until_str = until_dt_naive.strftime('%Y%m%dT%H%M%S')
                    parts = [p for p in rrule_str.split(';') if not p.startswith('UNTIL=') and not p.startswith('COUNT=')]
                    parts.append(f'UNTIL={until_str}')
                    new_rrule = ';'.join(parts)
                    cursor.execute("UPDATE local_events SET rrule = ? WHERE id = ?", (new_rrule, original_id))
                conn.commit()
                print(f"DEBUG: Successfully committed local event deletion")
            return True
        except sqlite3.Error as e:
            print(f"DEBUG: SQLite error in delete_event: {e}")
            error_message = f"로컬 이벤트 삭제 중 DB 오류가 발생했습니다: {e}"
            if data_manager: data_manager.report_error(error_message)
            else: print(error_message)
            return False
        except Exception as e:
            print(f"DEBUG: General exception in LocalProvider.delete_event: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_calendars(self):
        return [{'id': LOCAL_CALENDAR_ID, 'summary': '로컬 캘린더',
                 'backgroundColor': self.settings.get("local_calendar_color", DEFAULT_LOCAL_CALENDAR_COLOR),
                 'provider': LOCAL_CALENDAR_PROVIDER_NAME}]

    def search_events(self, query, data_manager=None):
        if not query: return []
        search_term = f"%{query}%"
        found_events = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event_json FROM local_events WHERE event_json LIKE ? OR event_json LIKE ?",
                               (f'%summary":"%{search_term}%', f'%description":"%{search_term}%'))
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
    
    def _convert_rrule_until_to_naive(self, rrule_str, original_tz):
        """RRULE 문자열의 UNTIL 값을 naive datetime으로 변환하여 시간대 충돌 방지"""
        if 'UNTIL=' not in rrule_str:
            return rrule_str
        
        try:
            parts = rrule_str.split(';')
            new_parts = []
            
            for part in parts:
                if part.startswith('UNTIL='):
                    until_str = part.split('=')[1]
                    
                    # UTC 시간을 파싱 (예: 20251206T235959Z)
                    if until_str.endswith('Z'):
                        # UTC 시간을 naive datetime으로 변환
                        naive_until_str = until_str[:-1]  # 'Z' 제거
                        new_parts.append(f'UNTIL={naive_until_str}')
                    else:
                        # 이미 naive 형식이면 그대로 유지
                        new_parts.append(part)
                else:
                    new_parts.append(part)
            
            return ';'.join(new_parts)
            
        except Exception as e:
            # 변환 실패 시 원본 반환 (다른 오류 방지)
            print(f"RRULE UNTIL 변환 실패: {e}")
            return rrule_str