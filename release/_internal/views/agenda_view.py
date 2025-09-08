# views/agenda_view.py
import datetime
from collections import OrderedDict
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QScrollArea, QWidget
from PyQt6.QtCore import Qt
from .base_view import BaseViewWidget
from .widgets import AgendaEventWidget

class AgendaViewWidget(BaseViewWidget):
    def __init__(self, main_widget=None):
        super().__init__(main_widget)
        self.init_ui()

    def init_ui(self):
        """UI를 초기화합니다."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.scroll_content = QWidget()
        self.events_layout = QVBoxLayout(self.scroll_content)
        self.events_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.events_layout.setSpacing(10)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

    def load_events(self):
        """이벤트를 로드하고 UI를 업데이트합니다."""
        self.clear_layout()
        
        agenda_data = self.data_manager.get_events_for_agenda(self.current_date)
        
        if not agenda_data:
            self.show_no_events_message()
            return

        sorted_agenda = OrderedDict(sorted(agenda_data.items()))

        for date, events in sorted_agenda.items():
            self.add_date_header(date)
            for event in events:
                event_widget = AgendaEventWidget(event, parent_view=self)
                # AgendaEventWidget의 신호를 AgendaViewWidget으로 전달
                event_widget.detail_requested.connect(self.detail_requested.emit)
                event_widget.edit_requested.connect(self.edit_event_requested.emit)
                self.events_layout.addWidget(event_widget)

    def clear_layout(self):
        while self.events_layout.count():
            child = self.events_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def show_no_events_message(self):
        no_events_label = QLabel("다가오는 일정이 없습니다.")
        no_events_label.setObjectName("no_events_label")
        no_events_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.events_layout.addWidget(no_events_label)

    def add_date_header(self, date):
        day_names = ["월", "화", "수", "목", "금", "토", "일"]
        header_text = f"{date.month}월 {date.day}일 {day_names[date.weekday()]}요일"
        
        # 오늘 날짜인지 확인
        today = datetime.date.today()
        is_today = (date == today)
        
        if is_today:
            header_text = f"{header_text} (오늘)"
        
        date_label = QLabel(header_text)
        date_label.setObjectName("agenda_date_header")
        
        # 오늘 날짜면 특별한 속성 설정
        if is_today:
            date_label.setProperty("isToday", True)
            date_label.style().unpolish(date_label)
            date_label.style().polish(date_label)
        
        self.events_layout.addWidget(date_label)

    def change_date(self, new_date):
        """날짜가 변경될 때 호출됩니다."""
        self.current_date = new_date
        self.load_events()

    def refresh(self):
        self.load_events()

    def redraw_events_with_current_data(self):
        """데이터가 업데이트될 때 호출되는 메서드입니다."""
        self.load_events()
