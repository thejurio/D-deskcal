# settings_window.py
import copy
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QHBoxLayout,
                             QColorDialog, QComboBox, QSlider, QSizePolicy,
                             QListWidget, QStackedWidget, QListWidgetItem, QFormLayout, QTimeEdit, QLineEdit)
from PyQt6.QtGui import QColor, QPixmap, QIcon, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTime, QObject, QThread

from custom_dialogs import BaseDialog, HotkeyInputDialog, CustomMessageBox
import gemini_parser
from config import (
                    DEFAULT_SYNC_INTERVAL, DEFAULT_LOCK_MODE_ENABLED, 
                    DEFAULT_LOCK_MODE_KEY, DEFAULT_WINDOW_MODE,
                    DEFAULT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATION_MINUTES,
                    DEFAULT_ALL_DAY_NOTIFICATION_ENABLED, DEFAULT_ALL_DAY_NOTIFICATION_TIME,
                    DEFAULT_NOTIFICATION_DURATION)

PASTEL_COLORS = {
    "기본": ["#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff", "#e4e4e4", "#f1f1f1"]
}
CUSTOM_COLOR_TEXT = "사용자 지정..."

class ApiKeyVerifier(QObject):
    """API 키 유효성 검사를 백그라운드 스레드에서 실행하는 워커"""
    verification_finished = pyqtSignal(bool, str)

    def run(self, api_key):
        is_valid, message = gemini_parser.verify_api_key(api_key)
        self.verification_finished.emit(is_valid, message)

