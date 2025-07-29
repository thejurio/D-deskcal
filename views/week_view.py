# views/week_view.py
import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QPushButton, QMenu, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QCursor, QPainter, QColor, QPen

from .widgets import EventLabelWidget, TimeScaleWidget
from .layout_calculator import WeekLayoutCalculator
from .base_view import BaseViewWidget

def get_text_color_for_background(hex_color):
    """주어진 배경색(hex)에 대해 검은색과 흰색 중 더 적합한 글자색을 반환합니다."""
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        return '#000000' if luminance > 149 else '#FFFFFF'
    except Exception:
        return '#FFFFFF'

class GridContainerWidget(QWidget):
    """시간 그리드의 배경에 오늘 날짜 하이라이트 및 가로/세로선을 그리는 위젯"""
    def __init__(self, main_widget, hour_height, total_hours, padding, parent=None):
        super().__init__(parent)
        self.main_widget = main_widget
        self.hour_height = hour_height
        self.total_hours = total_hours
        self.padding = padding
        today = datetime.date.today()
        self.start_of_week = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
        self.full_view_width = self.width()

    def set_view_info(self, new_date, full_width):
        self.start_of_week = new_date - datetime.timedelta(days=(new_date.weekday() + 1) % 7)
        self.full_view_width = full_width
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        
        current_theme = self.main_widget.main_widget.settings.get("theme", "dark")
        time_grid_left = 50

        today = datetime.date.today()
        day_column_width = (self.full_view_width - time_grid_left) / 7
        if self.start_of_week <= today < self.start_of_week + datetime.timedelta(days=7):
            highlight_color = QColor("#FFFFAA") if current_theme == "light" else QColor("#4A4A26")
            day_offset = (today - self.start_of_week).days
            x = time_grid_left + day_offset * day_column_width
            painter.fillRect(int(x), 0, int(day_column_width), self.height(), highlight_color)

        line_color = QColor("#444") if current_theme == "dark" else QColor("#E0E0E0")
        painter.setPen(QPen(line_color, 1))

        for hour in range(1, self.total_hours + 1):
            y = self.padding + hour * self.hour_height
            painter.drawLine(time_grid_left, y, self.full_view_width, y)
            
        for i in range(7):
            x = time_grid_left + i * day_column_width
            painter.drawLine(int(x), 0, int(x), self.height())


