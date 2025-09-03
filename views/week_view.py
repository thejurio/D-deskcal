# views/week_view.py
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dateutil import parser as dateutil_parser # [수정] dateutil.parser 임포트
from PyQt6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, 
                             QPushButton, QToolTip, QStackedWidget)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QRectF, QSize, QEvent
from PyQt6.QtGui import QCursor, QPainter, QColor, QPen, QMouseEvent

from custom_dialogs import WeekSelectionDialog
from .widgets import draw_event
from .layout_calculator import WeekLayoutCalculator
from .base_view import BaseViewWidget
from .month_view import RotatingIcon

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, main_widget, parent=None):
        super().__init__(parent)
        self.main_widget = main_widget

    def mousePressEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

TIME_GRID_LEFT = 50
HEADER_HEIGHT = 30
ALL_DAY_LANE_HEIGHT = 25
HORIZONTAL_MARGIN = 2

class HeaderCanvas(QWidget):
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
        
        settings = self.parent_view.main_widget.settings
        is_dark = settings.get("theme", "dark") == "dark"
        start_day_of_week = settings.get("start_day_of_week", 6)
        hide_weekends = settings.get("hide_weekends", False)
        
        painter.save()
        header_bg_color = QColor("#2A2A2A") if is_dark else QColor("#F0F0F0")
        painter.fillRect(self.rect(), header_bg_color)
        
        colors = {
            "weekday": self.parent_view.weekdayColor,
            "saturday": self.parent_view.saturdayColor,
            "sunday": self.parent_view.sundayColor,
            "today": self.parent_view.todayForegroundColor
        }
        
        today = datetime.date.today()
        start_of_week = self.parent_view._get_start_of_week()

        if hide_weekends:
            days_to_display = ["월", "화", "수", "목", "금"]
            for i, day_text in enumerate(days_to_display):
                day_date = start_of_week + datetime.timedelta(days=i)
                text = f"{day_text} ({day_date.day})"
                
                font_color = colors['today'] if day_date == today else colors['weekday']
                painter.setPen(font_color)
                
                x = self.column_x_coords[i]
                width = self.column_x_coords[i+1] - x
                rect = QRectF(x, 0, width, HEADER_HEIGHT)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        else:
            if start_day_of_week == 0:
                days_of_week_str = ["월", "화", "수", "목", "금", "토", "일"]
            else:
                days_of_week_str = ["일", "월", "화", "수", "목", "금", "토"]

            for i in range(7):
                day_date = start_of_week + datetime.timedelta(days=i)
                text = f"{days_of_week_str[i]} ({day_date.day})"
                
                font_color = colors['weekday']
                if day_date == today:
                    font_color = colors['today']
                elif day_date.weekday() == 6:
                    font_color = colors['sunday']
                elif day_date.weekday() == 5:
                    font_color = colors['saturday']
                
                painter.setPen(font_color)
                
                x = self.column_x_coords[i]
                width = self.column_x_coords[i+1] - x
                rect = QRectF(x, 0, width, HEADER_HEIGHT)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        
        painter.restore()

