# recurrence_dialog.py
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QWidget, QComboBox, QSpinBox, QDateEdit, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, QDate
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU

from custom_dialogs import BaseDialog

class RecurrenceRuleDialog(BaseDialog):
    def __init__(self, rrule_str=None, start_date=None, parent=None, settings=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.start_date = start_date if start_date else QDate.currentDate()
        
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

        # 0. 시작일 지정
        start_date_layout = QHBoxLayout()
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(self.start_date)
        start_date_layout.addWidget(QLabel("시작일:"))
        start_date_layout.addWidget(self.start_date_edit)
        layout.addLayout(start_date_layout)

        # 1. 반복 주기
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

        # 2. 요일 선택 (주간 반복 시)
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

        # 2.5. 월간 반복 옵션
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

        # 3. 종료 조건
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
        self.ends_on_dateedit = QDateEdit()
        self.ends_on_dateedit.setCalendarPopup(True)
        self.ends_on_dateedit.setDate(self.start_date.addMonths(3))
        ends_on_layout.addWidget(self.ends_on_radio)
        ends_on_layout.addWidget(self.ends_on_dateedit)

        ends_after_layout = QHBoxLayout()
        self.ends_after_spin = QSpinBox()
        self.ends_after_spin.setRange(1, 999)
        ends_after_layout.addWidget(self.ends_after_radio)
        ends_after_layout.addWidget(self.ends_after_spin)

        ends_layout.addWidget(self.ends_never_radio)
        ends_layout.addLayout(ends_on_layout)
        ends_layout.addLayout(ends_after_layout)
        layout.addLayout(ends_layout)

        # 확인/취소 버튼
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
        """반복 주기에 따라 관련 UI를 활성화/비활성화합니다."""
        selected_freq = self.freq_combo.currentData()
        self.weekly_widget.setVisible(selected_freq == WEEKLY)
        self.monthly_widget.setVisible(selected_freq == MONTHLY)

    def parse_rrule(self, rrule_str):
        """기존 RRULE 문자열을 파싱하여 UI에 상태를 설정합니다."""
        if not rrule_str or not rrule_str.startswith("RRULE:"):
            # 기본값: 매주, 현재 요일 선택
            self.freq_combo.setCurrentIndex(1) # 주
            start_weekday = self.start_date.dayOfWeek() -1 # Qt(월=1) -> dateutil(월=0)
            self.weekday_buttons[start_weekday].setChecked(True)
            return

        try:
            # RRULE 파싱을 위해 dtstart를 제공해야 정확하게 동작합니다.
            rule = rrulestr(rrule_str.replace("RRULE:", ""), dtstart=self.start_date.toPyDate())
            
            # 주기 및 간격 설정
            self.freq_combo.setCurrentIndex(self.freq_combo.findData(rule._freq))
            self.interval_spin.setValue(rule._interval)

            # 주간 반복 시 요일 설정
            if rule._byweekday:
                # 월간 반복의 BYDAY=(MO(+1)) 같은 형태와 주간 반복의 BYDAY=MO,TU를 구분
                if not rule._bymonthday and not rule._byyearday and not rule._bymonth:
                    weekday_indices = {day.weekday: day for day in self.weekday_map.values()}
                    for i, btn in self.weekday_buttons.items():
                        is_checked = any(wd.weekday == i for wd in rule._byweekday)
                        btn.setChecked(is_checked)

            # 월간 반복 설정
            if rule._freq == MONTHLY:
                if rule._byweekday:
                    self.monthly_by_weekday_radio.setChecked(True)
                    pos = rule._byweekday[0].n # +1, -1 등
                    self.monthly_week_combo.setCurrentIndex(pos - 1 if pos > 0 else 4) # 5번째를 '마지막'으로
                    self.monthly_weekday_combo.setCurrentIndex(rule._byweekday[0].weekday)
                else:
                    self.monthly_by_day_radio.setChecked(True)

            # 종료 조건 설정
            if rule._until:
                self.ends_on_radio.setChecked(True)
                self.ends_on_dateedit.setDate(QDate(rule._until))
            elif rule._count:
                self.ends_after_radio.setChecked(True)
                self.ends_after_spin.setValue(rule._count)
            else:
                self.ends_never_radio.setChecked(True)

        except Exception as e:
            print(f"RRULE 파싱 실패: {e}")

    def get_rule_data(self):
        """UI 상태를 기반으로 RRULE 문자열과 시작일을 반환합니다."""
        rrule_str = self.generate_rrule_string()
        start_date = self.start_date_edit.date()
        return rrule_str, start_date

    def generate_rrule_string(self):
        """UI 상태를 기반으로 RRULE 문자열을 생성합니다."""
        # '반복 안 함'에 해당하는 프리셋이 없으므로, 사용자가 직접 UI를 조작하여
        # 반복 없음을 나타내도록 유도해야 합니다. 예를 들어, freq_combo의 첫 항목을
        # '반복 없음'으로 두고, 해당 항목이 선택되면 None을 반환하게 할 수 있습니다.
        # 현재 구현에서는 freq_combo에 '반복 없음' 항목이 없으므로 항상 규칙을 생성합니다.

        parts = []
        freq = self.freq_combo.currentData()
        freq_map = {DAILY: "DAILY", WEEKLY: "WEEKLY", MONTHLY: "MONTHLY", YEARLY: "YEARLY"}
        parts.append(f"FREQ={freq_map[freq]}")
        
        interval = self.interval_spin.value()
        if interval > 1:
            parts.append(f"INTERVAL={interval}")

        if freq == WEEKLY:
            byday = [str(self.weekday_map[i]) for i, btn in self.weekday_buttons.items() if btn.isChecked()]
            if byday:
                parts.append(f"BYDAY={','.join(byday)}")
        
        elif freq == MONTHLY:
            if self.monthly_by_weekday_radio.isChecked():
                week_pos = self.monthly_week_combo.currentIndex()
                setpos = week_pos + 1 if week_pos < 4 else -1
                
                day_index = self.monthly_weekday_combo.currentIndex()
                day_name = str(self.weekday_map[day_index])
                
                parts.append(f"BYDAY={day_name}")
                parts.append(f"BYSETPOS={setpos}")

        if self.ends_on_radio.isChecked():
            until_date = self.ends_on_dateedit.date().toPyDate()
            parts.append(f"UNTIL={until_date.strftime('%Y%m%d')}T235959Z")
        elif self.ends_after_radio.isChecked():
            parts.append(f"COUNT={self.ends_after_spin.value()}")
            
        return "RRULE:" + ";".join(parts) if parts else None
