import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QWidget, QStackedWidget, QGridLayout, QScrollArea, QMenu, QGraphicsOpacityEffect, QTextEdit, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QObject, QThread, QEvent, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QCursor
import gemini_parser

class BaseDialog(QDialog):
    def __init__(self, parent=None, settings=None, pos: QPoint = None):
        super().__init__(parent)
        self.settings = settings
        self.oldPos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.apply_opacity()

    def apply_opacity(self):
        if self.settings:
            main_opacity = self.settings.get("window_opacity", 0.95)
            dialog_opacity = main_opacity + (1 - main_opacity) * 0.85
            self.setWindowOpacity(dialog_opacity)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

class CustomMessageBox(BaseDialog):
    def __init__(self, parent=None, title="알림", text="메시지 내용", settings=None, pos=None, ok_only=False):
        super().__init__(parent, settings, pos)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        content_layout.addWidget(self.title_label)
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setMinimumHeight(50)
        self.text_label.setStyleSheet("padding-top: 10px; padding-bottom: 10px;")
        content_layout.addWidget(self.text_label)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.yes_button = QPushButton("확인")
        self.yes_button.clicked.connect(self.accept)
        button_layout.addWidget(self.yes_button)
        self.no_button = QPushButton("취소")
        self.no_button.clicked.connect(self.reject)
        button_layout.addWidget(self.no_button)
        
        if ok_only:
            self.no_button.setVisible(False)
            
        content_layout.addLayout(button_layout)

