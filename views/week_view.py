# views/week_view.py
import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QPushButton, QMenu
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction

from .widgets import EventLabelWidget
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

            time_label_width = self.grid_layout.itemAtPosition(0, 0).widget().width()
            hour_height = 40
            
            if pos_in_viewport.x() < time_label_width: return

            content_widget = self.scroll_area.widget()
            days_width = content_widget.width() - time_label_width
            if days_width <= 0: return
            
            day_column_width = days_width / 7
            day_index = int((pos_in_viewport.x() - time_label_width) // day_column_width)
            if not (0 <= day_index < 7): return

            hour = int(pos_in_viewport.y() // hour_height)
            minute = int((pos_in_viewport.y() % hour_height) / hour_height * 60)
            minute = round(minute / 15) * 15
            if minute == 60:
                minute = 0
                hour += 1
            if not (0 <= hour < 24): return

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

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("week_scroll_area")
        main_layout.addWidget(scroll_area)
        container = QWidget()
        scroll_area.setWidget(container)
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(0)

        # --- Time Labels and Grid Lines (Revised) ---
        for hour in range(24):
            time_label = QLabel(f"{hour:02d}:00")
            time_label.setFixedSize(50, 40)
            # Align vertically centered, then use padding to push the text up.
            time_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
            time_label.setStyleSheet("color: #aaa; background-color: transparent; padding-bottom: 38px;")
            self.grid_layout.addWidget(time_label, hour, 0)

            for col in range(7):
                line_widget = QWidget()
                line_widget.setObjectName("time_slot")
                # Use a more visible solid line for the top border
                line_widget.setStyleSheet("border-top: 1px solid #444; border-right: 1px solid #444;")
                self.grid_layout.addWidget(line_widget, hour, col + 1)
        
        # Add a final line for the end of the last hour
        final_line_container = QWidget()
        final_line_container.setFixedHeight(1)
        final_line_layout = QHBoxLayout(final_line_container)
        final_line_layout.setContentsMargins(0,0,0,0)
        final_line = QWidget()
        final_line.setStyleSheet("border-top: 1px solid #444;")
        final_line_layout.addWidget(final_line)
        self.grid_layout.addWidget(final_line_container, 24, 1, 1, 7)


        for i in range(1, 8): self.grid_layout.setColumnStretch(i, 1)
        
        self.timeline = QWidget(container)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")
        self.update_timeline()

        self.event_widgets = []
        self.all_day_event_widgets = []
        self.scroll_area = scroll_area
        self.last_mouse_pos = None

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
            hour_height = 40
            y = now.hour * hour_height + int(now.minute / 60 * hour_height)
            x = self.grid_layout.itemAtPosition(0, 0).widget().width()
            width = self.grid_layout.parentWidget().width() - x
            self.timeline.setGeometry(x, y, width, 2)
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

    def contextMenuEvent(self, event):
        pos = event.pos()
        target_event = None

        pos_in_scroll_widget = self.scroll_area.widget().mapFrom(self, pos)
        for widget in self.event_widgets:
            if widget.geometry().contains(pos_in_scroll_widget) and widget.isVisible():
                target_event = widget.event_data
                break
        
        if not target_event:
            pos_in_all_day_widget = self.all_day_widget.mapFrom(self, pos)
            for widget in self.all_day_event_widgets:
                if widget.geometry().contains(pos_in_all_day_widget) and widget.isVisible():
                    target_event = widget.event_data
                    break
        
        menu = QMenu(self)
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
        msg_box = CustomMessageBox(self, title='삭제 확인', text=f"'{summary}' 일정을 정말 삭제하시겠습니까?")
        if msg_box.exec():
            self.data_manager.delete_event(event_data)

    def clear_events(self):
        for widget in self.event_widgets: widget.deleteLater()
        self.event_widgets.clear()
        for widget in self.all_day_event_widgets: widget.deleteLater()
        self.all_day_event_widgets.clear()

    def draw_events(self, events, start_of_week):
        parent_widget = self.grid_layout.parentWidget()
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        events_by_day = {}
        for event in events:
            start_dt = datetime.datetime.fromisoformat(event['start']['dateTime']).replace(tzinfo=None)
            end_dt = datetime.datetime.fromisoformat(event['end']['dateTime']).replace(tzinfo=None)

            loop_end_date = end_dt.date()
            if end_dt.time() == datetime.time.min:
                loop_end_date -= datetime.timedelta(days=1)

            d = start_dt.date()
            while d <= loop_end_date:
                if start_of_week <= d <= end_of_week:
                    if d not in events_by_day:
                        events_by_day[d] = []
                    
                    seg_start = start_dt if d == start_dt.date() else datetime.datetime.combine(d, datetime.time.min)
                    seg_end = end_dt if d == end_dt.date() else datetime.datetime.combine(d + datetime.timedelta(days=1), datetime.time.min)
                    
                    events_by_day[d].append((seg_start, seg_end, event))
                d += datetime.timedelta(days=1)

        for day, day_event_tuples in events_by_day.items():
            day_event_tuples.sort(key=lambda e: e[0])
            
            groups = []
            for event_tuple in day_event_tuples:
                placed = False
                seg_start = event_tuple[0]
                for group in groups:
                    last_seg_end = group[-1][1]
                    if seg_start >= last_seg_end:
                        group.append(event_tuple)
                        placed = True
                        break
                if not placed:
                    groups.append([event_tuple])

            for group in groups:
                num_columns = len(group)
                for i, event_tuple in enumerate(group):
                    start_dt, end_dt, original_event = event_tuple
                    
                    col_index = (start_dt.weekday() + 1) % 7 + 1
                    
                    start_rect = self.grid_layout.cellRect(start_dt.hour, col_index)
                    
                    y = start_rect.y() + int(start_dt.minute / 60 * start_rect.height())
                    duration_minutes = (end_dt - start_dt).total_seconds() / 60
                    height = int(duration_minutes / 60 * start_rect.height())
                    
                    total_width = start_rect.width()
                    width = total_width // num_columns
                    x = start_rect.x() + i * width

                    event_widget = EventLabelWidget(original_event, parent_widget)
                    event_widget.setText(original_event.get('summary', '(제목 없음)'))
                    event_widget.edit_requested.connect(self.edit_event_requested)
                    event_widget.setStyleSheet(f"background-color: {original_event.get('color', '#555555')}; color: white; border-radius: 4px; padding: 2px 4px; font-size: 8pt;")
                    event_widget.setWordWrap(True)
                    event_widget.setAlignment(Qt.AlignmentFlag.AlignTop)
                    event_widget.setGeometry(x + 1, y, width - 2, height)
                    event_widget.show()
                    self.event_widgets.append(event_widget)

    def refresh(self):
        self.clear_events()
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

        week_events = self.data_manager.get_events_for_period(start_of_week, end_of_week)
        
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in week_events if event.get('calendarId') in selected_ids]

        time_events = [e for e in filtered_events if 'dateTime' in e.get('start', {})]
        all_day_events = [e for e in filtered_events if 'date' in e.get('start', {})]
        self.draw_events(time_events, start_of_week)
        self.draw_all_day_events(all_day_events, start_of_week)
        self.update_timeline()

        if start_of_week <= today <= end_of_week:
            now = datetime.datetime.now()
            hour_height = 40
            target_y = now.hour * hour_height
            scroll_to = target_y - self.scroll_area.height() // 2
            self.scroll_area.verticalScrollBar().setValue(scroll_to)

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

            if draw_start_date > draw_end_date:
                continue

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_timeline()
