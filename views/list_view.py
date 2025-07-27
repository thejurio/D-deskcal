from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

class EventListItemWidget(QWidget):
    """
    ListView의 각 항목을 위한 커스텀 위젯.
    색상 블록, 일정 제목, 날짜를 표시합니다.
    """
    def __init__(self, event_data):
        super().__init__()
        self.event_data = event_data
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.summary_label = QLabel(self.event_data.get('summary', '(제목 없음)'))
        self.summary_label.setStyleSheet("font-weight: bold; font-size: 10pt; background-color: transparent;")

        # 날짜/시간 정보 파싱 및 포맷팅
        start_info = self.event_data.get('start', {})
        end_info = self.event_data.get('end', {})
        is_all_day = 'date' in start_info

        start_str = start_info.get('date') or start_info.get('dateTime')
        end_str = end_info.get('date') or end_info.get('dateTime')

        try:
            if is_all_day:
                date_text = f"{start_str} (하루 종일)"
            else:
                start_dt = datetime.datetime.fromisoformat(start_str)
                end_dt = datetime.datetime.fromisoformat(end_str)
                date_text = f"{start_dt.strftime('%Y-%m-%d %H:%M')} ~ {end_dt.strftime('%H:%M')}"
        except (ValueError, TypeError):
            date_text = "날짜 정보 없음"

        self.date_label = QLabel(date_text)
        self.date_label.setStyleSheet("font-size: 9pt; color: #BBBBBB; background-color: transparent;")

        layout.addWidget(self.summary_label)
        layout.addWidget(self.date_label)

    def paintEvent(self, event):
        """위젯 왼쪽에 캘린더 색상으로 된 세로 막대를 그립니다."""
        super().paintEvent(event)
        painter = QPainter(self)
        color = QColor(self.event_data.get('color', '#555555'))
        
        # 왼쪽에 세로 막대 그리기
        painter.fillRect(0, 0, 5, self.height(), color)


class ListViewWidget(QWidget):
    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget { border: none; }") # 테두리 제거
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.list_widget)

    def on_item_double_clicked(self, item):
        """리스트 항목을 더블클릭했을 때 이벤트 편집 창을 엽니다."""
        # QListWidgetItem에서 커스텀 위젯을 가져온 후, 위젯의 event_data를 사용합니다.
        custom_widget = self.list_widget.itemWidget(item)
        if custom_widget and hasattr(custom_widget, 'event_data'):
            self.main_widget.open_event_editor(custom_widget.event_data)

    def refresh(self):
        """현재 월력 뷰가 보고 있는 달의 데이터를 받아 목록을 업데이트합니다."""
        self.list_widget.clear()
        
        current_month_view_date = self.main_widget.month_view.current_date
        year, month = current_month_view_date.year, current_month_view_date.month
        
        events = self.data_manager.get_events(year, month)
        
        # 시작 날짜/시간 순으로 정렬
        events.sort(key=lambda x: x.get('start', {}).get('dateTime', x.get('start', {}).get('date', '')))

        if not events:
            # 이벤트가 없을 때 표시할 아이템
            item = QListWidgetItem("이 달에는 일정이 없습니다.")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_widget.addItem(item)
        else:
            for event_data in events:
                item = QListWidgetItem(self.list_widget)
                widget = EventListItemWidget(event_data)
                
                # 각 항목의 크기를 내용에 맞게 조절
                item.setSizeHint(widget.sizeHint())
                
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, widget)
