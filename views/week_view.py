# views/week_view.py
import datetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QMenu, QToolTip
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QRectF
from PyQt6.QtGui import QAction, QCursor, QPainter, QColor, QPen, QFontMetrics

from custom_dialogs import WeekSelectionDialog
from .widgets import draw_event
from .layout_calculator import WeekLayoutCalculator
from .base_view import BaseViewWidget

class ClickableLabel(QLabel):
    """클릭 이벤트를 처리할 수 있는 커스텀 QLabel"""
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

# 레이아웃을 위한 상수 정의
TIME_GRID_LEFT = 50
HEADER_HEIGHT = 30
ALL_DAY_LANE_HEIGHT = 25
HORIZONTAL_MARGIN = 8

class HeaderCanvas(QWidget):
    """요일 헤더를 그리는 위젯"""
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.column_x_coords = []
        self.setFixedHeight(HEADER_HEIGHT)

    def set_data(self, column_x_coords):
        self.column_x_coords = column_x_coords
        self.update()

    def paintEvent(self, event):
        if not self.column_x_coords:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        is_dark = self.parent_view.main_widget.settings.get("theme", "dark") == "dark"
        
        painter.save()
        header_bg_color = QColor("#2A2A2A") if is_dark else QColor("#F0F0F0")
        painter.fillRect(self.rect(), header_bg_color)
        
        colors = {"weekday": "#D0D0D0" if is_dark else "#222222", "saturday": "#8080FF" if is_dark else "#0000DD", "sunday": "#FF8080" if is_dark else "#DD0000", "today": "#FFFF77" if is_dark else "#A0522D" }
        days_of_week_str = ["일", "월", "화", "수", "목", "금", "토"]
        today = datetime.date.today()
        start_of_week = self.parent_view.current_date - datetime.timedelta(days=(self.parent_view.current_date.weekday() + 1) % 7)

        for i in range(7):
            day_date = start_of_week + datetime.timedelta(days=i)
            text = f"{days_of_week_str[i]} ({day_date.day})"
            
            font_color = colors['weekday']
            if day_date == today: font_color = colors['today']
            elif i == 0: font_color = colors['sunday']
            elif i == 6: font_color = colors['saturday']
            
            painter.setPen(QColor(font_color))
            
            x = self.column_x_coords[i]
            width = self.column_x_coords[i+1] - x
            rect = QRectF(x, 0, width, HEADER_HEIGHT)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

class AllDayCanvas(QWidget):
    """종일 이벤트를 그리는 위젯"""
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.setMouseTracking(True)
        self.event_positions = []
        self.column_x_coords = []
        self.event_rects = []
        self.hovered_event_id = None

    def set_data(self, positions, num_lanes, column_x_coords):
        self.event_positions = positions
        self.column_x_coords = column_x_coords
        height = num_lanes * ALL_DAY_LANE_HEIGHT + 5 if num_lanes > 0 else 0
        self.setFixedHeight(height)
        self.setVisible(height > 0)
        self.update()

    def get_event_at(self, pos):
        for rect, event_data in self.event_rects:
            if rect.contains(pos):
                return event_data
        return None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        event_under_mouse = self.get_event_at(event.pos())
        current_event_id = event_under_mouse.get('id') if event_under_mouse else None
        
        if self.hovered_event_id != current_event_id:
            self.hovered_event_id = current_event_id
            if current_event_id:
                QToolTip.showText(QCursor.pos(), event_under_mouse.get('summary', ''))
            else:
                QToolTip.hideText()

    def paintEvent(self, event):
        if not self.column_x_coords:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.event_rects.clear()

        for pos_info in self.event_positions:
            event_data, lane, start_col, span = pos_info['event'], pos_info['lane'], pos_info['start_col'], pos_info['span']
            
            start_x = self.column_x_coords[start_col]
            end_x = self.column_x_coords[start_col + span]
            
            x = start_x + (HORIZONTAL_MARGIN / 2)
            y = lane * ALL_DAY_LANE_HEIGHT + 2
            width = (end_x - start_x) - HORIZONTAL_MARGIN
            height = ALL_DAY_LANE_HEIGHT - 4
            
            rect = QRect(int(x), int(y), int(width), int(height))
            self.event_rects.append((rect, event_data))
            
            summary = event_data.get('summary', '')
            if 'recurrence' in event_data: summary = f"🔄 {summary}"
            
            is_completed = self.parent_view.data_manager.is_event_completed(event_data.get('id'))
            draw_event(painter, rect, event_data, time_text="", summary_text=summary, is_completed=is_completed)

    def mouseDoubleClickEvent(self, event):
        clicked_event = self.get_event_at(event.pos())
        if clicked_event:
            self.parent_view.edit_event_requested.emit(clicked_event)

    def contextMenuEvent(self, event):
        clicked_event = self.get_event_at(event.pos())
        self.parent_view.show_context_menu(event.globalPos(), clicked_event)


