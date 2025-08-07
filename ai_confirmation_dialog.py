# ai_confirmation_dialog.py
import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QLineEdit, QComboBox, QTextEdit,
                             QCalendarWidget, QTimeEdit, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTime

from custom_dialogs import BaseDialog

class CalendarPopup(QDialog):
    """날짜 선택을 위한 달력 팝업"""
    date_selected = pyqtSignal(QDate)

    def __init__(self, parent=None, current_date_str=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        
        if current_date_str:
            try:
                initial_date = QDate.fromString(current_date_str, "yyyy-MM-dd")
                if initial_date.isValid():
                    self.calendar.setSelectedDate(initial_date)
            except Exception:
                pass # 파싱 실패 시 오늘 날짜로 둠

        self.calendar.clicked.connect(self.on_date_clicked)
        layout.addWidget(self.calendar)

    def on_date_clicked(self, date):
        self.date_selected.emit(date)
        self.close()

class EventEditWidget(QWidget):
    """AI가 분석한 개별 일정을 표시하고 수정하는 위젯"""
    def __init__(self, event_data, index):
        super().__init__()
        self.event_data = event_data
        self.index = index
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        self.setObjectName("event_card")

        top_layout = QHBoxLayout()
        self.selector_checkbox = QCheckBox("이 일정 등록하기")
        self.selector_checkbox.setChecked(True)
        top_layout.addWidget(self.selector_checkbox)
        top_layout.addStretch(1)
        self.all_day_checkbox = QCheckBox("하루 종일")
        top_layout.addWidget(self.all_day_checkbox)
        main_layout.addLayout(top_layout)

        self.title_input = QLineEdit(self.event_data.get('title', ''))
        main_layout.addWidget(self.title_input)

        # --- 날짜 및 시간 UI 개선 ---
        grid_layout = QGridLayout()
        
        # 시작일
        self.start_date_input = QLineEdit(self.event_data.get('startDate', ''))
        self.start_date_input.setReadOnly(True)
        start_cal_button = QPushButton("📅")
        start_cal_button.clicked.connect(lambda: self.show_calendar(self.start_date_input))
        
        # 시작 시간
        self.start_time_input = QTimeEdit()
        self.start_time_input.setDisplayFormat("HH:mm")
        if self.event_data.get('startTime'):
            self.start_time_input.setTime(QTime.fromString(self.event_data['startTime'], "HH:mm"))
        else:
            self.all_day_checkbox.setChecked(True) # 시간이 없으면 하루종일로 간주

        grid_layout.addWidget(QLabel("시작:"), 0, 0)
        grid_layout.addWidget(self.start_date_input, 0, 1)
        grid_layout.addWidget(start_cal_button, 0, 2)
        grid_layout.addWidget(self.start_time_input, 0, 3)

        # 종료일
        self.end_date_input = QLineEdit(self.event_data.get('endDate', ''))
        self.end_date_input.setReadOnly(True)
        end_cal_button = QPushButton("📅")
        end_cal_button.clicked.connect(lambda: self.show_calendar(self.end_date_input))

        # 종료 시간
        self.end_time_input = QTimeEdit()
        self.end_time_input.setDisplayFormat("HH:mm")
        if self.event_data.get('endTime'):
            self.end_time_input.setTime(QTime.fromString(self.event_data['endTime'], "HH:mm"))

        grid_layout.addWidget(QLabel("종료:"), 1, 0)
        grid_layout.addWidget(self.end_date_input, 1, 1)
        grid_layout.addWidget(end_cal_button, 1, 2)
        grid_layout.addWidget(self.end_time_input, 1, 3)
        
        main_layout.addLayout(grid_layout)
        
        # 설명
        self.description_input = QTextEdit(self.event_data.get('description', ''))
        self.description_input.setFixedHeight(60)
        main_layout.addWidget(self.description_input)

        # 마감일 옵션
        self.deadline_checkbox = None
        if self.event_data.get('startDate') != self.event_data.get('endDate'):
            self.deadline_checkbox = QCheckBox("마감일만 등록 (종료일에 하루 종일 일정으로 등록)")
            main_layout.addWidget(self.deadline_checkbox)

        # 시그널 연결 및 초기 상태 설정
        self.all_day_checkbox.stateChanged.connect(self.toggle_time_edits)
        self.toggle_time_edits(self.all_day_checkbox.isChecked())

    def show_calendar(self, target_line_edit):
        popup = CalendarPopup(self, target_line_edit.text())
        popup.date_selected.connect(lambda date: target_line_edit.setText(date.toString("yyyy-MM-dd")))
        
        button = self.sender()
        popup_pos = self.mapToGlobal(button.pos())
        popup_pos.setY(popup_pos.y() + button.height())
        popup.move(popup_pos)
        popup.show()

    def toggle_time_edits(self, checked):
        self.start_time_input.setEnabled(not checked)
        self.end_time_input.setEnabled(not checked)

    def get_data(self):
        if not self.selector_checkbox.isChecked():
            return None
        
        is_deadline_only = self.deadline_checkbox.isChecked() if self.deadline_checkbox else False
        is_all_day = self.all_day_checkbox.isChecked()

        return {
            'title': self.title_input.text(),
            'startDate': self.start_date_input.text(),
            'startTime': self.start_time_input.time().toString("HH:mm") if not is_all_day else "",
            'endDate': self.end_date_input.text(),
            'endTime': self.end_time_input.time().toString("HH:mm") if not is_all_day else "",
            'location': self.event_data.get('location', ''),
            'description': self.description_input.toPlainText(),
            'isDeadlineOnly': is_deadline_only,
            'isAllDay': is_all_day
        }

class AIConfirmationDialog(BaseDialog):
    """AI 분석 결과를 확인하고, 수정하여 등록하는 다이얼로그"""
    def __init__(self, parsed_events, data_manager, parent=None, settings=None, pos=None):
        super().__init__(parent, settings, pos)
        self.parsed_events = parsed_events
        self.data_manager = data_manager
        self.event_widgets = []

        self.setWindowTitle("AI 분석 결과 확인")
        self.setMinimumSize(600, 500)
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(f"AI가 {len(self.parsed_events)}개의 일정을 찾았습니다. 등록할 캘린더를 선택하세요."))
        top_layout.addStretch(1)
        self.calendar_combo = QComboBox()
        self.populate_calendars()
        top_layout.addWidget(self.calendar_combo)
        content_layout.addLayout(top_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.events_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area)

        for i, event_data in enumerate(self.parsed_events):
            event_widget = EventEditWidget(event_data, i)
            self.events_layout.addWidget(event_widget)
            self.event_widgets.append(event_widget)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.register_button = QPushButton("선택한 일정 등록")
        self.register_button.setDefault(True)
        self.register_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.register_button)
        content_layout.addLayout(button_layout)

    def populate_calendars(self):
        all_calendars = self.data_manager.get_all_calendars(fetch_if_empty=True)
        for cal in all_calendars:
            self.calendar_combo.addItem(cal['summary'], cal['id'])
        
        last_id = self.settings.get('last_selected_calendar_id')
        if last_id:
            index = self.calendar_combo.findData(last_id)
            if index != -1:
                self.calendar_combo.setCurrentIndex(index)

    def get_final_events_and_calendar(self):
        final_events = []
        for widget in self.event_widgets:
            data = widget.get_data()
            if data:
                final_events.append(data)
        
        calendar_id = self.calendar_combo.currentData()
        provider_name = self.get_provider_for_calendar(calendar_id)

        return final_events, calendar_id, provider_name

    def get_provider_for_calendar(self, calendar_id):
        all_calendars = self.data_manager.get_all_calendars(fetch_if_empty=False)
        for cal in all_calendars:
            if cal['id'] == calendar_id:
                return cal.get('provider')
        return None