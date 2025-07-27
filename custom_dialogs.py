import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QWidget, QComboBox, QStackedWidget, QGridLayout)
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
        self.setMinimumWidth(350) # 최소 너비 설정

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
        self.text_label.setMinimumHeight(50) # 최소 높이 조정
        self.text_label.setStyleSheet("padding-top: 10px; padding-bottom: 10px;") # 상하 패딩 추가
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

class NewDateSelectionDialog(QDialog):
    """
    년/월을 타일 형태로 선택하는 새로운 다이얼로그 (개선된 버전).
    """
    def __init__(self, current_date, parent=None):
        super().__init__(parent)
        self.current_display_year = current_date.year
        self.selected_year = current_date.year
        self.selected_month = current_date.month
        self.oldPos = None

        self.setWindowTitle("날짜 이동")
        self.setModal(True)
        self.setFixedSize(320, 320)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)

        # --- 상단 네비게이션 ---
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("<")
        self.next_button = QPushButton(">")
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.title_label)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.next_button)
        content_layout.addLayout(nav_layout)

        # --- 뷰 전환 스택 위젯 ---
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        # --- 하단 버튼 ---
        bottom_layout = QHBoxLayout()
        self.back_to_year_button = QPushButton("연도 선택")
        self.back_to_year_button.setVisible(False) # 처음엔 숨김
        close_button = QPushButton("닫기")
        
        bottom_layout.addWidget(self.back_to_year_button)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(close_button)
        content_layout.addLayout(bottom_layout)

        # --- 뷰 생성 및 연결 ---
        self.year_view = self.create_grid_view(self.select_year)
        self.month_view = self.create_grid_view(self.select_month)
        self.stacked_widget.addWidget(self.year_view)
        self.stacked_widget.addWidget(self.month_view)

        self.prev_button.clicked.connect(self.on_prev_clicked)
        self.next_button.clicked.connect(self.on_next_clicked)
        self.back_to_year_button.clicked.connect(self.show_year_view)
        close_button.clicked.connect(self.reject)

        self.show_year_view()

    def create_grid_view(self, click_handler):
        """3x4 격자 뷰를 생성하는 헬퍼 함수."""
        view = QWidget()
        grid = QGridLayout(view)
        grid.setSpacing(5)
        for i in range(12):
            button = QPushButton()
            button.setFixedSize(65, 45)
            # 람다에 현재 버튼을 전달하여 스코프 문제 해결
            button.clicked.connect(lambda _, b=button: click_handler(b.text()))
            grid.addWidget(button, i // 4, i % 4)
        return view

    def show_year_view(self):
        """연도 선택 뷰를 표시하고 내용을 채웁니다."""
        self.current_mode = 'year'
        self.back_to_year_button.setVisible(False)
        self.populate_year_grid()
        self.stacked_widget.setCurrentWidget(self.year_view)

    def show_month_view(self):
        """월 선택 뷰를 표시하고 내용을 채웁니다."""
        self.current_mode = 'month'
        self.back_to_year_button.setVisible(True)
        self.populate_month_grid()
        self.stacked_widget.setCurrentWidget(self.month_view)

    def populate_year_grid(self):
        """연도 뷰의 버튼 텍스트와 스타일을 설정합니다."""
        start_year = self.current_display_year - (self.current_display_year % 12)
        self.title_label.setText(f"{start_year} - {start_year + 11}")
        grid = self.year_view.layout()
        for i in range(12):
            year = start_year + i
            button = grid.itemAt(i).widget()
            button.setText(str(year))
            # 현재 선택된 연도와 스타일이 겹치지 않도록 초기화
            button.setStyleSheet("")
            if year == self.selected_year:
                button.setStyleSheet("background-color: #0078D7;")

    def populate_month_grid(self):
        """월 뷰의 버튼 텍스트와 스타일을 설정합니다."""
        self.title_label.setText(f"{self.selected_year}년")
        grid = self.month_view.layout()
        for i in range(12):
            month = i + 1
            button = grid.itemAt(i).widget()
            button.setText(f"{month}월")
            button.setStyleSheet("")
            if self.selected_year == datetime.date.today().year and month == self.selected_month:
                 button.setStyleSheet("background-color: #0078D7;")

    def select_year(self, year_text):
        self.selected_year = int(year_text)
        self.show_month_view()

    def select_month(self, month_text):
        self.selected_month = int(month_text.replace("월", ""))
        self.accept()

    def on_prev_clicked(self):
        if self.current_mode == 'year':
            self.current_display_year -= 12
            self.populate_year_grid()
        else: # month mode
            self.selected_year -= 1
            self.populate_month_grid()

    def on_next_clicked(self):
        if self.current_mode == 'year':
            self.current_display_year += 12
            self.populate_year_grid()
        else: # month mode
            self.selected_year += 1
            self.populate_month_grid()
            
    def get_selected_date(self):
        return self.selected_year, self.selected_month

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