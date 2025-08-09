# recurrence_dialog.py
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QWidget, QComboBox, QSpinBox, QDateEdit, 
                             QRadioButton, QButtonGroup, QLineEdit, QCalendarWidget)
from PyQt6.QtCore import Qt, QDate, QEvent, QPoint, pyqtSignal, QDateTime
from PyQt6.QtGui import QIcon
from dateutil.rrule import rrule, rrulestr, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU

from custom_dialogs import BaseDialog

class DateSelector(QWidget):
    """
    QLineEdit를 클릭하면 캘린더 팝업이 나타나는 커스텀 날짜 선택 위젯.
    """
    dateChanged = pyqtSignal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_date = QDate.currentDate()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.line_edit = QLineEdit()
        self.line_edit.setReadOnly(True)
        self.line_edit.installEventFilter(self)

        layout.addWidget(self.line_edit)

        self.calendar_popup = QCalendarWidget(self)
        self.calendar_popup.setWindowFlags(Qt.WindowType.Popup)
        self.calendar_popup.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar_popup.clicked.connect(self.date_selected_from_popup)
        
        self.update_display()

    def eventFilter(self, obj, event):
        if obj == self.line_edit and event.type() == QEvent.Type.MouseButtonPress:
            self.show_calendar()
            return True
        return super().eventFilter(obj, event)

    def show_calendar(self):
        self.calendar_popup.setSelectedDate(self.current_date)
        pos = self.mapToGlobal(self.line_edit.geometry().bottomLeft())
        self.calendar_popup.move(pos)
        self.calendar_popup.show()

    def date_selected_from_popup(self, date):
        self.setDate(date)
        self.calendar_popup.close()

    def setDate(self, qdate):
        if self.current_date != qdate:
            self.current_date = qdate
            self.update_display()
            self.dateChanged.emit(self.current_date)

    def date(self):
        return self.current_date

    def update_display(self):
        self.line_edit.setText(self.current_date.toString("yyyy-MM-dd"))

