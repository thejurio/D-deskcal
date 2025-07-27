import datetime
import uuid
from dateutil.rrule import rrulestr, rrule # 임포트를 상단으로 이동

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QTextEdit, QPushButton, QCheckBox, QDateTimeEdit, QComboBox, QWidget, QStackedWidget)
from PyQt6.QtCore import QDateTime, Qt

from custom_dialogs import CustomMessageBox, BaseDialog
from config import GOOGLE_CALENDAR_PROVIDER_NAME, LOCAL_CALENDAR_PROVIDER_NAME
from recurrence_dialog import RecurrenceRuleDialog

class EventEditorWindow(BaseDialog):
    # 삭제 액션을 위한 커스텀 반환 코드
    DeleteRole = 2

    # __init__ 생성자에 'calendars' 파라미터를 추가합니다.
    def __init__(self, mode='new', data=None, calendars=None, settings=None, parent=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.mode = mode
        self.calendars = calendars if calendars else []
        self.event_data = data if isinstance(data, dict) else {}
        self.date_info = data if isinstance(data, (datetime.date, datetime.datetime)) else None
        self.custom_rrule = None # 직접 설정한 RRULE 저장
        
        self.setWindowTitle("일정 추가" if self.mode == 'new' else "일정 수정")
        self.setMinimumWidth(400)
        self.setMinimumHeight(450)
        
        self.initUI()
        self.populate_data()

    def initUI(self):
        # ... (기존 initUI 상단 부분은 동일) ...
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(15, 15, 15, 15)

        self.calendar_combo = QComboBox()
        for calendar in self.calendars:
            user_data = {'id': calendar['id'], 'provider': calendar['provider']}
            self.calendar_combo.addItem(calendar['summary'], userData=user_data)
        
        layout.addWidget(QLabel("캘린더:"))
        layout.addWidget(self.calendar_combo)

        self.summary_edit = QLineEdit()
        layout.addWidget(QLabel("제목:"))
        layout.addWidget(self.summary_edit)

        time_layout = QHBoxLayout()
        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setCalendarPopup(True)
        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setCalendarPopup(True)
        
        time_layout.addWidget(QLabel("시작:"))
        time_layout.addWidget(self.start_time_edit)
        time_layout.addWidget(QLabel("종료:"))
        time_layout.addWidget(self.end_time_edit)
        layout.addLayout(time_layout)

        self.all_day_checkbox = QCheckBox("하루 종일")
        self.all_day_checkbox.stateChanged.connect(self.toggle_time_edit)
        
        # --- ▼▼▼ [개선] 반복 설정 UI (라벨 + 버튼 레이아웃) ▼▼▼ ---
        self.recurrence_layout = QHBoxLayout()
        self.recurrence_layout.setContentsMargins(0,0,0,0)
        
        self.recurrence_label = QLabel("반복")
        self.recurrence_button = QPushButton("반복 안 함")
        self.recurrence_button.setStyleSheet("text-align: right; border: none;")
        self.recurrence_arrow_label = QLabel(">")

        self.recurrence_layout.addWidget(self.recurrence_label)
        self.recurrence_layout.addWidget(self.recurrence_button, 1) # 버튼이 남은 공간을 모두 차지하도록 stretch=1
        self.recurrence_layout.addWidget(self.recurrence_arrow_label)

        # 전체 레이아웃을 담을 위젯 (클릭 이벤트 처리를 위해)
        self.recurrence_widget = QWidget()
        self.recurrence_widget.setLayout(self.recurrence_layout)
        self.recurrence_widget.mousePressEvent = lambda event: self.open_recurrence_dialog()
        # --- ▲▲▲ 여기까지 개선 ▲▲▲ ---

        time_options_layout = QHBoxLayout()
        time_options_layout.addWidget(self.all_day_checkbox)
        time_options_layout.addStretch(1)
        
        layout.addLayout(time_options_layout)
        layout.addWidget(self.recurrence_widget)

        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(100)
        layout.addWidget(QLabel("설명:"))
        layout.addWidget(self.description_edit)

        button_layout = QHBoxLayout()
        self.delete_button = QPushButton("삭제")
        self.save_button = QPushButton("저장")
        self.cancel_button = QPushButton("취소")
        
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.delete_button.setVisible(self.mode == 'edit')
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.delete_button.clicked.connect(self.request_delete)

    def accept(self):
        """'저장' 버튼 클릭 시 동작을 오버라이드하여 반복 일정 수정 시 경고를 표시합니다."""
        # --- ▼▼▼ [개선] 반복 일정 수정 시 경고 메시지 추가 ▼▼▼ ---
        if self.mode == 'edit' and 'recurrence' in self.event_data:
            msg_box = CustomMessageBox(
                self,
                title='수정 확인',
                text=f"'{self.summary_edit.text()}'은(는) 반복 일정입니다.\n이 일정을 수정하면 모든 관련 반복 일정이 수정됩니다.\n\n계속하시겠습니까?",
                settings=self.settings
            )
            if not msg_box.exec():
                return # 사용자가 '취소'를 누르면 저장하지 않고 함수 종료
        # --- ▲▲▲ 여기까지 개선 ▲▲▲ ---
        super().accept() # QDialog의 기본 accept 동작 실행 (창 닫고 Accepted 반환)

    def open_recurrence_dialog(self):
        """반복 설정 다이얼로그를 엽니다."""
        dialog = RecurrenceRuleDialog(
            rrule_str=self.custom_rrule,
            start_date=self.start_time_edit.date(),
            parent=self, 
            settings=self.settings,
            pos=self.mapToGlobal(self.recurrence_button.pos())
        )
        if dialog.exec():
            self.custom_rrule, start_date = dialog.get_rule_data()
            
            # --- ▼▼▼ [개선] 지정된 시작일로 UI 업데이트 ▼▼▼ ---
            if self.custom_rrule:
                current_start_dt = self.start_time_edit.dateTime()
                new_start_dt = QDateTime(start_date, current_start_dt.time())
                
                # 시작일이 변경되었으면 시간 정보도 함께 업데이트
                if new_start_dt != current_start_dt:
                    duration = self.end_time_edit.dateTime().toPyDateTime() - current_start_dt.toPyDateTime()
                    self.start_time_edit.setDateTime(new_start_dt)
                    self.end_time_edit.setDateTime(new_start_dt.addSecs64(int(duration.total_seconds())))
            # --- ▲▲▲ 여기까지 개선 ▲▲▲ ---
            
            self.update_recurrence_button_text()

        self.sync_end_date_on_recurrence()

    def update_recurrence_button_text(self):
        """RRULE을 기반으로 버튼 텍스트를 업데이트합니다."""
        if self.custom_rrule:
            text = self.rrule_to_text(self.custom_rrule)
            self.recurrence_button.setText(text)
        else:
            self.recurrence_button.setText("반복 안 함")

    def rrule_to_text(self, rrule_str):
        """RRULE 문자열을 사람이 읽기 쉬운 한국어 텍스트로 변환합니다."""
        if not rrule_str:
            return "반복 안 함"
        try:
            rule = rrulestr(rrule_str.replace("RRULE:", ""), dtstart=self.start_time_edit.dateTime().toPyDateTime())
            
            parts = []
            # 1. 주기 및 간격
            interval = rule._interval
            if rule._freq == YEARLY:
                parts.append(f"매년" if interval == 1 else f"{interval}년마다")
            elif rule._freq == MONTHLY:
                parts.append(f"매월" if interval == 1 else f"{interval}개월마다")
            elif rule._freq == WEEKLY:
                parts.append(f"매주" if interval == 1 else f"{interval}주마다")
            elif rule._freq == DAILY:
                parts.append(f"매일" if interval == 1 else f"{interval}일마다")

            # 2. 요일 또는 날짜
            if rule._freq == WEEKLY and rule._byweekday:
                days = ["월", "화", "수", "목", "금", "토", "일"]
                selected_days = sorted([d.weekday for d in rule._byweekday])
                parts.append(" ".join([days[i] for i in selected_days]) + "요일")
            
            if rule._freq == MONTHLY:
                if rule._bymonthday:
                    parts.append(f"{rule._bymonthday[0]}일")
                elif rule._byweekday:
                    pos_map = {1: "첫째 주", 2: "둘째 주", 3: "셋째 주", 4: "넷째 주", -1: "마지막 주"}
                    days = ["월", "화", "수", "목", "금", "토", "일"]
                    pos = rule._bysetpos[0]
                    day_of_week = rule._byweekday[0].weekday
                    parts.append(f"{pos_map[pos]} {days[day_of_week]}요일")

            # 3. 종료 조건
            if rule._until:
                parts.append(f"{rule._until.strftime('%Y-%m-%d')}까지")
            elif rule._count:
                parts.append(f"{rule._count}회")

            return ", ".join(parts)
        except Exception as e:
            print(f"RRULE 텍스트 변환 오류: {e}")
            return rrule_str # 변환 실패 시 원본 문자열 반환

    def sync_end_date_on_recurrence(self):
        """반복이 설정된 경우, 종료 날짜를 시작 날짜와 동일하게 맞춥니다."""
        is_recurring = self.custom_rrule is not None
        if is_recurring:
            start_dt = self.start_time_edit.dateTime()
            end_dt = self.end_time_edit.dateTime()
            
            if start_dt.date() != end_dt.date():
                new_end_dt = QDateTime(start_dt.date(), end_dt.time())
                if new_end_dt < start_dt:
                    new_end_dt = new_end_dt.addDays(1)
                self.end_time_edit.setDateTime(new_end_dt)


    def request_delete(self):
        """삭제 버튼 클릭 시 확인 메시지를 표시하고, 확인 시 삭제 코드를 반환하며 창을 닫습니다."""
        summary = self.summary_edit.text()
        
        # --- ▼▼▼ [개선] 반복 일정 삭제 시 경고 메시지 강화 ▼▼▼ ---
        is_recurring = 'recurrence' in self.event_data
        if is_recurring:
            text = f"'{summary}'은(는) 반복 일정입니다.\n이 일정을 삭제하면 모든 관련 반복 일정이 삭제됩니다.\n\n정말 삭제하시겠습니까?"
        else:
            text = f"'{summary}' 일정을 정말 삭제하시겠습니까?"
        # --- ▲▲▲ 여기까지 개선 ▲▲▲ ---

        msg_box = CustomMessageBox(
            self,
            title='삭제 확인',
            text=text,
            settings=self.settings
        )
        if msg_box.exec():
            self.done(self.DeleteRole) # '삭제' 역할로 다이얼로그 종료


    def toggle_time_edit(self, state):
        is_all_day = (state == Qt.CheckState.Checked.value)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd" if is_all_day else "yyyy-MM-dd hh:mm")
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd" if is_all_day else "yyyy-MM-dd hh:mm")

    def populate_data(self):
        """기존 데이터를 UI에 채웁니다."""
        if self.mode == 'edit' and self.event_data:
            target_cal_id = self.event_data.get('calendarId')
        else:
            target_cal_id = self.settings.get('last_selected_calendar_id')

        if target_cal_id:
            index = self.calendar_combo.findData({'id': target_cal_id, 'provider': self.event_data.get('provider')})
            if index != -1: self.calendar_combo.setCurrentIndex(index)

        if self.mode == 'edit' and self.event_data:
            self.summary_edit.setText(self.event_data.get('summary', ''))
            self.description_edit.setText(self.event_data.get('description', ''))

            start_info = self.event_data.get('start', {})
            end_info = self.event_data.get('end', {})
            is_all_day = 'date' in start_info
            self.all_day_checkbox.setChecked(is_all_day)

            start_str = start_info.get('date') or start_info.get('dateTime')
            end_str = end_info.get('date') or end_info.get('dateTime')
            self.start_time_edit.setDateTime(QDateTime.fromString(start_str, Qt.DateFormat.ISODateWithMs))
            end_dt = QDateTime.fromString(end_str, Qt.DateFormat.ISODateWithMs)
            if is_all_day: end_dt = end_dt.addDays(-1)
            self.end_time_edit.setDateTime(end_dt)

            recurrence = self.event_data.get('recurrence')
            if recurrence:
                self.custom_rrule = recurrence[0]
                self.update_recurrence_button_text()
                self.sync_end_date_on_recurrence()

        elif self.mode == 'new' and self.date_info:
            start_dt = self.date_info if isinstance(self.date_info, datetime.datetime) else datetime.datetime.combine(self.date_info, datetime.datetime.now().time())
            start_dt = start_dt.replace(minute=0, second=0, microsecond=0)
            end_dt = start_dt + datetime.timedelta(hours=1)
            self.start_time_edit.setDateTime(QDateTime(start_dt))
            self.end_time_edit.setDateTime(QDateTime(end_dt))
        
        # populate_data가 끝난 후, 버튼 텍스트 최종 업데이트
        self.update_recurrence_button_text()

    def get_event_data(self):
        """UI에서 입력받은 정보를 Google API 형식의 딕셔너리로 반환합니다."""
        summary = self.summary_edit.text()
        description = self.description_edit.toPlainText()
        is_all_day = self.all_day_checkbox.isChecked()
        start_dt = self.start_time_edit.dateTime().toPyDateTime()
        end_dt = self.end_time_edit.dateTime().toPyDateTime()

        event_body = {'summary': summary, 'description': description}

        # --- ▼▼▼ [개선] 반복 일정의 시작일을 규칙에 맞게 조정 ▼▼▼ ---
        if self.custom_rrule:
            event_body['recurrence'] = [self.custom_rrule]
            try:
                # UI의 시작 시간을 기준으로 규칙의 첫 발생 시점을 계산합니다.
                rule = rrulestr(self.custom_rrule, dtstart=start_dt)
                first_occurrence_dt = rule[0]

                # 첫 발생 시점이 UI의 시작 시간과 다르면, 시작/종료 시간을 조정합니다.
                if first_occurrence_dt != start_dt:
                    duration = end_dt - start_dt
                    end_dt = first_occurrence_dt + duration
                    start_dt = first_occurrence_dt
            except Exception as e:
                print(f"반복 규칙의 첫 발생일 계산 중 오류: {e}")
                # 오류 발생 시, 사용자가 선택한 날짜를 그대로 사용합니다.
                pass
        # --- ▲▲▲ 여기까지 개선 ▲▲▲ ---

        if is_all_day:
            event_body['start'] = {'date': start_dt.strftime('%Y-%m-%d')}
            event_body['end'] = {'date': (end_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}
        else:
            event_body['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Seoul'}
            event_body['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Seoul'}

        if self.mode == 'edit':
            event_body['id'] = self.event_data.get('id')
        elif self.calendar_combo.currentData()['provider'] == LOCAL_CALENDAR_PROVIDER_NAME:
            event_body['id'] = str(uuid.uuid4())

        selected_calendar_data = self.calendar_combo.currentData()
        return {
            'calendarId': selected_calendar_data['id'],
            'provider': selected_calendar_data['provider'],
            'body': event_body
        }