class AllDayCanvas(QWidget):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.setMouseTracking(True)
        self.event_positions = []
        self.column_x_coords = []
        self.event_rects = []
        self.hovered_event = None
        self._pending_context_pos = None  # PyInstaller 환경 대응
        self.installEventFilter(self)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        event_under_cursor = self.get_event_at(event.pos())
        if self.hovered_event != event_under_cursor:
            self.hovered_event = event_under_cursor
            if self.hovered_event:
                self.parent_view.handle_hover_enter(self, self.hovered_event)
            else:
                self.parent_view.handle_hover_leave(self)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.parent_view.handle_hover_leave(self)
    
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

    def paintEvent(self, event):
        if not self.column_x_coords:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.event_rects.clear()

        for pos_info in self.event_positions:
            event_data, lane, start_col, span = pos_info['event'], pos_info['lane'], pos_info['start_col'], pos_info['span']
            
            if start_col + span > len(self.column_x_coords) -1: continue

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
        if not self.parent_view.main_widget.is_interaction_unlocked():
            return
            
        clicked_event = self.get_event_at(event.pos())
        if clicked_event:
            print(f"[DEBUG] AllDayCanvas mouseDoubleClickEvent: 일정 발견 - {clicked_event.get('summary', 'Unknown')} (더블클릭 - 상세보기)")
            self.parent_view.detail_requested.emit(clicked_event)

    def eventFilter(self, obj, ev):
        """PyInstaller 환경에서 안정적인 우클릭 처리"""
        if obj == self and ev.type() == QEvent.Type.MouseButtonPress:
            if isinstance(ev, QMouseEvent) and ev.button() == Qt.MouseButton.RightButton:
                print(f"[DEBUG] AllDayCanvas eventFilter: RightClick detected at {ev.pos()}")
                
                # 지연된 컨텍스트 메뉴 처리
                self._pending_context_pos = ev.pos()
                QTimer.singleShot(0, self._process_deferred_context_menu)
                return True  # 이벤트 전파 차단
        return super().eventFilter(obj, ev)

    def _process_deferred_context_menu(self):
        """PyInstaller 환경을 위한 지연된 컨텍스트 메뉴 처리"""
        if not hasattr(self, '_pending_context_pos') or self._pending_context_pos is None:
            print(f"[DEBUG] AllDayCanvas _process_deferred_context_menu: No pending position")
            return
            
        pos = self._pending_context_pos
        self._pending_context_pos = None
        
        print(f"[DEBUG] AllDayCanvas _process_deferred_context_menu: Processing at {pos}")
        
        if not self.parent_view.main_widget.is_interaction_unlocked():
            print(f"[DEBUG] AllDayCanvas _process_deferred_context_menu: Interaction locked, skipping")
            return
            
        # 이벤트 탐지
        target_event = self.get_event_at(pos)
        print(f"[DEBUG] AllDayCanvas _process_deferred_context_menu: Event found={target_event.get('summary') if target_event else 'None'}")
        
        # 날짜 정보 계산
        date_info = self.parent_view._get_date_from_pos(pos) if hasattr(self.parent_view, '_get_date_from_pos') else None
        
        # 글로벌 위치 계산
        global_pos = self.mapToGlobal(pos)
        
        # BaseView 공용 컨텍스트 메뉴 호출
        self.parent_view.show_context_menu(global_pos, target_event, date_info)