class NewDateSelectionDialog(BaseDialog):
    def __init__(self, current_date, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.current_display_year = current_date.year
        self.selected_year = current_date.year
        self.selected_month = current_date.month
        self.setWindowTitle("날짜 이동")
        self.setModal(True)
        self.setFixedSize(320, 320)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("<")
        self.next_button = QPushButton(">")
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.title_label)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.next_button)
        content_layout.addLayout(nav_layout)
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)
        bottom_layout = QHBoxLayout()
        self.back_to_year_button = QPushButton("연도 선택")
        self.back_to_year_button.setVisible(False)
        close_button = QPushButton("닫기")
        bottom_layout.addWidget(self.back_to_year_button)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(close_button)
        content_layout.addLayout(bottom_layout)
        self.year_view = self.create_grid_view(self.select_year)
        self.month_view = self.create_grid_view(self.select_month)
        self.stacked_widget.addWidget(self.year_view)
        self.stacked_widget.addWidget(self.month_view)
        self.prev_button.clicked.connect(self.on_prev_clicked)
        self.next_button.clicked.connect(self.on_next_clicked)
        self.back_to_year_button.clicked.connect(self.show_year_view)
        close_button.clicked.connect(self.reject)
        self.show_year_view()
    def create_grid_view(self, click_handler):
        view = QWidget()
        grid = QGridLayout(view)
        grid.setSpacing(5)
        for i in range(12):
            button = QPushButton()
            button.setFixedSize(65, 45)
            button.clicked.connect(lambda _, b=button: click_handler(b.text()))
            grid.addWidget(button, i // 4, i % 4)
        return view
    def show_year_view(self):
        self.current_mode = 'year'
        self.back_to_year_button.setVisible(False)
        self.populate_year_grid()
        self.stacked_widget.setCurrentWidget(self.year_view)
    def show_month_view(self):
        self.current_mode = 'month'
        self.back_to_year_button.setVisible(True)
        self.populate_month_grid()
        self.stacked_widget.setCurrentWidget(self.month_view)
    def populate_year_grid(self):
        start_year = self.current_display_year - 5
        self.title_label.setText(f"{start_year} - {start_year + 11}")
        grid = self.year_view.layout()
        for i in range(12):
            year = start_year + i
            button = grid.itemAt(i).widget()
            button.setText(str(year))
            button.setStyleSheet("")
            if year == self.selected_year:
                button.setStyleSheet("background-color: #0078D7;")
    def populate_month_grid(self):
        self.title_label.setText(f"{self.selected_year}년")
        grid = self.month_view.layout()
        for i in range(12):
            month = i + 1
            button = grid.itemAt(i).widget()
            button.setText(f"{month}월")
            button.setStyleSheet("")
            if self.selected_year == datetime.date.today().year and month == self.selected_month:
                 button.setStyleSheet("background-color: #0078D7;")
    def select_year(self, year_text):
        self.selected_year = int(year_text)
        self.show_month_view()
    def select_month(self, month_text):
        self.selected_month = int(month_text.replace("월", ""))
        self.accept()
    def on_prev_clicked(self):
        if self.current_mode == 'year':
            self.current_display_year -= 12
            self.populate_year_grid()
        else:
            self.selected_year -= 1
            self.populate_month_grid()
    def on_next_clicked(self):
        if self.current_mode == 'year':
            self.current_display_year += 12
            self.populate_year_grid()
        else:
            self.selected_year += 1
            self.populate_month_grid()
    def get_selected_date(self): return self.selected_year, self.selected_month

class WeekSelectionDialog(BaseDialog):
    def __init__(self, current_date, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.current_display_year = current_date.year
        self.selected_year = current_date.year
        self.selected_month = current_date.month
        self.selected_date = current_date
        self.weeks_in_month = []

        self.setWindowTitle("주 이동")
        self.setModal(True)
        self.setFixedSize(320, 320)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)

        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("<")
        self.next_button = QPushButton(">")
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.title_label)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.next_button)
        content_layout.addLayout(nav_layout)

        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        bottom_layout = QHBoxLayout()
        self.back_button = QPushButton("뒤로")
        self.back_button.setVisible(False)
        close_button = QPushButton("닫기")
        bottom_layout.addWidget(self.back_button)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(close_button)
        content_layout.addLayout(bottom_layout)

        self.year_view = self.create_grid_view(self.select_year, 4)
        self.month_view = self.create_grid_view(self.select_month, 4)
        self.week_view = self.create_list_view(self.select_week)

        self.stacked_widget.addWidget(self.year_view)
        self.stacked_widget.addWidget(self.month_view)
        self.stacked_widget.addWidget(self.week_view)

        self.prev_button.clicked.connect(self.on_prev_clicked)
        self.next_button.clicked.connect(self.on_next_clicked)
        self.back_button.clicked.connect(self.on_back_clicked)
        close_button.clicked.connect(self.reject)

        self.show_year_view()

    def create_grid_view(self, click_handler, cols=4):
        view = QWidget()
        grid = QGridLayout(view)
        grid.setSpacing(5)
        for i in range(12):
            button = QPushButton()
            button.setFixedSize(65, 45)
            button.clicked.connect(lambda _, b=button: click_handler(b))
            grid.addWidget(button, i // cols, i % cols)
        return view

    def create_list_view(self, click_handler):
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setSpacing(5)
        layout.setContentsMargins(0,0,0,0)
        return view

    def show_year_view(self):
        self.current_mode = 'year'
        self.back_button.setVisible(False)
        self.populate_year_grid()
        self.stacked_widget.setCurrentWidget(self.year_view)

    def show_month_view(self):
        self.current_mode = 'month'
        self.back_button.setVisible(True)
        self.populate_month_grid()
        self.stacked_widget.setCurrentWidget(self.month_view)

    def show_week_view(self):
        self.current_mode = 'week'
        self.back_button.setVisible(True)
        self.populate_week_list()
        self.stacked_widget.setCurrentWidget(self.week_view)

    def populate_year_grid(self):
        start_year = self.current_display_year - (self.current_display_year % 12)
        self.title_label.setText(f"{start_year} - {start_year + 11}")
        grid = self.year_view.layout()
        for i in range(12):
            year = start_year + i
            button = grid.itemAt(i).widget()
            button.setText(str(year))
            button.setStyleSheet("background-color: transparent;" if year != self.selected_year else "background-color: #0078D7;")

    def populate_month_grid(self):
        self.title_label.setText(f"{self.selected_year}년")
        grid = self.month_view.layout()
        for i in range(12):
            month = i + 1
            button = grid.itemAt(i).widget()
            button.setText(f"{month}월")
            button.setStyleSheet("background-color: transparent;" if month != self.selected_month else "background-color: #0078D7;")

    def populate_week_list(self):
        self.title_label.setText(f"{self.selected_year}년 {self.selected_month}월")
        layout = self.week_view.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.weeks_in_month.clear()
        first_day = datetime.date(self.selected_year, self.selected_month, 1)
        cal_start_date = first_day - datetime.timedelta(days=(first_day.weekday() + 1) % 7)

        week_num = 1
        current_date = cal_start_date
        while True:
            start_of_week = current_date
            end_of_week = start_of_week + datetime.timedelta(days=6)

            if start_of_week.month == self.selected_month or end_of_week.month == self.selected_month:
                self.weeks_in_month.append(start_of_week)
                week_text = f"{week_num}주 ({start_of_week.strftime('%m.%d')} ~ {end_of_week.strftime('%m.%d')})"
                
                button = QPushButton(week_text)
                button.setFixedSize(280, 40)
                button.clicked.connect(lambda _, b=button: self.select_week(b))
                
                is_current_week = start_of_week <= self.selected_date <= end_of_week
                button.setStyleSheet("background-color: #0078D7;" if is_current_week else "background-color: transparent;")
                
                layout.addWidget(button)
                week_num += 1

            current_date += datetime.timedelta(days=7)
            if current_date.month > self.selected_month and current_date.year >= self.selected_year:
                if not (current_date.month == 1 and self.selected_month == 12):
                    break
            if current_date.year > self.selected_year:
                break
        layout.addStretch(1)

    def select_year(self, button):
        self.selected_year = int(button.text())
        self.show_month_view()

    def select_month(self, button):
        self.selected_month = int(button.text().replace("월", ""))
        self.show_week_view()
    
    def select_week(self, button):
        for i in range(self.week_view.layout().count() -1):
            if self.week_view.layout().itemAt(i).widget() == button:
                self.selected_date = self.weeks_in_month[i]
                break
        self.accept()

    def on_prev_clicked(self):
        if self.current_mode == 'year':
            self.current_display_year -= 12
            self.populate_year_grid()
        elif self.current_mode == 'month':
            self.selected_year -= 1
            self.populate_month_grid()
        elif self.current_mode == 'week':
            self.selected_month -= 1
            if self.selected_month == 0:
                self.selected_month = 12
                self.selected_year -= 1
            self.populate_week_list()

    def on_next_clicked(self):
        if self.current_mode == 'year':
            self.current_display_year += 12
            self.populate_year_grid()
        elif self.current_mode == 'month':
            self.selected_year += 1
            self.populate_month_grid()
        elif self.current_mode == 'week':
            self.selected_month += 1
            if self.selected_month == 13:
                self.selected_month = 1
                self.selected_year += 1
            self.populate_week_list()
            
    def on_back_clicked(self):
        if self.current_mode == 'week':
            self.show_month_view()
        elif self.current_mode == 'month':
            self.show_year_view()

    def get_selected_date(self):
        return self.selected_date

class MoreEventsDialog(BaseDialog):
    edit_requested = pyqtSignal(dict)
    delete_requested = pyqtSignal(dict)
    def __init__(self, date_obj, events, parent=None, settings=None, pos=None, data_manager=None):
        super().__init__(parent, settings, pos)
        self.date_obj = date_obj
        self.events = events
        self.data_manager = data_manager
        
        self.setWindowTitle(f"{date_obj.strftime('%Y-%m-%d')} 일정")
        self.setMinimumWidth(300)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        self.content_layout = QVBoxLayout(background_widget)
        title_label = QLabel(f"{date_obj.strftime('%Y년 %m월 %d일')}")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 5px;")
        self.content_layout.addWidget(title_label)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")
        self.content_layout.addWidget(self.scroll_area)
        
        self.rebuild_event_list()

        close_button_layout = QHBoxLayout()
        close_button_layout.addStretch(1)
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.reject)
        close_button_layout.addWidget(close_button)
        self.content_layout.addLayout(close_button_layout)
        
        # ▼ 팝오버 상태
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(500)
        self._hover_timer.timeout.connect(self._show_hover_popover)
        self._hover_target_btn = None
        self._hover_event_data = None
        self._current_popover = None

        self.edit_requested.connect(self.accept)
        self.delete_requested.connect(self.accept)
        
        if self.data_manager:
            self.data_manager.event_completion_changed.connect(self.rebuild_event_list)

    def rebuild_event_list(self):
        event_list_widget = QWidget()
        event_list_layout = QVBoxLayout(event_list_widget)
        event_list_layout.setContentsMargins(5, 0, 5, 5)
        event_list_layout.setSpacing(5)
        
        sorted_events = sorted(self.events, key=lambda e: (e['start'].get('dateTime', e['start'].get('date'))))
        for event in sorted_events:
            event_button = QPushButton(event.get('summary', '(제목 없음)'))
                        # ▼ 버튼에 호버 이벤트 연결
            event_button.setMouseTracking(True)
            event_button.installEventFilter(self)
            event_button._event_data = event

            if self.data_manager:
                finished = self.data_manager.is_event_completed(event.get('id'))
                style_sheet = f"background-color: {event.get('color', '#555555')}; text-align: left; padding-left: 10px;"
                if finished:
                    style_sheet += "text-decoration: line-through;"
                    opacity_effect = QGraphicsOpacityEffect()
                    opacity_effect.setOpacity(0.5)
                    event_button.setGraphicsEffect(opacity_effect)
                else:
                    event_button.setGraphicsEffect(None)
                event_button.setStyleSheet(style_sheet)

            event_button.clicked.connect(lambda _, e=event: self.edit_requested.emit(e))
            event_button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            event_button.customContextMenuRequested.connect(lambda pos, e=event: self.show_context_menu(pos, e))
            event_list_layout.addWidget(event_button)
            
        event_list_layout.addStretch(1)
        self.scroll_area.setWidget(event_list_widget)

    def eventFilter(self, obj, ev):
        if isinstance(obj, QPushButton):
            if ev.type() in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
                self._hover_target_btn = obj
                self._hover_event_data = getattr(obj, "_event_data", None)
                self._hover_timer.start()
            elif ev.type() in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                self._hover_timer.stop()
                self._close_hover_popover()
        return super().eventFilter(obj, ev)

    def _show_hover_popover(self):
        if not self._hover_event_data:
            return
        self._close_hover_popover()
        self._current_popover = EventPopover(self._hover_event_data, self.settings, self)

        # BaseView의 배치 로직과 동일(커서/화면 기준 정렬):contentReference[oaicite:8]{index=8}
        popover_size = self._current_popover.sizeHint()
        cursor_pos = QCursor.pos()
        screen_rect = self.screen().availableGeometry() if self.screen() else \
                      self.parent().screen().availableGeometry()

        x = cursor_pos.x() + 15 if cursor_pos.x() < screen_rect.center().x() else cursor_pos.x() - popover_size.width() - 15
        y = cursor_pos.y() + 15 if cursor_pos.y() < screen_rect.center().y() else cursor_pos.y() - popover_size.height() - 15

        x = max(screen_rect.left(), min(x, screen_rect.right() - popover_size.width()))
        y = max(screen_rect.top(),  min(y, screen_rect.bottom() - popover_size.height()))

        self._current_popover.move(x, y)
        self._current_popover.show()

    def _close_hover_popover(self):
        if self._current_popover:
            self._current_popover.close()
            self._current_popover = None

    def show_context_menu(self, pos, event_data):
        menu = QMenu(self)
        if self.settings:
            main_opacity = self.settings.get("window_opacity", 0.95)
            menu_opacity = main_opacity + (1 - main_opacity) * 0.85
            menu.setWindowOpacity(menu_opacity)

        edit_action = QAction("수정", self)
        edit_action.triggered.connect(lambda: self.edit_requested.emit(event_data))
        menu.addAction(edit_action)

        if self.data_manager:
            event_id = event_data.get('id')
            is_completed = self.data_manager.is_event_completed(event_id)
            if is_completed:
                reopen_action = QAction("진행", self)
                reopen_action.triggered.connect(lambda: self.data_manager.unmark_event_as_completed(event_id))
                menu.addAction(reopen_action)
            else:
                complete_action = QAction("완료", self)
                complete_action.triggered.connect(lambda: self.data_manager.mark_event_as_completed(event_id))
                menu.addAction(complete_action)

        delete_action = QAction("삭제", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(event_data))
        menu.addAction(delete_action)
        
        sender_button = self.sender()
        menu.exec(sender_button.mapToGlobal(pos))

