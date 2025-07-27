import datetime
import calendar
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from custom_dialogs import CustomMessageBox, NewDateSelectionDialog
from .widgets import EventLabelWidget

# DayCellWidget 클래스는 변경사항 없습니다.
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


# 상단의 import 구문과 EventLabelWidget, DayCellWidget 클래스는 그대로 둡니다.

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
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(50)
        self.resize_timer.timeout.connect(self.redraw_events_with_current_data)
        
        # DataManager의 신호를 받으면 on_data_updated 슬롯을 호출
        self.data_manager.data_updated.connect(self.on_data_updated)
        
        self.initUI()
        self.refresh() # 위젯 생성 시 기본 틀을 한번 그려줌

    def on_data_updated(self, year, month):
        """데이터가 업데이트되었다는 신호를 받았을 때 호출되는 슬롯."""
        # 현재 보고 있는 월의 데이터가 업데이트되었을 때만 화면을 다시 그림
        if year == self.current_date.year and month == self.current_date.month:
            print(f"{year}년 {month}월 데이터 변경 감지, 화면을 새로고침합니다.")
            self.redraw_events_with_current_data()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        
        # month_label을 QPushButton으로 변경
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
        """날짜 선택 다이얼로그를 엽니다."""
        dialog = NewDateSelectionDialog(self.current_date, self)
        if dialog.exec():
            year, month = dialog.get_selected_date()
            self.current_date = self.current_date.replace(year=year, month=month, day=1)
            self.refresh()

    def on_add_event_requested(self, date_obj): self.add_event_requested.emit(date_obj)
    def on_edit_event_requested(self, event_data): self.edit_event_requested.emit(event_data)

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
                if day == 0:
                    # 이전/다음 달 날짜를 계산해야 함
                    # 이 부분은 조금 더 복잡한 로직이 필요하여 일단은 빈칸으로 둡니다.
                    # 정확한 구현을 위해 1일의 요일과 마지막 날의 요일을 알아야 합니다.
                    continue

                current_day_obj = datetime.date(year, month, day)
                day_widget = DayCellWidget(current_day_obj, self)
                day_widget.add_event_requested.connect(self.on_add_event_requested)
                day_label = QLabel(str(day))
                day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                day_widget.layout.addWidget(day_label)

                font_color = "white"
                if current_day_obj.month != month:
                    font_color = "#777777" # 다른 달의 날짜는 회색으로
                elif day_index == 0: # 일요일
                    font_color = "#ff8080"
                elif day_index == 6: # 토요일
                    font_color = "#8080ff"
                
                day_label.setStyleSheet(f"color: {font_color}; background-color: transparent;")

                if current_day_obj == today:
                    day_widget.setStyleSheet("background-color: #444422;") # 오늘 날짜 셀 배경색 변경
                    day_label.setStyleSheet("color: #FFFF77; font-weight: bold; background-color: transparent;") # 오늘 날짜 텍스트 스타일
                else:
                    day_widget.setStyleSheet("background-color: transparent;")

                self.calendar_grid.addWidget(day_widget, week_index + 1, day_index)
                self.date_to_cell_map[current_day_obj] = {'row': week_index + 1, 'col': day_index, 'widget': day_widget}

        # 이전/다음 달 날짜 채우기
        first_day_of_month = datetime.date(year, month, 1)
        weekday_of_first = (first_day_of_month.weekday() + 1) % 7  # 일요일=0
        
        prev_month_date = first_day_of_month - datetime.timedelta(days=1)
        
        for i in range(weekday_of_first - 1, -1, -1):
            day = prev_month_date.day
            current_day_obj = prev_month_date
            
            day_widget = DayCellWidget(current_day_obj, self)
            day_widget.add_event_requested.connect(self.on_add_event_requested)
            day_label = QLabel(str(day))
            day_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            day_widget.layout.addWidget(day_label)
            day_label.setStyleSheet("color: #777777;") # 이전 달 날짜는 회색
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
            day_label.setStyleSheet("color: #777777;") # 다음 달 날짜는 회색
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

        for event in events:
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
                for d in event_span_days:
                    occupied_lanes.setdefault(d, []).append(y_level)

                days_by_row = {}
                for day in event_span_days:
                    info = self.date_to_cell_map.get(day)
                    if info: days_by_row.setdefault(info['row'], []).append(day)

                for row, days_in_row in days_by_row.items():
                    segment_start_date, segment_end_date = min(days_in_row), max(days_in_row)
                    start_cell, end_cell = self.date_to_cell_map[segment_start_date], self.date_to_cell_map[segment_end_date]
                    start_rect, end_rect = self.calendar_grid.cellRect(start_cell['row'], start_cell['col']), self.calendar_grid.cellRect(end_cell['row'], end_cell['col'])

                    if not start_rect.isValid() or not end_rect.isValid(): continue

                    y_offset, event_height, event_spacing = 25, 20, 2
                    x, y = start_rect.left(), start_rect.top() + y_offset + (y_level * (event_height + event_spacing))
                    width, height = end_rect.right() - start_rect.left(), event_height

                    is_true_start = (segment_start_date == event_start_date)
                    is_true_end = (segment_end_date == event_end_date)
                    is_week_start = (start_cell['col'] == 0)
                    is_week_end = (end_cell['col'] == 6)
                    
                    radius, sharp = "5px", "0px"
                    tlr = radius if is_true_start or is_week_start else sharp
                    blr = radius if is_true_start or is_week_start else sharp
                    trr = radius if is_true_end or is_week_end else sharp
                    brr = radius if is_true_end or is_week_end else sharp
                    border_radius_style = f"border-radius: {tlr} {trr} {brr} {blr};"

                    event_widget = EventLabelWidget(event, self)
                    event_widget.edit_requested.connect(self.on_edit_event_requested)
                    
                    event_widget.setText(event.get('summary', ''))
                    
                    # --- 툴팁 추가 (수정된 로직) ---
                    start_info = event.get('start', {})
                    is_all_day = 'date' in start_info
                    
                    tooltip_text = f"<b>{event.get('summary', '')}</b>" # 기본적으로 제목만 표시
                    
                    if not is_all_day:
                        start_str = start_info.get('dateTime')
                        try:
                            start_dt = datetime.datetime.fromisoformat(start_str)
                            tooltip_text += f"<br>{start_dt.strftime('%H:%M')}" # 시간 정보가 있을 때만 시간 추가
                        except (ValueError, TypeError, AttributeError):
                            pass # 시간 정보 파싱 실패 시 아무것도 안 함
                    
                    event_widget.setToolTip(tooltip_text)
                    # --- 여기까지 ---

                    event_widget.setGeometry(x, y, width, height)
                    event_color = event.get('color', '#555555')
                    event_widget.setStyleSheet(f"background-color: {event_color}; color: white; {border_radius_style} padding-left: 5px; font-size: 9pt;")
                    event_widget.setAlignment(Qt.AlignmentFlag.AlignVCenter)
                    event_widget.show()
                    self.event_widgets.append(event_widget)

            except Exception as e:
                print(f"이벤트 그리기 오류: {e}, 이벤트: {event.get('summary', '')}")
                continue

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start() 

    def go_to_previous_month(self):
        self.current_date = self.current_date.replace(day=1) - datetime.timedelta(days=1)
        self.refresh()

    def go_to_next_month(self):
        self.current_date = (self.current_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        self.refresh()

    def get_events_for_date(self, date_obj):
        events = self.data_manager.get_events(date_obj.year, date_obj.month)
        return [e for e in events if datetime.date.fromisoformat(e['start'].get('date', e['start'].get('dateTime')[:10])) <= date_obj <= datetime.date.fromisoformat(e['end'].get('date', e['end'].get('dateTime')[:10])) - datetime.timedelta(days=1 if 'date' in e['end'] else 0)]

    def contextMenuEvent(self, event):
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        pos = event.pos()
        target_date = None
        target_event = None

        # 마우스 위치에 이벤트 위젯이 있는지 확인
        for event_widget in self.event_widgets:
            if event_widget.geometry().contains(pos):
                target_event = event_widget.event_data
                break
        
        # 이벤트 위젯이 없다면, 날짜 셀이 있는지 확인
        if not target_event:
            for date, cell_info in self.date_to_cell_map.items():
                cell_rect = self.calendar_grid.cellRect(cell_info['row'], cell_info['col'])
                if cell_rect.contains(pos):
                    target_date = date
                    break

        menu = QMenu(self)
        
        # 상황별 메뉴 추가
        if target_event:
            edit_action = QAction("수정", self)
            edit_action.triggered.connect(lambda: self.edit_event_requested.emit(target_event))
            menu.addAction(edit_action)
            
            delete_action = QAction("삭제", self)
            # 삭제 액션에 확인 창을 띄우는 함수를 연결합니다.
            delete_action.triggered.connect(lambda: self.confirm_delete_event(target_event))
            menu.addAction(delete_action)

        elif target_date:
            add_action = QAction("일정 추가", self)
            add_action.triggered.connect(lambda: self.add_event_requested.emit(target_date))
            menu.addAction(add_action)

        # 공통 메뉴 추가 (MainWidget의 메서드 호출)
        self.main_widget.add_common_context_menu_actions(menu)
        
        menu.exec(event.globalPos())

    def confirm_delete_event(self, event_data):
        """삭제 확인 대화 상자를 표시하고 사용자의 선택에 따라 이벤트를 삭제합니다."""
        summary = event_data.get('summary', '(제목 없음)')
        
        msg_box = CustomMessageBox(
            self,
            title='삭제 확인',
            text=f"'{summary}' 일정을 정말 삭제하시겠습니까?"
        )
        
        # exec()는 사용자가 "확인"을 누르면 True, "취소"를 누르면 False를 반환합니다.
        if msg_box.exec():
            self.main_widget.data_manager.delete_event(event_data)