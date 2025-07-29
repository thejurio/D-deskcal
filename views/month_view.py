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
        self.event_layout = [] # (QRect, event_data, style_info) 튜플 저장
        self.more_events_data = []
        self.more_button_rect = QRect()
        self.hovered_event_id = None
        self.setMouseTracking(True)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def set_events(self, event_layout_data, more_events_data):
        self.event_layout = event_layout_data
        self.more_events_data = more_events_data
        self.update()

    def get_event_at(self, pos):
        for rect, event_data, _ in self.event_layout:
            if rect.contains(pos):
                return event_data
        return None

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            clicked_event = self.get_event_at(event.pos())
            if clicked_event:
                self.edit_event_requested.emit(clicked_event)
            else:
                self.add_event_requested.emit(self.date_obj)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            if self.more_button_rect.contains(event.pos()):
                self.more_events_requested.emit(self.date_obj, self.more_events_data)
                
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        event_under_mouse = self.get_event_at(event.pos())
        
        if event_under_mouse:
            event_id = event_under_mouse.get('id')
            if self.hovered_event_id != event_id:
                self.hovered_event_id = event_id
                QToolTip.showText(QCursor.pos(), event_under_mouse.get('summary', ''))
        else:
            if self.hovered_event_id is not None:
                self.hovered_event_id = None
                QToolTip.hideText()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        y_offset, event_height, event_spacing = 25, 20, 2
        max_slots = (self.height() - y_offset) // (event_height + event_spacing)
        max_visible_y_level = max_slots - 1

        for rect, event_data, style_info in self.event_layout:
            summary = event_data.get('summary', '')
            if 'recurrence' in event_data: summary = f"🔄 {summary}"
            draw_event(painter, rect, event_data, time_text=None, summary_text=summary)

        # 더보기 버튼 그리기
        if self.more_events_data:
            y = y_offset + (max_visible_y_level * (event_height + event_spacing))
            self.more_button_rect = QRect(0, y, self.width(), event_height)
            
            # 폰트를 굵게 설정
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            
            painter.setPen(QColor("#a0c4ff"))
            painter.drawText(self.more_button_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"  + {len(self.more_events_data)}개 더보기")