class TimeGridCanvas(QWidget):
    """시간 그리드와 시간별 이벤트를 그리는 위젯"""
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.setMouseTracking(True)
        self.event_positions = []
        self.column_x_coords = []
        self.event_rects = []
        self.hovered_event_id = None
        min_height = self.parent_view.total_hours * self.parent_view.hour_height
        self.setMinimumHeight(min_height)

    def set_data(self, positions, column_x_coords):
        self.event_positions = positions
        self.column_x_coords = column_x_coords
        self.update()

    def get_event_at(self, pos):
        for rect, event_data in self.event_rects:
            if rect.contains(pos):
                return event_data
        return None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        event_under_mouse = self.get_event_at(event.pos())
        current_event_id = event_under_mouse.get('id') if event_under_mouse else None
        
        if self.hovered_event_id != current_event_id:
            self.hovered_event_id = current_event_id
            if current_event_id:
                QToolTip.showText(QCursor.pos(), event_under_mouse.get('summary', ''))
            else:
                QToolTip.hideText()

    def paintEvent(self, event):
        if not self.column_x_coords:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_dark = self.parent_view.main_widget.settings.get("theme", "dark") == "dark"
        self.event_rects.clear()

        self._draw_time_grid(painter, is_dark)
        self._draw_timed_events(painter)

    def _draw_time_grid(self, painter, is_dark):
        painter.save()
        today = datetime.date.today()
        start_of_week = self.parent_view.current_date - datetime.timedelta(days=(self.parent_view.current_date.weekday() + 1) % 7)

        if start_of_week <= today < start_of_week + datetime.timedelta(days=7):
            highlight_color = QColor("#FFFFAA") if not is_dark else QColor("#4A4A26")
            day_offset = (today - start_of_week).days
            x = self.column_x_coords[day_offset]
            width = self.column_x_coords[day_offset+1] - x
            painter.fillRect(int(x), 0, int(width), self.height(), highlight_color)

        line_color = QColor("#444") if is_dark else QColor("#E0E0E0")
        painter.setPen(QPen(line_color, 1))
        
        for hour in range(1, self.parent_view.total_hours + 1):
            y = hour * self.parent_view.hour_height
            painter.drawLine(TIME_GRID_LEFT, y, self.width(), y)
        
        for x in self.column_x_coords:
            painter.drawLine(int(x), 0, int(x), self.height())

        text_color = QColor("#D0D0D0") if is_dark else QColor("#222222")
        painter.setPen(text_color)
        for hour in range(self.parent_view.total_hours + 1):
            y = hour * self.parent_view.hour_height
            rect = QRect(0, y - self.parent_view.hour_height // 2, 45, self.parent_view.hour_height)
            painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{hour:02d}:00")
        painter.restore()

    def _draw_timed_events(self, painter):
        painter.save()
        for pos_info in self.event_positions:
            event_data = pos_info['event']
            rect_coords = pos_info['rect']
            
            # This calculation might need adjustment if layout_calculator changes
            day_column_width = (self.width() - TIME_GRID_LEFT) / 7
            
            x = rect_coords[0] + TIME_GRID_LEFT + (HORIZONTAL_MARGIN / 2)
            y = rect_coords[1]
            width = rect_coords[2] - HORIZONTAL_MARGIN
            height = rect_coords[3]
            
            rect = QRect(int(x), int(y), int(width), int(height))
            self.event_rects.append((rect, event_data))
            
            start_dt = datetime.datetime.fromisoformat(event_data['start']['dateTime'])
            end_dt = datetime.datetime.fromisoformat(event_data['end']['dateTime'])
            time_text = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"
            summary = event_data.get('summary', '')
            if 'recurrence' in event_data: summary = f"🔄 {summary}"

            is_completed = self.parent_view.data_manager.is_event_completed(event_data.get('id'))
            draw_event(painter, rect, event_data, time_text=time_text, summary_text=summary, is_completed=is_completed)
        painter.restore()

    def mouseDoubleClickEvent(self, event):
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
        self.hour_height = 56
        self.total_hours = 24
        
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
        
        # ClickableLabel 사용
        self.week_range_label = ClickableLabel()
        self.week_range_label.setObjectName("week_range_label")
        self.week_range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_range_label.clicked.connect(self.open_week_selection_dialog)
        
        prev_button.setObjectName("nav_button"); next_button.setObjectName("nav_button")
        
        prev_button.clicked.connect(self.go_to_previous_week)
        next_button.clicked.connect(self.go_to_next_week)
        
        nav_layout.addWidget(prev_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.week_range_label)
        nav_layout.addStretch(1)
        nav_layout.addWidget(next_button)
        main_layout.addLayout(nav_layout)

        self.header_canvas = HeaderCanvas(self)
        self.all_day_canvas = AllDayCanvas(self)
        main_layout.addWidget(self.header_canvas)
        main_layout.addWidget(self.all_day_canvas)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("week_scroll_area")
        main_layout.addWidget(self.scroll_area)
        
        self.time_grid_canvas = TimeGridCanvas(self)
        self.scroll_area.setWidget(self.time_grid_canvas)

        self.timeline = QWidget(self.time_grid_canvas)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")

    def open_week_selection_dialog(self):
        dialog = WeekSelectionDialog(self.current_date, self, settings=self.main_widget.settings, pos=QCursor.pos())
        if dialog.exec():
            self.current_date = dialog.get_selected_date()
            self.refresh()

    def go_to_previous_week(self): self.current_date -= datetime.timedelta(days=7); self.refresh()
    def go_to_next_week(self): self.current_date += datetime.timedelta(days=7); self.refresh()

    def _calculate_column_positions(self, total_width):
        """정수 기반으로 7개 요일 칸의 x좌표를 계산하여 누적 오차를 방지합니다."""
        positions = [TIME_GRID_LEFT]
        grid_width = total_width - TIME_GRID_LEFT
        
        base_col_width = grid_width // 7
        remainder = grid_width % 7
        
        current_x = TIME_GRID_LEFT
        for i in range(7):
            col_width = base_col_width + (1 if i < remainder else 0)
            current_x += col_width
            positions.append(current_x)
            
        return positions

    def _get_datetime_from_pos(self, pos):
        column_xs = self._calculate_column_positions(self.time_grid_canvas.width())
        if not (column_xs[0] <= pos.x() < column_xs[7]): return None
        
        day_index = 0
        for i in range(7):
            if column_xs[i] <= pos.x() < column_xs[i+1]:
                day_index = i
                break
        
        hour = int(pos.y() / self.hour_height)
        minute = int((pos.y() % self.hour_height) / self.hour_height * 60)
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
            clicked_widget = self.childAt(self.mapFromGlobal(global_pos))
            if isinstance(clicked_widget, (TimeGridCanvas, AllDayCanvas)):
                 local_pos = clicked_widget.mapFromGlobal(global_pos)
                 if isinstance(clicked_widget, TimeGridCanvas):
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
            y = now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            self.timeline.setGeometry(TIME_GRID_LEFT, int(y), self.time_grid_canvas.width() - TIME_GRID_LEFT, 2)
        else:
            self.timeline.hide()

    def refresh(self):
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        end_of_week = start_of_week + datetime.timedelta(days=6)
        
        # 주차 계산 (해당 월의 몇 번째 주인지)
        first_day_of_month = start_of_week.replace(day=1)
        # 해당 월의 첫 번째 일요일 찾기
        first_sunday = first_day_of_month - datetime.timedelta(days=(first_day_of_month.weekday() + 1) % 7)
        week_number = (start_of_week - first_sunday).days // 7 + 1

        # HTML을 사용하여 레이블 텍스트 설정
        main_text = f"{start_of_week.month}월 {week_number}주"
        sub_text = f"({start_of_week.strftime('%Y.%m.%d')} - {end_of_week.strftime('%Y.%m.%d')})"
        
        is_dark = self.main_widget.settings.get("theme", "dark") == "dark"
        text_color = "#D0D0D0" if is_dark else "#222222"
        
        label_html = f"""
        <p style="font-size: 16px; font-weight: bold; color: {text_color}; margin-bottom: -2px;">{main_text}</p>
        <p style="font-size: 10px; color: {text_color}; margin-top: 0px;">{sub_text}</p>
        """
        self.week_range_label.setText(label_html)

        self.redraw_events_with_current_data()
        self.update_timeline()

        today = datetime.date.today()
        if start_of_week <= today <= end_of_week:
            now = datetime.datetime.now()
            target_y = now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            scroll_offset = self.scroll_area.height() * 0.3
            self.scroll_area.verticalScrollBar().setValue(int(target_y - scroll_offset))

    def redraw_events_with_current_data(self):
        start_of_week = self.current_date - datetime.timedelta(days=(self.current_date.weekday() + 1) % 7)
        
        week_events = self.data_manager.get_events_for_period(start_of_week, start_of_week + datetime.timedelta(days=6))
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in week_events if event.get('calendarId') in selected_ids]

        time_events, all_day_events = [], []
        for e in filtered_events:
            is_all_day_native = 'date' in e['start']
            start_str = e['start'].get('dateTime', e['start'].get('date'))
            end_str = e['end'].get('dateTime', e['end'].get('date'))
            start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', ''))
            end_dt = datetime.datetime.fromisoformat(end_str.replace('Z', ''))
            duration_seconds = (end_dt - start_dt).total_seconds()
            is_multi_day = duration_seconds >= 86400
            is_exactly_24h_midnight = duration_seconds == 86400 and start_dt.time() == datetime.time(0, 0) and end_dt.time() == datetime.time(0, 0)

            if is_all_day_native or (is_multi_day and not is_exactly_24h_midnight):
                all_day_events.append(e)
            elif 'dateTime' in e['start']:
                time_events.append(e)

        calculator = WeekLayoutCalculator(time_events, all_day_events, start_of_week, self.hour_height)
        
        all_day_positions, num_lanes = calculator.calculate_all_day_events()
        
        # 정확한 칸 위치 계산
        column_xs = self._calculate_column_positions(self.time_grid_canvas.width())
        
        # layout_calculator가 이 정보를 알도록 수정이 필요할 수 있음
        # 지금은 TimeGridCanvas에서만 이 정보를 사용
        time_event_positions = calculator.calculate_time_events((self.time_grid_canvas.width() - TIME_GRID_LEFT) / 7)
        
        self.header_canvas.set_data(column_xs)
        self.all_day_canvas.set_data(all_day_positions, num_lanes, column_xs)
        self.time_grid_canvas.set_data(time_event_positions, column_xs)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.redraw_events_with_current_data()
        self.update_timeline()
        
    def apply_settings(self):
        super().apply_settings()
        self.refresh()
        
        current_theme = self.main_widget.settings.get("theme", "dark")
        if current_theme == "dark":
            QToolTip.setStyleSheet("QToolTip { background-color: #2E2E2E; color: #E0E0E0; border: 1px solid #555555; }")
        else:
            QToolTip.setStyleSheet("QToolTip { background-color: #FFFFE0; color: #000000; border: 1px solid #AAAAAA; }")
        
        nav_style = self.main_widget.theme_manager.get_nav_button_style()
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == "nav_button":
                btn.setStyleSheet(nav_style)
        
        scroll_area_style = self.main_widget.theme_manager.get_scroll_area_style()
        self.scroll_area.setStyleSheet(scroll_area_style)
        
        self.timeline.setStyleSheet(f"background-color: {self.main_widget.theme_manager.get_timeline_color()};")
        self.header_canvas.update()
        self.all_day_canvas.update()
        self.time_grid_canvas.update()