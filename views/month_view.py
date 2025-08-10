# views/month_view.py
import datetime
import calendar
from collections import defaultdict
from PyQt6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QPushButton, QSizePolicy, QStackedWidget)
from PyQt6.QtGui import QCursor, QPainter, QFontMetrics
from PyQt6.QtCore import (Qt, pyqtSignal, QTimer, QSize, QPropertyAnimation, 
                          pyqtProperty)
from PyQt6.QtSvg import QSvgRenderer

from custom_dialogs import NewDateSelectionDialog, MoreEventsDialog
from .widgets import EventLabelWidget
from .layout_calculator import MonthLayoutCalculator
from .base_view import BaseViewWidget

class RotatingIcon(QWidget):
    """SVG 아이콘을 로드하여 회전시키는 애니메이션 위젯"""
    def __init__(self, svg_path, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(svg_path)
        self.setFixedSize(self.renderer.defaultSize())
        self._angle = 0

        self.animation = QPropertyAnimation(self, b'angle', self)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setDuration(1200)
        self.animation.setLoopCount(-1) # 무한 반복

    @pyqtProperty(int)
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 위젯의 중심으로 이동하고 회전한 뒤, 다시 원래 위치로 복귀하여 그립니다.
        center = self.rect().center()
        painter.translate(center)
        painter.rotate(self._angle)
        painter.translate(-center)
        
        self.renderer.render(painter)

    def start(self):
        self.animation.start()

    def stop(self):
        self.animation.stop()
        self._angle = 0
        self.update()

class DayCellWidget(QWidget):
    add_event_requested = pyqtSignal(datetime.date)
    edit_event_requested = pyqtSignal(dict)
    
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
        self.events_layout.addStretch()
        outer_layout.addWidget(self.events_container)

    def mouseDoubleClickEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        self.add_event_requested.emit(self.date_obj)

    def clear_events(self):
        while self.events_layout.count() > 1:
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
        self.data_manager.sync_state_changed.connect(self.on_sync_state_changed)

    def on_data_updated(self, year, month):
        if year == self.current_date.year and month == self.current_date.month:
            self.refresh()

    def initUI(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        self.month_button = QPushButton()
        self.month_button.clicked.connect(self.open_date_selection_dialog)
        prev_button.clicked.connect(self.go_to_previous_month)
        next_button.clicked.connect(self.go_to_next_month)
        
        # --- [핵심 수정] 애니메이션 아이콘과 QStackedWidget 사용 ---
        self.sync_icon = RotatingIcon("icons/refresh.svg")
        
        self.sync_status_container = QStackedWidget()
        # 아이콘 크기를 24x24로 명시적으로 고정하여 레이아웃 문제를 해결합니다.
        self.sync_status_container.setFixedSize(QSize(24, 24)) 
        self.sync_status_container.addWidget(QWidget()) # 0번 페이지: 빈 위젯
        self.sync_status_container.addWidget(self.sync_icon) # 1번 페이지: 회전 아이콘

        center_nav_layout = QHBoxLayout()
        center_nav_layout.setSpacing(0)
        center_nav_layout.setContentsMargins(25, 0, 0, 0) # 왼쪽 여백 25px 추가
        center_nav_layout.addWidget(self.month_button)
        center_nav_layout.addWidget(self.sync_status_container)

        nav_layout.addWidget(prev_button)
        nav_layout.addStretch(1)
        nav_layout.addLayout(center_nav_layout)
        nav_layout.addStretch(1)
        nav_layout.addWidget(next_button)
        # --- 여기까지 수정 ---
        
        self.main_layout.addLayout(nav_layout)
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setObjectName("calendar_grid")
        self.calendar_grid.setSpacing(0)
        self.main_layout.addLayout(self.calendar_grid)

    def on_sync_state_changed(self, is_syncing, year, month):
        # 현재 보고 있는 월에 대한 동기화 상태만 UI에 반영
        if year == self.current_date.year and month == self.current_date.month:
            if is_syncing:
                self.sync_status_container.setCurrentIndex(1)
                self.sync_icon.start()
            else:
                self.sync_icon.stop()
                self.sync_status_container.setCurrentIndex(0)

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

        if self.calendar_grid is not None:
            while self.calendar_grid.count():
                child = self.calendar_grid.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            self.main_layout.removeItem(self.calendar_grid)
            self.calendar_grid.deleteLater()
        
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setObjectName("calendar_grid")
        self.calendar_grid.setSpacing(0)
        self.main_layout.addLayout(self.calendar_grid)
        self.date_to_cell_map.clear()
        
        start_day_of_week_setting = self.main_widget.settings.get("start_day_of_week", 6)
        hide_weekends = self.main_widget.settings.get("hide_weekends", False)
        
        colors = {
            "weekday": self.weekdayColor, "saturday": self.saturdayColor, "sunday": self.sundayColor,
            "today_bg": self.todayBackgroundColor, "today_fg": self.todayForegroundColor, "other_month": self.otherMonthColor
        }
        self.month_button.setStyleSheet(f"color: {colors['weekday'].name()}; background-color: transparent; border: none; font-size: 16px; font-weight: bold;")
        
        year, month = self.current_date.year, self.current_date.month
        self.month_button.setText(f"{year}년 {month}월")

        days_of_week_text = ["월", "화", "수", "목", "금", "토", "일"]
        
        if start_day_of_week_setting == 6:
            ordered_day_texts = days_of_week_text[-1:] + days_of_week_text[:-1]
            ordered_weekday_indices = [6, 0, 1, 2, 3, 4, 5]
        else:
            ordered_day_texts = days_of_week_text
            ordered_weekday_indices = [0, 1, 2, 3, 4, 5, 6]

        col_map = {}
        grid_col_idx = 0
        for i, day_text in enumerate(ordered_day_texts):
            weekday_idx = ordered_weekday_indices[i]
            
            if hide_weekends and weekday_idx in [5, 6]:
                continue

            label = QLabel(day_text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            color = colors['weekday']
            if weekday_idx == 6: color = colors['sunday']
            elif weekday_idx == 5: color = colors['saturday']
            label.setStyleSheet(f"color: {color.name()}; font-weight: bold;")
            
            self.calendar_grid.addWidget(label, 0, grid_col_idx)
            col_map[weekday_idx] = grid_col_idx
            grid_col_idx += 1

        first_day_of_month = self.current_date.replace(day=1)
        _, num_days_in_month = calendar.monthrange(self.current_date.year, self.current_date.month)
        last_day_of_month = self.current_date.replace(day=num_days_in_month)

        if start_day_of_week_setting == 6:
            offset = (first_day_of_month.weekday() + 1) % 7
        else:
            offset = first_day_of_month.weekday()
        start_date_of_view = first_day_of_month - datetime.timedelta(days=offset)

        end_of_5th_week = start_date_of_view + datetime.timedelta(days=34)
        num_days_in_grid = 35 if last_day_of_month <= end_of_5th_week else 42
        
        today = datetime.date.today()

        for i in range(num_days_in_grid):
            current_day_obj = start_date_of_view + datetime.timedelta(days=i)
            day_of_week_idx = current_day_obj.weekday()
            
            if hide_weekends and day_of_week_idx in [5, 6]:
                continue
            
            if day_of_week_idx not in col_map:
                continue

            grid_row = i // 7 + 1
            grid_col = col_map[day_of_week_idx]
            
            cell_widget = DayCellWidget(current_day_obj, self)
            cell_widget.add_event_requested.connect(self.add_event_requested)
            
            font_color = colors['weekday']
            is_current_month = current_day_obj.month == self.current_date.month
            
            if not is_current_month:
                font_color = colors['other_month']
            elif day_of_week_idx == 6: font_color = colors['sunday']
            elif day_of_week_idx == 5: font_color = colors['saturday']

            cell_widget.day_label.setStyleSheet(f"color: {font_color.name()}; background-color: transparent;")
            
            if current_day_obj == today:
                cell_widget.setStyleSheet("background-color: rgba(0, 120, 215, 51); border-radius: 5px;")
                cell_widget.day_label.setStyleSheet(f"color: {colors['today_fg'].name()}; font-weight: bold; background-color: transparent;")
            
            self.calendar_grid.addWidget(cell_widget, grid_row, grid_col)
            self.date_to_cell_map[current_day_obj] = cell_widget

        for i in range(1, self.calendar_grid.rowCount()):
            self.calendar_grid.setRowStretch(i, 1)
        for i in range(self.calendar_grid.columnCount()):
            self.calendar_grid.setColumnStretch(i, 1)
        
        self.schedule_draw_events()

    def schedule_draw_events(self):
        QTimer.singleShot(10, self._draw_events_internal)

    def _draw_events_internal(self):
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
            
            # [수정] 이벤트 높이 간격을 줄여 더 많은 일정을 표시하도록 함
            event_height = QFontMetrics(self.font()).height() + 2
            y_offset = cell_widget.day_label.height() + cell_widget.layout().spacing()
            max_slots = (cell_widget.height() - y_offset) // (event_height + cell_widget.events_layout.spacing())
            if max_slots < 0: max_slots = 0

            sorted_day_events = sorted(events_by_day.get(date, []), key=lambda p: p['y_level'])
            total_events_on_day = len(sorted_day_events)
            
            events_to_render = []
            more_events_data = []
            show_more_button = total_events_on_day > max_slots and max_slots > 0

            if show_more_button:
                num_visible_events = max_slots - 1
                events_to_render = sorted_day_events[:num_visible_events]
                more_events_data = [p['event'] for p in sorted_day_events[num_visible_events:] if p.get('event')]
            else:
                events_to_render = sorted_day_events[:max_slots]

            rendered_y_levels = set()
            for pos_info in events_to_render:
                y_level = pos_info['y_level']
                event_data = pos_info.get('event')
                
                if event_data:
                    is_completed = self.data_manager.is_event_completed(event_data.get('id'))
                    is_other_month = date.month != self.current_date.month
                    event_widget = EventLabelWidget(
                        event_data, 
                        is_completed=is_completed, 
                        is_other_month=is_other_month, 
                        main_widget=self.main_widget, 
                        parent=cell_widget.events_container
                    )
                    event_widget.edit_requested.connect(self.edit_event_requested)
                    cell_widget.events_layout.insertWidget(y_level, event_widget)
                    rendered_y_levels.add(y_level)

            num_slots_to_fill = len(events_to_render)
            if show_more_button:
                num_slots_to_fill = max_slots -1

            for i in range(num_slots_to_fill):
                if i not in rendered_y_levels:
                    placeholder = QWidget(cell_widget)
                    placeholder.setFixedHeight(event_height)
                    cell_widget.events_layout.insertWidget(i, placeholder)

            if show_more_button and more_events_data:
                more_button = QPushButton(f"+ {len(more_events_data)}개 더보기")
                # [수정] '더보기' 버튼의 폰트를 줄이고 패딩을 제거하여 공간 확보
                more_button.setStyleSheet("text-align: left; border: none; color: #82a7ff; background-color: transparent; padding: 0px; font-size: 8pt;")
                more_button.setFixedHeight(event_height)
                more_button.clicked.connect(lambda _, d=date, e=more_events_data: self.show_more_events_popup(d, e))
                cell_widget.events_layout.insertWidget(max_slots - 1, more_button)

    def get_event_at(self, pos):
        pass

    def mouseDoubleClickEvent(self, event):
        pass

    def mousePressEvent(self, event):
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
        pass