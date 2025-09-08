# constants/text_constants.py
"""
UI 텍스트 상수 정의
모든 사용자 인터페이스 문자열을 중앙에서 관리
다국어 지원을 위한 기반 구조
"""

# ============================================================================
# 일반 UI 텍스트
# ============================================================================
class GeneralText:
    # 기본 액션
    OK = "확인"
    CANCEL = "취소"
    SAVE = "저장"
    DELETE = "삭제"
    EDIT = "편집"
    ADD = "추가"
    REMOVE = "제거"
    CLOSE = "닫기"
    APPLY = "적용"
    RESET = "초기화"
    
    # 상태
    SUCCESS = "성공"
    ERROR = "오류"
    WARNING = "경고"
    INFO = "정보"
    LOADING = "로딩 중..."
    COMPLETED = "완료"
    FAILED = "실패"
    
    # 진행 상태
    REOPEN = "진행"
    
    # 일반적인 단어
    YES = "예"
    NO = "아니오"
    NONE = "없음"
    ALL = "전체"
    SELECT = "선택"
    DESELECT = "선택 해제"


# ============================================================================
# 메뉴 및 네비게이션 텍스트
# ============================================================================
class MenuText:
    # 메인 메뉴
    FILE = "파일"
    EDIT = "편집"
    VIEW = "보기"
    TOOLS = "도구"
    HELP = "도움말"
    
    # 서브 메뉴
    NEW = "새로 만들기"
    OPEN = "열기"
    SAVE_AS = "다른 이름으로 저장"
    EXPORT = "내보내기"
    IMPORT = "가져오기"
    PREFERENCES = "환경설정"
    EXIT = "종료"
    
    # 보기 메뉴
    MONTH_VIEW = "월간 보기"
    WEEK_VIEW = "주간 보기"
    DAY_VIEW = "일간 보기"
    AGENDA_VIEW = "일정 보기"


# ============================================================================
# 캘린더 특화 텍스트
# ============================================================================
class CalendarText:
    # 월 이름
    MONTHS = [
        "1월", "2월", "3월", "4월", "5월", "6월",
        "7월", "8월", "9월", "10월", "11월", "12월"
    ]
    
    # 요일 이름 (짧은 형태)
    WEEKDAYS_SHORT = ["일", "월", "화", "수", "목", "금", "토"]
    
    # 요일 이름 (긴 형태)
    WEEKDAYS_LONG = [
        "일요일", "월요일", "화요일", "수요일", 
        "목요일", "금요일", "토요일"
    ]
    
    # 캘린더 액션
    TODAY = "오늘"
    PREVIOUS = "이전"
    NEXT = "다음"
    GOTO = "이동"
    
    # 이벤트 관련
    EVENT = "일정"
    EVENTS = "일정들"
    NEW_EVENT = "새 일정"
    EDIT_EVENT = "일정 편집"
    DELETE_EVENT = "일정 삭제"
    DUPLICATE_EVENT = "일정 복제"
    
    # 시간 관련
    ALL_DAY = "하루 종일"
    START_TIME = "시작 시간"
    END_TIME = "종료 시간"
    DURATION = "기간"
    
    # 반복 관련
    REPEAT = "반복"
    NO_REPEAT = "반복 안 함"
    DAILY = "매일"
    WEEKLY = "매주"
    MONTHLY = "매월"
    YEARLY = "매년"
    CUSTOM = "사용자 정의"
    
    # 월간뷰 전용
    DAYS_OF_WEEK = ["월", "화", "수", "목", "금", "토", "일"]  # 월요일 시작
    YEAR_MONTH_FORMAT = "{year}년 {month}월"
    MORE_EVENTS_FORMAT = "+ {count}개 더보기"
    NO_TITLE = "제목 없음"
    
    # 컨텍스트 메뉴
    CONTEXT_EDIT = "수정"
    CONTEXT_REOPEN = "진행"
    CONTEXT_COMPLETE = "완료"
    CONTEXT_DELETE = "삭제"
    CONTEXT_ADD_EVENT = "일정 추가"
    
    # 반복 주기별 텍스트 (간격 포함)
    YEARLY_SINGLE = "매년"
    MONTHLY_SINGLE = "매월"
    WEEKLY_SINGLE = "매주"
    DAILY_SINGLE = "매일"
    
    # 주차별 위치
    WEEK_POSITIONS = {
        1: "첫째 주",
        2: "둘째 주", 
        3: "셋째 주",
        4: "넷째 주",
        -1: "마지막 주"
    }
    
    # 반복 종료 조건
    UNTIL_DATE = "까지"
    COUNT_TIMES = "회"


