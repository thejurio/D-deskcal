# views/week_view.py
import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea
from PyQt6.QtCore import Qt, QTimer
from .widgets import EventLabelWidget

class WeekViewWidget(QWidget):
    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.initUI()

        # --- 현재 시간 표시 타이머 ---
        self.timeline_timer = QTimer(self)
        self.timeline_timer.setInterval(60 * 1000) # 1분마다 업데이트
        self.timeline_timer.timeout.connect(self.update_timeline)
        self.timeline_timer.start()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0) # 레이아웃 간격 제거

        # --- 상단 요일 헤더 ---
        header_widget = QWidget() # 헤더 배경을 위한 래퍼 위젯
        header_widget.setObjectName("week_header")
        header_widget.setFixedHeight(30)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(50, 0, 0, 0)
        
        days = ["일", "월", "화", "수", "목", "금", "토"]
        for day in days:
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(label)
        main_layout.addWidget(header_widget)

        # --- 종일 이벤트 영역 ---
        self.all_day_widget = QWidget()
        self.all_day_widget.setObjectName("all_day_area")
        self.all_day_widget.setFixedHeight(25) # 초기 높이, 내용에 따라 늘어날 수 있음
        self.all_day_layout = QHBoxLayout(self.all_day_widget)
        self.all_day_layout.setContentsMargins(50, 2, 0, 2)
        main_layout.addWidget(self.all_day_widget)

        # --- 스크롤 영역 ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("week_scroll_area")
        main_layout.addWidget(scroll_area)

        container = QWidget()
        scroll_area.setWidget(container)
        
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(0)

        # --- 시간 라벨 및 그리드 라인 ---
        for hour in range(24):
            time_label = QLabel(f"{hour:02d}:00")
            time_label.setFixedSize(50, 40)
            time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            time_label.setStyleSheet("color: #aaa;")
            self.grid_layout.addWidget(time_label, hour, 0)

            for col in range(7):
                line_widget = QWidget()
                line_widget.setObjectName("time_slot")
                line_widget.setStyleSheet("border-bottom: 1px dotted #555; border-right: 1px solid #444;")
                self.grid_layout.addWidget(line_widget, hour, col + 1)
        
        for i in range(1, 8):
            self.grid_layout.setColumnStretch(i, 1)
        
        # --- 현재 시간선 위젯 ---
        self.timeline = QWidget(container)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")
        self.update_timeline() # 초기 위치 설정

        self.event_widgets = []
        self.scroll_area = scroll_area
        self.last_mouse_pos = None

    def update_timeline(self):
        """현재 시간선의 위치를 업데이트합니다."""
        now = datetime.datetime.now()
        
        # 현재 뷰가 이번 주를 포함하는지 확인
        start_of_week = self.main_widget.month_view.current_date - datetime.timedelta(days=(self.main_widget.month_view.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)

        if start_of_week <= now.date() <= end_of_week:
            self.timeline.show()
            
            # 시간선의 y 좌표 계산
            hour_height = 40 # 시간 라벨의 높이와 동일
            y = now.hour * hour_height + int(now.minute / 60 * hour_height)
            
            # 시간선의 x 좌표와 너비 계산
            x = self.grid_layout.itemAtPosition(0, 0).widget().width() # 시간 라벨의 너비
            width = self.grid_layout.parentWidget().width() - x
            
            self.timeline.setGeometry(x, y, width, 2) # 높이는 2px
        else:
            self.timeline.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.DragMoveCursor)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.last_mouse_pos:
            delta = event.pos() - self.last_mouse_pos
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.setValue(scrollbar.value() - delta.y())
            self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = None
            self.unsetCursor()

    def clear_events(self):
        """그려진 모든 이벤트 위젯을 삭제합니다."""
        for widget in self.event_widgets:
            widget.deleteLater()
        self.event_widgets = []

    def draw_events(self, events):
        """주어진 이벤트 목록을 그리드에 그립니다. (겹침 처리 포함)"""
        self.clear_events()
        parent_widget = self.grid_layout.parentWidget()

        # 이벤트를 날짜별로 그룹화
        events_by_day = {}
        for event in events:
            start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
            day_key = start_dt.date()
            if day_key not in events_by_day:
                events_by_day[day_key] = []
            events_by_day[day_key].append(event)

        for day, day_events in events_by_day.items():
            # 시작 시간으로 정렬
            day_events.sort(key=lambda e: e['start']['dateTime'])
            
            # 겹침 그룹 찾기
            groups = []
            for event in day_events:
                placed = False
                start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
                end_dt = datetime.datetime.fromisoformat(event['end']['dateTime'])
                
                for group in groups:
                    # 그룹의 마지막 이벤트와 겹치지 않으면 그룹에 추가
                    last_event_end_dt = datetime.datetime.fromisoformat(group[-1]['end']['dateTime'])
                    if start_dt >= last_event_end_dt:
                        group.append(event)
                        placed = True
                        break
                if not placed:
                    groups.append([event])

            # 그룹별로 이벤트 그리기
            for group in groups:
                num_columns = len(group)
                for i, event in enumerate(group):
                    start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
                    end_dt = datetime.datetime.fromisoformat(event['end']['dateTime'])
                    
                    col_index = (start_dt.weekday() + 1) % 7 + 1
                    
                    start_rect = self.grid_layout.cellRect(start_dt.hour, col_index)
                    
                    y = start_rect.y() + int(start_dt.minute / 60 * start_rect.height())
                    duration_minutes = (end_dt - start_dt).total_seconds() / 60
                    height = int(duration_minutes / 60 * start_rect.height())
                    
                    total_width = start_rect.width()
                    width = total_width // num_columns
                    x = start_rect.x() + i * width

                    event_widget = EventLabelWidget(event, parent_widget)
                    event_widget.setText(event.get('summary', '(제목 없음)'))
                    event_widget.edit_requested.connect(self.main_widget.open_event_editor)
                    event_widget.setStyleSheet(f"""
                        background-color: {event.get('color', '#555555')};
                        color: white;
                        border-radius: 4px;
                        padding: 2px 4px;
                        font-size: 8pt;
                    """)
                    event_widget.setWordWrap(True)
                    event_widget.setAlignment(Qt.AlignmentFlag.AlignTop)
                    
                    event_widget.setGeometry(x + 1, y, width - 2, height)
                    event_widget.show()
                    self.event_widgets.append(event_widget)

    def refresh(self):
        """주간 뷰의 데이터를 새로고침합니다."""
        print("주간 뷰 새로고침 호출됨")
        current_date = self.main_widget.month_view.current_date
        
        year, week_num, _ = current_date.isocalendar()
        
        # 주의 시작일 계산 (오류 수정)
        start_of_week = current_date - datetime.timedelta(days=(current_date.weekday() + 1) % 7)
        
        print(f"이번 주: {year}년 {week_num}주차")
        
        # DataManager로부터 해당 주의 이벤트 데이터를 직접 가져옵니다.
        week_events = self.data_manager.get_week_events(year, week_num)
        
        # 이벤트를 시간 지정 / 종일로 분리
        time_events = [e for e in week_events if 'dateTime' in e.get('start', {})]
        all_day_events = [e for e in week_events if 'date' in e.get('start', {})]
        
        self.draw_events(time_events)
        self.draw_all_day_events(all_day_events, start_of_week)

        # --- 현재 시간으로 스크롤 이동 ---
        now = datetime.datetime.now()
        if start_of_week <= now.date() <= start_of_week + datetime.timedelta(days=6):
            hour_height = 40 # 시간 라벨 높이
            target_y = now.hour * hour_height
            # 뷰의 절반 높이를 빼서 중앙에 오도록 함
            scroll_to = target_y - self.scroll_area.height() // 2
            self.scroll_area.verticalScrollBar().setValue(scroll_to)

    def draw_all_day_events(self, events, start_of_week):
        """종일 이벤트를 상단 영역에 그립니다. (여러 날 걸친 이벤트 처리 포함)"""
        # 기존 위젯 정리
        layout = self.all_day_widget.layout()
        if layout is not None:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            # 기존 레이아웃 삭제
            QWidget().setLayout(layout)

        if not events:
            self.all_day_widget.setVisible(False)
            return
        
        self.all_day_widget.setVisible(True)
        
        # 이벤트 그리기를 위해 QGridLayout 사용
        grid = QGridLayout(self.all_day_widget)
        grid.setContentsMargins(50, 2, 0, 2)
        grid.setSpacing(1)

        # TODO: 겹침 처리 로직 (y-level) 필요
        for event in events:
            start_date = datetime.date.fromisoformat(event['start']['date'])
            # Google Calendar API에서 종일 이벤트의 end.date는 실제 종료일 + 1일로 옴
            end_date = datetime.date.fromisoformat(event['end']['date']) - datetime.timedelta(days=1)

            start_offset = (start_date - start_of_week).days
            end_offset = (end_date - start_of_week).days
            
            # 현재 주에 표시될 부분만 계산
            draw_start_offset = max(0, start_offset)
            draw_end_offset = min(6, end_offset)
            
            span = draw_end_offset - draw_start_offset + 1
            
            if span > 0:
                event_label = EventLabelWidget(event, self.all_day_widget)
                event_label.setText(event['summary'])
                event_label.edit_requested.connect(self.main_widget.open_event_editor)
                event_label.setStyleSheet(f"background-color: {event['color']}; border-radius: 3px; padding: 1px 3px;")
                
                # TODO: y-level (겹침) 처리 필요
                grid.addWidget(event_label, 0, draw_start_offset, 1, span)

        # 동적으로 높이 조절 (최대 3줄)
        # num_rows = min(grid.rowCount(), 3)
        # self.all_day_widget.setFixedHeight(num_rows * 22)
