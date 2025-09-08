# error_constants.py
"""
예외 처리를 위한 상수 및 에러 메시지 정의
사용자 친화적이고 일관된 오류 메시지 제공
"""

# 파일 I/O 관련 오류 메시지
class FileErrors:
    FILE_NOT_FOUND = "파일을 찾을 수 없습니다"
    PERMISSION_DENIED = "파일에 대한 권한이 없습니다"
    FILE_CORRUPTED = "파일이 손상되어 읽을 수 없습니다"
    DISK_FULL = "디스크 공간이 부족합니다"
    FILE_IN_USE = "파일이 다른 프로그램에서 사용 중입니다"
    INVALID_PATH = "파일 경로가 잘못되었습니다"
    
    @staticmethod
    def get_file_error_message(error_type: str, file_path: str = "", suggestion: str = "") -> str:
        """파일 오류에 대한 상세한 사용자 메시지를 생성합니다."""
        base_messages = {
            'FileNotFoundError': f"{FileErrors.FILE_NOT_FOUND}: {file_path}",
            'PermissionError': f"{FileErrors.PERMISSION_DENIED}: {file_path}",
            'OSError': f"파일 시스템 오류가 발생했습니다: {file_path}",
            'json.JSONDecodeError': f"{FileErrors.FILE_CORRUPTED}: {file_path}"
        }
        
        message = base_messages.get(error_type, f"파일 처리 중 오류가 발생했습니다: {file_path}")
        
        if suggestion:
            message += f"\n\n해결 방법: {suggestion}"
        
        return message

# 네트워크 관련 오류 메시지
class NetworkErrors:
    CONNECTION_FAILED = "인터넷 연결을 확인해주세요"
    TIMEOUT = "서버 응답 시간이 초과되었습니다"
    SERVER_ERROR = "서버에서 오류가 발생했습니다"
    AUTHENTICATION_FAILED = "인증에 실패했습니다"
    ACCESS_DENIED = "접근 권한이 없습니다"
    SERVICE_UNAVAILABLE = "서비스를 일시적으로 사용할 수 없습니다"
    
    @staticmethod
    def get_network_error_message(error_type: str, service: str = "", suggestion: str = "") -> str:
        """네트워크 오류에 대한 상세한 사용자 메시지를 생성합니다."""
        base_messages = {
            'ConnectionError': f"{NetworkErrors.CONNECTION_FAILED}",
            'Timeout': f"{NetworkErrors.TIMEOUT}",
            'HttpError_401': f"{NetworkErrors.AUTHENTICATION_FAILED}",
            'HttpError_403': f"{NetworkErrors.ACCESS_DENIED}",
            'HttpError_500': f"{NetworkErrors.SERVER_ERROR}",
            'HttpError_503': f"{NetworkErrors.SERVICE_UNAVAILABLE}"
        }
        
        message = base_messages.get(error_type, f"네트워크 오류가 발생했습니다")
        
        if service:
            message += f" ({service})"
        
        if suggestion:
            message += f"\n\n해결 방법: {suggestion}"
            
        return message

# 데이터베이스 관련 오류 메시지  
class DatabaseErrors:
    CONNECTION_FAILED = "데이터베이스 연결에 실패했습니다"
    DATA_CORRUPTED = "데이터베이스가 손상되었습니다"
    DISK_FULL = "데이터베이스 저장 공간이 부족합니다"
    CONSTRAINT_VIOLATION = "데이터 제약 조건 위반입니다"
    TRANSACTION_FAILED = "데이터베이스 작업이 실패했습니다"
    
    @staticmethod
    def get_database_error_message(error_type: str, operation: str = "", suggestion: str = "") -> str:
        """데이터베이스 오류에 대한 상세한 사용자 메시지를 생성합니다."""
        base_messages = {
            'sqlite3.Error': f"{DatabaseErrors.CONNECTION_FAILED}",
            'sqlite3.IntegrityError': f"{DatabaseErrors.CONSTRAINT_VIOLATION}",
            'sqlite3.OperationalError': f"{DatabaseErrors.DATA_CORRUPTED}",
            'sqlite3.DatabaseError': f"{DatabaseErrors.TRANSACTION_FAILED}"
        }
        
        message = base_messages.get(error_type, f"데이터베이스 오류가 발생했습니다")
        
        if operation:
            message += f" ({operation} 작업 중)"
        
        if suggestion:
            message += f"\n\n해결 방법: {suggestion}"
            
        return message

