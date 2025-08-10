import datetime
import uuid
from dateutil.rrule import rrulestr, YEARLY, MONTHLY, WEEKLY, DAILY

from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QTextEdit, QPushButton, QCheckBox, QComboBox,
                             QWidget, QCalendarWidget, QTimeEdit, QSizePolicy)
from PyQt6.QtGui import QIcon, QColor, QPixmap
from PyQt6.QtCore import QDateTime, Qt, QTimer, QEvent, pyqtSignal

from custom_dialogs import CustomMessageBox, BaseDialog
from config import LOCAL_CALENDAR_PROVIDER_NAME
from recurrence_dialog import RecurrenceRuleDialog

class DateSelector(QWidget):
    """
    QLineEdit를 클릭하면 캘린더 팝업이 나타나는 커스텀 날짜 선택 위젯.
    """
    dateTimeChanged = pyqtSignal(QDateTime)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_datetime = QDateTime.currentDateTime()

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
        self.calendar_popup.clicked.connect(self.date_selected)

        self.update_display()

    def eventFilter(self, obj, event):
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
        self.event_data = data if isinstance(data, dict) else {}
        self.date_info = data if isinstance(data, (datetime.date, datetime.datetime)) else None
        self.custom_rrule = None
        self.data_manager = data_manager
        self.initial_completed_state = False

        self.setWindowTitle("일정 추가" if self.mode == 'new' else "일정 수정")
        self.setMinimumWidth(450)

        self.initUI()

        if self.data_manager:
            self.data_manager.calendar_list_changed.connect(self.repopulate_calendars)

        self.repopulate_calendars()
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
        layout.addWidget(QLabel("캘린더:"))
        layout.addWidget(self.calendar_combo)

        start_layout = QHBoxLayout()
        self.start_date_selector = DateSelector()
        self.start_time_edit = QTimeEdit()
        self.start_time_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        start_layout.addWidget(QLabel("시작:"))
        start_layout.addWidget(self.start_date_selector)
        start_layout.addWidget(self.start_time_edit)
        layout.addLayout(start_layout)

        self.start_date_selector.dateTimeChanged.connect(self._on_start_datetime_changed)
        self.start_time_edit.timeChanged.connect(self._on_start_datetime_changed)

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
        
        # --- UI/UX 개선: 반복 설정 위젯 변경 ---
        recurrence_row_layout = QHBoxLayout()
        recurrence_row_layout.addWidget(QLabel("반복:"))
        
        self.recurrence_edit_button = QPushButton("반복 안 함")
        self.recurrence_edit_button.setObjectName("recurrenceButton") # 스타일링을 위한 ID
        self.recurrence_edit_button.clicked.connect(self.open_recurrence_dialog)
        
        recurrence_row_layout.addWidget(self.recurrence_edit_button)

        time_options_layout = QHBoxLayout()
        time_options_layout.addWidget(self.all_day_checkbox)
        time_options_layout.addStretch(1)

        self.completed_checkbox = QCheckBox("완료")
        time_options_layout.addWidget(self.completed_checkbox)

        layout.addLayout(time_options_layout)
        layout.addLayout(recurrence_row_layout) # 개선된 레이아웃 추가

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

    def _on_start_datetime_changed(self):
        start_dt = self.get_start_datetime()
        end_dt = self.get_end_datetime()
        if start_dt >= end_dt:
            new_end_dt = start_dt.addSecs(3600)
            self.set_end_datetime(new_end_dt)

    def repopulate_calendars(self):
        current_selection_id = None
        if self.calendar_combo.count() > 0:
            current_selection_data = self.calendar_combo.currentData()
            if current_selection_data:
                current_selection_id = current_selection_data.get('id')
        self.calendar_combo.clear()
        calendars = self.data_manager.get_all_calendars(fetch_if_empty=True)
        if not calendars:
            self.calendar_combo.addItem("캘린더 목록 로딩 중...")
            self.calendar_combo.setEnabled(False)
            return
        self.calendar_combo.setEnabled(True)
        target_cal_id_to_select = None
        for calendar in calendars:
            user_data = {'id': calendar['id'], 'provider': calendar['provider']}
            custom_colors = self.settings.get("calendar_colors", {})
            color_hex = custom_colors.get(calendar['id'], calendar.get('backgroundColor', '#9fc6e7'))
            color = QColor(color_hex)
            pixmap = QPixmap(16, 16)
            pixmap.fill(color)
            icon = QIcon(pixmap)
            self.calendar_combo.addItem(icon, calendar['summary'], userData=user_data)
        if current_selection_id:
            target_cal_id_to_select = current_selection_id
        elif self.mode == 'edit' and self.event_data:
            target_cal_id_to_select = self.event_data.get('calendarId')
        else:
            target_cal_id_to_select = self.settings.get('last_selected_calendar_id')
        if target_cal_id_to_select:
            for i in range(self.calendar_combo.count()):
                combo_data = self.calendar_combo.itemData(i)
                if combo_data and combo_data.get('id') == target_cal_id_to_select:
                    self.calendar_combo.setCurrentIndex(i)
                    break

    def accept(self):
        start_dt = self.get_start_datetime()
        end_dt = self.get_end_datetime()
        if start_dt > end_dt:
            msg_box = CustomMessageBox(self, title='시간 오류', text="끝나는 시각이 시작 시각보다 빠를 수 없습니다.", settings=self.settings, ok_only=True)
            msg_box.exec()
            return
        event_id = self.event_data.get('id', '')
        is_recurring_instance = '_' in event_id and self.event_data.get('provider') == LOCAL_CALENDAR_PROVIDER_NAME
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
        dialog = RecurrenceRuleDialog(rrule_str=self.custom_rrule, start_date=start_date, parent=self, settings=self.settings, pos=self.mapToGlobal(self.recurrence_edit_button.pos()))
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
        # --- UI/UX 개선: 업데이트 대상을 새 버튼으로 변경 ---
        if self.custom_rrule:
            text = self.rrule_to_text(self.custom_rrule, self.get_start_datetime().toPyDateTime())
            self.recurrence_edit_button.setText(text)
        else:
            self.recurrence_edit_button.setText("반복 안 함")

    def rrule_to_text(self, rrule_str, dtstart):
        if not rrule_str: return "반복 안 함"
        try:
            if not isinstance(dtstart, datetime.datetime):
                dtstart = datetime.datetime.combine(dtstart, datetime.time.min)
            rule = rrulestr(rrule_str.replace("RRULE:", ""), dtstart=dtstart)
            parts, interval = [], rule._interval
            if rule._freq == YEARLY: parts.append("매년" if interval == 1 else f"{interval}년마다")
            elif rule._freq == MONTHLY: parts.append("매월" if interval == 1 else f"{interval}개월마다")
            elif rule._freq == WEEKLY: parts.append("매주" if interval == 1 else f"{interval}주마다")
            elif rule._freq == DAILY: parts.append("매일" if interval == 1 else f"{interval}일마다")
            if rule._freq == WEEKLY and rule._byweekday:
                days = ["월", "화", "수", "목", "금", "토", "일"]
                selected_days = sorted(rule._byweekday)
                parts.append(" ".join([days[i] for i in selected_days]) + "요일")
            if rule._freq == MONTHLY:
                if rule._bymonthday: parts.append(f"{rule._bymonthday[0]}일")
                elif rule._byweekday and rule._bysetpos:
                    pos_map = {1: "첫째 주", 2: "둘째 주", 3: "셋째 주", 4: "넷째 주", -1: "마지막 주"}
                    days = ["월", "화", "수", "목", "금", "토", "일"]
                    pos, day_of_week = rule._bysetpos[0], rule._byweekday[0]
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
        return QDateTime(self.start_date_selector.dateTime().date(), self.start_time_edit.time())

    def get_end_datetime(self):
        return QDateTime(self.end_date_selector.dateTime().date(), self.end_time_edit.time())

    def set_start_datetime(self, qdatetime):
        self.start_date_selector.setDateTime(qdatetime)
        self.start_time_edit.setTime(qdatetime.time())

    def set_end_datetime(self, qdatetime):
        self.end_date_selector.setDateTime(qdatetime)
        self.end_time_edit.setTime(qdatetime.time())

    def populate_data(self):
        target_cal_id = None
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
            for i in range(self.calendar_combo.count()):
                combo_data = self.calendar_combo.itemData(i)
                if combo_data and combo_data.get('id') == target_cal_id:
                    self.calendar_combo.setCurrentIndex(i)
                    break
        if self.mode == 'edit' and self.event_data:
            self.summary_edit.setText(self.event_data.get('summary', ''))
            self.description_edit.setText(self.event_data.get('description', ''))
            start_info, end_info = self.event_data.get('start', {}), self.event_data.get('end', {})
            is_all_day = 'date' in start_info
            self.all_day_checkbox.setChecked(is_all_day)
            start_str, end_str = start_info.get('date') or start_info.get('dateTime'), end_info.get('date') or end_info.get('dateTime')
            start_dt, end_dt = QDateTime.fromString(start_str, Qt.DateFormat.ISODateWithMs).toLocalTime(), QDateTime.fromString(end_str, Qt.DateFormat.ISODateWithMs).toLocalTime()
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
        summary, description = self.summary_edit.text(), self.description_edit.toPlainText()
        is_all_day = self.all_day_checkbox.isChecked()
        start_dt, end_dt = self.get_start_datetime().toPyDateTime(), self.get_end_datetime().toPyDateTime()
        event_body = self.event_data.copy() if self.mode == 'edit' else {}
        event_body.update({'summary': summary, 'description': description})
        if self.custom_rrule:
            event_body['recurrence'] = [self.custom_rrule]
            try:
                rule = rrulestr(self.custom_rrule, dtstart=start_dt)
                first_occurrence_dt = rule[0]
                if first_occurrence_dt != start_dt:
                    duration = end_dt - start_dt
                    end_dt, start_dt = first_occurrence_dt + duration, first_occurrence_dt
            except Exception as e:
                print(f"반복 규칙의 첫 발생일 계산 중 오류: {e}")
        if is_all_day:
            event_body['start'] = {'date': start_dt.strftime('%Y-%m-%d')}
            event_body['end'] = {'date': (end_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}
        else:
            user_timezone_str = self.settings.get("user_timezone", "Asia/Seoul")
            try:
                event_body['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': user_timezone_str}
                event_body['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': user_timezone_str}
            except Exception:
                event_body['start'] = {'dateTime': start_dt.isoformat() + 'Z', 'timeZone': 'UTC'}
                event_body['end'] = {'dateTime': end_dt.isoformat() + 'Z', 'timeZone': 'UTC'}
        if self.mode == 'edit':
            event_id = self.event_data.get('id', '')
            is_recurring_instance = '_' in event_id and self.event_data.get('provider') == LOCAL_CALENDAR_PROVIDER_NAME
            event_body['id'] = self.event_data.get('originalId', event_id.split('_')[0]) if is_recurring_instance else event_id
        elif self.calendar_combo.currentData()['provider'] == LOCAL_CALENDAR_PROVIDER_NAME:
            event_body['id'] = str(uuid.uuid4())
        selected_calendar_data = self.calendar_combo.currentData()
        return {'calendarId': selected_calendar_data['id'], 'provider': selected_calendar_data['provider'], 'body': event_body}