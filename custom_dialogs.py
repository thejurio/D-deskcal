import datetime
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QComboBox
from PyQt6.QtCore import Qt

class CustomMessageBox(QDialog):
    """
    프레임리스, 드래그 이동, 커스텀 스타일을 지원하는 맞춤형 메시지 박스 클래스.
    """
    def __init__(self, parent=None, title="알림", text="메시지 내용"):
        super().__init__(parent)
        self.oldPos = None

        self.setWindowTitle(title)
        self.setModal(True)
        
        # 프레임리스 및 투명 배경 설정
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 전체 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 배경 위젯 (스타일 적용 대상)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        # 콘텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)

        # 제목 라벨
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        content_layout.addWidget(self.title_label)

        # 메시지 라벨
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setMinimumHeight(60)
        self.text_label.setStyleSheet("padding-top: 10px;")
        content_layout.addWidget(self.text_label)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        self.yes_button = QPushButton("확인")
        self.yes_button.clicked.connect(self.accept) # accept()는 QDialog.exec()가 1을 반환하게 함
        button_layout.addWidget(self.yes_button)

        self.no_button = QPushButton("취소")
        self.no_button.clicked.connect(self.reject) # reject()는 QDialog.exec()가 0을 반환하게 함
        button_layout.addWidget(self.no_button)
        
        content_layout.addLayout(button_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

class DateSelectionDialog(QDialog):
    """
    년/월 선택을 위한 커스텀 다이얼로그.
    """
    def __init__(self, current_date, parent=None):
        super().__init__(parent)
        self.selected_year = current_date.year
        self.selected_month = current_date.month
        self.oldPos = None

        self.setWindowTitle("날짜 이동")
        self.setModal(True)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)

        # 제목
        title_label = QLabel("날짜 이동")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        content_layout.addWidget(title_label)

        # 년/월 선택 레이아웃
        combo_layout = QHBoxLayout()
        
        # 년도 콤보박스
        self.year_combo = QComboBox()
        current_year = datetime.date.today().year
        for year in range(current_year - 10, current_year + 11):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(str(self.selected_year))
        combo_layout.addWidget(self.year_combo)

        # 월 콤보박스
        self.month_combo = QComboBox()
        for month in range(1, 13):
            self.month_combo.addItem(f"{month:02d}")
        self.month_combo.setCurrentText(f"{self.selected_month:02d}")
        combo_layout.addWidget(self.month_combo)
        
        content_layout.addLayout(combo_layout)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        ok_button = QPushButton("확인")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        content_layout.addLayout(button_layout)

    def get_selected_date(self):
        """사용자가 선택한 년/월을 반환합니다."""
        year = int(self.year_combo.currentText())
        month = int(self.month_combo.currentText())
        return year, month

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None