class MonthViewWidget(BaseViewWidget):
    def __init__(self, main_widget):
        super().__init__(main_widget)
        self.date_to_cell_map = {}
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
            self.current_date = self.current_date.replace(year=year, month=month, day=1)
            self.refresh()

    def show_more_events_popup(self, date_obj, events):
        dialog = MoreEventsDialog(date_obj, events, self, settings=self.main_widget.settings, pos=QCursor.pos(), data_manager=self.data_manager)
        dialog.edit_requested.connect(self.edit_event_requested)
        dialog.delete_requested.connect(self.confirm_delete_event)
        dialog.exec()

    def refresh(self): self.draw_grid(self.current_date.year, self.current_date.month)

    def draw_grid(self, year, month):
        # ... (기존 draw_grid 로직은 거의 동일, DayCellWidget 생성 부분만 수정) ...
        current_theme = self.main_widget.settings.get("theme", "dark")
        is_dark = current_theme == "dark"
        colors = {"weekday": "#D0D0D0" if is_dark else "#222222", "saturday": "#8080FF" if is_dark else "#0000DD", "sunday": "#FF8080" if is_dark else "#DD0000", "today_bg": "#444422" if is_dark else "#FFFFAA", "today_fg": "#FFFF77" if is_dark else "#A0522D", "other_month": "#777777" if is_dark else "#AAAAAA"}
        self.month_button.setStyleSheet(f"color: {colors['weekday']}; background-color: transparent; border: none; font-size: 16px; font-weight: bold;")
        while self.calendar_grid.count():
            child = self.calendar_grid.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.date_to_cell_map.clear()
        self.month_button.setText(f"{year}년 {month}월")
        days_of_week = ["일", "월", "화", "수", "목", "금", "토"]
        for i, day in enumerate(days_of_week):
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = colors['sunday'] if day == "일" else (colors['saturday'] if day == "토" else colors['weekday'])
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.calendar_grid.addWidget(label, 0, i)

        cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
        month_calendar = cal.monthdayscalendar(year, month)
        today = datetime.date.today()
        
        # DayCellWidget 생성 및 연결
        def create_day_cell(date_obj):
            day_widget = DayCellWidget(date_obj, self)
            day_widget.add_event_requested.connect(self.add_event_requested)
            day_widget.edit_event_requested.connect(self.edit_event_requested)
            day_widget.more_events_requested.connect(self.show_more_events_popup)
            return day_widget

        for week_index, week in enumerate(month_calendar):
            for day_index, day in enumerate(week):
                if day == 0: continue
                current_day_obj = datetime.date(year, month, day)
                day_widget = create_day_cell(current_day_obj)
                day_label = QLabel(str(day))
                day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                day_widget.layout.addWidget(day_label)
                font_color = colors['weekday']
                if day_index == 0: font_color = colors['sunday']
                elif day_index == 6: font_color = colors['saturday']
                day_label.setStyleSheet(f"color: {font_color}; background-color: transparent;")
                if current_day_obj == today:
                    day_widget.setStyleSheet(f"background-color: {colors['today_bg']};")
                    day_label.setStyleSheet(f"color: {colors['today_fg']}; font-weight: bold; background-color: transparent;")
                self.calendar_grid.addWidget(day_widget, week_index + 1, day_index)
                self.date_to_cell_map[current_day_obj] = day_widget
        # ... (이전/다음 달 날짜 채우는 로직도 create_day_cell 사용하도록 수정) ...
        first_day_of_month = datetime.date(year, month, 1)
        weekday_of_first = (first_day_of_month.weekday() + 1) % 7
        prev_month_date = first_day_of_month - datetime.timedelta(days=1)
        for i in range(weekday_of_first - 1, -1, -1):
            day_widget = create_day_cell(prev_month_date)
            day_label = QLabel(str(prev_month_date.day))
            day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            day_widget.layout.addWidget(day_label)
            day_label.setStyleSheet(f"color: {colors['other_month']};")
            self.calendar_grid.addWidget(day_widget, 1, i)
            self.date_to_cell_map[prev_month_date] = day_widget
            prev_month_date -= datetime.timedelta(days=1)
        
        last_day_of_month = datetime.date(year, month, calendar.monthrange(year, month)[1])
        weekday_of_last = (last_day_of_month.weekday() + 1) % 7
        next_month_date = last_day_of_month + datetime.timedelta(days=1)
        row = len(month_calendar)
        for i in range(weekday_of_last + 1, 7):
            day_widget = create_day_cell(next_month_date)
            day_label = QLabel(str(next_month_date.day))
            day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            day_widget.layout.addWidget(day_label)
            day_label.setStyleSheet(f"color: {colors['other_month']};")
            self.calendar_grid.addWidget(day_widget, row, i)
            self.date_to_cell_map[next_month_date] = day_widget
            next_month_date += datetime.timedelta(days=1)

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
        
        # 3. 각 DayCellWidget에 그릴 데이터 전달
        for date, cell_widget in self.date_to_cell_map.items():
            max_slots = (cell_widget.height() - y_offset) // (event_height + event_spacing)
            max_visible_y_level = max(0, max_slots - 1)
            
            visible_events, more_events = [], []
            
            # y_level을 기준으로 보이는 이벤트와 '더보기' 이벤트를 나눔
            event_y_levels_on_day = {layout[1]['id']: layout[0].y() for layout in events_by_day.get(date, [])}
            
            sorted_day_events = sorted(events_by_day.get(date, []), key=lambda x: x[0].y())
            
            for layout_item in sorted_day_events:
                event = layout_item[1]
                y_level = (layout_item[0].y() - y_offset) // (event_height + event_spacing)

                if y_level < max_visible_y_level:
                    visible_events.append(layout_item)
                else:
                    more_events.append(event)
            
            # 중복 제거
            more_events = list({e['id']: e for e in more_events}.values())

            cell_widget.set_events(visible_events, more_events)

    # resizeEvent는 BaseViewWidget의 기본 동작으로 충분하므로, 재정의 필요 없음
    # contextMenuEvent도 BaseViewWidget의 기본 동작으로 충분
    def go_to_previous_month(self):
        self.current_date = self.current_date.replace(day=1) - datetime.timedelta(days=1)
        self.refresh()

    def go_to_next_month(self):
        self.current_date = (self.current_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        self.refresh()

    def contextMenuEvent(self, event):
        pos = event.pos()
        target_widget = self.childAt(pos)
        
        day_cell = None
        while target_widget is not None:
            if isinstance(target_widget, DayCellWidget):
                day_cell = target_widget
                break
            target_widget = target_widget.parent()

        menu = QMenu(self)
        main_opacity = self.main_widget.settings.get("window_opacity", 0.95)
        menu_opacity = main_opacity + (1 - main_opacity) * 0.85
        menu.setWindowOpacity(menu_opacity)
        
        target_event = None
        if day_cell:
            pos_in_cell = day_cell.mapFrom(self, pos)
            target_event = day_cell.get_event_at(pos_in_cell)

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
        elif day_cell:
            add_action = QAction("일정 추가", self)
            add_action.triggered.connect(lambda: self.add_event_requested.emit(day_cell.date_obj))
            menu.addAction(add_action)
            
        self.main_widget.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())