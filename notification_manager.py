# notification_manager.py
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from resource_path import get_icon_path

class NotificationPopup(QWidget):
    def __init__(self, title, message, duration_seconds=0, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.setup_ui(title, message)
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
        
        close_button = QPushButton("X")
        close_button.setObjectName("notification_close_button")
        close_button.setFixedSize(20, 20)
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

        # 스타일시트 적용
        self.background_widget.setStyleSheet("""
            QWidget#notification_popup {
                background-color: #333;
                color: #EEE;
                border-radius: 10px;
                border: 1px solid #555;
            }
            QLabel#notification_message {
                color: #CCC;
                font-size: 12pt;
            }
            QPushButton#notification_close_button {
                background-color: transparent;
                color: #AAA;
                border: none;
                font-weight: bold;
            }
            QPushButton#notification_close_button:hover {
                color: #FFF;
            }
        """)

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