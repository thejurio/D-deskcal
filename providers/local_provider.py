import sqlite3
import json
import datetime
from .base_provider import BaseCalendarProvider
from config import (DB_FILE, LOCAL_CALENDAR_ID, LOCAL_CALENDAR_PROVIDER_NAME,
                    DEFAULT_LOCAL_CALENDAR_COLOR, DEFAULT_LOCAL_CALENDAR_EMOJI)

class LocalCalendarProvider(BaseCalendarProvider):
    def __init__(self, settings):
        self.settings = settings
        self._init_db()

    def _init_db(self):
        """데이터베이스와 events 테이블을 생성합니다. (없을 경우에만)"""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                # Google Calendar API와 유사한 구조로 이벤트를 저장할 테이블
                # event_json 필드에 이벤트 정보를 JSON 텍스트로 저장합니다.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        event_json TEXT NOT NULL
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            print(f"로컬 DB 초기화 중 오류 발생: {e}")

    # providers/local_provider.py 파일입니다.

    def get_events(self, start_date, end_date):
        """특정 기간 사이의 로컬 이벤트를 반환합니다."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT event_json FROM events
                    WHERE start_date <= ? AND end_date >= ?
                """, (end_date.isoformat(), start_date.isoformat()))

                events = [json.loads(row[0]) for row in cursor.fetchall()]

                # --- ▼▼▼ 여기가 수정된 핵심입니다 ▼▼▼ ---
                # 설정에 저장된 calendar_colors와 calendar_emojis 딕셔너리를 가져옵니다.
                calendar_colors = self.settings.get("calendar_colors", {})
                calendar_emojis = self.settings.get("calendar_emojis", {})
                
                for event in events:
                    event['calendarId'] = LOCAL_CALENDAR_ID
                    # 'local_calendar' ID를 키로 사용하여 설정된 색상과 이모티콘을 가져옵니다.
                    # 만약 설정된 값이 없으면, 기본값을 사용합니다.
                    event['color'] = calendar_colors.get(LOCAL_CALENDAR_ID, DEFAULT_LOCAL_CALENDAR_COLOR)
                    event['emoji'] = calendar_emojis.get(LOCAL_CALENDAR_ID, DEFAULT_LOCAL_CALENDAR_EMOJI)
                # --- ▲▲▲ 여기까지가 수정된 핵심입니다 ▲▲▲ ---
                
                return events
        except sqlite3.Error as e:
            print(f"로컬 이벤트 조회 중 오류 발생: {e}")
            return []

# providers/local_provider.py 파일입니다.

    def add_event(self, event_data):
        """새로운 로컬 이벤트를 DB에 추가하고, 추가된 이벤트 객체를 반환합니다."""
        try:
            body = event_data.get('body')
            if not body:
                return None

            event_id = body.get('id')
            start_date = body.get('start', {}).get('date') or body.get('start', {}).get('dateTime', '')[:10]
            end_date = body.get('end', {}).get('date') or body.get('end', {}).get('dateTime', '')[:10]
            
            if not all([event_id, start_date, end_date]):
                return None

            body['provider'] = LOCAL_CALENDAR_PROVIDER_NAME
            body['calendarId'] = LOCAL_CALENDAR_ID

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO events (id, start_date, end_date, event_json)
                    VALUES (?, ?, ?, ?)
                """, (event_id, start_date, end_date, json.dumps(body)))
                conn.commit()
            
            # DataManager와의 일관성을 위해 저장된 이벤트 본문을 반환
            return body
        except (sqlite3.Error, KeyError) as e:
            print(f"로컬 이벤트 추가 중 오류 발생: {e}")
            return None

    def update_event(self, event_data):
        """기존 로컬 이벤트를 수정하고, 수정된 이벤트 객체를 반환합니다."""
        # INSERT OR REPLACE를 사용하므로 add_event와 로직이 동일합니다.
        return self.add_event(event_data)

    def delete_event(self, event_data):
        """기존 로컬 이벤트를 삭제합니다."""
        try:
            # event_data 딕셔너리에서 실제 이벤트 ID를 추출합니다.
            event_id = event_data.get('body', {}).get('id') or event_data.get('id')
            if not event_id:
                print("삭제할 이벤트의 ID를 찾을 수 없습니다.")
                return False

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
                conn.commit()
                # 실제로 삭제가 일어났는지 확인
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