class EventPopover(BaseDialog):
    def __init__(self, event_data, settings, parent=None):
        super().__init__(parent, settings)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        background_widget = QWidget()
        background_widget.setObjectName("popover_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(5)

        summary = event_data.get('summary', '(제목 없음)')
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        content_layout.addWidget(summary_label)

        time_text = self.format_event_time(event_data)
        if time_text:
            time_label = QLabel(time_text)
            time_label.setStyleSheet("font-size: 9pt; color: #B0B0B0;")
            content_layout.addWidget(time_label)
        
        self.apply_popover_opacity()

    def apply_popover_opacity(self):
        if not self.settings: return
        
        main_opacity = self.settings.get("window_opacity", 0.95)
        popover_opacity = min(1.0, main_opacity + 0.1)
        alpha = int(popover_opacity * 255)
        
        theme_name = self.settings.get("theme", "dark")
        base_color = "30, 30, 30" if theme_name == "dark" else "250, 250, 250"

        style = f"""
            QWidget#popover_background {{
                background-color: rgba({base_color}, {alpha});
                border-radius: 8px;
            }}
        """
        self.setStyleSheet(style)

    def format_event_time(self, event_data):
        start = event_data.get('start', {})
        end = event_data.get('end', {})

        if 'dateTime' in start:
            start_dt = datetime.datetime.fromisoformat(start['dateTime'])
            end_dt = datetime.datetime.fromisoformat(end['dateTime'])
            
            if start_dt.date() == end_dt.date():
                return f"{start_dt.strftime('%p %I:%M')} - {end_dt.strftime('%p %I:%M')}"
            else:
                return f"{start_dt.strftime('%m/%d %p %I:%M')} - {end_dt.strftime('%m/%d %p %I:%M')}"
        
        elif 'date' in start:
            start_date = datetime.date.fromisoformat(start['date'])
            end_date = datetime.date.fromisoformat(end['date'])
            
            if (end_date - start_date).days == 1:
                 return f"{start_date.strftime('%Y년 %m월 %d일')} (하루 종일)"
            else:
                 end_date_adjusted = end_date - datetime.timedelta(days=1)
                 return f"{start_date.strftime('%m월 %d일')} - {end_date_adjusted.strftime('%m월 %d일')}"
        return ""

class AIEventInputDialog(BaseDialog):
    def __init__(self, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.setWindowTitle("AI로 일정 추가")
        self.setModal(True)
        self.setMinimumSize(450, 300)
        
        # 항상 위에 표시되도록 플래그 추가
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel("분석할 텍스트를 입력하세요")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        content_layout.addWidget(title_label)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("여기에 이메일, 메신저 대화 내용 등을 붙여넣으세요...")
        content_layout.addWidget(self.text_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.analyze_button = QPushButton("분석 시작")
        self.analyze_button.setDefault(True)
        self.analyze_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.analyze_button)
        content_layout.addLayout(button_layout)

    def get_text(self):
        return self.text_input.toPlainText()

class HotkeyInputDialog(BaseDialog):
    def __init__(self, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.setWindowTitle("단축키 설정")
        self.setModal(True)
        self.setFixedSize(350, 180)

        self.hotkey_str = ""
        self.key_map = self._get_key_map()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)

        info_label = QLabel("등록할 단축키 조합을 누르세요.\n(예: Ctrl + Shift + F1)")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(info_label)

        self.hotkey_display = QLabel("...")
        self.hotkey_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hotkey_display.setObjectName("hotkey_display")
        self.hotkey_display.setMinimumHeight(40)
        content_layout.addWidget(self.hotkey_display)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.ok_button = QPushButton("확인")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        content_layout.addLayout(button_layout)

    def _get_key_map(self):
        key_map = {}
        for key_name in dir(Qt.Key):
            if key_name.startswith('Key_'):
                key_value = getattr(Qt.Key, key_name)
                key_map[key_value] = key_name.replace('Key_', '')
        return key_map

    def keyPressEvent(self, event):
        event.accept()
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_unknown, Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        mod_list = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            mod_list.append("Ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            mod_list.append("Shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            mod_list.append("Alt")

        key_str = self.key_map.get(key, QKeySequence(key).toString().upper())
        
        if not key_str or key_str.isspace():
             return

        if key_str not in mod_list:
            mod_list.append(key_str)

        self.hotkey_str = " + ".join(mod_list)
        self.hotkey_display.setText(self.hotkey_str)
        self.ok_button.setEnabled(True)

    def get_hotkey(self):
        return self.hotkey_str

class SingleKeyInputDialog(BaseDialog):
    def __init__(self, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.setWindowTitle("잠금 해제 키 설정")
        self.setModal(True)
        self.setFixedSize(350, 180)

        self.key_str = ""
        self.key_map = self._get_key_map()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)

        info_label = QLabel("등록할 키 하나를 누르세요.\n(예: Ctrl, Alt, Shift, F1, A 등)")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(info_label)

        self.key_display = QLabel("...")
        self.key_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_display.setObjectName("hotkey_display")
        self.key_display.setMinimumHeight(40)
        content_layout.addWidget(self.key_display)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.ok_button = QPushButton("확인")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        content_layout.addLayout(button_layout)

    def _get_key_map(self):
        key_map = {}
        for key_name in dir(Qt.Key):
            if key_name.startswith('Key_'):
                key_value = getattr(Qt.Key, key_name)
                # QKeySequence.toString()이 더 나은 이름을 제공하는 경우가 많으므로,
                # 기본적인 이름만 매핑하고 나머지는 QKeySequence에 의존합니다.
                key_map[key_value] = key_name.replace('Key_', '')
        return key_map

    def keyPressEvent(self, event):
        event.accept()
        key = event.key()
        
        # 제어 키(Ctrl, Alt 등) 자체는 무시하고, 다른 키와 조합될 때만 의미가 있도록 합니다.
        # 하지만 여기서는 단일 키를 원하므로, 키가 눌렸다는 사실 자체가 중요합니다.
        if key == Qt.Key.Key_unknown:
            return

        # Qt.Key enum 값으로부터 사람이 읽을 수 있는 문자열을 얻습니다.
        key_str = self.key_map.get(key, QKeySequence(key).toString())

        if not key_str or key_str.isspace():
             return

        self.key_str = key_str
        self.key_display.setText(self.key_str)
        self.ok_button.setEnabled(True)

    def get_key(self):
        # keyboard 라이브러리와 호환되도록 소문자로 반환
        return self.key_str.lower()

class ApiKeyVerifier(QObject):
    """API 키 유효성 검사를 백그라운드 스레드에서 실행하는 워커"""
    verification_finished = pyqtSignal(bool, str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        is_valid, message = gemini_parser.verify_api_key(self.api_key)
        self.verification_finished.emit(is_valid, message)

class APIKeyInputDialog(BaseDialog):
    def __init__(self, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.setWindowTitle("Gemini API 키 설정")
        self.setModal(True)
        self.setMinimumWidth(400)

        self.api_key = ""
        self.verification_thread = None
        self.verifier = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)

        title_label = QLabel("Gemini API 키 입력")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        content_layout.addWidget(title_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("여기에 API 키를 붙여넣으세요")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        content_layout.addWidget(self.api_key_input)

        self.status_label = QLabel(" ")
        self.status_label.setStyleSheet("font-size: 8pt; padding-top: 5px;")
        content_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.ok_button = QPushButton("확인 및 저장")
        self.ok_button.clicked.connect(self.verify_and_accept)
        self.ok_button.setDefault(True)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        content_layout.addLayout(button_layout)

    def verify_and_accept(self):
        self.api_key = self.api_key_input.text().strip()
        if not self.api_key:
            self.status_label.setText("API 키를 입력해주세요.")
            self.status_label.setStyleSheet("color: #E57373;")
            return

        self.ok_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("API 키 유효성을 확인하는 중입니다...")
        self.status_label.setStyleSheet("color: #9E9E9E;")

        self.verification_thread = QThread()
        self.verifier = ApiKeyVerifier(self.api_key)
        self.verifier.moveToThread(self.verification_thread)
        self.verifier.verification_finished.connect(self.on_verification_finished)
        self.verification_thread.started.connect(self.verifier.run)
        self.verification_thread.finished.connect(self.verification_thread.deleteLater)
        self.verification_thread.start()

    def on_verification_finished(self, is_valid, message):
        self.status_label.setText(message)
        if is_valid:
            self.status_label.setStyleSheet("color: #81C784;")
            # 잠시 후 다이얼로그를 닫습니다.
            QThread.msleep(500) 
            self.accept()
        else:
            self.status_label.setStyleSheet("color: #E57373;")
            self.ok_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
        
        self.verification_thread.quit()
        self.verification_thread.wait()

    def get_api_key(self):
        return self.api_key

    def closeEvent(self, event):
        if self.verification_thread and self.verification_thread.isRunning():
            self.verification_thread.quit()
            self.verification_thread.wait()
        super().closeEvent(event)

class RecurringDeleteDialog(BaseDialog):
    """
    A dialog to ask the user how to delete a recurring event.
    """
    def __init__(self, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.setWindowTitle("반복 일정 삭제")
        self.selected_option = None  # To store the user's choice

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(20, 15, 20, 15)
        content_layout.setSpacing(10)

        label = QLabel("이것은 반복 일정입니다. 어떻게 삭제하시겠습니까?")
        label.setWordWrap(True)
        content_layout.addWidget(label)

        # Create buttons
        self.instance_button = QPushButton("이 일정만 삭제")
        self.future_button = QPushButton("이 일정 및 향후 모든 일정 삭제")
        self.all_button = QPushButton("모든 일정 삭제")
        self.cancel_button = QPushButton("취소")

        # Connect signals
        self.instance_button.clicked.connect(lambda: self.set_option_and_accept('instance'))
        self.future_button.clicked.connect(lambda: self.set_option_and_accept('future'))
        self.all_button.clicked.connect(lambda: self.set_option_and_accept('all'))
        self.cancel_button.clicked.connect(self.reject)
        
        # Layout
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.instance_button)
        button_layout.addWidget(self.future_button)
        button_layout.addWidget(self.all_button)
        button_layout.addSpacing(10)
        button_layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)
        
        content_layout.addLayout(button_layout)

    def set_option_and_accept(self, option):
        self.selected_option = option
        self.accept()

    def get_selected_option(self):
        return self.selected_option
