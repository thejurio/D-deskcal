# views/month_view.py
import datetime
import calendar
from collections import defaultdict
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QGraphicsOpacityEffect, QMenu, QToolTip
from PyQt6.QtGui import QFont, QCursor, QPainter, QColor, QPen, QTextOption, QAction
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QRectF
from custom_dialogs import NewDateSelectionDialog, MoreEventsDialog
from .widgets import get_text_color_for_background, draw_event
from .layout_calculator import MonthLayoutCalculator
from .base_view import BaseViewWidget


class DayCellWidget(QWidget):
    add_event_requested = pyqtSignal(datetime.date)
    edit_event_requested = pyqtSignal(dict)
    more_events_requested = pyqtSignal(datetime.date, list)

    def __init__(self, date_obj, parent_view=None):
        super().__init__(parent_view)
        self.date_obj = date_obj
        self.parent_view = parent_view
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def mouseDoubleClickEvent(self, event):
        # MonthViewWidget에서 직접 처리하므로, 여기서는 단순 요청만 보냄
        self.add_event_requested.emit(self.date_obj)


class MonthViewWidget(BaseViewWidget):
    def __init__(self, main_widget):
        super().__init__(main_widget)
        self.date_to_cell_map = {}
        self.event_rects = []  # (QRect, event_data) 튜플 저장
        self.more_buttons = {} # {date: QRect} 딕셔너리 저장
        self.hovered_event_id = None
        self.setMouseTracking(True)
        self.initUI()
        self.refresh()
        self.data_manager.event_completion_changed.connect(self.redraw_events_with_current_data)

    def on_data_updated(self, year, month):
        if year == self.current_date.year and month == self.current_date.month:
            self.redraw_events_with_current_data()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        self.month_button = QPushButton()
        self.month_button.clicked.connect(self.open_date_selection_dialog)
        prev_button.clicked.connect(self.go_to_previous_month)
        next_button.clicked.connect(self.go_to_next_month)
        nav_layout.addWidget(prev_button); nav_layout.addStretch(1); nav_layout.addWidget(self.month_button); nav_layout.addStretch(1); nav_layout.addWidget(next_button)
        main_layout.addLayout(nav_layout)
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(0)
        main_layout.addLayout(self.calendar_grid)

    def open_date_selection_dialog(self):
        dialog = NewDateSelectionDialog(self.current_date, self, settings=self.main_widget.settings, pos=QCursor.pos())
        if dialog.exec():
            year, month = dialog.get_selected_date()
            new_date = self.current_date.replace(year=year, month=month, day=1)
            self.date_selected.emit(new_date)

    def show_more_events_popup(self, date_obj, events):
        dialog = MoreEventsDialog(date_obj, events, self, settings=self.main_widget.settings, pos=QCursor.pos(), data_manager=self.data_manager)
        dialog.edit_requested.connect(self.edit_event_requested)
        dialog.delete_requested.connect(self.confirm_delete_event)
        dialog.exec()

    def refresh(self):
        if self.is_resizing:
            return
        self.draw_grid(self.current_date.year, self.current_date.month)

    def draw_grid(self, year, month):
        # 1. 설정값 가져오기
        start_day_of_week = self.main_widget.settings.get("start_day_of_week", 6) # 6=일, 0=월
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        
        # 2. 기존 위젯 정리
        current_theme = self.main_widget.settings.get("theme", "dark")
        is_dark = current_theme == "dark"
        colors = {"weekday": "#D0D0D0" if is_dark else "#222222", "saturday": "#8080FF" if is_dark else "#0000DD", "sunday": "#FF8080" if is_dark else "#DD0000", "today_bg": "#444422" if is_dark else "#FFFFAA", "today_fg": "#FFFF77" if is_dark else "#A0522D", "other_month": "#777777" if is_dark else "#AAAAAA"}
        self.month_button.setStyleSheet(f"color: {colors['weekday']}; background-color: transparent; border: none; font-size: 16px; font-weight: bold;")
        while self.calendar_grid.count():
            child = self.calendar_grid.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.date_to_cell_map.clear()
        self.month_button.setText(f"{year}년 {month}월")

        # 3. 요일 헤더 생성
        if start_day_of_week == 0: # 월요일 시작
            days_of_week_labels = ["월", "화", "수", "목", "금", "토", "일"]
            weekend_indices = [5, 6]
        else: # 일요일 시작
            days_of_week_labels = ["일", "월", "화", "수", "목", "금", "토"]
            weekend_indices = [0, 6]

        col_idx = 0
        for i, day in enumerate(days_of_week_labels):
            if hide_weekends and i in weekend_indices:
                continue
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = colors['sunday'] if i == weekend_indices[0] else (colors['saturday'] if i == weekend_indices[1] else colors['weekday'])
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.calendar_grid.addWidget(label, 0, col_idx)
            col_idx += 1

        # 4. 날짜 셀 생성
        cal = calendar.Calendar(firstweekday=start_day_of_week)
        month_calendar = cal.monthdayscalendar(year, month)
        today = datetime.date.today()
        
        def create_day_cell(date_obj):
            day_widget = DayCellWidget(date_obj, self)
            day_widget.add_event_requested.connect(self.add_event_requested)
            day_widget.edit_event_requested.connect(self.edit_event_requested)
            day_widget.more_events_requested.connect(self.show_more_events_popup)
            return day_widget

        for week_index, week in enumerate(month_calendar):
            col_idx = 0
            for day_of_week, day in enumerate(week):
                # day_of_week는 0=월 ~ 6=일 (Calendar 객체 기준)
                # 주말 숨기기 옵션이 켜져 있으면 주말(토,일)은 건너뜀
                # calendar 모듈에서 월요일 시작 시: 토=5, 일=6 / 일요일 시작 시: 토=5, 일=6 이 아님.
                # cal.iterweekdays()를 통해 확인 필요. 월(0)...일(6) 순서 고정.
                # 따라서 토요일은 5, 일요일은 6
                if hide_weekends and day_of_week in [5, 6]:
                    continue
                
                if day == 0:
                    # 빈 칸도 그려야 레이아웃이 맞음
                    self.calendar_grid.addWidget(QWidget(), week_index + 1, col_idx)
                    col_idx += 1
                    continue

                current_day_obj = datetime.date(year, month, day)
                day_widget = create_day_cell(current_day_obj)
                day_label = QLabel(str(day))
                day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                day_widget.layout.addWidget(day_label)
                
                font_color = colors['weekday']
                # 시작 요일에 따라 주말 인덱스가 달라짐
                if (start_day_of_week == 6 and day_of_week == 6) or (start_day_of_week == 0 and day_of_week == 5): # 토요일
                    font_color = colors['saturday']
                elif (start_day_of_week == 6 and day_of_week == 0) or (start_day_of_week == 0 and day_of_week == 6): # 일요일
                    font_color = colors['sunday']

                day_label.setStyleSheet(f"color: {font_color}; background-color: transparent;")
                if current_day_obj == today:
                    day_widget.setStyleSheet(f"background-color: {colors['today_bg']};")
                    day_label.setStyleSheet(f"color: {colors['today_fg']}; font-weight: bold; background-color: transparent;")
                
                self.calendar_grid.addWidget(day_widget, week_index + 1, col_idx)
                self.date_to_cell_map[current_day_obj] = day_widget
                col_idx += 1

        # 이전/다음 달 날짜는 주말 숨기기 시 표시하지 않음 (단순화)
        if not hide_weekends:
            # ... (이전/다음 달 날짜 채우는 로직은 여기에 위치) ...
            pass # 현재 구현에서는 생략

        for i in range(1, self.calendar_grid.rowCount()): self.calendar_grid.setRowStretch(i, 1)
        for i in range(self.calendar_grid.columnCount()): self.calendar_grid.setColumnStretch(i, 1)
        QTimer.singleShot(0, self.redraw_events_with_current_data)

    def redraw_events_with_current_data(self):
        all_events = self.data_manager.get_events(self.current_date.year, self.current_date.month)
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in all_events if event.get('calendarId') in selected_ids]
        
        # 1. 레이아웃 계산
        calculator = MonthLayoutCalculator(filtered_events, self.date_to_cell_map.keys())
        event_positions, _ = calculator.calculate()

        # 2. 날짜별로 이벤트 레이아웃 정보 그룹화
        events_by_day = defaultdict(list)
        y_offset, event_height, event_spacing = 25, 20, 2

        for pos_info in event_positions:
            event = pos_info['event']
            y_level = pos_info['y_level']
            
            for day in pos_info['days_in_view']:
                start_cell_info = self.date_to_cell_map.get(day)
                if not start_cell_info: continue
                
                # 셀 안에서의 y 좌표 계산
                y = y_offset + (y_level * (event_height + event_spacing))
                
                # 여러 날에 걸친 이벤트의 스타일 정보 계산 (왼쪽/오른쪽 모서리 둥글게)
                is_start = day == pos_info['start_date']
                is_end = day == pos_info['end_date']
                style_info = {'is_start': is_start, 'is_end': is_end}
                
                rect = QRect(0, y, start_cell_info.width(), event_height) # DayCellWidget 내부 좌표
                events_by_day[day].append((rect, event, style_info))
        
        # 3. 각 DayCellWidget에 그릴 데이터 전달 -> 이제 MonthViewWidget이 직접 그림
        self.update() # paintEvent 호출

    def redraw_events_with_current_data(self):
        # 데이터 변경 시 전체 그리드를 다시 만들 필요 없이, paintEvent만 다시 호출합니다.
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.event_rects.clear()
        self.more_buttons.clear()

        all_events = self.data_manager.get_events(self.current_date.year, self.current_date.month)
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in all_events if event.get('calendarId') in selected_ids]
        
        if not self.date_to_cell_map:
            return

        calculator = MonthLayoutCalculator(filtered_events, self.date_to_cell_map.keys())
        event_positions, _ = calculator.calculate()

        events_by_day = defaultdict(list)
        y_offset, event_height, event_spacing = 25, 20, 2

        for pos_info in event_positions:
            event_data = pos_info['event']
            y_level = pos_info['y_level']
            
            for day in pos_info['days_in_view']:
                cell_widget = self.date_to_cell_map.get(day)
                if not cell_widget: continue
                
                y = y_offset + (y_level * (event_height + event_spacing))
                
                # MonthViewWidget 좌표계로 변환
                cell_pos = cell_widget.pos()
                global_rect = QRect(cell_pos.x(), cell_pos.y() + y, cell_widget.width(), event_height)
                
                is_start = day == pos_info['start_date']
                is_end = day == pos_info['end_date']
                style_info = {'is_start': is_start, 'is_end': is_end}
                
                events_by_day[day].append((global_rect, event_data, style_info))

        for date, cell_widget in self.date_to_cell_map.items():
            if not cell_widget.isVisible(): continue
            
            max_slots = (cell_widget.height() - y_offset) // (event_height + event_spacing)
            max_visible_y_level = max(0, max_slots - 1)
            
            visible_events, more_events_data = [], []
            sorted_day_events = sorted(events_by_day.get(date, []), key=lambda x: x[0].y())
            
            y_levels_on_day = set()
            for rect, event_data, style in sorted_day_events:
                y_level = (rect.y() - cell_widget.y() - y_offset) // (event_height + event_spacing)
                if y_level < max_visible_y_level:
                    visible_events.append((rect, event_data, style))
                    y_levels_on_day.add(y_level)
                else:
                    more_events_data.append(event_data)

            for rect, event_data, style in visible_events:
                summary = event_data.get('summary', '')
                if 'recurrence' in event_data: summary = f"🔄 {summary}"
                
                adjusted_rect = rect.adjusted(2, 0, -2, 0)
                is_completed = self.data_manager.is_event_completed(event_data.get('id'))
                
                # ▼▼▼ [수정] 그리는 순간에 최신 색상 가져와 적용 ▼▼▼
                event_data_copy = event_data.copy()
                event_data_copy['color'] = self.data_manager.get_color_for_calendar(event_data.get('calendarId'))
                
                draw_event(painter, adjusted_rect, event_data_copy, time_text=None, summary_text=summary, is_completed=is_completed)
                # ▲▲▲ 여기까지 수정 ▲▲▲
                self.event_rects.append((rect, event_data))

            if more_events_data:
                y = y_offset + (max_visible_y_level * (event_height + event_spacing))
                cell_pos = cell_widget.pos()
                more_rect = QRect(cell_pos.x(), cell_pos.y() + y, cell_widget.width(), event_height)
                
                font = painter.font(); font.setBold(True); painter.setFont(font)
                painter.setPen(QColor("#a0c4ff"))
                painter.drawText(more_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"  + {len(more_events_data)}개 더보기")
                self.more_buttons[date] = (more_rect, more_events_data)

    def get_event_at(self, pos):
        for rect, event_data in self.event_rects:
            if rect.contains(pos):
                return event_data
        return None

    def mouseDoubleClickEvent(self, event):
        clicked_event = self.get_event_at(event.pos())
        if clicked_event:
            self.edit_event_requested.emit(clicked_event)
        else:
            target_widget = self.childAt(event.pos())
            if isinstance(target_widget, DayCellWidget):
                self.add_event_requested.emit(target_widget.date_obj)

    def mousePressEvent(self, event):
        for date, (rect, data) in self.more_buttons.items():
            if rect.contains(event.pos()):
                self.show_more_events_popup(date, data)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        event_under_mouse = self.get_event_at(event.pos())
        current_event_id = event_under_mouse.get('id') if event_under_mouse else None
        
        if self.hovered_event_id != current_event_id:
            self.hovered_event_id = current_event_id
            if current_event_id:
                QToolTip.showText(QCursor.pos(), event_under_mouse.get('summary', ''))
            else:
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def go_to_previous_month(self):
        self.navigation_requested.emit("backward")

    def go_to_next_month(self):
        self.navigation_requested.emit("forward")

    def contextMenuEvent(self, event):
        pos = event.pos()
        target_event = self.get_event_at(pos)
        
        date_info = None
        if not target_event:
            target_widget = self.childAt(pos)
            if isinstance(target_widget, DayCellWidget):
                date_info = target_widget.date_obj

        self.show_context_menu(event.globalPos(), target_event, date_info)