class SettingsWindow(BaseDialog):
    transparency_changed = pyqtSignal(float)
    theme_changed = pyqtSignal(str)

    def __init__(self, data_manager, settings, parent=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.data_manager = data_manager
        
        self.original_settings = settings
        self.temp_settings = copy.deepcopy(settings)
        self.changed_fields = set()

        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumSize(560, 500)
        
        margin_widget = QWidget()
        margin_widget.setObjectName("settings_margin_background")
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(margin_widget)
        margin_layout = QVBoxLayout(margin_widget)
        margin_layout.setContentsMargins(10, 10, 10, 10)
        content_widget = QWidget()
        content_widget.setObjectName("settings_content_background")
        margin_layout.addWidget(content_widget)
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(0)
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("settings_nav")
        self.nav_list.setFixedWidth(140)
        self.nav_list.setFont(QFont("Malgun Gothic", 10))
        self.stack = QStackedWidget()
        self.stack.setObjectName("settings_stack")
        top_layout.addWidget(self.nav_list)
        top_layout.addWidget(self.stack)
        main_layout.addLayout(top_layout, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        bottom_layout.addStretch(1)
        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.save_and_close)
        self.save_button.setDefault(True)
        bottom_layout.addWidget(self.save_button)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_button)
        bottom_container = QWidget()
        bottom_container.setObjectName("bottom_container")
        bottom_container.setLayout(bottom_layout)
        main_layout.addWidget(bottom_container)

        self.checkboxes = {}
        self.color_combos = {}
        
        self.create_connectivity_page()
        self.create_appearance_page()
        self.create_behavior_page()
        
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
        self.data_manager.calendar_list_changed.connect(self.rebuild_ui)
        self.rebuild_ui()
        self.set_stylesheet()

    def _mark_as_changed(self, field_name):
        self.changed_fields.add(field_name)

    def set_stylesheet(self):
        is_dark = self.temp_settings.get("theme", "dark") == "dark"
        margin_color = "rgb(30, 30, 30)" if is_dark else "#FAFAFA"
        content_bg = "#3C3C3C" if is_dark else "#FFFFFF"
        nav_bg = "#2E2E2E" if is_dark else "#FFFFFF"
        nav_border = "#444" if is_dark else "#E0E0E0"
        bottom_bg = nav_bg
        nav_item_hover_bg = "#4A4A4A" if is_dark else "#F0F0F0"
        section_title_fg = "#E0E0E0" if is_dark else "#111111"
        general_text_color = "#E0E0E0" if is_dark else "#222222"
        nav_item_selected_bg = "#0078D7"
        nav_item_selected_fg = "#FFFFFF"

        qss = f"""
            QWidget#settings_margin_background {{ background-color: {margin_color}; border-radius: 12px; }}
            QWidget#settings_content_background {{ border-radius: 8px; }}
            QListWidget#settings_nav {{
                background-color: {nav_bg}; border-right: 1px solid {nav_border};
                outline: 0px; border-top-left-radius: 8px; border-bottom-left-radius: 8px;
                color: {general_text_color};
            }}
            QListWidget#settings_nav::item {{ padding: 15px; border: none; }}
            QListWidget#settings_nav::item:selected {{ background-color: {nav_item_selected_bg}; color: {nav_item_selected_fg}; font-weight: bold; }}
            QListWidget#settings_nav::item:hover:!selected {{ background-color: {nav_item_hover_bg}; }}
            QWidget#settings_page {{ background-color: {content_bg}; color: {general_text_color}; border-top-right-radius: 8px; }}
            QWidget#bottom_container {{ background-color: {bottom_bg}; border-top: 1px solid {nav_border}; border-bottom-right-radius: 8px; }}
            QLabel#section_title {{ font-size: 18px; font-weight: bold; padding-top: 10px; padding-bottom: 15px; color: {section_title_fg}; }}
            QWidget#settings_page QScrollArea, QWidget#transparent_container {{ background-color: transparent; }}
            QWidget#settings_page QLabel:!#section_title {{ color: {general_text_color}; }}
            QWidget#settings_page QCheckBox {{ color: {general_text_color}; }}
        """
        self.setStyleSheet(qss)

    def _create_section_label(self, text):
        label = QLabel(text)
        label.setObjectName("section_title")
        return label

    def create_connectivity_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setContentsMargins(25, 15, 25, 25)
        self.nav_list.addItem(QListWidgetItem("🔗 연동 및 데이터"))
        
        layout.addWidget(self._create_section_label("Google 계정 연동"))
        account_layout = QHBoxLayout(); self.account_status_label = QLabel("상태 확인 중..."); self.account_button = QPushButton("로그인")
        account_layout.addWidget(self.account_status_label, 1); account_layout.addWidget(self.account_button)
        self.account_button.clicked.connect(self.handle_account_button_click)
        layout.addLayout(account_layout)
        layout.addSpacing(20)

        layout.addWidget(self._create_section_label("Gemini AI 연동"))
        api_key_layout = QHBoxLayout()
        self.gemini_api_key_input = QLineEdit(); self.gemini_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_api_key_input.setPlaceholderText("Gemini API 키를 여기에 붙여넣으세요")
        self.verify_api_key_button = QPushButton("확인")
        api_key_layout.addWidget(self.gemini_api_key_input); api_key_layout.addWidget(self.verify_api_key_button)
        self.api_key_status_label = QLabel(""); self.api_key_status_label.setStyleSheet("font-size: 8pt; padding-left: 5px;")
        gemini_form_layout = QFormLayout(); gemini_form_layout.addRow("API 키:", api_key_layout); gemini_form_layout.addRow("", self.api_key_status_label)
        layout.addLayout(gemini_form_layout)
        current_api_key = self.temp_settings.get("gemini_api_key")
        if current_api_key: self.gemini_api_key_input.setPlaceholderText(f"저장된 키 유지 (마지막 4자리: {current_api_key[-4:]})")
        self.gemini_api_key_input.textChanged.connect(self.on_api_key_text_changed)
        self.verify_api_key_button.clicked.connect(self.on_verify_api_key_clicked)
        layout.addSpacing(20)

        layout.addWidget(self._create_section_label("동기화"))
        form_layout_sync = QFormLayout()
        self.sync_interval_combo = QComboBox()
        self.sync_options = { 0: "사용 안 함", 1: "1분", 5: "5분", 15: "15분", 30: "30분", 60: "1시간" }
        for minutes, text in self.sync_options.items(): self.sync_interval_combo.addItem(text, minutes)
        self.sync_interval_combo.setCurrentIndex(self.sync_interval_combo.findData(self.temp_settings.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL)))
        self.sync_interval_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("sync_interval_minutes"))
        form_layout_sync.addRow("자동 동기화 주기:", self.sync_interval_combo)
        layout.addLayout(form_layout_sync)

        self.stack.addWidget(page)

    def create_appearance_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setContentsMargins(25, 15, 25, 25)
        self.nav_list.addItem(QListWidgetItem("🎨 화면 표시"))

        layout.addWidget(self._create_section_label("테마 및 투명도"))
        form_layout_theme = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_options = { "dark": "어두운 테마", "light": "밝은 테마" }
        for value, text in self.theme_options.items(): self.theme_combo.addItem(text, value)
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.temp_settings.get("theme", "dark")))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        form_layout_theme.addRow("테마 선택:", self.theme_combo)
        
        opacity_widget = QWidget(); opacity_layout = QHBoxLayout(opacity_widget); opacity_layout.setContentsMargins(0,0,0,0)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal); self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(int(self.temp_settings.get("window_opacity", 0.95) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}% "); self.opacity_label.setMinimumWidth(40)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider); opacity_layout.addWidget(self.opacity_label)
        form_layout_theme.addRow("전체 투명도:", opacity_widget)
        layout.addLayout(form_layout_theme)
        layout.addSpacing(20)

        layout.addWidget(self._create_section_label("달력 표시"))
        form_layout_display = QFormLayout()
        self.start_day_combo = QComboBox(); self.start_day_combo.addItem("일요일", 6); self.start_day_combo.addItem("월요일", 0)
        self.start_day_combo.setCurrentIndex(self.start_day_combo.findData(self.temp_settings.get("start_day_of_week", 6)))
        self.start_day_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("start_day_of_week"))
        form_layout_display.addRow("한 주의 시작:", self.start_day_combo)
        self.hide_weekends_checkbox = QCheckBox("주말(토, 일) 숨기기")
        self.hide_weekends_checkbox.setChecked(self.temp_settings.get("hide_weekends", False))
        self.hide_weekends_checkbox.stateChanged.connect(lambda: self._mark_as_changed("hide_weekends"))
        form_layout_display.addRow("", self.hide_weekends_checkbox)
        layout.addLayout(form_layout_display)
        layout.addSpacing(20)

        layout.addWidget(self._create_section_label("캘린더 표시 및 색상 설정"))
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        layout.addWidget(scroll_area)
        self.calendar_list_widget = QWidget(); self.calendar_list_widget.setObjectName("transparent_container")
        self.calendar_list_layout = QVBoxLayout(self.calendar_list_widget)
        self.calendar_list_layout.setContentsMargins(0,0,0,0); self.calendar_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.calendar_list_widget)
        
        self.stack.addWidget(page)

    def create_behavior_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setContentsMargins(25, 15, 25, 25)
        self.nav_list.addItem(QListWidgetItem("🔔 동작 및 알림"))

        layout.addWidget(self._create_section_label("데스크톱 알림"))
        form_layout_notif = QFormLayout()
        self.notifications_enabled_checkbox = QCheckBox("시간 지정 일정 알림 표시")
        is_enabled = self.temp_settings.get("notifications_enabled", DEFAULT_NOTIFICATIONS_ENABLED)
        self.notifications_enabled_checkbox.setChecked(is_enabled)
        self.notifications_enabled_checkbox.stateChanged.connect(self.on_notifications_toggled)
        form_layout_notif.addRow("", self.notifications_enabled_checkbox)
        self.notification_minutes_spinbox = QComboBox()
        self.notification_time_options = { 1: "1분 전", 5: "5분 전", 10: "10분 전", 15: "15분 전", 30: "30분 전" }
        for minutes, text in self.notification_time_options.items(): self.notification_minutes_spinbox.addItem(text, minutes)
        current_minutes = self.temp_settings.get("notification_minutes", DEFAULT_NOTIFICATION_MINUTES)
        self.notification_minutes_spinbox.setCurrentIndex(self.notification_minutes_spinbox.findData(current_minutes))
        self.notification_minutes_spinbox.setEnabled(is_enabled)
        self.notification_minutes_spinbox.currentIndexChanged.connect(lambda: self._mark_as_changed("notification_minutes"))
        form_layout_notif.addRow("알림 시간:", self.notification_minutes_spinbox)
        self.notification_duration_combo = QComboBox()
        self.duration_options = { 5: "5초", 10: "10초", 20: "20초", 60: "1분", 0: "닫지 않음" }
        for seconds, text in self.duration_options.items(): self.notification_duration_combo.addItem(text, seconds)
        current_duration = self.temp_settings.get("notification_duration", DEFAULT_NOTIFICATION_DURATION)
        self.notification_duration_combo.setCurrentIndex(self.notification_duration_combo.findData(current_duration))
        self.notification_duration_combo.setEnabled(is_enabled)
        self.notification_duration_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("notification_duration"))
        form_layout_notif.addRow("팝업 표시 시간:", self.notification_duration_combo)
        self.all_day_notification_checkbox = QCheckBox("하루 종일 일정 알림 표시")
        is_all_day_enabled = self.temp_settings.get("all_day_notification_enabled", DEFAULT_ALL_DAY_NOTIFICATION_ENABLED)
        self.all_day_notification_checkbox.setChecked(is_all_day_enabled)
        self.all_day_notification_checkbox.stateChanged.connect(self.on_all_day_notifications_toggled)
        form_layout_notif.addRow("", self.all_day_notification_checkbox)
        self.all_day_notification_time_edit = QTimeEdit()
        self.all_day_notification_time_edit.setDisplayFormat("HH:mm")
        default_time_str = self.temp_settings.get("all_day_notification_time", DEFAULT_ALL_DAY_NOTIFICATION_TIME)
        self.all_day_notification_time_edit.setTime(QTime.fromString(default_time_str, "HH:mm"))
        self.all_day_notification_time_edit.setEnabled(is_all_day_enabled)
        self.all_day_notification_time_edit.timeChanged.connect(lambda: self._mark_as_changed("all_day_notification_time"))
        form_layout_notif.addRow("알림 시간:", self.all_day_notification_time_edit)
        layout.addLayout(form_layout_notif)
        layout.addSpacing(20)

        layout.addWidget(self._create_section_label("창 동작"))
        form_layout_behavior = QFormLayout()
        self.window_mode_combo = QComboBox()
        self.window_mode_options = {"AlwaysOnTop": "항상 위에", "Normal": "일반", "AlwaysOnBottom": "항상 아래에"}
        for value, text in self.window_mode_options.items(): self.window_mode_combo.addItem(text, value)
        current_window_mode = self.temp_settings.get("window_mode", DEFAULT_WINDOW_MODE)
        self.window_mode_combo.setCurrentIndex(self.window_mode_combo.findData(current_window_mode))
        self.window_mode_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("window_mode"))
        form_layout_behavior.addRow("창 위치:", self.window_mode_combo)
        
        self.lock_mode_checkbox = QCheckBox("잠금 모드 사용 (지정한 키를 누를 때만 상호작용)")
        is_lock_mode_enabled = self.temp_settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED)
        self.lock_mode_checkbox.setChecked(is_lock_mode_enabled)
        self.lock_mode_checkbox.stateChanged.connect(self.on_lock_mode_toggled)
        form_layout_behavior.addRow("", self.lock_mode_checkbox)
        
        self.lock_key_combo = QComboBox()
        self.lock_key_options = { "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "z": "Z", "a": "A", "q": "Q" }
        for value, text in self.lock_key_options.items(): self.lock_key_combo.addItem(text, value)
        current_lock_key = self.temp_settings.get("lock_mode_key", DEFAULT_LOCK_MODE_KEY)
        self.lock_key_combo.setCurrentIndex(self.lock_key_combo.findData(current_lock_key))
        self.lock_key_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("lock_mode_key"))
        self.lock_key_combo.setEnabled(is_lock_mode_enabled)
        form_layout_behavior.addRow("잠금 해제 키:", self.lock_key_combo)

        self.startup_checkbox = QCheckBox("Windows 시작 시 자동 실행")
        self.startup_checkbox.setChecked(self.temp_settings.get("start_on_boot", False))
        self.startup_checkbox.stateChanged.connect(lambda: self._mark_as_changed("start_on_boot"))
        form_layout_behavior.addRow("", self.startup_checkbox)
        layout.addLayout(form_layout_behavior)
        layout.addSpacing(20)

        layout.addWidget(self._create_section_label("글로벌 단축키"))
        form_layout_hotkey = QFormLayout()
        
        hotkey_layout = QHBoxLayout()
        self.ai_hotkey_display = QLineEdit()
        self.ai_hotkey_display.setReadOnly(True)
        self.ai_hotkey_display.setPlaceholderText("단축키 없음")
        
        set_hotkey_button = QPushButton("단축키 등록")
        set_hotkey_button.clicked.connect(self.open_hotkey_dialog)
        clear_hotkey_button = QPushButton("해제")
        clear_hotkey_button.clicked.connect(self.clear_ai_hotkey)

        hotkey_layout.addWidget(self.ai_hotkey_display)
        hotkey_layout.addWidget(set_hotkey_button)
        hotkey_layout.addWidget(clear_hotkey_button)

        form_layout_hotkey.addRow("AI 일정 추가:", hotkey_layout)
        layout.addLayout(form_layout_hotkey)

        self.stack.addWidget(page)

    def open_hotkey_dialog(self):
        dialog = HotkeyInputDialog(self, self.settings, self.pos())
        if dialog.exec():
            hotkey = dialog.get_hotkey()
            if not hotkey:
                return

            confirm_dialog = CustomMessageBox(
                self, 
                title="단축키 확인", 
                text=f"'{hotkey}'을(를) AI 일정 추가 단축키로 등록하시겠습니까?",
                settings=self.settings
            )
            if confirm_dialog.exec():
                self.temp_settings['ai_add_event_hotkey'] = hotkey
                self.ai_hotkey_display.setText(hotkey)
                self._mark_as_changed('ai_add_event_hotkey')

    def clear_ai_hotkey(self):
        self.temp_settings['ai_add_event_hotkey'] = ""
        self.ai_hotkey_display.setText("")
        self._mark_as_changed('ai_add_event_hotkey')

    def update_hotkey_display(self):
        hotkey = self.temp_settings.get("ai_add_event_hotkey", "")
        self.ai_hotkey_display.setText(hotkey)

    def on_api_key_text_changed(self):
        self._mark_as_changed("gemini_api_key")
        self.api_key_status_label.setText("")

    def on_verify_api_key_clicked(self):
        api_key = self.gemini_api_key_input.text().strip()
        if not api_key:
            api_key = self.temp_settings.get("gemini_api_key")
            if not api_key:
                self.api_key_status_label.setText("오류: 확인할 API 키가 없습니다."); self.api_key_status_label.setStyleSheet("color: #E57373;"); return
        self.api_key_status_label.setText("확인 중..."); self.api_key_status_label.setStyleSheet("color: #9E9E9E;"); self.verify_api_key_button.setEnabled(False)
        self.worker = ApiKeyVerifier(); self.thread = QThread(); self.worker.moveToThread(self.thread)
        self.worker.verification_finished.connect(self.on_verification_finished)
        self.thread.started.connect(lambda: self.worker.run(api_key)); self.thread.finished.connect(self.thread.deleteLater); self.thread.start()

    def on_verification_finished(self, is_valid, message):
        self.api_key_status_label.setText(message)
        self.api_key_status_label.setStyleSheet(f"color: {{'#81C784' if is_valid else '#E57373'}}");
        self.verify_api_key_button.setEnabled(True); self.thread.quit(); self.worker.deleteLater()

    def on_lock_mode_toggled(self, state):
        self._mark_as_changed("lock_mode_enabled"); is_checked = bool(state); self.lock_key_combo.setEnabled(is_checked)
        if not is_checked: self.window_mode_combo.setCurrentIndex(self.window_mode_combo.findData("Normal")); self._mark_as_changed("window_mode")

    def on_notifications_toggled(self, state):
        self._mark_as_changed("notifications_enabled"); is_checked = bool(state)
        self.notification_minutes_spinbox.setEnabled(is_checked); self.notification_duration_combo.setEnabled(is_checked)

    def on_all_day_notifications_toggled(self, state):
        self._mark_as_changed("all_day_notification_enabled"); is_checked = bool(state); self.all_day_notification_time_edit.setEnabled(is_checked)

    def rebuild_ui(self):
        self.update_account_status()
        self.populate_calendar_list()
        self.update_hotkey_display()

    def update_account_status(self):
        if self.data_manager.auth_manager.is_logged_in():
            user_info = self.data_manager.auth_manager.get_user_info()
            self.account_status_label.setText(user_info.get('email', "정보 확인 불가")); self.account_button.setText("로그아웃")
        else:
            self.account_status_label.setText("연결되지 않음"); self.account_button.setText("로그인")

    def handle_account_button_click(self):
        if self.data_manager.auth_manager.is_logged_in(): self.data_manager.auth_manager.logout() # This line might need escaping if it contained special characters
        else: self.data_manager.auth_manager.login()

    def populate_calendar_list(self):
        while self.calendar_list_layout.count():
            child = self.calendar_list_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.checkboxes.clear(); self.color_combos.clear()
        selected_calendars = self.temp_settings.get("selected_calendars", [])
        try:
            calendar_list = self.data_manager.get_all_calendars()
            if not calendar_list: self.calendar_list_layout.addWidget(QLabel("표시할 캘린더가 없습니다.\nGoogle 계정에 로그인하여 캘린더를 불러오세요.")); return
            if not selected_calendars and calendar_list:
                primary_cal = next((cal for cal in calendar_list if cal.get('primary')), calendar_list[0])
                selected_calendars = [primary_cal['id']]
            for calendar in calendar_list:
                cal_id = calendar["id"]; row_layout = QHBoxLayout(); checkbox = QCheckBox()
                checkbox.setChecked(cal_id in selected_calendars)
                checkbox.stateChanged.connect(lambda state, c_id=cal_id: self._mark_as_changed("selected_calendars"))
                self.checkboxes[cal_id] = checkbox
                color_combo = self.create_color_combo(cal_id, calendar['backgroundColor']); self.color_combos[cal_id] = color_combo
                color_combo.activated.connect(lambda idx, c_id=cal_id: self.handle_color_change(c_id, idx))
                name_label = QLabel(calendar["summary"]); name_label.setWordWrap(True)
                row_layout.addWidget(checkbox); row_layout.addWidget(color_combo); row_layout.addWidget(name_label, 1)
                self.calendar_list_layout.addLayout(row_layout)
        except Exception as e:
            self.calendar_list_layout.addWidget(QLabel(f"캘린더 목록 로드 실패:\n{e}"))

    def on_opacity_changed(self, value):
        self._mark_as_changed("window_opacity"); opacity_float = value / 100.0
        self.temp_settings["window_opacity"] = opacity_float; self.opacity_label.setText(f"{self.opacity_slider.value()}% ")
        self.transparency_changed.emit(opacity_float)

    def on_theme_changed(self, text):
        self._mark_as_changed("theme"); selected_theme_name = self.theme_combo.currentData()
        self.temp_settings["theme"] = selected_theme_name; self.theme_changed.emit(selected_theme_name); self.set_stylesheet()

    def create_color_icon(self, color_hex):
        pixmap = QPixmap(16, 16); pixmap.fill(QColor(color_hex)); return QIcon(pixmap)

    def create_color_combo(self, cal_id, default_color):
        combo = QComboBox(); combo.setIconSize(QSize(16, 16)); combo.setFixedWidth(45); combo.setMaxVisibleItems(5)
        current_color = self.temp_settings.get("calendar_colors", {}).get(cal_id, default_color)
        for color in PASTEL_COLORS["기본"]:
            combo.addItem(self.create_color_icon(color), "", userData=color)
        if current_color not in PASTEL_COLORS["기본"]:
            combo.insertItem(0, self.create_color_icon(current_color), "", userData=current_color)
        combo.addItem(CUSTOM_COLOR_TEXT)
        index = combo.findData(current_color)
        if index != -1: combo.setCurrentIndex(index)
        return combo

    def handle_color_change(self, cal_id, index):
        self._mark_as_changed("calendar_colors"); combo = self.color_combos[cal_id]
        if combo.itemText(index) == CUSTOM_COLOR_TEXT:
            current_color_hex = combo.currentData() or self.temp_settings.get("calendar_colors", {}).get(cal_id, "#FFFFFF")
            new_color = QColorDialog.getColor(QColor(current_color_hex), self, "색상 선택")
            if new_color.isValid():
                hex_color = new_color.name()
                if combo.findData(hex_color) == -1: combo.insertItem(0, self.create_color_icon(hex_color), "", userData=hex_color)
                combo.setCurrentIndex(combo.findData(hex_color))
            else: combo.setCurrentIndex(combo.findData(current_color_hex))
        self.temp_settings.setdefault("calendar_colors", {})[cal_id] = combo.currentData()

    def save_and_close(self):
        self.temp_settings["selected_calendars"] = [cal_id for cal_id, cb in self.checkboxes.items() if cb.isChecked()]
        self.temp_settings.setdefault("calendar_colors", {}).update({cal_id: combo.currentData() for cal_id, combo in self.color_combos.items() if combo.currentData()})
        if "calendar_emojis" in self.temp_settings: del self.temp_settings["calendar_emojis"]
        self.temp_settings["sync_interval_minutes"] = self.sync_interval_combo.currentData()
        self.temp_settings["start_day_of_week"] = self.start_day_combo.currentData()
        self.temp_settings["hide_weekends"] = self.hide_weekends_checkbox.isChecked()
        self.temp_settings["window_opacity"] = self.opacity_slider.value() / 100.0
        self.temp_settings["theme"] = self.theme_combo.currentData()
        self.temp_settings["window_mode"] = self.window_mode_combo.currentData()
        self.temp_settings["lock_mode_enabled"] = self.lock_mode_checkbox.isChecked()
        self.temp_settings["lock_mode_key"] = self.lock_key_combo.currentData()
        self.temp_settings["start_on_boot"] = self.startup_checkbox.isChecked()
        self.temp_settings["notifications_enabled"] = self.notifications_enabled_checkbox.isChecked()
        self.temp_settings["notification_minutes"] = self.notification_minutes_spinbox.currentData()
        self.temp_settings["notification_duration"] = self.notification_duration_combo.currentData()
        self.temp_settings["all_day_notification_enabled"] = self.all_day_notification_checkbox.isChecked()
        self.temp_settings["all_day_notification_time"] = self.all_day_notification_time_edit.time().toString("HH:mm")
        new_api_key = self.gemini_api_key_input.text().strip()
        if new_api_key: self.temp_settings["gemini_api_key"] = new_api_key
        self.original_settings.clear(); self.original_settings.update(self.temp_settings)
        self.done(1)
        
    def get_changed_fields(self):
        return list(self.changed_fields)
