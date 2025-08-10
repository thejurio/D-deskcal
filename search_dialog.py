# search_dialog.py
import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QListWidget, QListWidgetItem, QLabel, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, pyqtSignal

from custom_dialogs import BaseDialog

class SearchResultWidget(QWidget):
    """검색 결과의 각 항목을 표시하는 커스텀 위젯"""
    def __init__(self, event_data, data_manager):
        super().__init__()
        self.event_data = event_data
        self.data_manager = data_manager
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # 캘린더 색상 + 이모지
        color_label = QLabel()
        color = event_data.get('color', '#555555')
        emoji = event_data.get('emoji', '')
        color_label.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        color_label.setFixedSize(20, 20)
        
        if emoji:
            emoji_label = QLabel(emoji, color_label)
            emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            emoji_label.setStyleSheet("background-color: transparent;")

        # 일정 제목 및 날짜
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        summary_label = QLabel(event_data.get('summary', '(제목 없음)'))
        summary_label.setStyleSheet("font-weight: bold;")

        # --- ▼▼▼ 완료된 일정 스타일 적용 (DB 기반) ▼▼▼ ---
        if self.data_manager:
            finished = self.data_manager.is_event_completed(event_data.get('id'))
            if finished:
                summary_label.setStyleSheet("font-weight: bold; text-decoration: line-through;")
                opacity_effect = QGraphicsOpacityEffect()
                opacity_effect.setOpacity(0.5)
                self.setGraphicsEffect(opacity_effect)
        # --- ▲▲▲ 여기까지 적용 ▲▲▲ ---

        date_str = self.format_event_date(event_data)
        date_label = QLabel(date_str)
        date_label.setStyleSheet("font-size: 9pt; color: #888888;")

        info_layout.addWidget(summary_label)
        info_layout.addWidget(date_label)

        layout.addWidget(color_label)
        layout.addLayout(info_layout)
        layout.addStretch(1)

    def format_event_date(self, event):
        start = event.get('start', {})
        if 'dateTime' in start:
            dt = datetime.datetime.fromisoformat(start['dateTime'])
            return dt.strftime('%Y년 %m월 %d일 %H:%M')
        elif 'date' in start:
            dt = datetime.date.fromisoformat(start['date'])
            return dt.strftime('%Y년 %m월 %d일 (하루 종일)')
        return "날짜 정보 없음"


class SearchDialog(BaseDialog):
    event_selected = pyqtSignal(dict)

    def __init__(self, data_manager, parent=None, settings=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.data_manager = data_manager
        
        self.setWindowTitle("일정 검색")
        self.setMinimumSize(450, 500)
        
        self.initUI()
        self.data_manager.event_completion_changed.connect(self.perform_search)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(15, 15, 15, 15)

        # 검색어 입력창
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색어를 입력하세요...")
        self.search_input.returnPressed.connect(self.perform_search)
        
        search_button = QPushButton("검색")
        search_button.clicked.connect(self.perform_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # 결과 목록
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("QListWidget { border: 1px solid #5A5A5A; }") # 테마 종속적
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.results_list)

        # 닫기 버튼 추가
        button_layout = QHBoxLayout()
        button_layout.addStretch(1) # 버튼을 오른쪽으로 밀어냄
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.reject) # reject() 슬롯에 연결하여 창을 닫음
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def perform_search(self):
        query = self.search_input.text()
        if not query:
            return

        self.results_list.clear()
        # TODO: 검색 중임을 나타내는 로딩 인디케이터 표시
        
        search_results = self.data_manager.search_events(query)

        if not search_results:
            # TODO: "검색 결과가 없습니다" 메시지 표시
            return

        for event in search_results:
            item = QListWidgetItem(self.results_list)
            widget = SearchResultWidget(event, self.data_manager)
            item.setSizeHint(widget.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, widget)

    def on_item_double_clicked(self, item):
        widget = self.results_list.itemWidget(item)
        if widget:
            self.event_selected.emit(widget.event_data)
            self.accept() # 검색창을 닫고 메인 뷰로 포커스 이동
