# custom_update_dialogs.py
"""
커스텀 업데이트 다이얼로그들
BaseDialog를 상속하여 다른 다이얼로그와 통일된 UI 제공
모든 스타일은 테마 파일에서 관리
"""

from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QWidget, QProgressBar, QTextEdit, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from custom_dialogs import BaseDialog
from update_dialog_texts import get_update_text


class UpdateAvailableDialog(BaseDialog):
    """업데이트 가능 알림 다이얼로그"""
    
    # 시그널 정의
    update_requested = pyqtSignal()
    update_cancelled = pyqtSignal()
    
    def __init__(self, release_data, current_version, parent=None, settings=None):
        super().__init__(parent=parent, settings=settings)
        
        self.release_data = release_data
        self.current_version = current_version
        self.new_version = release_data.get('tag_name', '').lstrip('v')
        
        self.setWindowTitle(get_update_text("available_title"))
        self.setModal(True)
        self.setFixedSize(500, 600)
        
        # 업데이트 다이얼로그는 높은 우선순위로 표시
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.init_ui()
        self.load_release_data()
    
    def init_ui(self):
        """UI 초기화"""
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 위젯
        background_widget = QWidget()
        background_widget.setObjectName("update_background")
        main_layout.addWidget(background_widget)
        
        # 컨텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 다이얼로그 오브젝트 이름 설정
        self.setObjectName("update_dialog")
        
        # 제목
        self.title_label = QLabel(get_update_text("available_title"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("update_title")
        content_layout.addWidget(self.title_label)
        
        # 버전 정보
        version_layout = QVBoxLayout()
        version_layout.setSpacing(8)
        
        # 새 버전
        self.new_version_label = QLabel(get_update_text("new_version", version=self.new_version))
        self.new_version_label.setObjectName("update_version")
        self.new_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(self.new_version_label)
        
        # 현재 버전
        self.current_version_label = QLabel(get_update_text("current_version", version=self.current_version))
        self.current_version_label.setObjectName("update_content")
        self.current_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(self.current_version_label)
        
        content_layout.addLayout(version_layout)
        
        # 업데이트 질문
        self.question_label = QLabel(get_update_text("update_question"))
        self.question_label.setObjectName("update_content")
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_label.setWordWrap(True)
        content_layout.addWidget(self.question_label)
        
        # 릴리스 노트 제목
        self.notes_title_label = QLabel(get_update_text("release_notes_title"))
        self.notes_title_label.setObjectName("update_content")
        content_layout.addWidget(self.notes_title_label)
        
        # 릴리스 노트 (스크롤 가능)
        scroll_area = QScrollArea()
        scroll_area.setObjectName("update_scroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)
        
        self.notes_text = QTextEdit()
        self.notes_text.setObjectName("update_details")
        self.notes_text.setReadOnly(True)
        scroll_area.setWidget(self.notes_text)
        content_layout.addWidget(scroll_area)
        
        # 신축성 공간
        content_layout.addStretch()
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 나중에 버튼
        self.later_btn = QPushButton(get_update_text("later_button"))
        self.later_btn.setObjectName("update_cancel_button")
        self.later_btn.clicked.connect(self.on_cancel)
        button_layout.addWidget(self.later_btn)
        
        # 업데이트 버튼
        self.update_btn = QPushButton(get_update_text("update_button"))
        self.update_btn.setObjectName("update_button")
        self.update_btn.clicked.connect(self.on_update)
        button_layout.addWidget(self.update_btn)
        
        content_layout.addLayout(button_layout)
    
    def load_release_data(self):
        """릴리스 데이터 로드"""
        try:
            release_notes = self.release_data.get('body', get_update_text("loading"))
            
            # 릴리스 노트를 간단히 정리
            if len(release_notes) > 1000:
                release_notes = release_notes[:1000] + "..."
            
            self.notes_text.setPlainText(release_notes)
            
        except Exception as e:
            self.notes_text.setPlainText(f"릴리스 노트를 불러올 수 없습니다: {e}")
    
    def on_update(self):
        """업데이트 버튼 클릭"""
        self.update_requested.emit()
        self.accept()
    
    def on_cancel(self):
        """취소 버튼 클릭"""
        self.update_cancelled.emit()
        self.reject()


class UpdateProgressDialog(BaseDialog):
    """업데이트 진행률 다이얼로그"""
    
    # 시그널 정의
    cancel_requested = pyqtSignal()
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent=parent, settings=settings)
        
        self.setWindowTitle(get_update_text("download_title"))
        self.setModal(True)
        self.setFixedSize(450, 300)
        
        # 진행률 다이얼로그는 더 높은 우선순위로 표시 (업데이트 확인 창보다 나중에 뜨므로)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.can_cancel = True
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 위젯
        background_widget = QWidget()
        background_widget.setObjectName("update_background")
        main_layout.addWidget(background_widget)
        
        # 컨텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 다이얼로그 오브젝트 이름 설정
        self.setObjectName("update_dialog")
        
        # 제목
        self.title_label = QLabel(get_update_text("download_title"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("update_title")
        content_layout.addWidget(self.title_label)
        
        # 상태 메시지
        self.status_label = QLabel(get_update_text("downloading_message"))
        self.status_label.setObjectName("update_status")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)
        
        # 진행률 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("update_progress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        content_layout.addWidget(self.progress_bar)
        
        # 진행률 텍스트
        self.progress_label = QLabel(get_update_text("preparing"))
        self.progress_label.setObjectName("update_progress_text")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.progress_label)
        
        # 신축성 공간
        content_layout.addStretch()
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 취소 버튼
        self.cancel_btn = QPushButton(get_update_text("cancel_button"))
        self.cancel_btn.setObjectName("update_cancel_button")
        self.cancel_btn.clicked.connect(self.on_cancel)
        button_layout.addWidget(self.cancel_btn)
        
        content_layout.addLayout(button_layout)
    
    def set_progress(self, value):
        """진행률 설정"""
        self.progress_bar.setValue(value)
        
        if value >= 100:
            self.progress_label.setText(get_update_text("completed"))
        else:
            self.progress_label.setText(get_update_text("download_progress", percent=value))
    
    def set_status(self, message):
        """상태 메시지 설정"""
        self.status_label.setText(message)
    
    def set_installing_mode(self):
        """설치 모드로 전환"""
        self.title_label.setText(get_update_text("install_progress"))
        self.status_label.setText(get_update_text("installing_message"))
        self.progress_label.setText(get_update_text("installing"))
        
        # 설치 중에는 취소 불가
        self.can_cancel = False
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText(get_update_text("please_wait"))
    
    def show_installation_phase(self):
        """설치 단계로 전환하고 Z-order 재조정"""
        self.set_installing_mode()
        # 설치 단계에서는 더 높은 우선순위로 표시
        self.raise_()
        self.activateWindow()
    
    def show(self):
        """창 표시시 적절한 Z-order 설정"""
        super().show()
        # 진행률 다이얼로그는 다른 창들 위에 표시
        QTimer.singleShot(50, self.raise_)
        QTimer.singleShot(100, self.activateWindow)
    
    def on_cancel(self):
        """취소 버튼 클릭"""
        if self.can_cancel:
            self.cancel_requested.emit()
            self.reject()


class UpdateCompleteDialog(BaseDialog):
    """업데이트 완료 다이얼로그"""

    def __init__(self, parent=None, settings=None):
        super().__init__(parent=parent, settings=settings)

        self.setWindowTitle(get_update_text("complete_title"))
        self.setModal(True)
        self.setFixedSize(400, 250)

        # 완료 다이얼로그는 최고 우선순위로 표시 (가장 나중에 뜨므로)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.init_ui()

    def _on_ok_clicked(self):
        """확인 버튼 클릭 처리 - UI 반응성 개선"""
        # 즉시 버튼 비활성화로 중복 클릭 방지
        self.ok_btn.setEnabled(False)
        self.ok_btn.setText("처리 중...")

        # 약간의 지연 후 다이얼로그 닫기
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.accept)
    
    def init_ui(self):
        """UI 초기화"""
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 위젯
        background_widget = QWidget()
        background_widget.setObjectName("update_background")
        main_layout.addWidget(background_widget)
        
        # 컨텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 다이얼로그 오브젝트 이름 설정
        self.setObjectName("update_dialog")
        
        # 제목
        self.title_label = QLabel(get_update_text("complete_title"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("update_title")
        content_layout.addWidget(self.title_label)
        
        # 완료 메시지
        self.message_label = QLabel(get_update_text("complete_message"))
        self.message_label.setObjectName("update_content")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        content_layout.addWidget(self.message_label)
        
        # 재시작 안내
        self.restart_label = QLabel(get_update_text("restart_message"))
        self.restart_label.setObjectName("update_content")
        self.restart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.restart_label.setWordWrap(True)
        content_layout.addWidget(self.restart_label)

        # 신축성 공간
        content_layout.addStretch()

        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # 확인 버튼
        self.ok_btn = QPushButton(get_update_text("ok_button"))
        self.ok_btn.setObjectName("update_button")
        self.ok_btn.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(self.ok_btn)
        
        content_layout.addLayout(button_layout)
    
    def show(self):
        """창 표시시 최고 우선순위로 설정"""
        super().show()
        # 완료 다이얼로그는 가장 나중에 뜨므로 최고 우선순위
        QTimer.singleShot(50, self.raise_)
        QTimer.singleShot(100, self.activateWindow)


class UpdateErrorDialog(BaseDialog):
    """업데이트 오류 다이얼로그"""
    
    def __init__(self, error_message, error_type="general", parent=None, settings=None):
        super().__init__(parent=parent, settings=settings)
        
        self.error_message = error_message
        self.error_type = error_type
        
        # 오류 타입에 따른 제목 설정
        if error_type == "download":
            title = get_update_text("download_error_title")
        elif error_type == "install":
            title = get_update_text("install_error_title")
        else:
            title = get_update_text("error_title")
        
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(450, 300)
        
        # 에러 다이얼로그도 최고 우선순위로 표시 (가장 나중에 뜨므로)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 위젯
        background_widget = QWidget()
        background_widget.setObjectName("update_background")
        main_layout.addWidget(background_widget)
        
        # 컨텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 다이얼로그 오브젝트 이름 설정
        self.setObjectName("update_dialog")
        
        # 제목
        title_text = ""
        if self.error_type == "download":
            title_text = get_update_text("download_error_title")
        elif self.error_type == "install":
            title_text = get_update_text("install_error_title")
        else:
            title_text = get_update_text("error_title")
            
        self.title_label = QLabel(title_text)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("update_title")
        content_layout.addWidget(self.title_label)
        
        # 오류 메시지
        message_text = ""
        if self.error_type == "download":
            message_text = get_update_text("download_error_message", error=self.error_message)
        elif self.error_type == "install":
            message_text = get_update_text("install_error_message", error=self.error_message)
        else:
            message_text = get_update_text("error_message", error=self.error_message)
        
        self.message_label = QLabel(message_text)
        self.message_label.setObjectName("update_content")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.message_label.setWordWrap(True)
        content_layout.addWidget(self.message_label)
        
        # 신축성 공간
        content_layout.addStretch()
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 확인 버튼
        self.ok_btn = QPushButton(get_update_text("ok_button"))
        self.ok_btn.setObjectName("update_cancel_button")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        content_layout.addLayout(button_layout)
    
    def show(self):
        """창 표시시 최고 우선순위로 설정"""
        super().show()
        # 에러 다이얼로그는 가장 나중에 뜨므로 최고 우선순위
        QTimer.singleShot(50, self.raise_)
        QTimer.singleShot(100, self.activateWindow)


class NoUpdateDialog(BaseDialog):
    """업데이트 없음 다이얼로그"""
    
    def __init__(self, current_version, parent=None, settings=None):
        super().__init__(parent=parent, settings=settings)
        
        self.current_version = current_version
        
        self.setWindowTitle(get_update_text("no_update_title"))
        self.setModal(True)
        self.setFixedSize(350, 200)
        
        # 업데이트 없음 다이얼로그도 최고 우선순위로 표시
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 위젯
        background_widget = QWidget()
        background_widget.setObjectName("update_background")
        main_layout.addWidget(background_widget)
        
        # 컨텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 다이얼로그 오브젝트 이름 설정
        self.setObjectName("update_dialog")
        
        # 제목
        self.title_label = QLabel(get_update_text("no_update_title"))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("update_title")
        content_layout.addWidget(self.title_label)
        
        # 메시지
        self.message_label = QLabel(get_update_text("no_update_message", version=self.current_version))
        self.message_label.setObjectName("update_content")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        content_layout.addWidget(self.message_label)
        
        # 신축성 공간
        content_layout.addStretch()
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 확인 버튼
        self.ok_btn = QPushButton(get_update_text("ok_button"))
        self.ok_btn.setObjectName("update_button")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        content_layout.addLayout(button_layout)
    
    def show(self):
        """창 표시시 적절한 Z-order 설정"""
        super().show()
        # 업데이트 없음 다이얼로그는 높은 우선순위로 표시
        QTimer.singleShot(50, self.raise_)
        QTimer.singleShot(100, self.activateWindow)