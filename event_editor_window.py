import datetime
import uuid
from dateutil.rrule import rrulestr, rrule, YEARLY, MONTHLY, WEEKLY, DAILY

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QTextEdit, QPushButton, QCheckBox, QDateTimeEdit, QComboBox, 
                             QWidget, QStackedWidget, QCalendarWidget, QTimeEdit, QSizePolicy)
from PyQt6.QtGui import QIcon, QColor, QPixmap
from PyQt6.QtCore import QDateTime, Qt, QTimer, QEvent, QPoint, pyqtSignal

from custom_dialogs import CustomMessageBox, BaseDialog
from config import GOOGLE_CALENDAR_PROVIDER_NAME, LOCAL_CALENDAR_PROVIDER_NAME
from recurrence_dialog import RecurrenceRuleDialog

class DateSelector(QWidget):
    """
    QLineEdit와 QPushButton을 조합하여 만든 커스텀 날짜 선택 위젯.
    QLineEdit나 버튼을 클릭하면 캘린더 팝업이 나타난다.
    """
    dateTimeChanged = pyqtSignal(QDateTime)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_datetime = QDateTime.currentDateTime()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.line_edit = QLineEdit()
        self.line_edit.setReadOnly(True)
        # 클릭 이벤트를 감지하기 위해 이벤트 필터 설치
        self.line_edit.installEventFilter(self)

        self.calendar_button = QPushButton()
        self.calendar_button.setIcon(QIcon("icons/search.svg")) # 임시 아이콘, 추후 변경 가능
        self.calendar_button.setFixedSize(28, 28)
        self.calendar_button.clicked.connect(self.show_calendar)

        layout.addWidget(self.line_edit)
        layout.addWidget(self.calendar_button)

        self.calendar_popup = QCalendarWidget(self)
        self.calendar_popup.setWindowFlags(Qt.WindowType.Popup)
        self.calendar_popup.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader) # 주차 번호 숨기기
        self.calendar_popup.clicked.connect(self.date_selected)
        
        self.update_display()

    def eventFilter(self, obj, event):
        # line_edit가 클릭되면 캘린더를 보여준다.
        if obj == self.line_edit and event.type() == QEvent.Type.MouseButtonPress:
            self.show_calendar()
            return True
        return super().eventFilter(obj, event)

    def show_calendar(self):
        self.calendar_popup.setSelectedDate(self.current_datetime.date())
        pos = self.mapToGlobal(self.line_edit.geometry().bottomLeft())
        self.calendar_popup.move(pos)
        self.calendar_popup.show()

    def date_selected(self, date):
        new_datetime = QDateTime(date, self.current_datetime.time())
        self.setDateTime(new_datetime)
        self.calendar_popup.close()

    def setDateTime(self, qdatetime):
        if self.current_datetime != qdatetime:
            self.current_datetime = qdatetime
            self.update_display()
            self.dateTimeChanged.emit(self.current_datetime)

    def dateTime(self):
        return self.current_datetime

    def update_display(self):
        self.line_edit.setText(self.current_datetime.toString("yyyy-MM-dd"))