class TimeGridCanvas(QWidget):
    def __init__(self, parent_view):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.setMouseTracking(True)
        self.event_positions = []
        self.column_x_coords = []
        self.event_rects = []
        min_height = self.parent_view.total_hours * self.parent_view.hour_height
        self.setMinimumHeight(min_height)
        self.hovered_event = None
        self._pending_context_pos = None  # PyInstaller 환경 대응
        self.installEventFilter(self)
        
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        event_under_cursor = self.get_event_at(event.pos())
        if self.hovered_event != event_under_cursor:
            self.hovered_event = event_under_cursor
            if self.hovered_event:
                self.parent_view.handle_hover_enter(self, self.hovered_event)
            else:
                self.parent_view.handle_hover_leave(self)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.parent_view.handle_hover_leave(self)
    
    def set_data(self, positions, column_x_coords):
        self.event_positions = positions
        self.column_x_coords = column_x_coords
        self.update()

    def get_event_at(self, pos):
        for rect, event_data in self.event_rects:
            if rect.contains(pos):
                return event_data
        return None

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
        start_of_week = self.parent_view._get_start_of_week()
        
        hide_weekends = self.parent_view.main_widget.settings.get("hide_weekends", False)
        
        if not hide_weekends and start_of_week <= today < start_of_week + datetime.timedelta(days=7):
            highlight_color = QColor(0, 120, 215, 51) # 20% 투명도의 은은한 파란색
            day_offset = (today - start_of_week).days
            x = self.column_x_coords[day_offset]
            width = self.column_x_coords[day_offset+1] - x
            painter.fillRect(int(x), 0, int(width), self.height(), highlight_color)

        line_color = QColor("#404040") if is_dark else QColor("#D0D0D0")
        painter.setPen(QPen(line_color, 1))
        
        for hour in range(1, self.parent_view.total_hours + 1):
            y = hour * self.parent_view.hour_height
            painter.drawLine(TIME_GRID_LEFT, y, self.width(), y)
        
        for x in self.column_x_coords:
            painter.drawLine(int(x), 0, int(x), self.height())

        painter.setPen(self.parent_view.weekdayColor)
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
            
            x = rect_coords[0] + TIME_GRID_LEFT + (HORIZONTAL_MARGIN / 2)
            y = rect_coords[1]
            width = rect_coords[2] - HORIZONTAL_MARGIN
            height = rect_coords[3]
            
            rect = QRect(int(x), int(y), int(width), int(height))
            self.event_rects.append((rect, event_data))
            
            start_dt = event_data['start']['local_dt']
            end_dt = event_data['end']['local_dt']
            time_text = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"
            summary = event_data.get('summary', '')
            if 'recurrence' in event_data: summary = f"🔄 {summary}"

            is_completed = self.parent_view.data_manager.is_event_completed(event_data.get('id'))
            draw_event(painter, rect, event_data, time_text=time_text, summary_text=summary, is_completed=is_completed)
        painter.restore()


    def mouseDoubleClickEvent(self, event):
        if not self.parent_view.main_widget.is_interaction_unlocked():
            return
            
        clicked_event = self.get_event_at(event.pos())
        if clicked_event:
            print(f"[DEBUG] TimeGridCanvas mouseDoubleClickEvent: 일정 발견 - {clicked_event.get('summary', 'Unknown')} (더블클릭 - 상세보기)")
            self.parent_view.detail_requested.emit(clicked_event)
        else:
            print(f"[DEBUG] TimeGridCanvas mouseDoubleClickEvent: 빈 곳 더블클릭 - 새 일정 추가")
            target_datetime = self.parent_view._get_datetime_from_pos(event.pos())
            if target_datetime:
                self.parent_view.add_event_requested.emit(target_datetime)

    def eventFilter(self, obj, ev):
        """PyInstaller 환경에서 안정적인 우클릭 처리"""
        if obj == self and ev.type() == QEvent.Type.MouseButtonPress:
            if isinstance(ev, QMouseEvent) and ev.button() == Qt.MouseButton.RightButton:
                print(f"[DEBUG] TimeGridCanvas eventFilter: RightClick detected at {ev.pos()}")
                
                # 지연된 컨텍스트 메뉴 처리
                self._pending_context_pos = ev.pos()
                QTimer.singleShot(0, self._process_deferred_context_menu)
                return True  # 이벤트 전파 차단
        return super().eventFilter(obj, ev)

    def _process_deferred_context_menu(self):
        """PyInstaller 환경을 위한 지연된 컨텍스트 메뉴 처리"""
        if not hasattr(self, '_pending_context_pos') or self._pending_context_pos is None:
            print(f"[DEBUG] TimeGridCanvas _process_deferred_context_menu: No pending position")
            return
            
        pos = self._pending_context_pos
        self._pending_context_pos = None
        
        print(f"[DEBUG] TimeGridCanvas _process_deferred_context_menu: Processing at {pos}")
        
        if not self.parent_view.main_widget.is_interaction_unlocked():
            print(f"[DEBUG] TimeGridCanvas _process_deferred_context_menu: Interaction locked, skipping")
            return
            
        # 이벤트 탐지
        target_event = self.get_event_at(pos)
        print(f"[DEBUG] TimeGridCanvas _process_deferred_context_menu: Event found={target_event.get('summary') if target_event else 'None'}")
        
        # 날짜 정보 계산 (빈 공간인 경우)
        date_info = None
        if not target_event:
            date_info = self.parent_view._get_datetime_from_pos(pos)
        
        # 글로벌 위치 계산
        global_pos = self.mapToGlobal(pos)
        
        # BaseView 공용 컨텍스트 메뉴 호출
        self.parent_view.show_context_menu(global_pos, target_event, date_info)


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
        self.data_manager.sync_state_changed.connect(self.on_sync_state_changed)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        
        self.week_range_label = ClickableLabel(self.main_widget)
        self.week_range_label.setObjectName("week_range_label")
        self.week_range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_range_label.clicked.connect(self.open_week_selection_dialog)
        
        prev_button.setObjectName("nav_button"); next_button.setObjectName("nav_button")
        
        prev_button.clicked.connect(self.go_to_previous_week)
        next_button.clicked.connect(self.go_to_next_week)
        
        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0,0,0,0)
        center_layout.setSpacing(5)
        center_layout.addStretch(11)
        center_layout.addWidget(self.week_range_label)
        center_layout.addStretch(10)

        nav_layout.addWidget(prev_button)
        nav_layout.addLayout(center_layout)
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

        self.all_day_canvas.contextMenuEvent = self.contextMenuEvent
        self.time_grid_canvas.contextMenuEvent = self.contextMenuEvent

        self.timeline = QWidget(self.time_grid_canvas)
        self.timeline.setObjectName("timeline")
        self.timeline.setStyleSheet("background-color: #FF3333;")

    def on_sync_state_changed(self, is_syncing):
        # Sync icon removed - no visual indication during sync
        pass

    def open_week_selection_dialog(self):
        if not self.main_widget.is_interaction_unlocked():
            return
        dialog = WeekSelectionDialog(self.current_date, self, settings=self.main_widget.settings, pos=QCursor.pos())
        if dialog.exec():
            new_date = dialog.get_selected_date()
            self.date_selected.emit(new_date)

    def go_to_previous_week(self):
        if not self.main_widget.is_interaction_unlocked():
            return
        self.navigation_requested.emit("backward")

    def go_to_next_week(self):
        if not self.main_widget.is_interaction_unlocked():
            return
        self.navigation_requested.emit("forward")
            
    def contextMenuEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        super().contextMenuEvent(event)

    def _get_start_of_week(self):
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        start_day_setting = self.main_widget.settings.get("start_day_of_week", 6)
        weekday = self.current_date.weekday()

        if hide_weekends:
            return self.current_date - datetime.timedelta(days=weekday)

        if start_day_setting == 6:
            return self.current_date - datetime.timedelta(days=(weekday + 1) % 7)
        else:
            return self.current_date - datetime.timedelta(days=weekday)

    def _calculate_column_positions(self, total_width):
        num_days = 5 if self.main_widget.settings.get("hide_weekends", False) else 7
        positions = [TIME_GRID_LEFT]
        grid_width = total_width - TIME_GRID_LEFT
        
        base_col_width = grid_width // num_days
        remainder = grid_width % num_days
        
        current_x = TIME_GRID_LEFT
        for i in range(num_days):
            col_width = base_col_width + (1 if i < remainder else 0)
            current_x += col_width
            positions.append(current_x)
            
        return positions

    def _get_datetime_from_pos(self, pos):
        column_xs = self._calculate_column_positions(self.time_grid_canvas.width())
        if not (column_xs[0] <= pos.x() < column_xs[-1]): return None
        
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        
        col_index = 0
        for i in range(len(column_xs) - 1):
            if column_xs[i] <= pos.x() < column_xs[i+1]:
                col_index = i
                break
        
        start_of_week = self._get_start_of_week()
        if hide_weekends:
            target_date = start_of_week + datetime.timedelta(days=col_index)
        else:
            target_date = start_of_week + datetime.timedelta(days=col_index)

        hour = int(pos.y() / self.hour_height)
        minute = int((pos.y() % self.hour_height) / self.hour_height * 60)
        minute = round(minute / 15) * 15
        if minute == 60: minute, hour = 0, hour + 1
        
        if not (0 <= hour < 25): return None
        if hour == 24: target_date += datetime.timedelta(days=1); hour = 0
            
        return datetime.datetime(target_date.year, target_date.month, target_date.day, hour, minute)

    def set_tooltips_enabled(self, enabled):
        self.tooltips_enabled = enabled
        if not enabled:
            QToolTip.hideText()

    def update_timeline(self):
        try:
            user_tz = ZoneInfo(self.main_widget.settings.get("user_timezone", "UTC"))
        except ZoneInfoNotFoundError:
            user_tz = ZoneInfo("UTC")
        now = datetime.datetime.now(user_tz)
        today = now.date()
        start_of_week = self._get_start_of_week()
        
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        if hide_weekends and today.weekday() >= 5:
            self.timeline.hide()
            return

        if start_of_week <= today < start_of_week + datetime.timedelta(days=7):
            self.timeline.show()
            
            column_xs = self._calculate_column_positions(self.time_grid_canvas.width())
            
            if hide_weekends:
                day_offset = today.weekday()
            else:
                day_offset = (today - start_of_week).days

            if day_offset < len(column_xs) -1:
                x = column_xs[day_offset]
                width = column_xs[day_offset + 1] - x
                y = now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
                self.timeline.setGeometry(int(x), int(y), int(width), 2)
            else:
                self.timeline.hide()
        else:
            self.timeline.hide()

    def refresh(self):
        start_of_week = self._get_start_of_week()
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        num_days = 5 if hide_weekends else 7
        end_of_week = start_of_week + datetime.timedelta(days=num_days - 1)
        
        first_day_of_month = start_of_week.replace(day=1)
        first_day_of_cal_week_start = first_day_of_month - datetime.timedelta(days=first_day_of_month.weekday())
        week_number = (start_of_week - first_day_of_cal_week_start).days // 7 + 1

        main_text = f"{start_of_week.month}월 {week_number}주"
        sub_text = f"({start_of_week.strftime('%Y.%m.%d')} - {end_of_week.strftime('%Y.%m.%d')})"
        
        label_html = f"""
        <p style="font-size: 16px; font-weight: bold; margin-bottom: -2px;">{main_text}</p>
        <p style="font-size: 10px; margin-top: 0px;">{sub_text}</p>
        """
        self.week_range_label.setText(label_html)

        self.redraw_events_with_current_data()
        self.update_timeline()

        today = datetime.date.today()
        if start_of_week <= today <= end_of_week:
            try:
                user_tz = ZoneInfo(self.main_widget.settings.get("user_timezone", "UTC"))
            except ZoneInfoNotFoundError:
                user_tz = ZoneInfo("UTC")
            now = datetime.datetime.now(user_tz)
            target_y = now.hour * self.hour_height + (now.minute / 60.0 * self.hour_height)
            scroll_offset = self.scroll_area.height() * 0.3
            self.scroll_area.verticalScrollBar().setValue(int(target_y - scroll_offset))

    def redraw_events_with_current_data(self):
        start_of_week = self._get_start_of_week()
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        num_days = 5 if hide_weekends else 7

        time_events, all_day_events = self.data_manager.get_classified_events_for_week(start_of_week)

        calculator = WeekLayoutCalculator(time_events, all_day_events, start_of_week, self.hour_height)
        
        all_day_positions, num_lanes = calculator.calculate_all_day_events()
        
        column_xs = self._calculate_column_positions(self.time_grid_canvas.width())
        
        day_width = (self.time_grid_canvas.width() - TIME_GRID_LEFT) / num_days
        time_event_positions = calculator.calculate_time_events(day_width)
        
        self.header_canvas.set_data(column_xs)
        self.all_day_canvas.set_data(all_day_positions, num_lanes, column_xs)
        self.time_grid_canvas.set_data(time_event_positions, column_xs)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.redraw_events_with_current_data()
        self.update_timeline()
        
    def on_data_updated(self, year, month):
        start_of_week, end_of_week = self.get_current_view_period()
        if start_of_week.year == year and start_of_week.month == month or \
           end_of_week.year == year and end_of_week.month == month:
            self.redraw_events_with_current_data()
            
    def get_current_view_period(self):
        start_of_week = self._get_start_of_week()
        num_days = 5 if self.main_widget.settings.get("hide_weekends", False) else 7
        end_of_week = start_of_week + datetime.timedelta(days=num_days - 1)
        return start_of_week, end_of_week