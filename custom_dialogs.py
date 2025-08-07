import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QWidget, QComboBox, QStackedWidget, QGridLayout, QScrollArea, QMenu, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QAction

class BaseDialog(QDialog):
    """
    모든 커스텀 다이얼로그의 기반이 되는 클래스.
    - 프레임리스 윈도우, 드래그 이동
    - 메인 윈도우와 연동된 투명도 적용
    - PyQt 기본 중앙 정렬 위치 사용
    """
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
        self.setMinimumWidth(350)
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
        start_year = self.current_display_year - (self.current_display_year % 12)
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
        self.week_view = self.create_list_view(self.select_week) # Week view is a list

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
        # Clear previous buttons
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
        # Find the index of the button text in the combo box to get the date
        for i in range(self.week_view.layout().count() -1): # Exclude stretch
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

class EventPopover(QDialog):
    """
    이벤트 위에 마우스를 올렸을 때 상세 정보를 보여주는 팝오버 위젯.
    """
# custom_dialogs.py 파일의 EventPopover 클래스

    def __init__(self, event_data, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        background_widget = QWidget()
        # ▼▼▼ [수정] popover_background -> main_background로 변경 ▼▼▼
        background_widget.setObjectName("main_background")
        # ▲▲▲ 테마의 메인 배경 스타일을 그대로 사용하도록 이름 변경
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(12, 10, 12, 10)
        content_layout.setSpacing(5)

        # 1. 이벤트 제목
        summary = event_data.get('summary', '(제목 없음)')
        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        content_layout.addWidget(summary_label)

        # 2. 이벤트 시간
        time_text = self.format_event_time(event_data)
        if time_text:
            time_label = QLabel(time_text)
            time_label.setStyleSheet("font-size: 9pt; color: #B0B0B0;")
            content_layout.addWidget(time_label)

    def format_event_time(self, event_data):
        """이벤트 데이터로부터 시간 문자열을 포맷팅합니다."""
        start = event_data.get('start', {})
        end = event_data.get('end', {})

        if 'dateTime' in start: # 시간 지정 이벤트
            start_dt = datetime.datetime.fromisoformat(start['dateTime'])
            end_dt = datetime.datetime.fromisoformat(end['dateTime'])
            
            if start_dt.date() == end_dt.date():
                return f"{start_dt.strftime('%p %I:%M')} - {end_dt.strftime('%p %I:%M')}"
            else:
                return f"{start_dt.strftime('%m/%d %p %I:%M')} - {end_dt.strftime('%m/%d %p %I:%M')}"
        
        elif 'date' in start: # 종일 이벤트
            start_date = datetime.date.fromisoformat(start['date'])
            end_date = datetime.date.fromisoformat(end['date'])
            
            # Google Calendar API는 종일 이벤트의 end.date를 실제 종료일+1일로 주므로, -1일 해줘야 함
            if (end_date - start_date).days == 1:
                 return f"{start_date.strftime('%Y년 %m월 %d일')} (하루 종일)"
            else:
                 end_date_adjusted = end_date - datetime.timedelta(days=1)
                 return f"{start_date.strftime('%m월 %d일')} - {end_date_adjusted.strftime('%m월 %d일')}"
        return ""