class EventEditorWindow(BaseDialog):
    DeleteRole = 2

    def __init__(self, mode='new', data=None, calendars=None, settings=None, parent=None, pos=None, data_manager=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.mode = mode
        # calendars 인자는 이제 사용하지 않지만, 호환성을 위해 남겨둡니다.
        self.event_data = data if isinstance(data, dict) else {}
        self.date_info = data if isinstance(data, (datetime.date, datetime.datetime)) else None
        self.custom_rrule = None
        self.data_manager = data_manager
        self.initial_completed_state = False
        
        self.setWindowTitle("일정 추가" if self.mode == 'new' else "일정 수정")
        self.setMinimumWidth(450)
        
        self.initUI()
        
        # DataManager의 신호에 연결
        if self.data_manager:
            self.data_manager.calendar_list_changed.connect(self.repopulate_calendars)
        
        # 초기 데이터 채우기
        self.repopulate_calendars() # 현재 캐시된 데이터로 우선 채움
        self.populate_data()
        
        QTimer.singleShot(0, self.adjustSize)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(15, 15, 15, 15)

        self.summary_edit = QLineEdit()
        layout.addWidget(QLabel("제목:"))
        layout.addWidget(self.summary_edit)

        self.calendar_combo = QComboBox()
        # 초기화 시점에는 비워둡니다. repopulate_calendars에서 채웁니다.
        
        layout.addWidget(QLabel("캘린더:"))
        layout.addWidget(self.calendar_combo)

        # --- 날짜/시간 선택 위젯 ---
        start_layout = QHBoxLayout()
        self.start_date_selector = DateSelector()
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        start_layout.addWidget(QLabel("시작:"))
        start_layout.addWidget(self.start_date_selector)
        start_layout.addWidget(self.start_time_edit)
        layout.addLayout(start_layout)

        end_layout = QHBoxLayout()
        self.end_date_selector = DateSelector()
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        end_layout.addWidget(QLabel("종료:"))
        end_layout.addWidget(self.end_date_selector)
        end_layout.addWidget(self.end_time_edit)
        layout.addLayout(end_layout)

        self.all_day_checkbox = QCheckBox("하루 종일")
        self.all_day_checkbox.stateChanged.connect(self.toggle_time_edit)
        
        self.recurrence_layout = QHBoxLayout()
        self.recurrence_layout.setContentsMargins(0,0,0,0)
        
        self.recurrence_label = QLabel("반복")
        self.recurrence_button = QPushButton("반복 안 함")
        self.recurrence_button.setStyleSheet("text-align: right; border: none;")
        self.recurrence_arrow_label = QLabel(">")

        self.recurrence_layout.addWidget(self.recurrence_label)
        self.recurrence_layout.addWidget(self.recurrence_button, 1)
        self.recurrence_layout.addWidget(self.recurrence_arrow_label)

        self.recurrence_widget = QWidget()
        self.recurrence_widget.setLayout(self.recurrence_layout)
        self.recurrence_widget.mousePressEvent = lambda event: self.open_recurrence_dialog()

        time_options_layout = QHBoxLayout()
        time_options_layout.addWidget(self.all_day_checkbox)
        time_options_layout.addStretch(1)
        
        self.completed_checkbox = QCheckBox("완료")
        time_options_layout.addWidget(self.completed_checkbox)

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

    def repopulate_calendars(self):
        """DataManager로부터 캘린더 목록을 가져와 콤보박스를 다시 채웁니다."""
        # 현재 선택된 ID 저장
        current_selection_id = None
        if self.calendar_combo.count() > 0:
            current_selection_id = self.calendar_combo.currentData()['id']

        self.calendar_combo.clear()
        
        # fetch_if_empty=True로 설정하여, 캐시가 없으면 비동기 로딩을 트리거합니다.
        calendars = self.data_manager.get_all_calendars(fetch_if_empty=True)
        
        if not calendars:
            self.calendar_combo.addItem("캘린더 목록 로딩 중...")
            self.calendar_combo.setEnabled(False)
            return

        self.calendar_combo.setEnabled(True)
        for calendar in calendars:
            user_data = {'id': calendar['id'], 'provider': calendar['provider']}
            custom_colors = self.settings.get("calendar_colors", {})
            color_hex = custom_colors.get(calendar['id'], calendar.get('backgroundColor', '#9fc6e7'))
            color = QColor(color_hex)
            pixmap = QPixmap(16, 16)
            pixmap.fill(color)
            icon = QIcon(pixmap)
            self.calendar_combo.addItem(icon, calendar['summary'], userData=user_data)

        # 이전에 선택했던 캘린더를 다시 선택
        if current_selection_id:
            index = self.calendar_combo.findData({'id': current_selection_id})
            if index != -1:
                self.calendar_combo.setCurrentIndex(index)
        # 또는, 수정 모드일 때 이벤트 데이터의 캘린더를 선택
        elif self.mode == 'edit' and self.event_data:
            target_cal_id = self.event_data.get('calendarId')
            index = self.calendar_combo.findData({'id': target_cal_id})
            if index != -1:
                self.calendar_combo.setCurrentIndex(index)
        # 또는, 마지막으로 사용한 캘린더를 선택
        else:
            last_used_id = self.settings.get('last_selected_calendar_id')
            if last_used_id:
                index = self.calendar_combo.findData({'id': last_used_id})
                if index != -1:
                    self.calendar_combo.setCurrentIndex(index)

    def accept(self):
        event_id = self.event_data.get('id', '')
        is_recurring_instance = '_' in event_id and self.event_data.get('provider') == 'LocalCalendarProvider'
        is_recurring_master = 'recurrence' in self.event_data

        if self.mode == 'edit' and (is_recurring_master or is_recurring_instance):
            text = f"'{self.summary_edit.text()}'은(는) 반복 일정입니다.\n이 일정을 수정하면 모든 관련 반복 일정이 수정됩니다.\n\n계속하시겠습니까?"
            msg_box = CustomMessageBox(self, title='수정 확인', text=text, settings=self.settings)
            if not msg_box.exec():
                return
        
        if self.mode == 'edit' and self.data_manager:
            new_completed_state = self.completed_checkbox.isChecked()
            if event_id and new_completed_state != self.initial_completed_state:
                if new_completed_state:
                    self.data_manager.mark_event_as_completed(event_id)
                else:
                    self.data_manager.unmark_event_as_completed(event_id)

        super().accept()

    def open_recurrence_dialog(self):
        start_date = self.start_date_selector.dateTime().date()
        dialog = RecurrenceRuleDialog(
            rrule_str=self.custom_rrule,
            start_date=start_date,
            parent=self, 
            settings=self.settings,
            pos=self.mapToGlobal(self.recurrence_button.pos())
        )
        if dialog.exec():
            self.custom_rrule, new_start_date = dialog.get_rule_data()
            
            if self.custom_rrule:
                current_start_dt = self.get_start_datetime()
                new_start_qdt = QDateTime(new_start_date, current_start_dt.time())
                
                if new_start_qdt != current_start_dt:
                    duration = self.get_end_datetime().toPyDateTime() - current_start_dt.toPyDateTime()
                    self.set_start_datetime(new_start_qdt)
                    self.set_end_datetime(new_start_qdt.addSecs64(int(duration.total_seconds())))
            
            self.update_recurrence_button_text()
        self.sync_end_date_on_recurrence()

    def update_recurrence_button_text(self):
        if self.custom_rrule:
            text = self.rrule_to_text(self.custom_rrule, self.get_start_datetime().toPyDateTime())
            self.recurrence_button.setText(text)
        else:
            self.recurrence_button.setText("반복 안 함")

    def rrule_to_text(self, rrule_str, dtstart):
        if not rrule_str: return "반복 안 함"
        try:
            rule = rrulestr(rrule_str.replace("RRULE:", ""), dtstart=dtstart)
            parts = []
            interval = rule._interval
            if rule._freq == YEARLY: parts.append(f"매년" if interval == 1 else f"{interval}년마다")
            elif rule._freq == MONTHLY: parts.append(f"매월" if interval == 1 else f"{interval}개월마다")
            elif rule._freq == WEEKLY: parts.append(f"매주" if interval == 1 else f"{interval}주마다")
            elif rule._freq == DAILY: parts.append(f"매일" if interval == 1 else f"{interval}일마다")
            if rule._freq == WEEKLY and rule._byweekday:
                days = ["월", "화", "수", "목", "금", "토", "일"]
                selected_days = sorted([d.weekday for d in rule._byweekday])
                parts.append(" ".join([days[i] for i in selected_days]) + "요일")
            if rule._freq == MONTHLY:
                if rule._bymonthday: parts.append(f"{rule._bymonthday[0]}일")
                elif rule._byweekday:
                    pos_map = {1: "첫째 주", 2: "둘째 주", 3: "셋째 주", 4: "넷째 주", -1: "마지막 주"}
                    days = ["월", "화", "수", "목", "금", "토", "일"]
                    pos, day_of_week = rule._bysetpos[0], rule._byweekday[0].weekday
                    parts.append(f"{pos_map[pos]} {days[day_of_week]}요일")
            if rule._until: parts.append(f"{rule._until.strftime('%Y-%m-%d')}까지")
            elif rule._count: parts.append(f"{rule._count}회")
            return ", ".join(parts)
        except Exception as e:
            print(f"RRULE 텍스트 변환 오류: {e}")
            return rrule_str

    def sync_end_date_on_recurrence(self):
        if self.custom_rrule:
            start_dt, end_dt = self.get_start_datetime(), self.get_end_datetime()
            if start_dt.date() != end_dt.date():
                new_end_dt = QDateTime(start_dt.date(), end_dt.time())
                if new_end_dt < start_dt: new_end_dt = new_end_dt.addDays(1)
                self.set_end_datetime(new_end_dt)

    def request_delete(self):
        summary = self.summary_edit.text()
        text = f"'{summary}' 일정을 정말 삭제하시겠습니까?"
        if 'recurrence' in self.event_data:
            text = f"'{summary}'은(는) 반복 일정입니다.\n이 일정을 삭제하면 모든 관련 반복 일정이 삭제됩니다.\n\n정말 삭제하시겠습니까?"
        msg_box = CustomMessageBox(self, title='삭제 확인', text=text, settings=self.settings)
        if msg_box.exec(): self.done(self.DeleteRole)

    def toggle_time_edit(self, state):
        is_all_day = (state == Qt.CheckState.Checked.value)
        self.start_time_edit.setVisible(not is_all_day)
        self.end_time_edit.setVisible(not is_all_day)
        self.adjustSize()

    def get_start_datetime(self):
        date_part = self.start_date_selector.dateTime().date()
        time_part = self.start_time_edit.time()
        return QDateTime(date_part, time_part)

    def get_end_datetime(self):
        date_part = self.end_date_selector.dateTime().date()
        time_part = self.end_time_edit.time()
        return QDateTime(date_part, time_part)

    def set_start_datetime(self, qdatetime):
        self.start_date_selector.setDateTime(qdatetime)
        self.start_time_edit.setTime(qdatetime.time())

    def set_end_datetime(self, qdatetime):
        self.end_date_selector.setDateTime(qdatetime)
        self.end_time_edit.setTime(qdatetime.time())

    def populate_data(self):
        if self.mode == 'edit' and self.event_data:
            event_id = self.event_data.get('id')
            if event_id and self.data_manager:
                self.initial_completed_state = self.data_manager.is_event_completed(event_id)
                self.completed_checkbox.setChecked(self.initial_completed_state)
            target_cal_id = self.event_data.get('calendarId')
        else:
            self.completed_checkbox.setVisible(False)
            target_cal_id = self.settings.get('last_selected_calendar_id')

        if target_cal_id:
            index = self.calendar_combo.findData({'id': target_cal_id, 'provider': self.event_data.get('provider')})
            if index != -1: self.calendar_combo.setCurrentIndex(index)

        if self.mode == 'edit' and self.event_data:
            self.summary_edit.setText(self.event_data.get('summary', ''))
            self.description_edit.setText(self.event_data.get('description', ''))
            start_info, end_info = self.event_data.get('start', {}), self.event_data.get('end', {})
            is_all_day = 'date' in start_info
            self.all_day_checkbox.setChecked(is_all_day)
            start_str = start_info.get('date') or start_info.get('dateTime')
            end_str = end_info.get('date') or end_info.get('dateTime')
            start_dt = QDateTime.fromString(start_str, Qt.DateFormat.ISODateWithMs)
            end_dt = QDateTime.fromString(end_str, Qt.DateFormat.ISODateWithMs)
            if is_all_day: end_dt = end_dt.addDays(-1)
            self.set_start_datetime(start_dt)
            self.set_end_datetime(end_dt)
            if 'recurrence' in self.event_data:
                self.custom_rrule = self.event_data['recurrence'][0]
                self.update_recurrence_button_text()
                self.sync_end_date_on_recurrence()
        elif self.mode == 'new' and self.date_info:
            start_dt_py = self.date_info if isinstance(self.date_info, datetime.datetime) else datetime.datetime.combine(self.date_info, datetime.datetime.now().time())
            start_dt_py = start_dt_py.replace(minute=0, second=0, microsecond=0)
            end_dt_py = start_dt_py + datetime.timedelta(hours=1)
            self.set_start_datetime(QDateTime(start_dt_py))
            self.set_end_datetime(QDateTime(end_dt_py))
        
        self.update_recurrence_button_text()
        self.toggle_time_edit(self.all_day_checkbox.checkState())

    def get_event_data(self):
        summary = self.summary_edit.text()
        description = self.description_edit.toPlainText()
        is_all_day = self.all_day_checkbox.isChecked()
        start_dt = self.get_start_datetime().toPyDateTime()
        end_dt = self.get_end_datetime().toPyDateTime()
        event_body = {'summary': summary, 'description': description}

        if self.custom_rrule:
            event_body['recurrence'] = [self.custom_rrule]
            try:
                rule = rrulestr(self.custom_rrule, dtstart=start_dt)
                first_occurrence_dt = rule[0]
                if first_occurrence_dt != start_dt:
                    duration = end_dt - start_dt
                    end_dt = first_occurrence_dt + duration
                    start_dt = first_occurrence_dt
            except Exception as e:
                print(f"반복 규칙의 첫 발생일 계산 중 오류: {e}")

        if is_all_day:
            event_body['start'] = {'date': start_dt.strftime('%Y-%m-%d')}
            event_body['end'] = {'date': (end_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}
        else:
            event_body['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Seoul'}
            event_body['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Seoul'}

        if self.mode == 'edit':
            event_id = self.event_data.get('id', '')
            is_recurring_instance = '_' in event_id and self.event_data.get('provider') == 'LocalCalendarProvider'
            event_body['id'] = self.event_data.get('originalId', event_id.split('_')[0]) if is_recurring_instance else event_id
        elif self.calendar_combo.currentData()['provider'] == LOCAL_CALENDAR_PROVIDER_NAME:
            event_body['id'] = str(uuid.uuid4())

        selected_calendar_data = self.calendar_combo.currentData()
        return {
            'calendarId': selected_calendar_data['id'],
            'provider': selected_calendar_data['provider'],
            'body': event_body
        }