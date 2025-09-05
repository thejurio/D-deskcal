# event_detail_texts.py
"""
일정상세창에 사용되는 모든 텍스트를 관리하는 설정 파일
테마와 언어 설정에 따라 다른 텍스트를 제공
"""

# 일정상세창 텍스트 설정
EVENT_DETAIL_TEXTS = {
    # 창 제목
    "window_title": "일정 상세보기",
    
    # 섹션 라벨
    "date_label": "날짜",
    "time_label": "시간",
    "recurrence_label": "반복",
    "description_label": "설명",
    "calendar_label": "캘린더",
    
    # 버튼 텍스트
    "edit_button": "편집",
    "delete_button": "삭제",
    "close_button": "닫기",
    
    # 기본값 텍스트
    "loading_title": "제목을 불러오는 중...",
    "no_title": "제목 없음",
    "all_day": "종일",
    "no_description": "설명 없음",
    "unknown_calendar": "알 수 없는 캘린더",
    
    # 날짜 형식
    "date_format": "%Y년 %m월 %d일",
    "date_range_format": "%Y년 %m월 %d일 ~ %Y년 %m월 %d일",
    "time_format": "%H:%M",
    "time_range_format": "%H:%M ~ %H:%M",
    
    # 요일 목록
    "weekdays": ["월", "화", "수", "목", "금", "토", "일"],
    
    # 캘린더 타입
    "primary_calendar": " (기본)",
    "reader_calendar": " (읽기전용)",
    "writer_calendar": " (편집가능)",
    
    # 삭제 확인 메시지
    "delete_confirm_title": "일정 삭제",
    "delete_confirm_message": "'{event_title}' 일정을 삭제하시겠습니까?",
    
    # 오류 메시지
    "edit_error": "일정 편집 중 오류가 발생했습니다: {error}",
    "delete_error": "일정 삭제 중 오류가 발생했습니다: {error}",
    "load_error": "일정 정보를 불러오는 중 오류가 발생했습니다: {error}"
}

def get_text(key: str, **kwargs) -> str:
    """
    지정된 키에 해당하는 텍스트를 반환합니다.
    
    Args:
        key: 텍스트 키
        **kwargs: 텍스트 포맷팅에 사용할 변수들
    
    Returns:
        포맷팅된 텍스트 문자열
    """
    text = EVENT_DETAIL_TEXTS.get(key, key)
    
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            # 포맷팅 실패 시 원본 텍스트 반환
            pass
    
    return text

def get_weekday_text(weekday_index: int) -> str:
    """
    요일 인덱스에 해당하는 요일 텍스트를 반환합니다.
    
    Args:
        weekday_index: 요일 인덱스 (0=월요일, 6=일요일)
    
    Returns:
        요일 텍스트
    """
    weekdays = EVENT_DETAIL_TEXTS.get("weekdays", ["월", "화", "수", "목", "금", "토", "일"])
    if 0 <= weekday_index < len(weekdays):
        return weekdays[weekday_index]
    return str(weekday_index)