# ============================================================================
# 설정 관련 텍스트
# ============================================================================
class SettingsText:
    # 설정 카테고리
    GENERAL = "일반"
    APPEARANCE = "모양"
    CALENDAR = "캘린더"
    NOTIFICATIONS = "알림"
    ADVANCED = "고급"
    ABOUT = "정보"
    
    # 일반 설정
    LANGUAGE = "언어"
    TIMEZONE = "시간대"
    START_WITH_SYSTEM = "시스템과 함께 시작"
    MINIMIZE_TO_TRAY = "트레이로 최소화"
    
    # 모양 설정
    THEME = "테마"
    LIGHT_THEME = "밝은 테마"
    DARK_THEME = "어두운 테마"
    OPACITY = "투명도"
    FONT_SIZE = "글꼴 크기"
    
    # 캘린더 설정
    FIRST_DAY_OF_WEEK = "한 주의 시작일"
    SHOW_WEEKENDS = "주말 표시"
    DEFAULT_VIEW = "기본 보기"
    SYNC_INTERVAL = "동기화 간격"
    
    # 알림 설정
    ENABLE_NOTIFICATIONS = "알림 사용"
    NOTIFICATION_TIME = "알림 시간"
    SOUND_ENABLED = "소리 사용"
    POPUP_ENABLED = "팝업 사용"


# ============================================================================
# 에러 메시지
# ============================================================================
class ErrorMessages:
    # 일반 에러
    UNKNOWN_ERROR = "알 수 없는 오류가 발생했습니다."
    OPERATION_FAILED = "작업을 완료할 수 없습니다."
    PERMISSION_DENIED = "권한이 없습니다."
    
    # 파일 관련 에러
    FILE_NOT_FOUND = "파일을 찾을 수 없습니다."
    FILE_SAVE_ERROR = "파일을 저장할 수 없습니다."
    FILE_LOAD_ERROR = "파일을 불러올 수 없습니다."
    
    # 네트워크 관련 에러
    CONNECTION_ERROR = "연결에 실패했습니다."
    NETWORK_TIMEOUT = "네트워크 응답 시간이 초과되었습니다."
    SERVER_ERROR = "서버 오류가 발생했습니다."
    
    # 데이터 관련 에러
    INVALID_DATA = "잘못된 데이터입니다."
    DATA_CORRUPTION = "데이터가 손상되었습니다."
    SYNC_ERROR = "동기화에 실패했습니다."
    
    # 캘린더 특화 에러
    EVENT_SAVE_ERROR = "일정을 저장할 수 없습니다."
    EVENT_DELETE_ERROR = "일정을 삭제할 수 없습니다."
    CALENDAR_LOAD_ERROR = "캘린더를 불러올 수 없습니다."
    
    # 시간 관련 에러
    TIME_ERROR_TITLE = "시간 오류"
    END_BEFORE_START = "끝나는 시각이 시작 시각보다 빠를 수 없습니다."


