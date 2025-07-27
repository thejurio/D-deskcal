import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

class ListViewWidget(QWidget):
    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager # 데이터 관리자 참조
        self.initUI()

    def initUI(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def refresh(self):
        """현재 월력 뷰가 보고 있는 달의 데이터를 받아 목록을 그립니다."""
        # 월력 뷰가 현재 보고 있는 날짜를 기준으로 데이터를 가져옴
        current_month_view_date = self.main_widget.month_view.current_date
        year, month = current_month_view_date.year, current_month_view_date.month
        events = self.data_manager.get_events(year, month)
        self.update_events_display(events)
    
    def update_events_display(self, events):
        """이벤트 목록을 받아와 화면의 내용을 업데이트합니다."""
        # 이전 위젯들을 모두 제거
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # 중첩된 레이아웃 내 위젯 삭제
                while child.layout().count():
                    sub_child = child.layout().takeAt(0)
                    if sub_child.widget():
                        sub_child.widget().deleteLater()
                child.layout().deleteLater()

        if not events:
            label = QLabel("표시할 일정이 없습니다.")
            label.setStyleSheet("color: white; background-color: transparent;")
            label.setFont(QFont("Malgun Gothic", 12))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(label)
        else:
            # 시간순으로 정렬
            events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
            
            # 오늘 날짜 이후의 일정만 필터링
            today = datetime.datetime.now(datetime.timezone.utc).isoformat()
            future_events = [e for e in events if e['start'].get('dateTime', e['start'].get('date')) >= today[:10]]

            if not future_events:
                label = QLabel("오늘 이후 예정된 일정이 없습니다.")
                label.setStyleSheet("color: white; background-color: transparent;")
                label.setFont(QFont("Malgun Gothic", 12))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.content_layout.addWidget(label)
                return

            for event in future_events:
                event_row_layout = QHBoxLayout()
                color_label = QLabel()
                event_color = event.get('color', '#FFFFFF')
                color_label.setStyleSheet(f"background-color: {event_color}; border-radius: 4px;")
                color_label.setFixedSize(QSize(8, 20))
                event_row_layout.addWidget(color_label)

                start_raw = event["start"].get("dateTime", event["start"].get("date"))
                summary = event["summary"]
                display_time = ""
                try:
                    if len(start_raw) == 10: # 하루 종일 일정
                        dt_object = datetime.datetime.strptime(start_raw, "%Y-%m-%d")
                        display_time = dt_object.strftime("%m-%d (종일)")
                    else: # 시간이 지정된 일정
                        dt_object = datetime.datetime.fromisoformat(start_raw)
                        display_time = dt_object.strftime("%m-%d %H:%M")
                except ValueError:
                    display_time = start_raw
                
                event_text = f"<b>{display_time}</b> - {summary}"
                text_label = QLabel(event_text)
                text_label.setStyleSheet("color: white; background-color: transparent;")
                text_label.setFont(QFont("Malgun Gothic", 11))
                text_label.setWordWrap(True)
                event_row_layout.addWidget(text_label)
                
                self.content_layout.addLayout(event_row_layout)