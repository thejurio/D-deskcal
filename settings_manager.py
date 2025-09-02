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

def save_settings_safe(data, preserve_keys=None):
    """
    설정을 안전하게 저장합니다. 지정된 키들은 기존 값을 보존합니다.
    
    Args:
        data: 저장할 설정 데이터
        preserve_keys: 보존할 키들의 리스트 (예: ['dialog_positions'])
    """
    if preserve_keys is None:
        preserve_keys = ['dialog_positions']
    
    # 기존 설정 로드
    existing_settings = load_settings()
    
    # 새 설정으로 업데이트
    existing_settings.update(data)
    
    # 보존할 키들을 기존 설정에서 가져와서 복원
    original_settings = load_settings()
    for key in preserve_keys:
        if key in original_settings:
            existing_settings[key] = original_settings[key]
            print(f"[DEBUG] settings_manager: '{key}' 키 보존됨")
    
    # 저장
    save_settings(existing_settings)