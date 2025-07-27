# views/week_view.py
import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QPushButton, QMenu
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor

from .widgets import EventLabelWidget, TimeScaleWidget
from custom_dialogs import CustomMessageBox

class WeekViewWidget(QWidget):
    add_event_requested = pyqtSignal(datetime.datetime)
    edit_event_requested = pyqtSignal(dict)

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.current_date = datetime.date.today() 
        self.day_labels = []
        self.hour_height = 40
        self.padding = 10 # TimeScaleWidget과 동일한 여백 값
        self.initUI()

        self.timeline_timer = QTimer(self)
        self.timeline_timer.setInterval(60 * 1000)
        self.timeline_timer.timeout.connect(self.update_timeline)
        self.timeline_timer.start()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if not self.scroll_area.geometry().contains(pos): return
            
            pos_in_viewport = self.scroll_area.widget().mapFrom(self, pos)
            pos_in_event_container = self.event_container.mapFromParent(pos_in_viewport)

            time_label_width = 50
            
            if pos_in_viewport.x() < time_label_width: return

            days_width = self.event_container.width()
            if days_width <= 0: return
            
            day_column_width = days_width / 7
            day_index = int(pos_in_event_container.x() // day_column_width)
            if not (0 <= day_index < 7): return

            hour = int(pos_in_event_container.y() // self.hour_height)
            minute = int((pos_in_event_container.y() % self.hour_height) / self.hour_height * 60)
            minute = round(minute / 15) * 15
            if minute == 60:
                minute = 0
                hour += 1
            if not (0 <= hour < 25): return

            start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
            target_date = start_of_week + datetime.timedelta(days=day_index)
            target_datetime = datetime.datetime(target_date.year, target_date.month, target_date.day, hour, minute)
            self.add_event_requested.emit(target_datetime)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        self.week_range_label = QLabel()
        self.week_range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_button_style = "QPushButton { color: white; background-color: transparent; border: none; font-size: 20px; } QPushButton:hover { color: #aaaaaa; }"
        week_label_style = "QLabel { color: white; background-color: transparent; font-size: 14px; font-weight: bold; }"
        prev_button.setStyleSheet(nav_button_style)
        next_button.setStyleSheet(nav_button_style)
        self.week_range_label.setStyleSheet(week_label_style)
        prev_button.clicked.connect(self.go_to_previous_week)
        next_button.clicked.connect(self.go_to_next_week)
        nav_layout.addWidget(prev_button)
        nav_layout.addWidget(self.week_range_label, 1)
        nav_layout.addWidget(next_button)
        main_layout.addLayout(nav_layout)

        header_widget = QWidget()
        header_widget.setObjectName("week_header")
        header_widget.setFixedHeight(30)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(50, 0, 0, 0)
        days = ["일", "월", "화", "수", "목", "금", "토"]
        self.day_labels.clear()
        for day in days:
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(label)
            self.day_labels.append(label)
        main_layout.addWidget(header_widget)

        self.all_day_widget = QWidget()
        self.all_day_widget.setObjectName("all_day_area")
        self.all_day_widget.setMinimumHeight(25)
        self.all_day_layout = QGridLayout(self.all_day_widget)
        self.all_day_layout.setContentsMargins(50, 2, 0, 2)
        self.all_day_layout.setSpacing(1)
        main_layout.addWidget(self.all_day_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("week_scroll_area")
        main_layout.addWidget(self.scroll_area)
        
        container = QWidget()
        self.scroll_area.setWidget(container)
        
        self.time_scale = TimeScaleWidget(container)
        self.time_scale.padding = self.padding
        container.setMinimumHeight(self.time_scale.minimumHeight())

        self.event_container = QWidget(container)
        self.event_container.setStyleSheet("background-color: transparent;")
        
        self.timeline = QWidget(container)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")
        
        self.event_widgets = []
        self.all_day_event_widgets = []
        self.last_mouse_pos = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        container_widget = self.scroll_area.widget()
        self.time_scale.setGeometry(0, 0, container_widget.width(), container_widget.minimumHeight())
        self.event_container.setGeometry(50, self.padding, container_widget.width() - 50, self.hour_height * 24)
        self.update_timeline()
        self.redraw_events_with_current_data()

    def go_to_previous_week(self):
        self.current_date -= datetime.timedelta(days=7)
        self.refresh()

    def go_to_next_week(self):
        self.current_date += datetime.timedelta(days=7)
        self.refresh()

    def update_timeline(self):
        now = datetime.datetime.now()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        if start_of_week <= now.date() <= end_of_week:
            self.timeline.show()
            y = now.hour * self.hour_height + int(now.minute / 60 * self.hour_height)
            self.timeline.setGeometry(50, y + self.padding, self.event_container.width(), 2)
        else:
            self.timeline.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.pos()
            self.setCursor(QCursor(Qt.CursorShape.DragMoveCursor))

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

    def contextMenuEvent(self, event):
        pos = event.pos()
        target_event = None
        pos_in_viewport = self.scroll_area.widget().mapFrom(self, pos)
        pos_in_event_container = self.event_container.mapFromParent(pos_in_viewport)
        for widget in self.event_widgets:
            if widget.geometry().contains(pos_in_event_container) and widget.isVisible():
                target_event = widget.event_data
                break
        if not target_event:
            pos_in_all_day_widget = self.all_day_widget.mapFrom(self, pos)
            for widget in self.all_day_event_widgets:
                if widget.geometry().contains(pos_in_all_day_widget) and widget.isVisible():
                    target_event = widget.event_data
                    break
        menu = QMenu(self)
        main_opacity = self.main_widget.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)
        if target_event:
            edit_action = QAction("수정", self)
            edit_action.triggered.connect(lambda: self.edit_event_requested.emit(target_event))
            menu.addAction(edit_action)
            delete_action = QAction("삭제", self)
            delete_action.triggered.connect(lambda: self.confirm_delete_event(target_event))
            menu.addAction(delete_action)
        self.main_widget.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())

    def confirm_delete_event(self, event_data):
        summary = event_data.get('summary', '(제목 없음)')
        msg_box = CustomMessageBox(self, title='삭제 확인', text=f"'{summary}' 일정을 정말 삭제하시겠습니까?", settings=self.main_widget.settings)
        if msg_box.exec():
            self.data_manager.delete_event(event_data)

    def clear_events(self):
        for widget in self.event_widgets: widget.deleteLater()
        self.event_widgets.clear()
        for widget in self.all_day_event_widgets: widget.deleteLater()
        self.all_day_event_widgets.clear()

    def draw_events(self, events, start_of_week):
        parent_widget = self.event_container
        
        events_by_day = {}
        for event in events:
            start_dt = datetime.datetime.fromisoformat(event['start']['dateTime']).replace(tzinfo=None)
            end_dt = datetime.datetime.fromisoformat(event['end']['dateTime']).replace(tzinfo=None)
            d = start_dt.date()
            while d <= end_dt.date():
                if start_of_week <= d <= start_of_week + datetime.timedelta(days=6):
                    if d not in events_by_day: events_by_day[d] = []
                    events_by_day[d].append(event)
                d += datetime.timedelta(days=1)

        for day_date, day_events in events_by_day.items():
            day_events.sort(key=lambda e: datetime.datetime.fromisoformat(e['start']['dateTime']))
            
            groups = []
            for event in day_events:
                placed = False
                start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
                for group in groups:
                    last_event_end_dt = datetime.datetime.fromisoformat(group[-1]['end']['dateTime'])
                    if start_dt >= last_event_end_dt:
                        group.append(event)
                        placed = True
                        break
                if not placed:
                    groups.append([event])

            day_column_width = parent_widget.width() / 7
            col_index = (day_date - start_of_week).days

            for group in groups:
                num_columns = len(group)
                for i, event in enumerate(group):
                    start_dt = datetime.datetime.fromisoformat(event['start']['dateTime']).replace(tzinfo=None)
                    end_dt = datetime.datetime.fromisoformat(event['end']['dateTime']).replace(tzinfo=None)
                    
                    y = start_dt.hour * self.hour_height + (start_dt.minute / 60) * self.hour_height
                    height = ((end_dt - start_dt).total_seconds() / 3600) * self.hour_height
                    
                    width = day_column_width / num_columns
                    x = col_index * day_column_width + i * width

                    event_widget = EventLabelWidget(event, parent_widget)
                    event_widget.setText(event.get('summary', '(제목 없음)'))
                    event_widget.edit_requested.connect(self.edit_event_requested)
                    event_widget.setStyleSheet(f"background-color: {event.get('color', '#555555')}; color: white; border-radius: 4px; padding: 2px 4px; font-size: 8pt;")
                    event_widget.setWordWrap(True)
                    event_widget.setAlignment(Qt.AlignmentFlag.AlignTop)
                    event_widget.setGeometry(int(x + 1), int(y), int(width - 2), int(height))
                    event_widget.show()
                    self.event_widgets.append(event_widget)

    def refresh(self):
        today = datetime.date.today()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        self.week_range_label.setText(f"{start_of_week.strftime('%Y년 %m월 %d일')} - {end_of_week.strftime('%m월 %d일')}")

        days_of_week = ["일", "월", "화", "수", "목", "금", "토"]
        for i in range(7):
            day_date = start_of_week + datetime.timedelta(days=i)
            label_text = f"{days_of_week[i]} ({day_date.day})"
            self.day_labels[i].setText(label_text)
            
            font_color = "white"
            if day_date == today: font_color = "#FFFF77"
            elif i == 0: font_color = "#ff8080"
            elif i == 6: font_color = "#8080ff"
            self.day_labels[i].setStyleSheet(f"color: {font_color}; font-weight: bold;")

        self.redraw_events_with_current_data()
        self.update_timeline()

        if start_of_week <= today <= end_of_week:
            now = datetime.datetime.now()
            target_y = now.hour * self.hour_height
            self.scroll_area.verticalScrollBar().setValue(target_y - self.scroll_area.height() // 2)

    def redraw_events_with_current_data(self):
        self.clear_events()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        week_events = self.data_manager.get_events_for_period(start_of_week, end_of_week)
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in week_events if event.get('calendarId') in selected_ids]

        time_events = [e for e in filtered_events if 'dateTime' in e.get('start', {})]
        all_day_events = [e for e in filtered_events if 'date' in e.get('start', {})]
        self.draw_events(time_events, start_of_week)
        self.draw_all_day_events(all_day_events, start_of_week)
        self.time_scale.update()

    def draw_all_day_events(self, events, start_of_week):
        if not events:
            self.all_day_widget.setVisible(False)
            return
        
        self.all_day_widget.setVisible(True)
        
        sorted_events = sorted(events, key=lambda e: (
            datetime.date.fromisoformat(e['start']['date']),
            -(datetime.date.fromisoformat(e['end']['date']) - datetime.date.fromisoformat(e['start']['date'])).days
        ))

        lanes_occupancy = [[] for _ in range(7)]
        event_to_lane = {}

        for event in sorted_events:
            start_date = datetime.date.fromisoformat(event['start']['date'])
            end_date = datetime.date.fromisoformat(event['end']['date']) - datetime.timedelta(days=1)
            
            event_start_offset = (start_date - start_of_week).days
            event_end_offset = (end_date - start_of_week).days

            lane_idx = 0
            while True:
                is_free = True
                for day_offset in range(max(0, event_start_offset), min(7, event_end_offset + 1)):
                    if lane_idx in lanes_occupancy[day_offset]:
                        is_free = False
                        break
                if is_free:
                    for day_offset in range(max(0, event_start_offset), min(7, event_end_offset + 1)):
                        lanes_occupancy[day_offset].append(lane_idx)
                    event_to_lane[event['id']] = lane_idx
                    break
                lane_idx += 1

        for event in events:
            start_date = datetime.date.fromisoformat(event['start']['date'])
            end_date = datetime.date.fromisoformat(event['end']['date']) - datetime.timedelta(days=1)
            
            draw_start_date = max(start_date, start_of_week)
            draw_end_date = min(end_date, start_of_week + datetime.timedelta(days=6))

            if draw_start_date > draw_end_date: continue

            start_offset = (draw_start_date - start_of_week).days
            span = (draw_end_date - draw_start_date).days + 1
            
            if span > 0:
                event_label = EventLabelWidget(event, self.all_day_widget)
                event_label.setText(event['summary'])
                event_label.edit_requested.connect(self.edit_event_requested)
                event_label.setStyleSheet(f"background-color: {event.get('color', '#555555')}; border-radius: 3px; padding: 1px 3px;")
                
                lane = event_to_lane.get(event['id'], 0)
                self.all_day_layout.addWidget(event_label, lane, start_offset, 1, span)
                self.all_day_event_widgets.append(event_label)
        
        num_lanes = max(event_to_lane.values()) + 1 if event_to_lane else 0
        self.all_day_widget.setMinimumHeight(max(1, num_lanes) * 22 if num_lanes > 0 else 25)