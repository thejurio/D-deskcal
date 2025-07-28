from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QHBoxLayout,
                             QColorDialog, QComboBox, QSlider, QSizePolicy)
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from custom_dialogs import BaseDialog
from config import DEFAULT_SYNC_INTERVAL

# --- 미리 정의된 상수들은 그대로 둡니다. ---
PASTEL_COLORS = {
    "기본": ["#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff", "#e4e4e4", "#f1f1f1"]
}
CUSTOM_COLOR_TEXT = "사용자 지정..."

class SettingsWindow(BaseDialog):
    transparency_changed = pyqtSignal(float)
    theme_changed = pyqtSignal(str)

    def __init__(self, data_manager, settings, parent=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.data_manager = data_manager
        # self.settings는 BaseDialog에서 처리

        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(500)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        content_layout = QVBoxLayout(background_widget)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_layout.addWidget(scroll_area)
        
        scroll_content = QWidget()
        self.layout = QVBoxLayout(scroll_content)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(scroll_content)

        self.local_calendar_checkbox = QCheckBox("로컬 캘린더 사용 (calendar.db)")
        self.local_calendar_checkbox.setChecked(self.settings.get("use_local_calendar", True))
        self.layout.addWidget(self.local_calendar_checkbox)
        self.layout.addWidget(QLabel("-" * 50))

        self.layout.addWidget(QLabel("Google 계정 연동:"))
        account_layout = QHBoxLayout()
        self.account_status_label = QLabel("상태 확인 중...")
        self.account_button = QPushButton("로그인")
        account_layout.addWidget(self.account_status_label, 1)
        account_layout.addWidget(self.account_button)
        self.layout.addLayout(account_layout)
        self.account_button.clicked.connect(self.handle_account_button_click)

        self.layout.addWidget(QLabel("-" * 50))
        self.layout.addWidget(QLabel("표시할 캘린더와 색상을 설정하세요:"))

        self.checkboxes = {}
        self.color_combos = {}

        self.layout.addWidget(QLabel("-" * 50))
        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("자동 동기화 주기:"))
        self.sync_interval_combo = QComboBox()
        self.sync_options = {
            0: "사용 안 함", 1: "1분", 5: "5분", 15: "15분", 30: "30분", 60: "1시간"
        }
        for minutes, text in self.sync_options.items():
            self.sync_interval_combo.addItem(text, minutes)
        
        current_interval = self.settings.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL)
        self.sync_interval_combo.setCurrentIndex(self.sync_interval_combo.findData(current_interval))
        sync_layout.addWidget(self.sync_interval_combo)
        self.layout.addLayout(sync_layout)

        self.layout.addWidget(QLabel("-" * 50))
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("테마 설정:"))
        self.theme_combo = QComboBox()
        self.theme_options = { "dark": "어두운 테마", "light": "밝은 테마" }
        for value, text in self.theme_options.items():
            self.theme_combo.addItem(text, value)
        
        current_theme = self.settings.get("theme", "dark")
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(current_theme))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        self.layout.addLayout(theme_layout)
        
        self.layout.addWidget(QLabel("-" * 50))
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("전체 투명도:"))
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        current_opacity = int(self.settings.get("window_opacity", 0.95) * 100)
        self.opacity_slider.setValue(current_opacity)
        
        self.opacity_label = QLabel(f"{current_opacity}%")
        self.opacity_label.setMinimumWidth(40)
        
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)
        self.layout.addLayout(opacity_layout)

        self.layout.addWidget(QLabel("-" * 50))

        self.calendar_list_widget = QWidget()
        self.calendar_list_layout = QVBoxLayout(self.calendar_list_widget)
        self.calendar_list_layout.setContentsMargins(0,0,0,0)
        self.layout.addWidget(self.calendar_list_widget)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        content_layout.addLayout(button_layout)

        self.data_manager.calendar_list_changed.connect(self.rebuild_ui)
        self.rebuild_ui()

    def rebuild_ui(self):
        self.update_account_status()
        self.populate_calendar_list()

    def update_account_status(self):
        if self.data_manager.auth_manager.is_logged_in():
            user_info = self.data_manager.auth_manager.get_user_info()
            if user_info and 'email' in user_info:
                self.account_status_label.setText(user_info['email'])
            else:
                self.account_status_label.setText("연결됨 (정보 확인 불가)")
            self.account_button.setText("로그아웃")
        else:
            self.account_status_label.setText("연결되지 않음")
            self.account_button.setText("로그인")

    def handle_account_button_click(self):
        if self.data_manager.auth_manager.is_logged_in():
            self.data_manager.auth_manager.logout()
        else:
            self.data_manager.auth_manager.login()

    def populate_calendar_list(self):
        while self.calendar_list_layout.count():
            child = self.calendar_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.checkboxes = {}
        self.color_combos = {}
        
        selected_calendars = self.settings.get("selected_calendars", [])

        try:
            calendar_list = self.data_manager.get_all_calendars()
            
            if not calendar_list:
                 self.calendar_list_layout.addWidget(QLabel("표시할 캘린더가 없습니다."))
                 return

            if not selected_calendars and calendar_list:
                primary_cal = next((cal for cal in calendar_list if cal.get('primary')), calendar_list[0])
                selected_calendars = [primary_cal['id']]

            for calendar in calendar_list:
                cal_id = calendar["id"]
                row_layout = QHBoxLayout()

                checkbox = QCheckBox()
                checkbox.setChecked(cal_id in selected_calendars)
                checkbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                self.checkboxes[cal_id] = checkbox

                color_combo = self.create_color_combo(cal_id, calendar['backgroundColor'])
                color_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                self.color_combos[cal_id] = color_combo
                color_combo.activated.connect(lambda idx, c_id=cal_id: self.handle_color_change(c_id, idx))

                name_label = QLabel(calendar["summary"])
                name_label.setWordWrap(True)
                
                row_layout.addWidget(checkbox)
                row_layout.addWidget(color_combo)
                row_layout.addWidget(name_label, 1)
                self.calendar_list_layout.addLayout(row_layout)

        except Exception as e:
            label = QLabel(f"캘린더 목록 로드 실패:\n{e}")
            label.setWordWrap(True)
            self.calendar_list_layout.addWidget(label)

    def on_opacity_changed(self, value):
        main_opacity = value / 100.0
        self.opacity_label.setText(f"{value}%")
        self.transparency_changed.emit(main_opacity)
        dialog_opacity = main_opacity + (1 - main_opacity) * 0.85
        self.setWindowOpacity(dialog_opacity)

    def on_theme_changed(self, text):
        selected_theme_name = self.theme_combo.currentData()
        self.theme_changed.emit(selected_theme_name)

    def create_color_icon(self, color_hex):
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color_hex))
        return QIcon(pixmap)

    def create_color_combo(self, cal_id, default_color):
        combo = QComboBox()
        combo.setIconSize(QSize(16, 16))
        combo.setMinimumWidth(20)
        combo.setMaxVisibleItems(5)
        
        calendar_colors = self.settings.get("calendar_colors", {})
        current_color = calendar_colors.get(cal_id, default_color)

        for color in PASTEL_COLORS["기본"]:
            combo.addItem(self.create_color_icon(color), "", userData=color)

        if current_color not in PASTEL_COLORS["기본"]:
            combo.insertItem(0, self.create_color_icon(current_color), "", userData=current_color)
        
        combo.addItem(CUSTOM_COLOR_TEXT)

        index = combo.findData(current_color)
        if index != -1:
            combo.setCurrentIndex(index)
            
        return combo

    def handle_color_change(self, cal_id, index):
        combo = self.color_combos[cal_id]
        selected_text = combo.itemText(index)

        if selected_text == CUSTOM_COLOR_TEXT:
            calendar_colors = self.settings.get("calendar_colors", {})
            current_color_hex = combo.currentData() or calendar_colors.get(cal_id, "#FFFFFF")
            
            new_color = QColorDialog.getColor(QColor(current_color_hex), self, "색상 선택")
            
            if new_color.isValid():
                hex_color = new_color.name()
                index = combo.findData(hex_color)
                if index == -1:
                    combo.insertItem(0, self.create_color_icon(hex_color), "", userData=hex_color)
                    combo.setCurrentIndex(0)
                else:
                    combo.setCurrentIndex(index)
            else:
                index = combo.findData(current_color_hex)
                if index != -1:
                    combo.setCurrentIndex(index)

    def save_and_close(self):
        self.settings["use_local_calendar"] = self.local_calendar_checkbox.isChecked()
        self.settings["selected_calendars"] = [cal_id for cal_id, cb in self.checkboxes.items() if cb.isChecked()]
        
        calendar_colors = self.settings.get("calendar_colors", {})
        for cal_id, combo in self.color_combos.items():
            if combo.currentData():
                calendar_colors[cal_id] = combo.currentData()
        self.settings["calendar_colors"] = calendar_colors

        if "calendar_emojis" in self.settings:
            del self.settings["calendar_emojis"]
        
        self.settings["sync_interval_minutes"] = self.sync_interval_combo.currentData()

        if "start_day_of_week" in self.settings:
            del self.settings["start_day_of_week"]

        self.settings["window_opacity"] = self.opacity_slider.value() / 100.0
        self.settings["theme"] = self.theme_combo.currentData()

        self.accept()