class WeekViewWidget(BaseViewWidget):
    def __init__(self, main_widget):
        super().__init__(main_widget)
        self.day_labels = []
        self.hour_height = 56
        self.total_hours = 24
        self.padding = 10
        self.all_day_event_widgets = []
        self.last_mouse_pos = None

        self.initUI()

        self.timeline_timer = QTimer(self)
        self.timeline_timer.setInterval(60 * 1000)
        self.timeline_timer.timeout.connect(self.update_timeline)
        self.timeline_timer.start()
        
        self.data_manager.event_completion_changed.connect(self.redraw_events_with_current_data)

    def set_resizing(self, is_resizing):
        self.is_resizing = is_resizing
        widgets_to_manage = self.event_widgets + self.all_day_event_widgets
        if self.is_resizing:
            for widget in widgets_to_manage:
                widget.hide()
        else:
            self.redraw_events_with_current_data()

    def _get_datetime_from_pos(self, pos):
        if not self.scroll_area.geometry().contains(pos):
            return None
        
        pos_in_viewport = self.scroll_area.widget().mapFrom(self, pos)
        
        time_label_width = 50
        if pos_in_viewport.x() < time_label_width:
            return None

        days_width = self.event_container.width()
        if days_width <= 0: return None
        
        day_column_width = days_width / 7
        day_index = int((pos_in_viewport.x() - time_label_width) // day_column_width)
        if not (0 <= day_index < 7): return None

        y_pos_in_grid = pos_in_viewport.y() - self.padding
        hour = int(y_pos_in_grid / self.hour_height)
        minute = int((y_pos_in_grid % self.hour_height) / self.hour_height * 60)
        minute = round(minute / 15) * 15
        if minute == 60:
            minute, hour = 0, hour + 1
        
        if not (0 <= hour < 25): return None

        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        target_date = start_of_week + datetime.timedelta(days=day_index)
        
        if hour == 24:
            target_date += datetime.timedelta(days=1)
            hour = 0
            
        return datetime.datetime(target_date.year, target_date.month, target_date.day, hour, minute)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            target_datetime = self._get_datetime_from_pos(event.pos())
            if target_datetime:
                self.add_event_requested.emit(target_datetime)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        self.week_range_label = QLabel()
        self.week_range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        prev_button.setObjectName("nav_button")
        next_button.setObjectName("nav_button")
        self.week_range_label.setObjectName("week_label")

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
        
        self.grid_container = GridContainerWidget(self, self.hour_height, self.total_hours, self.padding)
        self.scroll_area.setWidget(self.grid_container)
        
        self.time_scale = TimeScaleWidget(self.hour_height, parent=self.grid_container)
        self.grid_container.setMinimumHeight(self.time_scale.minimumHeight())

        self.event_container = QWidget(self.grid_container)
        self.event_container.setStyleSheet("background-color: transparent;")
        
        self.timeline = QWidget(self.event_container)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")
        
        self.event_widgets, self.all_day_event_widgets = [], []
        self.last_mouse_pos = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        viewport_width = self.scroll_area.viewport().width()

        self.time_scale.setGeometry(0, 0, 50, self.grid_container.height())
        self.event_container.setGeometry(50, self.padding, viewport_width - 50, self.hour_height * 24)
        self.grid_container.set_view_info(self.current_date, self.width())
        
        self.update_timeline()
        if not self.is_resizing:
            self.redraw_events_with_current_data()

    def go_to_previous_week(self): self.current_date -= datetime.timedelta(days=7); self.refresh()
    def go_to_next_week(self): self.current_date += datetime.timedelta(days=7); self.refresh()

    def update_timeline(self):
        now = datetime.datetime.now()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)

        if start_of_week <= now.date() <= end_of_week:
            self.timeline.show()
            y = now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            self.timeline.setGeometry(0, int(y), self.event_container.width(), 2)
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
        
        widget_at_pos = self.childAt(pos)
        if widget_at_pos:
            if self.scroll_area.geometry().contains(pos):
                pos_in_viewport = self.scroll_area.widget().mapFrom(self, pos)
                for w in self.event_widgets:
                    if w.geometry().contains(pos_in_viewport) and w.isVisible():
                        target_event = w.event_data
                        break
            elif self.all_day_widget.geometry().contains(pos):
                pos_in_all_day_widget = self.all_day_widget.mapFrom(self, pos)
                for w in self.all_day_event_widgets:
                    if w.geometry().contains(pos_in_all_day_widget) and w.isVisible():
                        target_event = w.event_data
                        break

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
            target_datetime = self._get_datetime_from_pos(pos)
            if target_datetime:
                add_action = QAction("일정 추가", self)
                add_action.triggered.connect(lambda: self.add_event_requested.emit(target_datetime))
                menu.addAction(add_action)

        self.main_widget.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())

    def clear_events(self):
        for widget in self.event_widgets: widget.deleteLater()
        self.event_widgets.clear()
        for widget in self.all_day_event_widgets: widget.deleteLater()
        self.all_day_event_widgets.clear()

    def draw_events(self, time_events, start_of_week):
        parent_widget = self.event_container
        
        # event_container의 현재 너비를 기준으로 하루 너비를 계산
        day_column_width = parent_widget.width() / 7
        
        calculator = WeekLayoutCalculator(time_events, [], start_of_week, self.hour_height)
        positions = calculator.calculate_time_events(day_column_width)

        for pos_info in positions:
            event = pos_info['event']
            x, y, width, height = pos_info['rect']

            event_widget = EventLabelWidget(event, parent_widget)
            
            start_dt = datetime.datetime.fromisoformat(event['start']['dateTime'])
            end_dt = datetime.datetime.fromisoformat(event['end']['dateTime'])
            time_text = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"
            summary = event.get('summary', '')
            if 'recurrence' in event: summary = f"🔄 {summary}"
            
            event_widget.setText(f"{time_text}<br><b>{summary}</b>")
            event_widget.edit_requested.connect(self.edit_event_requested)
            
            event_color = event.get('color', '#555555')
            text_color = get_text_color_for_background(event_color)
            finished = self.data_manager.is_event_completed(event.get('id'))
            style_sheet = f"background-color: {event_color}; color: {text_color}; border-radius: 4px; padding: 4px; font-size: 8pt; text-align: left; vertical-align: top;"
            
            current_effect = event_widget.graphicsEffect()
            if finished:
                style_sheet += "text-decoration: line-through;"
                if not isinstance(current_effect, QGraphicsOpacityEffect):
                    opacity_effect = QGraphicsOpacityEffect(); opacity_effect.setOpacity(0.5); event_widget.setGraphicsEffect(opacity_effect)
            else:
                if isinstance(current_effect, QGraphicsOpacityEffect): event_widget.setGraphicsEffect(None)

            event_widget.setStyleSheet(style_sheet)
            event_widget.setWordWrap(True)
            event_widget.setAlignment(Qt.AlignmentFlag.AlignTop)
            event_widget.setGeometry(x, y, width, height)
            event_widget.show()
            self.event_widgets.append(event_widget)

    def refresh(self):
        today = datetime.date.today()
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        self.grid_container.set_view_info(self.current_date, self.width())
        
        self.week_range_label.setText(f"{start_of_week.strftime('%Y년 %m월 %d일')} - {end_of_week.strftime('%m월 %d일')}")

        current_theme = self.main_widget.settings.get("theme", "dark")
        is_dark = current_theme == "dark"
        colors = {"weekday": "#D0D0D0" if is_dark else "#222222", "saturday": "#8080FF" if is_dark else "#0000DD", "sunday": "#FF8080" if is_dark else "#DD0000", "today": "#FFFF77" if is_dark else "#A0522D" }

        days_of_week_str = ["일", "월", "화", "수", "목", "금", "토"]
        for i in range(7):
            day_date = start_of_week + datetime.timedelta(days=i)
            self.day_labels[i].setText(f"{days_of_week_str[i]} ({day_date.day})")
            
            font_color = colors['weekday']
            if day_date == today: font_color = colors['today']
            elif i == 0: font_color = colors['sunday']
            elif i == 6: font_color = colors['saturday']
            self.day_labels[i].setStyleSheet(f"color: {font_color}; font-weight: bold;")
        
        self.week_range_label.setStyleSheet(f"color: {colors['weekday']}; font-size: 16px; font-weight: bold;")

        self.redraw_events_with_current_data()
        self.update_timeline()

        if start_of_week <= today <= end_of_week:
            now = datetime.datetime.now()
            target_y = now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            scroll_offset = self.scroll_area.height() * 0.3
            self.scroll_area.verticalScrollBar().setValue(int(target_y - scroll_offset))

    def redraw_events_with_current_data(self):
        self.clear_events()
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

        self.draw_events(time_events, start_of_week)
        self.draw_all_day_events(all_day_events, start_of_week)
        self.scroll_area.widget().update()


    def draw_all_day_events(self, all_day_events, start_of_week):
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
            
            current_effect = event_label.graphicsEffect()
            if finished:
                style_sheet += "text-decoration: line-through;"
                if not isinstance(current_effect, QGraphicsOpacityEffect):
                    opacity_effect = QGraphicsOpacityEffect(); opacity_effect.setOpacity(0.5); event_label.setGraphicsEffect(opacity_effect)
            else:
                if isinstance(current_effect, QGraphicsOpacityEffect): event_label.setGraphicsEffect(None)

            event_label.setStyleSheet(style_sheet)
            
            self.all_day_layout.addWidget(event_label, lane, start_col, 1, span)
            self.all_day_event_widgets.append(event_label)
        
        new_height = max(1, num_lanes) * 25 if num_lanes > 0 else 0
        self.all_day_widget.setMinimumHeight(new_height)
        self.all_day_widget.adjustSize()