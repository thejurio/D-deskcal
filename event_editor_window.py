import datetime
import uuid
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QTextEdit, QPushButton, QCheckBox, QDateTimeEdit, QComboBox, QWidget)
from PyQt6.QtCore import QDateTime, Qt

from custom_dialogs import CustomMessageBox, BaseDialog
from config import GOOGLE_CALENDAR_PROVIDER_NAME, LOCAL_CALENDAR_PROVIDER_NAME

class EventEditorWindow(BaseDialog):
    # 삭제 액션을 위한 커스텀 반환 코드
    DeleteRole = 2

    # __init__ 생성자에 'calendars' 파라미터를 추가합니다.
    def __init__(self, mode='new', data=None, calendars=None, settings=None, parent=None):
        super().__init__(parent=parent, settings=settings)
        self.mode = mode
        self.calendars = calendars if calendars else []
        # self.settings는 BaseDialog에서 이미 처리됨
        self.event_data = data if isinstance(data, dict) else {}
        # data가 datetime.date 또는 datetime.datetime 객체일 수 있으므로 date_info로 저장
        self.date_info = data if isinstance(data, (datetime.date, datetime.datetime)) else None
        
        self.setWindowTitle("일정 추가" if self.mode == 'new' else "일정 수정")
        self.setMinimumWidth(400)
        self.setMinimumHeight(450) # 최소 높이 추가
        
        self.initUI()
        self.populate_data()

    def initUI(self):
        # 전체 레이아웃과 배경 위젯 설정
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(15, 15, 15, 15) # 콘텐츠 여백 추가

        # --- ▼▼▼ 캘린더 선택 콤보박스를 추가합니다. ▼▼▼ ---
        self.calendar_combo = QComboBox()
        for calendar in self.calendars:
            # addItem의 두 번째 인자(userData)에 캘린더의 고유 ID와 provider 정보를 저장합니다.
            user_data = {'id': calendar['id'], 'provider': calendar['provider']}
            self.calendar_combo.addItem(calendar['summary'], userData=user_data)
        
        layout.addWidget(QLabel("캘린더:"))
        layout.addWidget(self.calendar_combo)
        # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

        # 제목
        self.summary_edit = QLineEdit()
        layout.addWidget(QLabel("제목:"))
        layout.addWidget(self.summary_edit)

        # 시간 설정
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

        # 종일 체크박스
        self.all_day_checkbox = QCheckBox("하루 종일")
        self.all_day_checkbox.stateChanged.connect(self.toggle_time_edit)
        layout.addWidget(self.all_day_checkbox)

        # 설명
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(100) # 설명란 최소 높이 지정
        layout.addWidget(QLabel("설명:"))
        layout.addWidget(self.description_edit)

        # 버튼
        button_layout = QHBoxLayout()
        self.delete_button = QPushButton("삭제")
        self.save_button = QPushButton("저장")
        self.cancel_button = QPushButton("취소")
        
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.delete_button.setVisible(self.mode == 'edit') # 수정 모드일 때만 보이도록 설정

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.delete_button.clicked.connect(self.request_delete)

    def request_delete(self):
        """삭제 버튼 클릭 시 확인 메시지를 표시하고, 확인 시 삭제 코드를 반환하며 창을 닫습니다."""
        msg_box = CustomMessageBox(
            self,
            title='삭제 확인',
            text=f"'{self.summary_edit.text()}' 일정을 정말 삭제하시겠습니까?",
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
        # --- ▼▼▼ 여기가 수정된 핵심입니다 ▼▼▼ ---
        if self.mode == 'edit' and self.event_data:
            # 수정 모드일 경우: 이벤트에 저장된 calendarId를 기준으로 기본값 설정
            target_cal_id = self.event_data.get('calendarId')
        else:
            # 새 일정 모드일 경우: settings에 저장된 마지막 선택 ID를 기준으로 기본값 설정
            target_cal_id = self.settings.get('last_selected_calendar_id')

        if target_cal_id:
            for i in range(self.calendar_combo.count()):
                if self.calendar_combo.itemData(i)['id'] == target_cal_id:
                    self.calendar_combo.setCurrentIndex(i)
                    break
        # --- ▲▲▲ 여기까지가 수정된 핵심입니다 ▲▲▲ ---
        if self.mode == 'edit' and self.event_data:
            self.summary_edit.setText(self.event_data.get('summary', ''))
            self.description_edit.setText(self.event_data.get('description', ''))

            # 이벤트의 calendarId를 기반으로 콤보박스의 기본값을 설정합니다.
            event_cal_id = self.event_data.get('calendarId')
            if event_cal_id:
                for i in range(self.calendar_combo.count()):
                    if self.calendar_combo.itemData(i)['id'] == event_cal_id:
                        self.calendar_combo.setCurrentIndex(i)
                        break

            start_info = self.event_data.get('start', {})
            end_info = self.event_data.get('end', {})

            is_all_day = 'date' in start_info
            self.all_day_checkbox.setChecked(is_all_day)

            start_str = start_info.get('date') or start_info.get('dateTime')
            end_str = end_info.get('date') or end_info.get('dateTime')

            self.start_time_edit.setDateTime(QDateTime.fromString(start_str, Qt.DateFormat.ISODateWithMs))
            end_dt = QDateTime.fromString(end_str, Qt.DateFormat.ISODateWithMs)
            if is_all_day:
                end_dt = end_dt.addDays(-1)
            self.end_time_edit.setDateTime(end_dt)

        elif self.mode == 'new' and self.date_info: # 'new' mode이고 date_info가 있을 때
            if isinstance(self.date_info, datetime.datetime):
                # datetime 객체면 시간 정보까지 사용
                start_dt = self.date_info
            else: # date 객체면 현재 시간 사용
                now = datetime.datetime.now()
                start_dt = datetime.datetime.combine(self.date_info, now.time())
            
            # 분을 0분으로 초기화
            start_dt = start_dt.replace(minute=0, second=0, microsecond=0)
            end_dt = start_dt + datetime.timedelta(hours=1)
            
            self.start_time_edit.setDateTime(QDateTime(start_dt))
            self.end_time_edit.setDateTime(QDateTime(end_dt))

    def get_event_data(self):
        """UI에서 입력받은 정보를 Google API 형식의 딕셔너리로 반환합니다."""
        summary = self.summary_edit.text()
        description = self.description_edit.toPlainText()
        is_all_day = self.all_day_checkbox.isChecked()

        start_dt = self.start_time_edit.dateTime().toPyDateTime()
        end_dt = self.end_time_edit.dateTime().toPyDateTime()

        event_body = {
            'summary': summary,
            'description': description,
        }

        if is_all_day:
            event_body['start'] = {'date': start_dt.strftime('%Y-%m-%d')}
            # 종일 일정의 종료일은 다음 날로 지정해야 합니다.
            event_body['end'] = {'date': (end_dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}
        else:
            event_body['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Seoul'}
            event_body['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Seoul'}

        # 수정 모드일 경우, 기존 이벤트 ID를 포함시킵니다.
        if self.mode == 'edit':
            event_body['id'] = self.event_data.get('id')
        # 로컬 캘린더의 새 이벤트는 자체 ID가 필요합니다.
        elif self.calendar_combo.currentData()['provider'] == LOCAL_CALENDAR_PROVIDER_NAME:
            event_body['id'] = str(uuid.uuid4())


        # 선택된 캘린더 정보(ID, Provider)를 함께 반환합니다.
        selected_calendar_data = self.calendar_combo.currentData()
        return {
            'calendarId': selected_calendar_data['id'],
            'provider': selected_calendar_data['provider'],
            'body': event_body
        }