# 인증 관련 오류 메시지
class AuthErrors:
    LOGIN_FAILED = "로그인에 실패했습니다"
    TOKEN_EXPIRED = "인증이 만료되었습니다. 다시 로그인해주세요"
    CREDENTIALS_MISSING = "인증 정보가 없습니다"
    INVALID_CREDENTIALS = "인증 정보가 잘못되었습니다"
    REFRESH_FAILED = "인증 갱신에 실패했습니다"
    
    @staticmethod
    def get_auth_error_message(error_type: str, suggestion: str = "") -> str:
        """인증 오류에 대한 상세한 사용자 메시지를 생성합니다."""
        base_messages = {
            'RefreshError': f"{AuthErrors.TOKEN_EXPIRED}",
            'GoogleAuthError': f"{AuthErrors.LOGIN_FAILED}",
            'ValueError': f"{AuthErrors.INVALID_CREDENTIALS}",
        }
        
        message = base_messages.get(error_type, f"인증 중 오류가 발생했습니다")
        
        if suggestion:
            message += f"\n\n해결 방법: {suggestion}"
        else:
            message += "\n\n해결 방법: 설정에서 다시 로그인을 시도해주세요"
            
        return message

# 데이터 파싱 관련 오류 메시지
class DataErrors:
    INVALID_FORMAT = "데이터 형식이 잘못되었습니다"
    PARSING_FAILED = "데이터 파싱에 실패했습니다"
    VALIDATION_FAILED = "데이터 검증에 실패했습니다"
    CONVERSION_FAILED = "데이터 변환에 실패했습니다"
    
    @staticmethod
    def get_data_error_message(error_type: str, data_type: str = "", suggestion: str = "") -> str:
        """데이터 처리 오류에 대한 상세한 사용자 메시지를 생성합니다."""
        base_messages = {
            'json.JSONDecodeError': f"{DataErrors.INVALID_FORMAT} (JSON)",
            'ValueError': f"{DataErrors.PARSING_FAILED}",
            'TypeError': f"{DataErrors.CONVERSION_FAILED}",
            'KeyError': f"필요한 데이터가 없습니다"
        }
        
        message = base_messages.get(error_type, f"데이터 처리 중 오류가 발생했습니다")
        
        if data_type:
            message += f" ({data_type})"
        
        if suggestion:
            message += f"\n\n해결 방법: {suggestion}"
            
        return message

# UI 관련 오류 메시지
class UIErrors:
    DIALOG_CREATION_FAILED = "대화상자를 생성할 수 없습니다"
    WIDGET_INITIALIZATION_FAILED = "UI 구성요소 초기화에 실패했습니다"
    THEME_LOAD_FAILED = "테마를 불러올 수 없습니다"
    RESOURCE_MISSING = "UI 리소스가 없습니다"
    
    @staticmethod
    def get_ui_error_message(error_type: str, component: str = "", suggestion: str = "") -> str:
        """UI 오류에 대한 상세한 사용자 메시지를 생성합니다."""
        base_messages = {
            'RuntimeError': f"{UIErrors.WIDGET_INITIALIZATION_FAILED}",
            'FileNotFoundError': f"{UIErrors.RESOURCE_MISSING}",
            'ValueError': f"UI 설정 값이 잘못되었습니다"
        }
        
        message = base_messages.get(error_type, f"UI 오류가 발생했습니다")
        
        if component:
            message += f" ({component})"
        
        if suggestion:
            message += f"\n\n해결 방법: {suggestion}"
        else:
            message += "\n\n해결 방법: 프로그램을 재시작하거나 설정을 초기화해주세요"
            
        return message

# 공통 해결 방법 제안
class CommonSuggestions:
    RESTART_PROGRAM = "프로그램을 재시작해보세요"
    CHECK_INTERNET = "인터넷 연결을 확인해주세요"
    CHECK_PERMISSIONS = "파일/폴더 권한을 확인해주세요"
    FREE_DISK_SPACE = "디스크 여유 공간을 확보해주세요"
    UPDATE_PROGRAM = "프로그램을 최신 버전으로 업데이트해주세요"
    CONTACT_SUPPORT = "문제가 지속되면 지원팀에 문의해주세요"
    RESET_SETTINGS = "설정을 초기화해보세요"
    RELOGIN = "로그아웃 후 다시 로그인해주세요"