import sqlite3
import json
import datetime
from .base_provider import BaseCalendarProvider

DB_FILE = "calendar.db"

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
                    event['calendarId'] = 'local_calendar'
                    # 'local_calendar' ID를 키로 사용하여 설정된 색상과 이모티콘을 가져옵니다.
                    # 만약 설정된 값이 없으면, 기본값을 사용합니다.
                    event['color'] = calendar_colors.get('local_calendar', "#4CAF50")
                    event['emoji'] = calendar_emojis.get('local_calendar', '💻')
                # --- ▲▲▲ 여기까지가 수정된 핵심입니다 ▲▲▲ ---
                
                return events
        except sqlite3.Error as e:
            print(f"로컬 이벤트 조회 중 오류 발생: {e}")
            return []

# providers/local_provider.py 파일입니다.

    def add_event(self, event_data):
        """새로운 로컬 이벤트를 DB에 추가합니다."""
        try:
            body = event_data['body']
            event_id = body['id']
            start_date = body['start'].get('date') or body['start'].get('dateTime')[:10]
            end_date = body['end'].get('date') or body['end'].get('dateTime')[:10]
            
            # 나중에 구글 이벤트와 구별하기 위해 provider 정보를 추가합니다.
            body['provider'] = 'LocalCalendarProvider'

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                # INSERT OR REPLACE는 id가 이미 존재하면 UPDATE처럼 동작합니다.
                cursor.execute("""
                    INSERT OR REPLACE INTO events (id, start_date, end_date, event_json)
                    VALUES (?, ?, ?, ?)
                """, (event_id, start_date, end_date, json.dumps(body)))
                conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"로컬 이벤트 추가 중 오류 발생: {e}")
            return False

    def update_event(self, event_id, event_data):
        """기존 로컬 이벤트를 수정합니다."""
        # INSERT OR REPLACE를 사용하므로 add_event와 로직이 동일합니다.
        return self.add_event(event_data)

    def delete_event(self, event_id):
        """기존 로컬 이벤트를 삭제합니다."""
        # TODO: 다음 단계에서 구현
        print(f"Local Provider: 이벤트 삭제 (ID: {event_id})")
        pass

    def get_calendars(self):
        """'로컬 캘린더' 자체에 대한 정보를 표준 형식으로 반환합니다."""
        return [{
            'id': 'local_calendar',  # 로컬 캘린더를 위한 고유 ID
            'summary': '로컬 캘린더',
            # 설정에 저장된 색상 또는 기본 색상을 사용합니다.
            'backgroundColor': self.settings.get("local_calendar_color", "#4CAF50"),
            'provider': 'LocalCalendarProvider'
        }]