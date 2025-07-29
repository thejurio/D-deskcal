# views/week_view.py
import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QPushButton, QMenu, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QRectF
from PyQt6.QtGui import QAction, QCursor, QPainter, QColor, QPen, QFontMetrics, QTextOption

from .widgets import EventLabelWidget # 종일 일정 표시에만 사용
from .layout_calculator import WeekLayoutCalculator
from .base_view import BaseViewWidget

def get_text_color_for_background(hex_color):
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return '#000000' if luminance > 149 else '#FFFFFF'
    except Exception:
        return '#FFFFFF'

class ScheduleCanvas(QWidget):
    """주간 뷰의 모든 그리드와 이벤트를 직접 그리는 단일 캔버스 위젯"""
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.event_rects = [] # (QRect, event_data) 튜플 저장
        self.setMouseTracking(True) # 마우스 추적 활성화 (향후 툴팁 등 확장을 위해)

    def set_events(self, event_positions):
        self.event_rects = event_positions
        self.update() # 위젯을 다시 그리도록 요청

    def get_event_at(self, pos):
        for rect, event_data in self.event_rects:
            if rect.contains(pos):
                return event_data
        return None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 필요한 정보들을 부모 뷰에서 가져옴
        pv = self.parent_view
        current_theme = pv.main_widget.settings.get("theme", "dark")
        time_grid_left = 50
        day_column_width = (self.width() - time_grid_left) / 7
        start_of_week = pv.current_date - datetime.timedelta(days=(pv.current_date.weekday() + 1) % 7)

        # 1. 오늘 날짜 하이라이트
        today = datetime.date.today()
        if start_of_week <= today < start_of_week + datetime.timedelta(days=7):
            highlight_color = QColor("#FFFFAA") if current_theme == "light" else QColor("#4A4A26")
            day_offset = (today - start_of_week).days
            x = time_grid_left + day_offset * day_column_width
            painter.fillRect(int(x), 0, int(day_column_width), self.height(), highlight_color)

        # 2. 가로/세로선
        line_color = QColor("#444") if current_theme == "dark" else QColor("#E0E0E0")
        painter.setPen(QPen(line_color, 1))
        for hour in range(1, pv.total_hours + 1):
            y = pv.padding + hour * pv.hour_height
            painter.drawLine(time_grid_left, y, self.width(), y)
        for i in range(7):
            x = time_grid_left + i * day_column_width
            painter.drawLine(int(x), 0, int(x), self.height())
        
        # 3. 시간 텍스트
        text_color = QColor("#D0D0D0") if current_theme == "dark" else QColor("#222222")
        painter.setPen(text_color)
        for hour in range(pv.total_hours + 1):
            y = pv.padding + hour * pv.hour_height
            rect = QRect(0, y - pv.hour_height // 2, 45, pv.hour_height)
            painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{hour:02d}:00")

        # 4. 일정 그리기
        text_option = QTextOption(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        for rect, event_data in self.event_rects:
            # 이벤트 배경 그리기
            event_color = QColor(event_data.get('color', '#555555'))
            painter.setBrush(event_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 4, 4)

            # 이벤트 텍스트 그리기
            text_color = QColor(get_text_color_for_background(event_data.get('color', '#555555')))
            painter.setPen(text_color)
            
            start_dt = datetime.datetime.fromisoformat(event_data['start']['dateTime'])
            end_dt = datetime.datetime.fromisoformat(event_data['end']['dateTime'])
            time_text = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"
            summary = event_data.get('summary', '')
            
            text_rect = rect.adjusted(4, 4, -4, -4)
            # QRect를 QRectF로 변환하여 전달
            painter.drawText(QRectF(text_rect), f"{time_text}\n{summary}", text_option)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            clicked_event = self.get_event_at(event.pos())
            if clicked_event:
                self.parent_view.edit_event_requested.emit(clicked_event)
            else:
                target_datetime = self.parent_view._get_datetime_from_pos(event.pos())
                if target_datetime:
                    self.parent_view.add_event_requested.emit(target_datetime)
    
    def contextMenuEvent(self, event):
        clicked_event = self.get_event_at(event.pos())
        self.parent_view.show_context_menu(event.globalPos(), clicked_event)

class WeekViewWidget(BaseViewWidget):
    def __init__(self, main_widget):
        super().__init__(main_widget)
        self.day_labels = []
        self.hour_height = 56
        self.total_hours = 24
        self.padding = 10
        self.all_day_event_widgets = []

        self.initUI()

        self.timeline_timer = QTimer(self)
        self.timeline_timer.setInterval(60 * 1000)
        self.timeline_timer.timeout.connect(self.update_timeline)
        self.timeline_timer.start()
        
        self.data_manager.event_completion_changed.connect(self.redraw_events_with_current_data)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        self.week_range_label = QLabel()
        self.week_range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev_button.setObjectName("nav_button"); next_button.setObjectName("nav_button")
        self.week_range_label.setObjectName("week_label")
        prev_button.clicked.connect(self.go_to_previous_week)
        next_button.clicked.connect(self.go_to_next_week)
        nav_layout.addWidget(prev_button); nav_layout.addWidget(self.week_range_label, 1); nav_layout.addWidget(next_button)
        main_layout.addLayout(nav_layout)

        header_widget = QWidget()
        header_widget.setObjectName("week_header")
        header_widget.setFixedHeight(30)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(50, 0, 0, 0)
        self.day_labels = [QLabel() for _ in range(7)]
        for label in self.day_labels:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(label)
        main_layout.addWidget(header_widget)

        self.all_day_widget = QWidget()
        self.all_day_widget.setObjectName("all_day_area")
        self.all_day_layout = QGridLayout(self.all_day_widget)
        self.all_day_layout.setContentsMargins(50, 2, 0, 2)
        self.all_day_layout.setSpacing(1)
        main_layout.addWidget(self.all_day_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("week_scroll_area")
        main_layout.addWidget(self.scroll_area)
        
        self.canvas = ScheduleCanvas(self)
        self.scroll_area.setWidget(self.canvas)
        self.canvas.setMinimumHeight(self.hour_height * self.total_hours + self.padding * 2)

        self.timeline = QWidget(self.canvas)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")

    def go_to_previous_week(self): self.current_date -= datetime.timedelta(days=7); self.refresh()
    def go_to_next_week(self): self.current_date += datetime.timedelta(days=7); self.refresh()

    def set_resizing(self, is_resizing):
        self.is_resizing = is_resizing
        # 더 이상 위젯을 숨길 필요가 없으므로 redraw만 호출
        if not self.is_resizing:
            self.redraw_events_with_current_data()
            
    def _get_datetime_from_pos(self, pos):
        # 캔버스 내부 좌표로 변환
        canvas_pos = self.canvas.mapFrom(self, pos)
        
        time_label_width, days_width = 50, self.canvas.width() - 50
        if not (time_label_width <= canvas_pos.x() < self.canvas.width()): return None
        
        day_column_width = days_width / 7
        day_index = int((canvas_pos.x() - time_label_width) // day_column_width)
        
        y_pos_in_grid = canvas_pos.y() - self.padding
        hour = int(y_pos_in_grid / self.hour_height)
        minute = int((y_pos_in_grid % self.hour_height) / self.hour_height * 60)
        minute = round(minute / 15) * 15
        if minute == 60: minute, hour = 0, hour + 1
        
        if not (0 <= hour < 25): return None

        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        target_date = start_of_week + datetime.timedelta(days=day_index)
        
        if hour == 24: target_date += datetime.timedelta(days=1); hour = 0
            
        return datetime.datetime(target_date.year, target_date.month, target_date.day, hour, minute)

    def show_context_menu(self, global_pos, target_event):
        menu = QMenu(self)
        main_opacity = self.main_widget.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)

        if target_event:
            event_id = target_event.get('id')
            is_completed = self.data_manager.is_event_completed(event_id)

            edit_action = QAction("수정", self)
            edit_action.triggered.connect(lambda: self.edit_event_requested.emit(target_event))
            menu.addAction(edit_action)

            if is_completed:
                reopen_action = QAction("진행", self)
                reopen_action.triggered.connect(lambda: self.data_manager.unmark_event_as_completed(event_id))
                menu.addAction(reopen_action)
            else:
                complete_action = QAction("완료", self)
                complete_action.triggered.connect(lambda: self.data_manager.mark_event_as_completed(event_id))
                menu.addAction(complete_action)

            delete_action = QAction("삭제", self)
            delete_action.triggered.connect(lambda: self.confirm_delete_event(target_event))
            menu.addAction(delete_action)
        else:
            local_pos = self.mapFromGlobal(global_pos)
            target_datetime = self._get_datetime_from_pos(local_pos)
            if target_datetime:
                add_action = QAction("일정 추가", self)
                add_action.triggered.connect(lambda: self.add_event_requested.emit(target_datetime))
                menu.addAction(add_action)

        self.main_widget.add_common_context_menu_actions(menu)
        menu.exec(global_pos)

    def update_timeline(self):
        now = datetime.datetime.now()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        
        if start_of_week <= now.date() < start_of_week + datetime.timedelta(days=7):
            self.timeline.show()
            y = self.padding + now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            self.timeline.setGeometry(50, int(y), self.canvas.width() - 50, 2)
        else:
            self.timeline.hide()

    def refresh(self):
        today = datetime.date.today()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        self.week_range_label.setText(f"{start_of_week.strftime('%Y년 %m월 %d일')} - {end_of_week.strftime('%m월 %d일')}")

        current_theme = self.main_widget.settings.get("theme", "dark")
        is_dark = current_theme == "dark"
        colors = {"weekday": "#D0D0D0" if is_dark else "#222222", "saturday": "#8080FF" if is_dark else "#0000DD", "sunday": "#FF8080" if is_dark else "#DD0000", "today": "#FFFF77" if is_dark else "#A0522D" }

        days_of_week_str = ["일", "월", "화", "수", "목", "금", "토"]
        for i in range(7):
            day_date = start_of_week + datetime.timedelta(days=i)
            self.day_labels[i].setText(f"{days_of_week_str[i]} ({day_date.day})")
            font_color = colors['weekday'];
            if day_date == today: font_color = colors['today']
            elif i == 0: font_color = colors['sunday']
            elif i == 6: font_color = colors['saturday']
            self.day_labels[i].setStyleSheet(f"color: {font_color}; font-weight: bold;")
        
        self.week_range_label.setStyleSheet(f"color: {colors['weekday']}; font-size: 16px; font-weight: bold;")

        self.redraw_events_with_current_data()
        self.update_timeline()

        if start_of_week <= today <= end_of_week:
            now = datetime.datetime.now()
            target_y = self.padding + now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            scroll_offset = self.scroll_area.height() * 0.3
            self.scroll_area.verticalScrollBar().setValue(int(target_y - scroll_offset))

    def redraw_events_with_current_data(self):
        # 종일 일정은 기존 위젯 방식 유지 (클릭 등 상호작용이 더 쉬움)
        for widget in self.all_day_event_widgets: widget.deleteLater()
        self.all_day_event_widgets.clear()

        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        week_events = self.data_manager.get_events_for_period(start_of_week, end_of_week)
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in week_events if event.get('calendarId') in selected_ids]

        time_events, all_day_events = [], []
        for e in filtered_events:
            start_str = e['start'].get('dateTime') or e['start'].get('date')
            end_str = e['end'].get('dateTime') or e['end'].get('date')
            start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', ''))
            end_dt = datetime.datetime.fromisoformat(end_str.replace('Z', ''))
            is_all_day_native = 'date' in e['start']
            is_multi_day = (end_dt - start_dt).total_seconds() >= 86400
            if is_all_day_native or (is_multi_day and 'dateTime' in e['start']):
                all_day_events.append(e)
            elif 'dateTime' in e['start']:
                time_events.append(e)

        self.draw_all_day_events(all_day_events, start_of_week)

        # 시간대별 일정 계산 및 캔버스에 전달
        time_grid_left = 50
        day_column_width = (self.canvas.width() - time_grid_left) / 7
        calculator = WeekLayoutCalculator(time_events, [], start_of_week, self.hour_height)
        positions = calculator.calculate_time_events(day_column_width)
        
        event_rects = []
        for pos_info in positions:
            rect_coords = pos_info['rect']
            # x 좌표에 time_grid_left를 더해 실제 캔버스 좌표로 변환
            rect = QRect(rect_coords[0] + time_grid_left, rect_coords[1] + self.padding, rect_coords[2], rect_coords[3])
            event_rects.append((rect, pos_info['event']))
            
        self.canvas.set_events(event_rects)


    def draw_all_day_events(self, all_day_events, start_of_week):
        # 이 함수는 기존과 거의 동일하게 유지
        if not all_day_events:
            self.all_day_widget.hide()
            return
        
        self.all_day_widget.show()
        
        while self.all_day_layout.count():
            child = self.all_day_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        calculator = WeekLayoutCalculator([], all_day_events, start_of_week)
        positions, num_lanes = calculator.calculate_all_day_events()

        for pos_info in positions:
            event, lane, start_col, span = pos_info['event'], pos_info['lane'], pos_info['start_col'], pos_info['span']
            event_label = EventLabelWidget(event, self.all_day_widget)
            summary = event.get('summary', '')
            if 'recurrence' in event: summary = f"🔄 {summary}"
            event_label.setText(summary)
            event_label.edit_requested.connect(self.edit_event_requested)
            event_color = event.get('color', '#555555')
            text_color = get_text_color_for_background(event_color)
            finished = self.data_manager.is_event_completed(event.get('id'))
            style_sheet = f"background-color: {event_color}; color: {text_color}; border-radius: 4px; padding: 2px 4px; font-size: 9pt;"
            
            if finished: style_sheet += "text-decoration: line-through;"
            
            event_label.setStyleSheet(style_sheet)
            self.all_day_layout.addWidget(event_label, lane, start_col, 1, span)
            self.all_day_event_widgets.append(event_label)
        
        new_height = max(1, num_lanes) * 25 if num_lanes > 0 else 0
        self.all_day_widget.setMinimumHeight(new_height)
        self.all_day_widget.adjustSize()