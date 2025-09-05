# notification_manager.py
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from resource_path import get_icon_path

class NotificationPopup(QWidget):
    def __init__(self, title, message, duration_seconds=0, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowFlags(
            Qt.WindowType.Tool | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.setup_ui(title, message)
        
        # 알림창은 항상 불투명하게 유지 (메인 프로그램의 투명도 설정과 독립적)
        self.setWindowOpacity(0.95)
        
        self.show_animation()

        if duration_seconds > 0:
            QTimer.singleShot(duration_seconds * 1000, self.close)

    def setup_ui(self, title, message):
        self.background_widget = QWidget()
        self.background_widget.setObjectName("notification_popup")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.background_widget)

        layout = QVBoxLayout(self.background_widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        top_layout = QHBoxLayout()
        
        icon_label = QLabel()
        # app_icon을 QIcon으로 설정하고 QPixmap으로 변환하여 QLabel에 표시
        app_icon = QIcon(get_icon_path('tray_icon.ico'))
        pixmap = app_icon.pixmap(16, 16)
        icon_label.setPixmap(pixmap)
        
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setObjectName("notification_title")
        
        close_button = QPushButton()
        close_button.setIcon(QIcon(get_icon_path("close_button.svg")))
        close_button.setIconSize(QSize(14, 14))
        close_button.setObjectName("notification_close_button")
        close_button.setFixedSize(22, 22)
        close_button.setToolTip("닫기")
        close_button.clicked.connect(self.close)
        
        top_layout.addWidget(icon_label)
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(close_button)
        
        layout.addLayout(top_layout)
        
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setObjectName("notification_message")
        layout.addWidget(message_label)

        # 테마에 따른 스타일시트 적용
        self.apply_theme_styles()

    def apply_theme_styles(self):
        """현재 테마에 따라 알림 팝업 스타일 적용"""
        # 기본값은 다크 테마
        theme = "dark"
        if self.settings:
            theme = self.settings.get("theme", "dark")
        
        if theme == "light":
            # 라이트 테마
            bg_color = "#F8F8F8"
            text_color = "#333"
            border_color = "#DDD" 
            message_color = "#555"
            title_color = "#2B5AA0"  # 파란색 계열 (하이라이트보다 어두운 색)
            close_btn_bg = "rgba(0, 0, 0, 0.1)"
            close_btn_border = "rgba(0, 0, 0, 0.2)"
            close_btn_hover_bg = "rgba(0, 0, 0, 0.2)"
            close_btn_hover_border = "rgba(0, 0, 0, 0.4)"
            close_btn_pressed_bg = "rgba(0, 0, 0, 0.3)"
        else:
            # 다크 테마  
            bg_color = "#333"
            text_color = "#EEE"
            border_color = "#555"
            message_color = "#CCC"
            title_color = "#4A7BC8"  # 파란색 계열 (하이라이트보다 어두운 색)
            close_btn_bg = "rgba(255, 255, 255, 0.1)"
            close_btn_border = "rgba(255, 255, 255, 0.2)"
            close_btn_hover_bg = "rgba(255, 255, 255, 0.2)"
            close_btn_hover_border = "rgba(255, 255, 255, 0.4)"
            close_btn_pressed_bg = "rgba(255, 255, 255, 0.3)"

        style = f"""
            QWidget#notification_popup {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 10px;
                border: 1px solid {border_color};
            }}
            QLabel#notification_title {{
                color: {title_color};
                font-weight: bold;
                font-size: 11pt;
            }}
            QLabel#notification_message {{
                color: {message_color};
                font-size: 10pt;
            }}
            QPushButton#notification_close_button {{
                background-color: {close_btn_bg};
                border: 1px solid {close_btn_border};
                border-radius: 11px;
                padding: 0px;
            }}
            QPushButton#notification_close_button:hover {{
                background-color: {close_btn_hover_bg};
                border: 1px solid {close_btn_hover_border};
            }}
            QPushButton#notification_close_button:pressed {{
                background-color: {close_btn_pressed_bg};
            }}
        """
        self.background_widget.setStyleSheet(style)

    def show_animation(self):
        # 화면 오른쪽 하단에 위치시키기
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.move(screen_geometry.width() - self.width() - 15, screen_geometry.height() - self.height() - 15)
        self.show()

# 이 함수는 이제 직접 사용되지 않고, MainWidget에서 NotificationPopup을 직접 생성합니다.
def show_notification(title, message):
    # 이 함수는 이제 직접적인 역할은 없지만, 테스트나 호환성을 위해 남겨둘 수 있습니다.
    # 실제 알림은 MainWidget에서 시그널을 받아 NotificationPopup 인스턴스를 생성하여 표시합니다.
    print(f"알림 요청 수신 (UI 스레드에서 처리 예정): 제목='{title}', 메시지='{message}'")

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    # NotificationPopup 직접 생성 테스트
    popup = NotificationPopup("일정 알림", "10분 후에 '팀 회의'가 시작됩니다.")
    sys.exit(app.exec())