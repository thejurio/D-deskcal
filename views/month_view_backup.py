# views/month_view.py
import datetime
import calendar
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

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
        
        # 클릭된 위치를 부모 좌표계로 변환
        parent_pos = self.mapToParent(event.pos())
        parent_posf = QPointF(parent_pos)
        
        # 부모에서 해당 위치의 이벤트 확인
        if hasattr(self.parent(), 'get_event_at'):
            ev = self.parent().get_event_at(parent_posf)
            if ev:
                # 일정이 있으면 상세보기 요청 (더블클릭 = 상세보기)
                self.parent().detail_requested.emit(ev)
                return
        
        # 일정이 없으면 새 일정 추가 처리
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
        self._pending_context_pos = None  # PyInstaller 환경 대응
        self.initUI()

        # 데이터 갱신 연결 (디바운스된 스마트 업데이트 사용)
        self.data_manager.event_completion_changed.connect(lambda: self._update_debounce_timer.start())
        self.data_manager.sync_state_changed.connect(self.on_sync_state_changed)

        # 페인터 렌더링 캐시
        self._render_boxes = []           # [{'rect': QRectF, 'event': dict, 'left_round': bool, 'right_round': bool, 'y_level': int}]
        self._hidden_events_by_date = {}  # date -> [event,...]
        self._event_height = 18
        
        self._lane_spacing = 2
        self._hover_event = None
        
        # 무한 루프 방지를 위한 플래그
        self._drawing_scheduled = False
        self._drawing_in_progress = False
        
        # paintEvent용 마우스 추적 변수 (BaseView 팝오버 시스템 사용)
        self._current_hover_event = None
        
        # 팝오버 안정성을 위한 지연 타이머
        self._leave_timer = QTimer()
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(10)  # 10ms - 극한의 응답성
        self._leave_timer.timeout.connect(self._delayed_hover_leave)
        
        # 스마트 업데이트 시스템
        self._last_event_hash = None
        self._is_rendering = False
        self._pending_updates = []
        
        # 배치 업데이트 디바운스 시스템
        self._update_debounce_timer = QTimer()
        self._update_debounce_timer.setSingleShot(True)
        self._update_debounce_timer.setInterval(50)  # 50ms 디바운스
        self._update_debounce_timer.timeout.connect(self._debounced_smart_refresh)

    # BaseView 쪽에서 호출됨  
    def on_data_updated(self, year, month):
        if year == self.current_date.year and month == self.current_date.month:
            # 디바운스된 업데이트 사용 (짧은 시간 내 여러 신호를 하나로 합침)
            self._update_debounce_timer.start()
    
    def _debounced_smart_refresh(self):
        """디바운스된 스마트 리프레시"""
        self.smart_refresh()
    
    def _calculate_events_hash(self):
        """현재 표시할 이벤트들의 해시값 계산"""
        all_events = self.data_manager.get_events(
            self.current_date.year, self.current_date.month
        )
        selected_ids = self.main_widget.settings.get("selected_calendars", [])
        filtered_events = [
            e for e in all_events if (not selected_ids or e.get('calendarId') in selected_ids)
        ]
        
        # 이벤트 ID와 수정 시간으로 해시 생성
        event_signatures = []
        for event in filtered_events:
            signature = (
                event.get('id', ''),
                event.get('updated', ''),
                event.get('summary', ''),
                str(event.get('start', {})),
                str(event.get('end', {})),
                event.get('color', '')
            )
            event_signatures.append(signature)
        
        return hash(tuple(sorted(event_signatures)))
    
    def smart_refresh(self):
        """스마트 업데이트: 실제 변경사항이 있을 때만 리프레시"""
        logger.debug("Smart refresh called")
        
        # 팝오버가 활성화되어 있으면 업데이트 지연
        if self.current_popover and self.current_popover.isVisible():
            logger.debug("Popover active - delaying refresh")
            self._pending_updates.append('refresh')
            return
        
        # 렌더링 중이면 업데이트 지연  
        if self._is_rendering:
            logger.debug("Rendering in progress - delaying refresh")
            self._pending_updates.append('refresh')
            return
            
        current_hash = self._calculate_events_hash()
        
        # 해시가 같으면 변경사항 없음 - 리프레시 스킵
        if current_hash == self._last_event_hash:
            logger.debug("Hash unchanged - skipping refresh")
            return
            
        logger.debug("Hash changed - performing refresh")
        self._last_event_hash = current_hash
        self.refresh()
    
    def resizeEvent(self, event):
        """리사이즈 시 실시간으로 이벤트 위치 재계산"""
        super().resizeEvent(event)
        if hasattr(self, 'date_to_cell_map') and self.date_to_cell_map:
            # 리사이즈가 완료된 후 이벤트 다시 그리기
            self.schedule_draw_events()

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

        center_nav_layout = QHBoxLayout()
        center_nav_layout.setSpacing(0)
        center_nav_layout.setContentsMargins(25, 0, 0, 0)
        center_nav_layout.addWidget(self.month_button)

        nav_layout.addWidget(prev_button)
        nav_layout.addStretch(1)
        nav_layout.addLayout(center_nav_layout)
        nav_layout.addStretch(1)
        nav_layout.addWidget(next_button)

        # 3픽셀 여백 추가 후 네비게이션 바 추가 (2픽셀 위로 이동)
        self.main_layout.addSpacing(3)
        self.main_layout.addLayout(nav_layout)

        self.calendar_grid = QGridLayout()
        self.calendar_grid.setObjectName("calendar_grid")
        self.calendar_grid.setSpacing(0)
        self.main_layout.addLayout(self.calendar_grid)

    # ---------------------------
    # 동기화 인디케이터
    # ---------------------------
    def on_sync_state_changed(self, is_syncing, year, month):
        """동기화 상태 변경 알림 (이제 동기화 일시정지는 팝오버 생성/소멸 시 처리)"""
        pass
    
    def show_popover(self):
        """팝오버 표시 시 동기화 일시정지 및 렌더링 보호"""
        # 동기화 일시정지
        if hasattr(self.data_manager, 'caching_manager') and hasattr(self.data_manager.caching_manager, 'pause_sync'):
            self.data_manager.caching_manager.pause_sync()
        
        # 기존 BaseView의 show_popover 호출
        super().show_popover()
        
        # 팝오버가 생성되었으면 close 이벤트 연결
        if self.current_popover:
            # 기존 close 메서드 백업하고 새로운 close 메서드로 교체
            original_close = self.current_popover.close
            
            def enhanced_close():
                original_close()
                # 동기화 재개
                if hasattr(self.data_manager, 'caching_manager') and hasattr(self.data_manager.caching_manager, 'resume_sync'):
                    self.data_manager.caching_manager.resume_sync()
                # 펜딩된 업데이트 처리
                if self._pending_updates:
                    QTimer.singleShot(100, self._process_pending_updates)
            
            self.current_popover.close = enhanced_close
                
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
            self.current_date, None,
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
            date_obj, events, None,
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

        # 해시 업데이트 (실제 refresh 실행 시)
        self._last_event_hash = self._calculate_events_hash()

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
            
            # 기본적으로 autoFillBackground를 False로 설정
            cell_widget.setAutoFillBackground(False)

            if current_day_obj == today:
                logger.debug(f"Setting up today cell: {current_day_obj}")
                cell_widget.setProperty("isToday", True)
                cell_widget.style().unpolish(cell_widget)
                cell_widget.style().polish(cell_widget)
                # 오늘 강조를 위한 추가 처리 - 레이어 순서 보장
                cell_widget.setAutoFillBackground(True)
                
                # 강제로 오늘 셀에 파란색 배경 적용
                cell_widget.setStyleSheet("""
                    DayCellWidget[isToday="true"] {
                        background-color: rgba(0, 120, 215, 80) !important;
                        border-radius: 5px !important;
                        border: none !important;
                    }
                """)
                
                cell_widget.day_label.setStyleSheet(
                    f"color: {colors['today_fg'].name()}; font-weight: bold; background-color: transparent;"
                )
                # 오늘 셀을 다른 위젯보다 앞으로 가져와서 하이라이트가 보이도록 함
                cell_widget.raise_()

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
        # 무한 루프 방지: 이미 스케줄되어 있거나 진행 중이면 무시
        if self._drawing_scheduled or self._drawing_in_progress:
            return
        
        self._drawing_scheduled = True
        QTimer.singleShot(10, self._draw_events_internal)

    # ---------------------------
    # 이벤트 배치 계산 + 그리기 준비
    # ---------------------------
    def _draw_events_internal(self):
        # 플래그 초기화
        self._drawing_scheduled = False
        
        # 이미 진행 중이면 무시 (재귀 방지)
        if self._drawing_in_progress:
            return
            
        if not self.date_to_cell_map:
            return
            
        # 진행 중 플래그 설정
        self._drawing_in_progress = True
        self._is_rendering = True

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
        
        # 오늘 날짜 셀이 있으면 맨 앞으로 가져와서 하이라이트가 보이도록 함
        today = datetime.date.today()
        if today in self.date_to_cell_map:
            today_cell = self.date_to_cell_map[today]
            today_cell.raise_()
        
        # 진행 중 플래그 해제
        self._drawing_in_progress = False
        self._is_rendering = False
        
        # 펜딩 업데이트 처리
        if self._pending_updates:
            QTimer.singleShot(50, self._process_pending_updates)

    def _process_pending_updates(self):
        """렌더링 완료 후 펜딩된 업데이트들 처리"""
        if not self._pending_updates:
            return
            
        # 팝오버가 여전히 활성화되어 있으면 조금 더 기다림
        if self.current_popover and self.current_popover.isVisible():
            QTimer.singleShot(100, self._process_pending_updates)
            return
        
        updates = self._pending_updates.copy()
        self._pending_updates.clear()
        
        for update in updates:
            if update == 'refresh':
                self.smart_refresh()

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
    # 개선된 히트 테스트
    # ---------------------------
    def get_event_at(self, pos):
        """위치에서 이벤트 찾기 - 성능과 정확도 개선"""
        # QPoint -> QPointF 변환
        if isinstance(pos, QPoint):
            pos = QPointF(pos)
        
        # _render_boxes가 없으면 None 반환
        if not hasattr(self, '_render_boxes') or not self._render_boxes:
            logger.debug(f"get_event_at: render_boxes empty, count={len(getattr(self, '_render_boxes', []))}")
            return None
            
        # Removed excessive position logging
        
        # 역순으로 검사 (위쪽 레이어부터)
        for i, item in enumerate(reversed(self._render_boxes)):
            rect = item['rect']
            
            # 기본 히트 테스트
            if rect.contains(pos):
                logger.debug(f"Found event: {item['event'].get('summary')}")
                return item['event']
        
        logger.debug("No exact hit, trying with margin")
        
        # 정확한 히트가 없으면 약간의 마진을 두고 재검사
        margin = 3.0  # 3픽셀 마진 (터치 친화적)
        for i, item in enumerate(reversed(self._render_boxes)):
            rect = item['rect']
            expanded_rect = rect.adjusted(-margin, -margin, margin, margin)
            if expanded_rect.contains(pos):
                logger.debug(f"Found event with margin: {item['event'].get('summary')}")
                return item['event']
        
        # Event not found - this is normal, no logging needed
        return None
    
    def get_events_in_area(self, rect_area):
        """특정 영역 내의 모든 이벤트 찾기 (다중 선택용)"""
        if not hasattr(self, '_render_boxes') or not self._render_boxes:
            return []
            
        found_events = []
        for item in self._render_boxes:
            if rect_area.intersects(item['rect']):
                found_events.append(item['event'])
        
        return found_events

    # ---------------------------
    # 팝오버 처리 (BaseView 시스템 사용)
    # ---------------------------
    def _handle_hover_at(self, pos_qpoint):
        """마우스 위치에서 이벤트를 찾아서 BaseView 팝오버 시스템에 전달"""
        ev = self.get_event_at(pos_qpoint)
        
        if ev is not None:
            # leave 타이머 중단 (이벤트가 있으면 leave하지 않음)
            self._leave_timer.stop()
            
            # 이벤트 ID로 비교 (객체 비교 대신 ID 비교로 깜빡임 방지)
            current_id = self._current_hover_event.get('id') if self._current_hover_event and hasattr(self._current_hover_event, 'get') else None
            new_id = ev.get('id') if hasattr(ev, 'get') else None
            
            if current_id != new_id:
                self._current_hover_event = ev
                if hasattr(ev, 'get'):
                    # BaseView의 팝오버 시스템 사용
                    self.handle_hover_enter(self, ev)
        else:
            if self._current_hover_event is not None:
                # 즉시 leave하지 않고 타이머로 지연
                self._leave_timer.start()
    
    def _delayed_hover_leave(self):
        """지연된 hover leave 처리 - 현재 마우스 위치 재확인"""
        if self._current_hover_event is not None:
            # 현재 마우스 위치에서 이벤트가 있는지 다시 확인
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            ev = self.get_event_at(cursor_pos)
            
            if ev is not None:
                logger.debug("Mouse still over event, keeping popover")
                return  # 여전히 이벤트 위에 있으면 leave하지 않음
            
            logger.debug("Calling handle_hover_leave")
            self.handle_hover_leave(self)
            self._current_hover_event = None

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
        elif et == QEvent.Type.MouseButtonPress:
            # PyInstaller 환경에서 안정적인 우클릭 처리
            if isinstance(ev, QMouseEvent) and ev.button() == Qt.MouseButton.RightButton:
                logger.debug(f"Right-click detected at {ev.pos()}")
                
                # obj 로컬 좌표 -> MonthView 좌표 변환
                if obj == self:
                    context_pos = ev.pos()
                else:
                    context_pos = obj.mapTo(self, ev.pos())
                
                logger.debug(f"Converted position: {context_pos}")
                
                # 지연된 컨텍스트 메뉴 처리 (이벤트 루프에서 안전하게)
                self._pending_context_pos = context_pos
                QTimer.singleShot(0, self._process_deferred_context_menu)
                return True  # 이벤트 전파 차단
        elif et in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            if self._current_hover_event is not None:
                # 지연된 leave 처리
                self._leave_timer.start()
        return super().eventFilter(obj, ev)

    # ---------------------------
    # 마우스/컨텍스트 메뉴
    # ---------------------------
    def mouseMoveEvent(self, event):
        # 부모 자신 위에서 움직일 때도 동작
        pos = event.position()
        if isinstance(pos, QPointF):
            pos = QPoint(int(pos.x()), int(pos.y()))
        self._handle_hover_at(pos)
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Mouse double-click event started - removed verbose logging
        if not self.main_widget.is_interaction_unlocked():
            return
        
        # 이벤트 위치에서 일정 찾기
        pos = event.position()
        ev = self.get_event_at(pos)
        
        if ev:
            # 일정이 발견되면 상세보기 다이얼로그로 열기 (더블클릭 = 상세보기)
            logger.info(f"Event double-clicked for details: {ev.get('summary', 'Unknown')}")
            self.detail_requested.emit(ev)
        else:
            # 일정이 없으면 새 일정 추가 모드 (날짜 영역에서만)
            logger.debug("Empty area double-clicked - checking date")
            target = self.childAt(event.pos())
            while target and not isinstance(target, DayCellWidget):
                target = target.parent()
            if isinstance(target, DayCellWidget):
                logger.info("Double-click on date area - adding new event")
                self.add_event_requested.emit(target.date_obj)
            else:
                logger.debug("Double-click on non-date area - ignored")



    def contextMenuEvent(self, event):
        if not self.main_widget.is_interaction_unlocked():
            return
        
        logger.debug(f"Context menu requested at {event.pos()}")
        
        # 우선 렌더박스에서 이벤트 찾기
        target_event = self.get_event_at(event.pos())
        logger.debug(f"Target event found: {target_event.get('summary') if target_event else 'None'}")
        
        # 렌더박스에서 찾지 못했으면 위젯 트리에서 EventLabelWidget 찾기 (백업)
        if not target_event:
            target_widget = self.childAt(event.pos())
            while target_widget and target_widget != self:
                if hasattr(target_widget, 'event_data'):
                    target_event = target_widget.event_data
                    logger.debug(f"Found via widget tree: {target_event.get('summary')}")
                    break
                target_widget = target_widget.parent()

        # 날짜 정보 찾기
        date_info = None
        target_widget = self.childAt(event.pos())
        while target_widget and target_widget != self:
            if isinstance(target_widget, DayCellWidget):
                date_info = target_widget.date_obj
                break
            target_widget = target_widget.parent()

        logger.debug(f"Final context menu target: event={target_event.get('summary') if target_event else 'None'}, date={date_info}")
        
        # BaseView 공용 컨텍스트 메뉴
        self.show_context_menu(event.globalPos(), target_event, date_info)

    def _process_deferred_context_menu(self):
        """PyInstaller 환경을 위한 지연된 컨텍스트 메뉴 처리"""
        if not hasattr(self, '_pending_context_pos') or self._pending_context_pos is None:
            logger.debug("No pending context menu position")
            return
            
        pos = self._pending_context_pos
        self._pending_context_pos = None  # 처리 완료 표시
        
        logger.debug(f"Processing deferred context menu at {pos}")
        
        if not self.main_widget.is_interaction_unlocked():
            logger.debug("Interaction locked - skipping context menu")
            return
            
        # 향상된 이벤트 탐지 (여러 방법으로 시도)
        target_event = None
        
        # 방법 1: 기본 render_boxes 검색
        target_event = self.get_event_at(pos)
        logger.debug(f"Method 1 result: {target_event.get('summary') if target_event else 'None'}")
        
        # 방법 2: 확장된 히트 영역으로 재시도
        if not target_event:
            expanded_margin = 8.0  # PyInstaller 환경에서 더 큰 마진
            target_event = self._get_event_at_with_margin(pos, expanded_margin)
            logger.debug(f"Method 2 (margin) result: {target_event.get('summary') if target_event else 'None'}")
        
        # 방법 3: 위젯 트리 검색
        if not target_event:
            target_widget = self.childAt(pos)
            while target_widget and target_widget != self:
                if hasattr(target_widget, 'event_data'):
                    target_event = target_widget.event_data
                    logger.debug(f"Method 3 (widget tree) result: {target_event.get('summary')}")
                    break
                target_widget = target_widget.parent()

        # 날짜 정보 찾기
        date_info = None
        target_widget = self.childAt(pos)
        while target_widget and target_widget != self:
            if isinstance(target_widget, DayCellWidget):
                date_info = target_widget.date_obj
                break
            target_widget = target_widget.parent()

        logger.debug(f"Deferred context menu final result - event={target_event.get('summary') if target_event else 'None'}, date={date_info}")
        
        # 글로벌 위치 계산
        global_pos = self.mapToGlobal(pos)
        
        # BaseView 공용 컨텍스트 메뉴 호출
        self.show_context_menu(global_pos, target_event, date_info)

    def _get_event_at_with_margin(self, pos, margin):
        """확장된 마진으로 이벤트 검색 (PyInstaller 환경 대응)"""
        if isinstance(pos, QPoint):
            pos = QPointF(pos)
        
        if not hasattr(self, '_render_boxes') or not self._render_boxes:
            return None
            
        # 큰 마진으로 검사
        for item in reversed(self._render_boxes):
            rect = item['rect']
            expanded_rect = rect.adjusted(-margin, -margin, margin, margin)
            if expanded_rect.contains(pos):
                logger.debug(f"Found with margin {margin}: {item['event'].get('summary')}")
                return item['event']
        
        return None

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

        # 모든 이벤트를 그린 후에 오늘 하이라이트를 맨 위에 다시 그리기
        self._paint_today_highlight(painter)

    def _paint_today_highlight(self, painter):
        """오늘 날짜 하이라이트를 직접 그리기 (모든 레이어 위에)"""
        today = datetime.date.today()
        
        # 오늘 날짜가 현재 달력에 있는지 확인
        if today not in self.date_to_cell_map:
            return
            
        today_cell = self.date_to_cell_map[today]
        
        # 셀의 실제 위치와 크기 가져오기
        cell_pos = today_cell.mapTo(self, QPoint(0, 0))
        cell_rect = today_cell.rect()
        
        # 실제 그릴 영역 계산
        highlight_rect = QRectF(
            cell_pos.x() + 2,  # 2픽셀 마진
            cell_pos.y() + 2,
            cell_rect.width() - 4,
            cell_rect.height() - 4
        )
        
        # 하이라이트 배경 그리기
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 120, 215, 80))  # rgba(0, 120, 215, 80)
        painter.drawRoundedRect(highlight_rect, 5, 5)
        painter.restore()
        
        logger.debug(f"Drawing today highlight: {today}, rect={highlight_rect}")
