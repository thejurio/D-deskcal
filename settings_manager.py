import json
import os
from config import SETTINGS_FILE

def load_settings():
    """설정 파일(settings.json)을 읽어와서 딕셔너리로 반환합니다."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {} # 파일이 손상되었을 경우 빈 딕셔너리 반환
    return {} # 파일이 없을 경우 빈 딕셔너리 반환

def save_settings(data):
    """설정 데이터(딕셔너리)를 settings.json 파일에 저장합니다."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)