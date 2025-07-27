import datetime
import calendar
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from custom_dialogs import CustomMessageBox, NewDateSelectionDialog, MoreEventsDialog
from .widgets import EventLabelWidget

class DayCellWidget(QWidget):
    add_event_requested = pyqtSignal(datetime.date)
    def __init__(self, date_obj, parent=None):
        super().__init__(parent)
        self.date_obj = date_obj
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(3, 3, 3, 3)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.add_event_requested.emit(self.date_obj)
        super().mouseDoubleClickEvent(event)

class MonthViewWidget(QWidget):
    add_event_requested = pyqtSignal(datetime.date)
    edit_event_requested = pyqtSignal(dict)

    def __init__(self, main_widget):
        super().__init__()
        self.main_widget = main_widget
        self.data_manager = main_widget.data_manager
        self.current_date = datetime.date.today()
        self.date_to_cell_map = {}
        self.event_widgets = []
        
        # --- ▼▼▼ 리사이즈 최적화 코드 변경 ▼▼▼ ---
        self.is_resizing = False 
        # self.resize_timer는 더 이상 필요 없으므로 삭제
        # --- ▲▲▲ 여기까지 변경 ▲▲▲ ---
        
        self.data_manager.data_updated.connect(self.on_data_updated)
        
        self.initUI()
        self.refresh()

    # --- ▼▼▼ 리사이즈 최적화 코드 추가 ▼▼▼ ---
    def set_resizing(self, is_resizing):
        """리사이즈 상태를 설정하고, 상태에 따라 이벤트 위젯을 숨기거나 다시 그립니다."""
        self.is_resizing = is_resizing
        if self.is_resizing:
            # 리사이즈 시작 시, 모든 이벤트 위젯을 숨깁니다.
            for widget in self.event_widgets:
                widget.hide()
        else:
            # 리사이즈 종료 시, 이벤트를 다시 그립니다.
            self.redraw_events_with_current_data()
    # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

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
        
        nav_button_style = "QPushButton { color: white; background-color: transparent; border: none; font-size: 20px; } QPushButton:hover { color: #aaaaaa; }"
        month_button_style = "QPushButton { color: white; background-color: transparent; border: none; font-size: 16px; font-weight: bold; } QPushButton:hover { color: #aaaaaa; }"
        
        prev_button.setStyleSheet(nav_button_style)
        next_button.setStyleSheet(nav_button_style)
        self.month_button.setStyleSheet(month_button_style)
        
        prev_button.clicked.connect(self.go_to_previous_month)
        next_button.clicked.connect(self.go_to_next_month)
        
        nav_layout.addWidget(prev_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.month_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(next_button)
        main_layout.addLayout(nav_layout)
        
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(0)
        main_layout.addLayout(self.calendar_grid)

    def open_date_selection_dialog(self):
        dialog = NewDateSelectionDialog(self.current_date, self, settings=self.main_widget.settings)
        if dialog.exec():
            year, month = dialog.get_selected_date()
            self.current_date = self.current_date.replace(year=year, month=month, day=1)
            self.refresh()

    def on_add_event_requested(self, date_obj): self.add_event_requested.emit(date_obj)
    def on_edit_event_requested(self, event_data): self.edit_event_requested.emit(event_data)

    def show_more_events_popup(self, date_obj, events):
        dialog = MoreEventsDialog(date_obj, events, self, settings=self.main_widget.settings)
        dialog.edit_requested.connect(self.on_edit_event_requested)
        dialog.delete_requested.connect(self.confirm_delete_event)
        dialog.exec()

    def refresh(self): self.draw_grid(self.current_date.year, self.current_date.month)

    def draw_grid(self, year, month):
        while self.calendar_grid.count():
            child = self.calendar_grid.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.date_to_cell_map.clear()
        self.month_button.setText(f"{year}년 {month}월")
        days_of_week = ["일", "월", "화", "수", "목", "금", "토"]
        for i, day in enumerate(days_of_week):
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = "#ff8080" if day == "일" else ("#8080ff" if day == "토" else "white")
            label.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.calendar_grid.addWidget(label, 0, i)

        cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
        month_calendar = cal.monthdayscalendar(year, month)
        today = datetime.date.today()

        for week_index, week in enumerate(month_calendar):
            for day_index, day in enumerate(week):
                if day == 0: continue
                current_day_obj = datetime.date(year, month, day)
                day_widget = DayCellWidget(current_day_obj, self)
                day_widget.add_event_requested.connect(self.on_add_event_requested)
                day_label = QLabel(str(day))
                day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                day_widget.layout.addWidget(day_label)
                font_color = "white"
                if day_index == 0: font_color = "#ff8080"
                elif day_index == 6: font_color = "#8080ff"
                day_label.setStyleSheet(f"color: {font_color}; background-color: transparent;")
                if current_day_obj == today:
                    day_widget.setStyleSheet("background-color: #444422;")
                    day_label.setStyleSheet("color: #FFFF77; font-weight: bold; background-color: transparent;")
                else:
                    day_widget.setStyleSheet("background-color: transparent;")
                self.calendar_grid.addWidget(day_widget, week_index + 1, day_index)
                self.date_to_cell_map[current_day_obj] = {'row': week_index + 1, 'col': day_index, 'widget': day_widget}

        first_day_of_month = datetime.date(year, month, 1)
        weekday_of_first = (first_day_of_month.weekday() + 1) % 7
        prev_month_date = first_day_of_month - datetime.timedelta(days=1)
        for i in range(weekday_of_first - 1, -1, -1):
            day = prev_month_date.day
            current_day_obj = prev_month_date
            day_widget = DayCellWidget(current_day_obj, self)
            day_widget.add_event_requested.connect(self.on_add_event_requested)
            day_label = QLabel(str(day))
            day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            day_widget.layout.addWidget(day_label)
            day_label.setStyleSheet("color: #777777;")
            self.calendar_grid.addWidget(day_widget, 1, i)
            self.date_to_cell_map[current_day_obj] = {'row': 1, 'col': i, 'widget': day_widget}
            prev_month_date -= datetime.timedelta(days=1)

        last_day_of_month = datetime.date(year, month, calendar.monthrange(year, month)[1])
        weekday_of_last = (last_day_of_month.weekday() + 1) % 7
        next_month_date = last_day_of_month + datetime.timedelta(days=1)
        row = len(month_calendar)
        for i in range(weekday_of_last + 1, 7):
            day = next_month_date.day
            current_day_obj = next_month_date
            day_widget = DayCellWidget(current_day_obj, self)
            day_widget.add_event_requested.connect(self.on_add_event_requested)
            day_label = QLabel(str(day))
            day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            day_widget.layout.addWidget(day_label)
            day_label.setStyleSheet("color: #777777;")
            self.calendar_grid.addWidget(day_widget, row, i)
            self.date_to_cell_map[current_day_obj] = {'row': row, 'col': i, 'widget': day_widget}
            next_month_date += datetime.timedelta(days=1)

        for i in range(1, self.calendar_grid.rowCount()): self.calendar_grid.setRowStretch(i, 1)
        for i in range(self.calendar_grid.columnCount()): self.calendar_grid.setColumnStretch(i, 1)
        QTimer.singleShot(0, self.redraw_events_with_current_data)

    def redraw_events_with_current_data(self):
        all_events = self.data_manager.get_events(self.current_date.year, self.current_date.month)
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [event for event in all_events if event.get('calendarId') in selected_ids]
        self.redraw_events(filtered_events)

    def redraw_events(self, events):
        for widget in self.event_widgets:
            widget.deleteLater()
        self.event_widgets.clear()
        if not events or not self.date_to_cell_map:
            return
            
        occupied_lanes = {}
        more_events_to_create = {}

        y_offset, event_height, event_spacing = 25, 20, 2

        for event in sorted(events, key=lambda e: (e['start'].get('date', e['start'].get('dateTime', ''))[:10])):
            try:
                start_info, end_info = event['start'], event['end']
                is_all_day = 'date' in start_info
                start_str, end_str = (start_info.get('date') or start_info.get('dateTime')), (end_info.get('date') or end_info.get('dateTime'))
                event_start_date, event_end_date = datetime.date.fromisoformat(start_str[:10]), datetime.date.fromisoformat(end_str[:10])
                if is_all_day and len(end_str) == 10: event_end_date -= datetime.timedelta(days=1)
                elif not is_all_day and end_str.endswith('00:00:00'): event_end_date -= datetime.timedelta(days=1)

                visible_days = self.date_to_cell_map.keys()
                view_start_date, view_end_date = min(visible_days), max(visible_days)
                
                draw_start_date = max(event_start_date, view_start_date)
                draw_end_date = min(event_end_date, view_end_date)
                
                if draw_start_date > draw_end_date: continue

                event_span_days = [draw_start_date + datetime.timedelta(d) for d in range((draw_end_date - draw_start_date).days + 1)]
                y_level = 0
                while True:
                    if not any(y_level in occupied_lanes.get(d, []) for d in event_span_days): break
                    y_level += 1
                
                days_by_row = {}
                for day in event_span_days:
                    info = self.date_to_cell_map.get(day)
                    if info: days_by_row.setdefault(info['row'], []).append(day)

                for row, days_in_row in days_by_row.items():
                    start_cell_info = self.date_to_cell_map.get(days_in_row[0])
                    if not start_cell_info: continue
                    
                    cell_height = self.calendar_grid.cellRect(start_cell_info['row'], start_cell_info['col']).height()
                    max_slots = (cell_height - y_offset) // (event_height + event_spacing)
                    max_visible_y_level = max_slots - 1

                    if y_level >= max_visible_y_level:
                        for day in days_in_row:
                            more_events_to_create.setdefault(day, []).append(event)
                        continue

                    for d in days_in_row:
                        occupied_lanes.setdefault(d, []).append(y_level)

                    segment_start_date, segment_end_date = min(days_in_row), max(days_in_row)
                    start_cell, end_cell = self.date_to_cell_map[segment_start_date], self.date_to_cell_map[segment_end_date]
                    start_rect, end_rect = self.calendar_grid.cellRect(start_cell['row'], start_cell['col']), self.calendar_grid.cellRect(end_cell['row'], end_cell['col'])

                    if not start_rect.isValid() or not end_rect.isValid(): continue

                    x, y = start_rect.left(), start_rect.top() + y_offset + (y_level * (event_height + event_spacing))
                    width, height = end_rect.right() - start_rect.left(), event_height

                    is_true_start, is_true_end = (segment_start_date == event_start_date), (segment_end_date == event_end_date)
                    is_week_start, is_week_end = (start_cell['col'] == 0), (end_cell['col'] == 6)
                    
                    radius, sharp = "5px", "0px"
                    tlr = radius if is_true_start or is_week_start else sharp
                    blr = radius if is_true_start or is_week_start else sharp
                    trr = radius if is_true_end or is_week_end else sharp
                    brr = radius if is_true_end or is_week_end else sharp
                    border_radius_style = f"border-radius: {tlr} {trr} {brr} {blr};"

                    event_widget = EventLabelWidget(event, self)
                    event_widget.edit_requested.connect(self.on_edit_event_requested)
                    event_widget.setText(event.get('summary', ''))
                    
                    start_info = event.get('start', {})
                    tooltip_text = f"<b>{event.get('summary', '')}</b>"
                    if 'dateTime' in start_info:
                        try:
                            start_dt = datetime.datetime.fromisoformat(start_info.get('dateTime'))
                            tooltip_text += f"<br>{start_dt.strftime('%H:%M')}"
                        except: pass
                    event_widget.setToolTip(tooltip_text)

                    event_widget.setGeometry(x, y, width, height)
                    event_color = event.get('color', '#555555')
                    event_widget.setStyleSheet(f"background-color: {event_color}; color: white; {border_radius_style} padding-left: 5px; font-size: 9pt;")
                    event_widget.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                    event_widget.show()
                    self.event_widgets.append(event_widget)
            except Exception as e:
                print(f"이벤트 그리기 오류: {e}, 이벤트: {event.get('summary', '')}")
                continue
        
        drawn_more_buttons = set()
        for day, hidden_events in more_events_to_create.items():
            if day in drawn_more_buttons: continue
            
            cell_info = self.date_to_cell_map.get(day)
            if not cell_info: continue

            unique_hidden_events = list({e['id']: e for e in hidden_events}.values())
            
            cell_rect = self.calendar_grid.cellRect(cell_info['row'], cell_info['col'])
            max_slots = (cell_rect.height() - y_offset) // (event_height + event_spacing)
            more_button_y_level = max_slots - 1

            if more_button_y_level < 0: continue

            x = cell_rect.left()
            y = cell_rect.top() + y_offset + (more_button_y_level * (event_height + event_spacing))
            width, height = cell_rect.width(), event_height

            more_button = QPushButton(f"+ {len(unique_hidden_events)}개 더보기", self)
            more_button.setStyleSheet("background-color: transparent; color: #a0c4ff; text-align: left; padding-left: 5px; border: none;")
            more_button.setGeometry(x, y, width, height)
            
            tooltip_text = "\n".join([f"• {e.get('summary', '')}" for e in unique_hidden_events])
            more_button.setToolTip(tooltip_text)
            
            more_button.clicked.connect(lambda _, d=day, evs=unique_hidden_events: self.show_more_events_popup(d, evs))
            
            more_button.show()
            self.event_widgets.append(more_button)
            drawn_more_buttons.add(day)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 리사이징 중에는 타이머를 사용하지 않고, 모든 이벤트 위젯의 위치를 즉시 재계산합니다.
        # 단, is_resizing 플래그가 True이면 위젯들은 숨겨진 상태이므로, 계산만 하고 화면에 표시는 안됩니다.
        # 리사이징이 끝나면 set_resizing(False)가 호출되면서 위젯들이 보이게 됩니다.
        if not self.is_resizing:
            self.redraw_events_with_current_data() 

    def go_to_previous_month(self):
        self.current_date = self.current_date.replace(day=1) - datetime.timedelta(days=1)
        self.refresh()

    def go_to_next_month(self):
        self.current_date = (self.current_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        self.refresh()

    def contextMenuEvent(self, event):
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu
        pos = event.pos()
        target_date = None
        target_event = None
        for event_widget in self.event_widgets:
            if event_widget.geometry().contains(pos):
                if isinstance(event_widget, EventLabelWidget):
                    target_event = event_widget.event_data
                break
        if not target_event:
            for date, cell_info in self.date_to_cell_map.items():
                cell_rect = self.calendar_grid.cellRect(cell_info['row'], cell_info['col'])
                if cell_rect.contains(pos):
                    target_date = date
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
        elif target_date:
            add_action = QAction("일정 추가", self)
            add_action.triggered.connect(lambda: self.add_event_requested.emit(target_date))
            menu.addAction(add_action)
        self.main_widget.add_common_context_menu_actions(menu)
        menu.exec(event.globalPos())

    def confirm_delete_event(self, event_data):
        summary = event_data.get('summary', '(제목 없음)')
        msg_box = CustomMessageBox(
            self,
            title='삭제 확인',
            text=f"'{summary}' 일정을 정말 삭제하시겠습니까?",
            settings=self.main_widget.settings
        )
        if msg_box.exec():
            self.main_widget.data_manager.delete_event(event_data)