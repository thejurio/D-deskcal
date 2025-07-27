import sqlite3
import json

DB_FILE = "calendar.db"

def init_db():
    """데이터베이스와 events 테이블을 생성합니다. (없을 경우에만)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 이벤트 데이터를 JSON 텍스트 형태로 저장할 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_cached_events():
    """캐시된 이벤트 목록을 데이터베이스에서 불러옵니다."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT event_data FROM events")
        # 저장된 JSON 텍스트를 다시 파이썬 딕셔너리로 변환
        events = [json.loads(row[0]) for row in cursor.fetchall()]
        conn.close()
        return events
    except sqlite3.Error:
        return [] # 오류 발생 시 빈 리스트 반환

def update_cache(events):
    """새로운 이벤트 목록으로 캐시를 업데이트합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 기존 캐시를 모두 삭제
    cursor.execute("DELETE FROM events")
    # 새로운 이벤트 목록을 저장 (파이썬 딕셔너리를 JSON 텍스트로 변환)
    for event in events:
        cursor.execute("INSERT INTO events (event_data) VALUES (?)", (json.dumps(event),))
    conn.commit()
    conn.close()