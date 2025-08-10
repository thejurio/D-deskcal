import datetime
import uuid
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QTextEdit, QPushButton, QCheckBox, QWidget, QCalendarWidget)
from PyQt6.QtCore import QDateTime, Qt, pyqtSignal, QEvent
from custom_dialogs import BaseDialog, CustomMessageBox

class DateSelector(QWidget):
    dateChanged = pyqtSignal(QDateTime)

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
            self.dateChanged.emit(self.current_datetime)

    def dateTime(self):
        return self.current_datetime

    def update_display(self):
        self.line_edit.setText(self.current_datetime.toString("yyyy-MM-dd"))

class TaskEditorWindow(BaseDialog):
    DeleteRole = 2

    def __init__(self, mode='new', data=None, settings=None, parent=None, pos=None, data_manager=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.mode = mode
        self.task_data = data if isinstance(data, dict) else {}
        self.date_info = data if isinstance(data, (datetime.date, datetime.datetime)) else None
        self.data_manager = data_manager

        self.setWindowTitle("작업 추가" if self.mode == 'new' else "작업 수정")
        self.setMinimumWidth(400)

        self.initUI()
        self.populate_data()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(15, 15, 15, 15)

        self.title_edit = QLineEdit()
        layout.addWidget(QLabel("작업 내용:"))
        layout.addWidget(self.title_edit)

        due_date_layout = QHBoxLayout()
        self.due_date_selector = DateSelector()
        due_date_layout.addWidget(QLabel("마감일:"))
        due_date_layout.addWidget(self.due_date_selector)
        layout.addLayout(due_date_layout)

        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(80)
        layout.addWidget(QLabel("메모:"))
        layout.addWidget(self.description_edit)
        
        self.completed_checkbox = QCheckBox("완료")
        layout.addWidget(self.completed_checkbox)

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

    def populate_data(self):
        if self.mode == 'edit' and self.task_data:
            self.title_edit.setText(self.task_data.get('title', ''))
            self.description_edit.setText(self.task_data.get('description', ''))
            if self.task_data.get('due_date'):
                due_date = QDateTime.fromString(self.task_data['due_date'], "yyyy-MM-dd")
                self.due_date_selector.setDateTime(due_date)
            self.completed_checkbox.setChecked(bool(self.task_data.get('completed_at')))
        elif self.mode == 'new':
            if self.date_info:
                # date_info가 datetime.datetime 객체일 수 있으므로 QDateTime으로 변환
                if isinstance(self.date_info, datetime.datetime):
                    self.due_date_selector.setDateTime(QDateTime(self.date_info))
                else: # datetime.date 객체
                    self.due_date_selector.setDateTime(QDateTime(self.date_info, datetime.datetime.now().time()))
            else:
                self.due_date_selector.setDateTime(QDateTime.currentDateTime())
            self.completed_checkbox.setVisible(False)

    def request_delete(self):
        text = f"'{self.title_edit.text()}' 작업을 정말 삭제하시겠습니까?"
        msg_box = CustomMessageBox(self, title='삭제 확인', text=text, settings=self.settings)
        if msg_box.exec():
            self.done(self.DeleteRole)

    def get_task_data(self):
        task_id = self.task_data.get('id') if self.mode == 'edit' else str(uuid.uuid4())
        
        is_checked = self.completed_checkbox.isChecked()
        was_completed = bool(self.task_data.get('completed_at'))
        
        completed_at = self.task_data.get('completed_at') # 기존 값 유지
        if is_checked and not was_completed:
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        elif not is_checked and was_completed:
            completed_at = None

        return {
            'id': task_id,
            'title': self.title_edit.text(),
            'description': self.description_edit.toPlainText(),
            'due_date': self.due_date_selector.dateTime().toString("yyyy-MM-dd"),
            'completed_at': completed_at
        }