# ============================================================================
# 성공 메시지
# ============================================================================
class SuccessMessages:
    # 일반 성공
    OPERATION_COMPLETED = "작업이 완료되었습니다."
    SAVE_SUCCESSFUL = "성공적으로 저장되었습니다."
    DELETE_SUCCESSFUL = "성공적으로 삭제되었습니다."
    
    # 캘린더 특화 성공
    EVENT_SAVED = "일정이 저장되었습니다."
    EVENT_DELETED = "일정이 삭제되었습니다."
    SYNC_COMPLETED = "동기화가 완료되었습니다."
    
    # 설정 관련
    SETTINGS_SAVED = "설정이 저장되었습니다."
    THEME_CHANGED = "테마가 변경되었습니다."


# ============================================================================
# 확인 메시지
# ============================================================================
class ConfirmationMessages:
    # 삭제 확인
    CONFIRM_DELETE = "정말로 삭제하시겠습니까?"
    CONFIRM_DELETE_EVENT = "이 일정을 삭제하시겠습니까?"
    CONFIRM_DELETE_ALL = "모든 항목을 삭제하시겠습니까?"
    
    # 변경사항 확인
    UNSAVED_CHANGES = "저장되지 않은 변경사항이 있습니다. 계속하시겠습니까?"
    RESET_SETTINGS = "설정을 초기값으로 되돌리시겠습니까?"
    
    # 종료 확인
    CONFIRM_EXIT = "프로그램을 종료하시겠습니까?"
    CONFIRM_CLOSE = "창을 닫으시겠습니까?"
    
    # 반복 일정 수정 확인
    RECURRING_EVENT_EDIT = "은(는) 반복 일정입니다.\n이 일정을 수정하면 모든 관련 반복 일정이 수정됩니다.\n\n계속하시겠습니까?"


# ============================================================================
# 툴팁 및 도움말 텍스트
# ============================================================================
class TooltipText:
    # 버튼 툴팁
    ADD_EVENT = "새 일정 추가"
    DELETE_EVENT = "선택한 일정 삭제"
    EDIT_EVENT = "일정 편집"
    SETTINGS = "설정 열기"
    
    # 네비게이션 툴팁
    PREVIOUS_MONTH = "이전 달"
    NEXT_MONTH = "다음 달"
    GO_TO_TODAY = "오늘로 이동"
    
    # 뷰 변경 툴팁
    SWITCH_TO_MONTH = "월간 보기로 전환"
    SWITCH_TO_WEEK = "주간 보기로 전환"
    SWITCH_TO_DAY = "일간 보기로 전환"


# ============================================================================
# 이벤트 에디터 특화 텍스트
# ============================================================================
class EventEditorText:
    # 윈도우 제목
    WINDOW_TITLE_NEW = "일정 추가"
    WINDOW_TITLE_EDIT = "일정 수정"
    
    # 필드 레이블
    LABEL_TITLE = "제목:"
    LABEL_CALENDAR = "캘린더:"
    LABEL_START = "시작:"
    LABEL_END = "종료:"
    LABEL_DESCRIPTION = "설명:"
    LABEL_REPEAT = "반복:"
    
    # 체크박스 텍스트
    CHECKBOX_ALL_DAY = "하루 종일"
    CHECKBOX_COMPLETED = "완료"
    
    # 기본 텍스트
    NO_TITLE = "(제목 없음)"
    CALENDAR_LOADING = "캘린더 목록 로딩 중..."
    
    # 삭제 확인 메시지 템플릿
    DELETE_CONFIRM_TEMPLATE = "'{0}' 일정을 정말 삭제하시겠습니까?"
    RECURRING_EDIT_TEMPLATE = "'{0}'{1}"
    
    # 다이얼로그 제목
    DELETE_CONFIRMATION_TITLE = "삭제 확인"
    EDIT_CONFIRMATION_TITLE = "수정 확인"


# ============================================================================
# 다국어 지원 함수
# ============================================================================
def get_text(key: str, language: str = 'ko') -> str:
    """
    언어별 텍스트 반환
    향후 다국어 지원을 위한 기반 함수
    """
    # 현재는 한국어만 지원, 향후 확장 예정
    return key  # 임시 구현


def format_text(template: str, **kwargs) -> str:
    """텍스트 템플릿 포맷팅"""
    return template.format(**kwargs)