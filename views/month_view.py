# views/month_view.py
import datetime
import calendar
from collections import defaultdict
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QMenu, QToolTip, QSizePolicy, QApplication
from PyQt6.QtGui import QFont, QCursor, QPainter, QColor, QAction, QFontMetrics
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect
from custom_dialogs import NewDateSelectionDialog, MoreEventsDialog
from .widgets import EventLabelWidget
from .layout_calculator import MonthLayoutCalculator
from .base_view import BaseViewWidget

class DayCellWidget(QWidget):
    add_event_requested = pyqtSignal(datetime.date)
    edit_event_requested = pyqtSignal(dict) # EventLabelWidget에서 직접 연결되므로 여기선 불필요할 수 있음
    
    def __init__(self, date_obj, parent_view=None):
        super().__init__(parent_view)
        self.date_obj = date_obj
        self.main_widget = parent_view.main_widget
        self.parent_view = parent_view
        
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(1, 1)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(2, 2, 2, 2)
        outer_layout.setSpacing(2)

        self.day_label = QLabel(str(date_obj.day))
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.day_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        outer_layout.addWidget(self.day_label)

        self.events_container = QWidget()
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(0, 0, 0, 0)
        self.events_layout.setSpacing(1)
        self.events_layout.addStretch() # 위젯이 위에서부터 쌓이도록
        outer_layout.addWidget(self.events_container)

    def mouseDoubleClickEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        self.add_event_requested.emit(self.date_obj)

    def clear_events(self):
        while self.events_layout.count() > 1: # 스트레치를 제외하고 모두 삭제
            child = self.events_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

