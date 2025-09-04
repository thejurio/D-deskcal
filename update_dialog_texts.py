# update_dialog_texts.py
"""
업데이트 다이얼로그에 사용되는 모든 텍스트를 관리하는 설정 파일
테마와 언어 설정에 따라 다른 텍스트를 제공
"""

# 업데이트 다이얼로그 텍스트 설정
UPDATE_DIALOG_TEXTS = {
    # 업데이트 확인 관련
    "checking_title": "업데이트 확인",
    "checking_message": "업데이트를 확인하는 중...",
    
    # 업데이트 가능
    "available_title": "업데이트 사용 가능",
    "available_message": "새로운 버전 v{version}이 사용 가능합니다.",
    "current_version": "현재 버전: {version}",
    "new_version": "새 버전: {version}",
    "update_question": "지금 업데이트하시겠습니까?",
    "release_notes_title": "릴리스 노트:",
    
    # 업데이트 없음
    "no_update_title": "업데이트 확인",
    "no_update_message": "현재 최신 버전({version})을 사용 중입니다.",
    
    # 업데이트 오류
    "error_title": "업데이트 확인 실패",
    "error_message": "업데이트를 확인할 수 없습니다:\n{error}\n\n인터넷 연결을 확인하고 다시 시도해주세요.",
    "auto_update_unavailable": "자동 업데이트 기능을 사용할 수 없습니다.\n수동으로 업데이트를 확인해주세요.",
    
    # 다운로드 진행
    "download_title": "업데이트 다운로드",
    "downloading_message": "업데이트를 다운로드하고 있습니다...",
    "installing_message": "업데이트를 설치하고 있습니다...",
    "download_progress": "다운로드 중... {percent}%",
    "install_progress": "설치 중...",
    
    # 다운로드/설치 완료
    "complete_title": "업데이트 완료",
    "complete_message": "업데이트가 완료되었습니다.",
    "restart_message": "업데이트 스크립트가 실행되었습니다.\n프로그램이 자동으로 종료되고 새 버전으로 재시작됩니다.",
    
    # 오류 메시지
    "download_error_title": "업데이트 실패",
    "download_error_message": "업데이트 다운로드에 실패했습니다:\n{error}",
    "install_error_title": "설치 실패",
    "install_error_message": "업데이트 설치에 실패했습니다:\n{error}",
    
    # 버튼 텍스트
    "update_button": "업데이트",
    "later_button": "나중에",
    "cancel_button": "취소",
    "ok_button": "확인",
    "close_button": "닫기",
    "details_button": "자세히",
    
    # 기타
    "loading": "로딩 중...",
    "please_wait": "잠시만 기다려주세요...",
    "version_format": "v{version}",
    "size_format": "{size} MB",
    "unknown_size": "크기 알 수 없음",
    
    # 진행 상태
    "preparing": "준비 중...",
    "connecting": "서버에 연결 중...",
    "downloading": "다운로드 중...",
    "extracting": "압축 해제 중...",
    "installing": "설치 중...",
    "finishing": "완료 중...",
    "completed": "완료됨",
    
    # 시간 표시
    "time_remaining": "남은 시간: {time}",
    "download_speed": "다운로드 속도: {speed}/초",
    "eta_unknown": "남은 시간 계산 중...",
}

def get_update_text(key: str, **kwargs) -> str:
    """
    지정된 키에 해당하는 업데이트 텍스트를 반환합니다.
    
    Args:
        key: 텍스트 키
        **kwargs: 텍스트 포맷팅에 사용할 변수들
    
    Returns:
        포맷팅된 텍스트 문자열
    """
    text = UPDATE_DIALOG_TEXTS.get(key, key)
    
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            # 포맷팅 실패 시 원본 텍스트 반환
            pass
    
    return text

def format_version(version: str) -> str:
    """
    버전 문자열을 포맷팅합니다.
    
    Args:
        version: 버전 문자열
    
    Returns:
        포맷팅된 버전 문자열
    """
    return get_update_text("version_format", version=version)

def format_file_size(size_bytes: int) -> str:
    """
    파일 크기를 읽기 쉬운 형태로 포맷팅합니다.
    
    Args:
        size_bytes: 바이트 단위 크기
    
    Returns:
        포맷팅된 크기 문자열
    """
    if size_bytes <= 0:
        return get_update_text("unknown_size")
    
    # MB 단위로 변환
    size_mb = round(size_bytes / (1024 * 1024), 1)
    return get_update_text("size_format", size=size_mb)