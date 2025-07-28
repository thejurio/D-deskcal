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
    - 지능형 팝업 위치 조정
    """
    def __init__(self, parent=None, settings=None, pos: QPoint = None):
        super().__init__(parent)
        self.settings = settings
        self.click_pos = pos
        self.oldPos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.apply_opacity()

    def showEvent(self, event):
        """다이얼로그가 표시되기 직전에 호출되어 위치를 조정합니다."""
        # 먼저 부모의 showEvent를 호출하여 다이얼로그의 지오메트리를 확정합니다.
        super().showEvent(event)

        if self.click_pos and self.parent():
            parent_rect = self.parent().geometry()
            dialog_size = self.frameGeometry().size()

            # 기본 위치: 클릭 지점
            x, y = self.click_pos.x(), self.click_pos.y()

            # 오른쪽 경계 확인
            if x + dialog_size.width() > parent_rect.right():
                x = self.click_pos.x() - dialog_size.width()
            
            # 아래쪽 경계 확인
            if y + dialog_size.height() > parent_rect.bottom():
                y = self.click_pos.y() - dialog_size.height()

            # 왼쪽/위쪽 경계 확인
            if x < parent_rect.left():
                x = parent_rect.left()
            if y < parent_rect.top():
                y = parent_rect.top()
            
            self.move(x, y)
        
        elif self.parent():
            # 클릭 위치 정보가 없으면 부모의 중앙에 배치
            parent_center = self.parent().geometry().center()
            dialog_rect = self.frameGeometry()
            self.move(parent_center - dialog_rect.center())

    def apply_opacity(self):
        if self.settings:
            main_opacity = self.settings.get("window_opacity", 0.95)
            # 메인 창보다 85% 덜 투명하게 (더 불투명하게)
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
    def __init__(self, parent=None, title="알림", text="메시지 내용", settings=None, pos=None):
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