class RecurrenceRuleDialog(BaseDialog):
    def __init__(self, rrule_str=None, start_date=None, parent=None, settings=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.initial_start_date = start_date if start_date else QDate.currentDate()
        
        self.setWindowTitle("반복 설정")
        self.setMinimumWidth(350)
        self.initUI()
        self.parse_rrule(rrule_str)
        self.freq_combo.currentIndexChanged.connect(self.update_ui_by_freq)
        self.update_ui_by_freq()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        start_date_layout = QHBoxLayout()
        self.start_date_selector = DateSelector()
        self.start_date_selector.setDate(self.initial_start_date)
        start_date_layout.addWidget(QLabel("시작일:"))
        start_date_layout.addWidget(self.start_date_selector)
        layout.addLayout(start_date_layout)

        freq_layout = QHBoxLayout()
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 99)
        self.freq_combo = QComboBox()
        self.freq_combo.addItem("일", DAILY)
        self.freq_combo.addItem("주", WEEKLY)
        self.freq_combo.addItem("개월", MONTHLY)
        self.freq_combo.addItem("년", YEARLY)
        
        freq_layout.addWidget(QLabel("매"))
        freq_layout.addWidget(self.interval_spin)
        freq_layout.addWidget(self.freq_combo)
        freq_layout.addWidget(QLabel("마다 반복"))
        layout.addLayout(freq_layout)

        self.weekly_widget = QWidget()
        weekly_layout = QHBoxLayout(self.weekly_widget)
        weekly_layout.setContentsMargins(0,0,0,0)
        self.weekday_buttons = {}
        self.weekday_map = {0: MO, 1: TU, 2: WE, 3: TH, 4: FR, 5: SA, 6: SU}
        for i, day_str in enumerate(["월", "화", "수", "목", "금", "토", "일"]):
            btn = QPushButton(day_str)
            btn.setCheckable(True)
            weekly_layout.addWidget(btn)
            self.weekday_buttons[i] = btn
        layout.addWidget(self.weekly_widget)

        self.monthly_widget = QWidget()
        monthly_layout = QVBoxLayout(self.monthly_widget)
        monthly_layout.setContentsMargins(0,0,0,0)
        self.monthly_by_day_radio = QRadioButton("매월 특정 날짜에 반복 (예: 15일)")
        self.monthly_by_weekday_radio = QRadioButton("매월 특정 주차/요일에 반복")
        self.monthly_by_day_radio.setChecked(True)
        
        monthly_weekday_layout = QHBoxLayout()
        self.monthly_week_combo = QComboBox()
        self.monthly_week_combo.addItems(["첫째 주", "둘째 주", "셋째 주", "넷째 주", "마지막 주"])
        self.monthly_weekday_combo = QComboBox()
        self.monthly_weekday_combo.addItems(["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"])
        monthly_weekday_layout.addWidget(self.monthly_week_combo)
        monthly_weekday_layout.addWidget(self.monthly_weekday_combo)

        monthly_layout.addWidget(self.monthly_by_day_radio)
        monthly_layout.addWidget(self.monthly_by_weekday_radio)
        monthly_layout.addLayout(monthly_weekday_layout)
        layout.addWidget(self.monthly_widget)

        ends_layout = QVBoxLayout()
        self.ends_never_radio = QRadioButton("안 함")
        self.ends_on_radio = QRadioButton("종료일:")
        self.ends_after_radio = QRadioButton("횟수:")
        
        self.ends_group = QButtonGroup()
        self.ends_group.addButton(self.ends_never_radio)
        self.ends_group.addButton(self.ends_on_radio)
        self.ends_group.addButton(self.ends_after_radio)
        self.ends_never_radio.setChecked(True)

        ends_on_layout = QHBoxLayout()
        self.ends_on_selector = DateSelector()
        self.ends_on_selector.setDate(self.initial_start_date.addMonths(3))
        ends_on_layout.addWidget(self.ends_on_radio)
        ends_on_layout.addWidget(self.ends_on_selector)

        ends_after_layout = QHBoxLayout()
        self.ends_after_spin = QSpinBox()
        self.ends_after_spin.setRange(1, 999)
        ends_after_layout.addWidget(self.ends_after_radio)
        ends_after_layout.addWidget(self.ends_after_spin)

        ends_layout.addWidget(self.ends_never_radio)
        ends_layout.addLayout(ends_on_layout)
        ends_layout.addLayout(ends_after_layout)
        layout.addLayout(ends_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.save_button = QPushButton("확인")
        self.cancel_button = QPushButton("취소")
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def update_ui_by_freq(self):
        selected_freq = self.freq_combo.currentData()
        self.weekly_widget.setVisible(selected_freq == WEEKLY)
        self.monthly_widget.setVisible(selected_freq == MONTHLY)

    def parse_rrule(self, rrule_str):
        if not rrule_str or not rrule_str.startswith("RRULE:"):
            self.freq_combo.setCurrentIndex(1)
            start_weekday = self.initial_start_date.dayOfWeek() - 1
            self.weekday_buttons[start_weekday].setChecked(True)
            return

        try:
            # QDate를 Python의 date 객체로 변환하여 전달
            start_pydate = self.initial_start_date.toPyDate()
            rule = rrulestr(rrule_str.replace("RRULE:", ""), dtstart=start_pydate)
            
            self.freq_combo.setCurrentIndex(self.freq_combo.findData(rule._freq))
            self.interval_spin.setValue(rule._interval)

            if rule._byweekday:
                if not rule._bymonthday and not rule._byyearday and not rule._bymonth:
                    for i, btn in self.weekday_buttons.items():
                        is_checked = any(wd.weekday == i for wd in rule._byweekday)
                        btn.setChecked(is_checked)

            if rule._freq == MONTHLY:
                if rule._byweekday:
                    self.monthly_by_weekday_radio.setChecked(True)
                    pos = rule._byweekday[0].n
                    self.monthly_week_combo.setCurrentIndex(pos - 1 if pos > 0 else 4)
                    self.monthly_weekday_combo.setCurrentIndex(rule._byweekday[0].weekday)
                else:
                    self.monthly_by_day_radio.setChecked(True)

            if rule._until:
                self.ends_on_radio.setChecked(True)
                self.ends_on_selector.setDate(QDate(rule._until))
            elif rule._count:
                self.ends_after_radio.setChecked(True)
                self.ends_after_spin.setValue(rule._count)
            else:
                self.ends_never_radio.setChecked(True)

        except Exception as e:
            print(f"RRULE 파싱 실패: {e}")

    def get_rule_data(self):
        rrule_str = self.generate_rrule_string()
        start_date = self.start_date_selector.date()
        return rrule_str, start_date

    def generate_rrule_string(self):
        parts = []
        freq = self.freq_combo.currentData()
        freq_map = {DAILY: "DAILY", WEEKLY: "WEEKLY", MONTHLY: "MONTHLY", YEARLY: "YEARLY"}
        parts.append(f"FREQ={freq_map[freq]}")
        
        interval = self.interval_spin.value()
        if interval > 1:
            parts.append(f"INTERVAL={interval}")

        if freq == WEEKLY:
            byday = [self.weekday_map[i].name for i, btn in self.weekday_buttons.items() if btn.isChecked()]
            if byday:
                parts.append(f"BYDAY={','.join(byday)}")
        
        elif freq == MONTHLY:
            if self.monthly_by_weekday_radio.isChecked():
                week_pos = self.monthly_week_combo.currentIndex()
                setpos = week_pos + 1 if week_pos < 4 else -1
                day_index = self.monthly_weekday_combo.currentIndex()
                day_name = self.weekday_map[day_index].name
                parts.append(f"BYDAY={day_name}")
                parts.append(f"BYSETPOS={setpos}")

        if self.ends_on_radio.isChecked():
            until_date = self.ends_on_selector.date().toPyDate()
            parts.append(f"UNTIL={until_date.strftime('%Y%m%d')}T235959Z")
        elif self.ends_after_radio.isChecked():
            parts.append(f"COUNT={self.ends_after_spin.value()}")
            
        return "RRULE:" + ";".join(parts) if parts else None