class MonthViewWidget(BaseViewWidget):
    def __init__(self, main_widget):
        super().__init__(main_widget)
        self.date_to_cell_map = {}
        self.setMouseTracking(True)
        self.initUI()
        self.data_manager.event_completion_changed.connect(self.refresh)

    def on_data_updated(self, year, month):
        if year == self.current_date.year and month == self.current_date.month:
            self.refresh()

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
        if not self.main_widget.is_interaction_unlocked(): return
        dialog = NewDateSelectionDialog(self.current_date, self, settings=self.main_widget.settings, pos=QCursor.pos())
        if dialog.exec():
            year, month = dialog.get_selected_date()
            self.date_selected.emit(self.current_date.replace(year=year, month=month, day=1))

    def show_more_events_popup(self, date_obj, events):
        if not self.main_widget.is_interaction_unlocked(): return
        dialog = MoreEventsDialog(date_obj, events, self, settings=self.main_widget.settings, pos=QCursor.pos(), data_manager=self.data_manager)
        dialog.edit_requested.connect(self.edit_event_requested)
        dialog.delete_requested.connect(self.confirm_delete_event)
        dialog.exec()

    def refresh(self):
        if self.is_resizing: return
        
        # 1. 설정값 및 색상 가져오기
        start_day_of_week = self.main_widget.settings.get("start_day_of_week", 6)
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        is_dark = self.main_widget.settings.get("theme", "dark") == "dark"
        # ▼▼▼ 'today_bg'와 'today_fg' 값을 수정합니다. ▼▼▼
        colors = {
            "weekday": "#D0D0D0" if is_dark else "#222222", 
            "saturday": "#8080FF" if is_dark else "#0000DD", 
            "sunday": "#FF8080" if is_dark else "#DD0000", 
            "today_bg": "#CCE5FF", # 연한 파란색 배경
            "today_fg": "#004C99", # 진한 파란색 글자
            "other_month": "#777777" if is_dark else "#AAAAAA"
        }
        # ▲▲▲ 여기까지 수정 ▲▲▲
        self.month_button.setStyleSheet(f"color: {colors['weekday']}; background-color: transparent; border: none; font-size: 16px; font-weight: bold;")

        # 2. 기존 위젯 정리
        while self.calendar_grid.count():
            child = self.calendar_grid.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.date_to_cell_map.clear()
        
        year, month = self.current_date.year, self.current_date.month
        self.month_button.setText(f"{year}년 {month}월")

        # 3. 요일 헤더 생성
        days_of_week_labels = ["일", "월", "화", "수", "목", "금", "토"]
        if start_day_of_week == 0: days_of_week_labels = days_of_week_labels[1:] + days_of_week_labels[:1]
        weekend_indices = [0, 6] if start_day_of_week == 6 else [5, 6]
        
        col_map = {}
        col_idx = 0
        for i, day in enumerate(days_of_week_labels):
            if hide_weekends and i in weekend_indices: continue
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = colors['sunday'] if i == weekend_indices[0] else (colors['saturday'] if i == weekend_indices[1] else colors['weekday'])
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.calendar_grid.addWidget(label, 0, col_idx)
            col_map[i] = col_idx
            col_idx += 1

        # 4. 날짜 셀 생성
        cal = calendar.Calendar(firstweekday=start_day_of_week)
        month_calendar = cal.monthdayscalendar(year, month)
        today = datetime.date.today()

        for week_index, week in enumerate(month_calendar):
            for day_of_week_idx, day in enumerate(week):
                if day == 0 or (hide_weekends and day_of_week_idx in weekend_indices): continue
                
                current_day_obj = datetime.date(year, month, day)
                cell_widget = DayCellWidget(current_day_obj, self)
                cell_widget.add_event_requested.connect(self.add_event_requested)
                
                font_color = colors['weekday']
                if day_of_week_idx == weekend_indices[0]: font_color = colors['sunday']
                elif day_of_week_idx == weekend_indices[1]: font_color = colors['saturday']
                
                cell_widget.day_label.setStyleSheet(f"color: {font_color}; background-color: transparent;")
                if current_day_obj == today:
                    cell_widget.setStyleSheet(f"background-color: {colors['today_bg']}; border-radius: 5px;")
                    cell_widget.day_label.setStyleSheet(f"color: {colors['today_fg']}; font-weight: bold; background-color: transparent;")
                
                self.calendar_grid.addWidget(cell_widget, week_index + 1, col_map[day_of_week_idx])
                self.date_to_cell_map[current_day_obj] = cell_widget

        for i in range(1, self.calendar_grid.rowCount()):
            self.calendar_grid.setRowStretch(i, 1)
        for i in range(self.calendar_grid.columnCount()):
            self.calendar_grid.setColumnStretch(i, 1)
        
        QTimer.singleShot(10, self.draw_events) # 0ms -> 10ms로 변경하여 레이아웃 계산 시간 확보

    def draw_events(self):
        if not self.date_to_cell_map: return

        for cell in self.date_to_cell_map.values():
            cell.clear_events()

        all_events = self.data_manager.get_events(self.current_date.year, self.current_date.month)
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [e for e in all_events if e.get('calendarId') in selected_ids]
        
        calculator = MonthLayoutCalculator(filtered_events, self.date_to_cell_map.keys())
        event_positions, _ = calculator.calculate()

        events_by_day = defaultdict(list)
        for pos_info in event_positions:
            for day in pos_info['days_in_view']:
                events_by_day[day].append(pos_info)

        for date, cell_widget in self.date_to_cell_map.items():
            if not cell_widget.isVisible(): continue
            
            # 요청사항 1: 이벤트 높이 5px 증가
            event_height = QFontMetrics(self.font()).height() + 9
            y_offset = cell_widget.day_label.height() + cell_widget.layout().spacing()
            max_slots = (cell_widget.height() - y_offset) // (event_height + cell_widget.events_layout.spacing())
            if max_slots < 0: max_slots = 0

            # 마지막 슬롯은 '더보기'를 위해 예약
            max_visible_y_level = max(0, max_slots - 1)

            sorted_day_events = sorted(events_by_day.get(date, []), key=lambda p: p['y_level'])
            
            more_events_data = []
            y_levels_on_day = set()

            # 표시할 이벤트와 '더보기'로 넘길 이벤트 분류
            for pos_info in sorted_day_events:
                y_level = pos_info['y_level']
                # 요청사항 2: 공간이 부족하면(슬롯 1개 이하) 이벤트 표시 안함
                if y_level < max_visible_y_level and max_slots > 1:
                    y_levels_on_day.add(y_level)
                else:
                    more_events_data.append(pos_info['event'])

            # 빈 슬롯 채우기
            num_slots_for_events = max_visible_y_level if max_slots > 1 else 0
            for i in range(num_slots_for_events):
                if i not in y_levels_on_day:
                    events_by_day[date].append({'y_level': i, 'event': None})
            
            sorted_day_events = sorted(events_by_day.get(date, []), key=lambda p: p['y_level'])
            
            # 이벤트 위젯 생성
            for pos_info in sorted_day_events:
                y_level = pos_info['y_level']
                if y_level >= num_slots_for_events: continue

                event_data = pos_info.get('event')
                if event_data:
                    is_completed = self.data_manager.is_event_completed(event_data.get('id'))
                    event_widget = EventLabelWidget(event_data, is_completed, main_widget=self.main_widget, parent=cell_widget.events_container)
                    event_widget.edit_requested.connect(self.edit_event_requested)
                    cell_widget.events_layout.insertWidget(y_level, event_widget)
                else: # 빈 이벤트 (자리 채우기용)
                    placeholder = QWidget(cell_widget)
                    placeholder.setFixedHeight(event_height)
                    cell_widget.events_layout.insertWidget(y_level, placeholder)

            # 요청사항 2, 3: '더보기' 버튼 조건 및 크기 수정
            if more_events_data and max_slots > 1:
                more_button = QPushButton(f"+ {len(more_events_data)}개 더보기")
                more_button.setStyleSheet("text-align: left; border: none; color: #a0c4ff; background-color: transparent;")
                more_button.setFixedHeight(int(event_height * 0.9)) # 높이 90%로 설정
                more_button.clicked.connect(lambda _, d=date, e=more_events_data: self.show_more_events_popup(d, e))
                cell_widget.events_layout.insertWidget(max_visible_y_level, more_button)

    def get_event_at(self, pos):
        # 이 메서드는 이제 사용되지 않음
        return None

    def mouseDoubleClickEvent(self, event):
        # DayCellWidget에서 처리하므로 MonthView의 이벤트는 비워둠
        pass

    def mousePressEvent(self, event):
        # DayCellWidget에서 처리하므로 MonthView의 이벤트는 비워둠
        pass

    def go_to_previous_month(self):
        if not self.main_widget.is_interaction_unlocked(): return
        self.navigation_requested.emit("backward")

    def go_to_next_month(self):
        if not self.main_widget.is_interaction_unlocked(): return
        self.navigation_requested.emit("forward")

    def contextMenuEvent(self, event):
        if not self.main_widget.is_interaction_unlocked(): return
        
        target_widget = self.childAt(event.pos())
        target_event = None
        date_info = None

        # 부모 위젯을 따라 올라가며 EventLabelWidget 또는 DayCellWidget 찾기
        while target_widget and target_widget != self:
            if isinstance(target_widget, EventLabelWidget):
                target_event = target_widget.event_data
                break
            if isinstance(target_widget, DayCellWidget):
                date_info = target_widget.date_obj
                break
            target_widget = target_widget.parent()
            
        self.show_context_menu(event.globalPos(), target_event, date_info)

    
    def paintEvent(self, event):
        # 위젯 기반으로 변경되었으므로 paintEvent는 비워둠
        pass
