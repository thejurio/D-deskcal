# views/month_view.py
import datetime
import calendar
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSizePolicy, QStackedWidget
)
from PyQt6.QtGui import (
    QCursor, QPainter, QFontMetrics, QColor, QPainterPath, QMouseEvent
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QSize, QPropertyAnimation,
    pyqtProperty, QPoint, QPointF, QRectF, QEvent
)
from PyQt6.QtSvg import QSvgRenderer

from custom_dialogs import NewDateSelectionDialog, MoreEventsDialog
from .layout_calculator import MonthLayoutCalculator
from .base_view import BaseViewWidget
from .widgets import get_text_color_for_background


# ---------------------------
# 회전 SVG 아이콘(동기화 표시)
# ---------------------------
class RotatingIcon(QWidget):
    def __init__(self, svg_path, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(svg_path)
        self.setFixedSize(self.renderer.defaultSize())
        self._angle = 0

        self.animation = QPropertyAnimation(self, b'angle', self)
        self.animation.setStartValue(0)
        self.animation.setEndValue(360)
        self.animation.setDuration(1200)
        self.animation.setLoopCount(-1)

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


# ---------------------------
# 날짜 셀(라벨/더보기만 배치)
# ---------------------------
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
        self.setMouseTracking(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(2, 2, 2, 2)
        outer_layout.setSpacing(2)

        self.day_label = QLabel(str(date_obj.day))
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.day_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        outer_layout.addWidget(self.day_label)

        # 일정은 페인터로 그림. 여기엔 높이 확보/더보기 버튼만.
        self.events_container = QWidget()
        self.events_container.setMouseTracking(True)
        self.events_layout = QVBoxLayout(self.events_container)
        self.events_layout.setContentsMargins(0, 0, 0, 0)
        self.events_layout.setSpacing(1)
        self.events_layout.addStretch()
        outer_layout.addWidget(self.events_container)

    def mouseDoubleClickEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        # 부모가 새 일정 추가 처리
        self.add_event_requested.emit(self.date_obj)

    def clear_events(self):
        # 맨 아래 stretch 하나만 남기고 제거
        while self.events_layout.count() > 1:
            item = self.events_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()


# ---------------------------
# 월간 뷰
# ---------------------------
class MonthViewWidget(BaseViewWidget):
    def __init__(self, main_widget):
        super().__init__(main_widget)
        self.date_to_cell_map = {}
        self.setMouseTracking(True)
        self.installEventFilter(self)  # 자기 자신도 필터링
        self.initUI()

        # 데이터 갱신 연결
        self.data_manager.event_completion_changed.connect(self.refresh)
        self.data_manager.sync_state_changed.connect(self.on_sync_state_changed)

        # 페인터 렌더링 캐시
        self._render_boxes = []           # [{'rect': QRectF, 'event': dict, 'left_round': bool, 'right_round': bool, 'y_level': int}]
        self._hidden_events_by_date = {}  # date -> [event,...]
        self._event_height = 18
        self._lane_spacing = 2
        self._hover_event = None

    # BaseView 쪽에서 호출됨
    def on_data_updated(self, year, month):
        if year == self.current_date.year and month == self.current_date.month:
            self.refresh()

    # ---------------------------
    # UI 구성
    # ---------------------------
    def initUI(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        nav_layout = QHBoxLayout()
        prev_button, next_button = QPushButton("<"), QPushButton(">")
        self.month_button = QPushButton()
        self.month_button.clicked.connect(self.open_date_selection_dialog)
        prev_button.clicked.connect(self.go_to_previous_month)
        next_button.clicked.connect(self.go_to_next_month)

        self.sync_icon = RotatingIcon("icons/refresh.svg")
        self.sync_status_container = QStackedWidget()
        self.sync_status_container.setFixedSize(QSize(24, 24))
        self.sync_status_container.addWidget(QWidget())   # idle
        self.sync_status_container.addWidget(self.sync_icon)

        center_nav_layout = QHBoxLayout()
        center_nav_layout.setSpacing(0)
        center_nav_layout.setContentsMargins(25, 0, 0, 0)
        center_nav_layout.addWidget(self.month_button)
        center_nav_layout.addWidget(self.sync_status_container)

        nav_layout.addWidget(prev_button)
        nav_layout.addStretch(1)
        nav_layout.addLayout(center_nav_layout)
        nav_layout.addStretch(1)
        nav_layout.addWidget(next_button)

        self.main_layout.addLayout(nav_layout)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setObjectName("calendar_grid")
        self.calendar_grid.setSpacing(0)
        self.main_layout.addLayout(self.calendar_grid)

    # ---------------------------
    # 동기화 인디케이터
    # ---------------------------
    def on_sync_state_changed(self, is_syncing, year, month):
        if year == self.current_date.year and month == self.current_date.month:
            if is_syncing:
                self.sync_status_container.setCurrentIndex(1)
                self.sync_icon.start()
            else:
                self.sync_icon.stop()
                self.sync_status_container.setCurrentIndex(0)
                
    # MonthViewWidget 내부에 추가
    def go_to_previous_month(self):
        if not self.main_widget.is_interaction_unlocked():
            return
        self.navigation_requested.emit("backward")

    def go_to_next_month(self):
        if not self.main_widget.is_interaction_unlocked():
            return
        self.navigation_requested.emit("forward")

    # ---------------------------
    # 날짜 선택
    # ---------------------------
    def open_date_selection_dialog(self):
        if not self.main_widget.is_interaction_unlocked():
            return
        dialog = NewDateSelectionDialog(
            self.current_date, self,
            settings=self.main_widget.settings,
            pos=QCursor.pos()
        )
        if dialog.exec():
            year, month = dialog.get_selected_date()
            self.date_selected.emit(self.current_date.replace(year=year, month=month, day=1))

    # ---------------------------
    # 더보기 팝업
    # ---------------------------
    def show_more_events_popup(self, date_obj, events):
        if not self.main_widget.is_interaction_unlocked():
            return
        dialog = MoreEventsDialog(
            date_obj, events, self,
            settings=self.main_widget.settings,
            pos=QCursor.pos(), data_manager=self.data_manager
        )
        dialog.edit_requested.connect(self.edit_event_requested)
        dialog.delete_requested.connect(self.confirm_delete_event)
        dialog.exec()

    # ---------------------------
    # 리프레시(그리드 재구성 + 렌더 파이프라인)
    # ---------------------------
    def refresh(self):
        if getattr(self, "is_resizing", False):
            return

        # 기존 그리드 제거
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
            "weekday": self.weekdayColor,
            "saturday": self.saturdayColor,
            "sunday": self.sundayColor,
            "today_bg": self.todayBackgroundColor,
            "today_fg": self.todayForegroundColor,
            "other_month": self.otherMonthColor,
        }
        self.month_button.setStyleSheet(
            f"color: {colors['weekday'].name()}; background-color: transparent; "
            f"border: none; font-size: 16px; font-weight: bold;"
        )

        year, month = self.current_date.year, self.current_date.month
        self.month_button.setText(f"{year}년 {month}월")

        # 요일 헤더
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
            if weekday_idx == 6:
                color = colors['sunday']
            elif weekday_idx == 5:
                color = colors['saturday']
            label.setStyleSheet(f"color: {color.name()}; font-weight: bold;")
            self.calendar_grid.addWidget(label, 0, grid_col_idx)
            col_map[weekday_idx] = grid_col_idx
            grid_col_idx += 1

        # 날짜 셀 구성
        first_day_of_month = self.current_date.replace(day=1)
        _, num_days_in_month = calendar.monthrange(self.current_date.year, self.current_date.month)
        last_day_of_month = self.current_date.replace(day=num_days_in_month)

        if start_day_of_week_setting == 6:
            offset = (first_day_of_month.weekday() + 1) % 7  # 일=0 기준
        else:
            offset = first_day_of_month.weekday()  # 월=0 기준
        start_date_of_view = first_day_of_month - datetime.timedelta(days=offset)

        end_of_5th_week = start_date_of_view + datetime.timedelta(days=34)
        num_days_in_grid = 35 if last_day_of_month <= end_of_5th_week else 42

        today = datetime.date.today()
        for i in range(num_days_in_grid):
            current_day_obj = start_date_of_view + datetime.timedelta(days=i)
            weekday_idx = current_day_obj.weekday()
            if hide_weekends and weekday_idx in [5, 6]:
                continue
            if weekday_idx not in col_map:
                continue

            grid_row = i // 7 + 1
            grid_col = col_map[weekday_idx]

            cell_widget = DayCellWidget(current_day_obj, self)
            cell_widget.add_event_requested.connect(self.add_event_requested)

            # ← 기본 화면 팝오버를 위해 마우스 이벤트를 부모가 훔쳐보도록 셀에도 필터 장착
            cell_widget.installEventFilter(self)
            cell_widget.events_container.installEventFilter(self)

            font_color = colors['weekday']
            is_current_month = current_day_obj.month == self.current_date.month
            if not is_current_month:
                font_color = colors['other_month']
            elif weekday_idx == 6:
                font_color = colors['sunday']
            elif weekday_idx == 5:
                font_color = colors['saturday']

            cell_widget.day_label.setStyleSheet(
                f"color: {font_color.name()}; background-color: transparent;"
            )

            if current_day_obj == today:
                cell_widget.setStyleSheet(
                    "background-color: rgba(0, 120, 215, 51); border-radius: 5px;"
                )
                cell_widget.day_label.setStyleSheet(
                    f"color: {colors['today_fg'].name()}; font-weight: bold; background-color: transparent;"
                )

            self.calendar_grid.addWidget(cell_widget, grid_row, grid_col)
            self.date_to_cell_map[current_day_obj] = cell_widget

        # 늘리기
        for i in range(1, self.calendar_grid.rowCount()):
            self.calendar_grid.setRowStretch(i, 1)
        for i in range(self.calendar_grid.columnCount()):
            self.calendar_grid.setColumnStretch(i, 1)

        # 렌더 예약
        self.schedule_draw_events()

    def schedule_draw_events(self):
        QTimer.singleShot(10, self._draw_events_internal)

    # ---------------------------
    # 이벤트 배치 계산 + 그리기 준비
    # ---------------------------
    def _draw_events_internal(self):
        if not self.date_to_cell_map:
            return

        # 더보기/자리 차지 위젯 초기화
        for cell in self.date_to_cell_map.values():
            cell.clear_events()

        # 이벤트 필터링
        all_events = self.data_manager.get_events(
            self.current_date.year, self.current_date.month
        )
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [
            e for e in all_events if (not selected_ids or e.get('calendarId') in selected_ids)
        ]

        # 배치 계산(세그먼트 포함)
        calculator = MonthLayoutCalculator(filtered_events, self.date_to_cell_map.keys())
        event_positions, _ = calculator.calculate()

        # 폰트/행 높이 파라미터
        fm = QFontMetrics(self.font())
        self._event_height = max(16, fm.height() + 2)
        self._lane_spacing = 2

        # 각 날짜 셀 상단 y오프셋(라벨 높이)과 표시 가능한 레인 수
        y_offset_by_date = {}
        max_slots_by_date = {}
        for d, cell in self.date_to_cell_map.items():
            y_offset = cell.day_label.height() + cell.layout().spacing()
            y_offset_by_date[d] = y_offset
            available = max(0, (cell.height() - y_offset) // (self._event_height + self._lane_spacing))
            max_slots_by_date[d] = available

        # 날짜별 실제 점유 레인 및 세그먼트 목록
        from collections import defaultdict
        lanes_by_day = defaultdict(set)
        segments_covering_day = defaultdict(list)
        for pos in event_positions:
            for seg in pos.get('segments', []):
                for day in seg['days']:
                    if day in self.date_to_cell_map:
                        lanes_by_day[day].add(seg['y_level'])
                        segments_covering_day[day].append(seg)

        # 날짜별 컷오프/숨김
        cutoff_by_date = {}
        self._hidden_events_by_date = {}
        for day, lanes in lanes_by_day.items():
            lanes_sorted = sorted(lanes)
            total = len(lanes_sorted)
            max_slots = max_slots_by_date.get(day, 0)
            show_more = (total > max_slots) and (max_slots > 0)
            cutoff = max_slots - 1 if show_more else max_slots
            cutoff = max(0, cutoff)
            cutoff_by_date[day] = cutoff

            hidden = []
            if cutoff < total:
                visible_levels = set(lanes_sorted[:cutoff])
                for seg in segments_covering_day[day]:
                    if seg['y_level'] not in visible_levels:
                        hidden.append(seg['event'])
            uniq, seen_ids = [], set()
            for ev in hidden:
                eid = ev.get('id')
                if eid not in seen_ids:
                    uniq.append(ev)
                    seen_ids.add(eid)
            self._hidden_events_by_date[day] = uniq

        # 컷오프 자리 위젯 및 +N 더보기 버튼
        for day, cell in self.date_to_cell_map.items():
            cutoff = cutoff_by_date.get(day, 0)
            for i in range(cutoff):
                placeholder = QWidget(cell)
                placeholder.setFixedHeight(self._event_height)
                placeholder.setMouseTracking(True)
                placeholder.installEventFilter(self)
                cell.events_layout.insertWidget(i, placeholder)

            hidden = self._hidden_events_by_date.get(day, [])
            if hidden:
                more_btn = QPushButton(f"+ {len(hidden)}개 더보기")
                more_btn.setStyleSheet(
                    "text-align: left; border: none; color: #82a7ff; "
                    "background-color: transparent; padding: 0px; font-size: 8pt;"
                )
                more_btn.setFixedHeight(self._event_height)
                more_btn.setMouseTracking(True)
                more_btn.installEventFilter(self)
                more_btn.clicked.connect(lambda _, d=day, e=hidden: self.show_more_events_popup(d, e))
                cell.events_layout.insertWidget(cutoff, more_btn)

        # 렌더링 박스 생성(셀 좌표계 -> 뷰 좌표계)
        self._render_boxes = []
        cell_left_by_date, cell_right_by_date, cell_top_by_date = {}, {}, {}

        for d, cell in self.date_to_cell_map.items():
            top_left = cell.mapTo(self, QPoint(0, 0))
            rect = cell.geometry()  # 부모 기준
            x = top_left.x()
            y = top_left.y()
            w = rect.width()
            cell_left_by_date[d] = x
            cell_right_by_date[d] = x + w
            cell_top_by_date[d] = y

        # 세그먼트 -> 실제 그릴 연속 구간(runs) 생성
        for pos in event_positions:
            ev = pos['event']
            for seg in pos.get('segments', []):
                draw_days = []
                for day in seg.get('days', []):
                    if (day in self.date_to_cell_map) and (seg['y_level'] < cutoff_by_date.get(day, 0)):
                        draw_days.append(day)

                runs = []
                if draw_days:
                    run_start = draw_days[0]
                    prev = draw_days[0]
                    for d in draw_days[1:]:
                        if (d - prev).days == 1:
                            prev = d
                        else:
                            runs.append((run_start, prev))
                            run_start = d
                            prev = d
                    runs.append((run_start, prev))

                # ▼ 이 세그먼트에서 "첫 번째로 보이는 run"에는 제목을 찍는다.
                first_visible_run = True

                for r_start, r_end in runs:
                    left_x = cell_left_by_date[r_start]
                    right_x = cell_right_by_date[r_end]
                    top_y = cell_top_by_date[r_start] + y_offset_by_date[r_start] + \
                            seg['y_level'] * (self._event_height + self._lane_spacing)

                    rect = QRectF(left_x + 2, top_y, (right_x - left_x) - 4, self._event_height)

                    # 라운딩: 실제 이벤트의 시작/끝 세그먼트일 때만 둥글게
                    left_round = (seg['segment_start'] == r_start) and seg['is_head']
                    right_round = (seg['segment_end'] == r_end) and seg['is_tail']
                    if seg.get('is_single', False):
                        left_round = True
                        right_round = True

                    self._render_boxes.append({
                        'rect': rect,
                        'event': ev,
                        'left_round': left_round,
                        'right_round': right_round,
                        'y_level': seg['y_level'],
                        # ▼ 새로 추가: 텍스트 표시 여부(세그먼트의 첫 가시 run에만 True)
                        'show_text': first_visible_run
                    })
                    first_visible_run = False

        self.update()  # paintEvent 트리거


    # ---------------------------
    # 캡슐(좌/우 라운딩) 그리기
    # ---------------------------
    # 기존 _paint_capsule를 아래로 완전 교체
    def _paint_capsule(self, painter: QPainter, rect: QRectF, color: QColor,
                    left_round: bool, right_round: bool):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

        r = min(6.0, rect.height() / 2.0)
        r = min(r, rect.width() / 2.0)
        if r <= 0.0:
            painter.drawRect(rect)
            return

        path = QPainterPath()

        # 시작점: 상단-좌측(라운드면 r만큼 안쪽)
        path.moveTo(rect.left() + (r if left_round else 0.0), rect.top())

        # 상단 직선 → 우측(라운드면 r 이전까지)
        path.lineTo(rect.right() - (r if right_round else 0.0), rect.top())

        # 우측 라운드(상단→하단, 시계방향)
        if right_round:
            path.arcTo(QRectF(rect.right() - 2*r, rect.top(), 2*r, rect.height()), 90, -180)
        else:
            path.lineTo(rect.right(), rect.bottom())

        # 하단 직선 → 좌측(라운드면 r 다음부터)
        path.lineTo(rect.left() + (r if left_round else 0.0), rect.bottom())

        # 좌측 라운드(하단→상단, 시계방향)
        if left_round:
            path.arcTo(QRectF(rect.left(), rect.top(), 2*r, rect.height()), 270, -180)
        else:
            path.lineTo(rect.left(), rect.top())

        path.closeSubpath()
        painter.drawPath(path)


    # ---------------------------
    # 히트 테스트
    # ---------------------------
    def get_event_at(self, pos):
        # QPoint -> QPointF 변환
        if isinstance(pos, QPoint):
            pos = QPointF(pos)
        for item in reversed(self._render_boxes):  # 위에 그린 것부터
            if item['rect'].contains(pos):
                return item['event']
        return None

    # ---------------------------
    # 팝오버 처리(공통)
    # ---------------------------
    def _handle_hover_at(self, pos_qpoint):
        ev = self.get_event_at(pos_qpoint)
        if ev is not None:
            if self._hover_event != ev:
                self._hover_event = ev
                self.handle_hover_enter(self, ev)  # BaseView 공용 팝오버
        else:
            if self._hover_event is not None:
                self.handle_hover_leave(self)
                self._hover_event = None

    # ---------------------------
    # eventFilter: 자식들이 먹는 마우스 이동을 여기서 처리
    # ---------------------------
    def eventFilter(self, obj, ev):
        et = ev.type()
        if et == QEvent.Type.MouseMove:
            # obj 로컬 좌표 -> MonthView 좌표
            if isinstance(ev, QMouseEvent):
                localf = ev.position()
                pos_in_self = obj.mapTo(self, QPoint(int(localf.x()), int(localf.y())))
                self._handle_hover_at(pos_in_self)
        elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            if self._hover_event is not None:
                self.handle_hover_leave(self)
                self._hover_event = None
        return super().eventFilter(obj, ev)

    # ---------------------------
    # 마우스/컨텍스트 메뉴
    # ---------------------------
    def mouseMoveEvent(self, event):
        # 부모 자신 위에서 움직일 때도 동작
        self._handle_hover_at(event.position())
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        ev = self.get_event_at(event.position())
        if ev:
            self.edit_event_requested.emit(ev)
        else:
            # 어느 날짜 셀인지 찾아서 새 일정 추가
            target = self.childAt(event.pos().toPoint())
            while target and not isinstance(target, DayCellWidget):
                target = target.parent()
            if isinstance(target, DayCellWidget):
                self.add_event_requested.emit(target.date_obj)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        target_event = self.get_event_at(event.pos())

        date_info = None
        target_widget = self.childAt(event.pos())
        while target_widget and target_widget != self:
            if isinstance(target_widget, DayCellWidget):
                date_info = target_widget.date_obj
                break
            target_widget = target_widget.parent()

        # BaseView 공용 컨텍스트 메뉴
        self.show_context_menu(event.globalPos(), target_event, date_info)

    # ---------------------------
    # 페인트
    # ---------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for item in self._render_boxes:
            rect = item['rect']
            ev = item['event']
            color = QColor(ev.get('color', '#555555'))

            # 완료 여부
            is_completed = self.data_manager.is_event_completed(ev.get('id'))

            painter.save()
            if is_completed:
                painter.setOpacity(0.5)

            # 바디
            self._paint_capsule(
                painter, rect, color,
                item.get('left_round', False),
                item.get('right_round', False)
            )

            # ▼ 텍스트는 세그먼트의 첫 가시 run에서만 보이도록(show_text)
            if item.get('show_text', item.get('left_round', False)):
                summary = ev.get('summary', '제목 없음')
                text_color = QColor(get_text_color_for_background(color.name()))
                painter.setPen(text_color)
                f = painter.font()
                f.setStrikeOut(bool(is_completed))
                painter.setFont(f)

                fm = painter.fontMetrics()
                elided = fm.elidedText(summary, Qt.TextElideMode.ElideRight, int(rect.width()) - 8)
                painter.drawText(
                    rect.adjusted(4, 0, -4, 0),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    elided
                )
            painter.restore()
