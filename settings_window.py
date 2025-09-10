# settings_window.py
import copy
from PyQt6.QtWidgets import (QVBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QHBoxLayout,
                             QColorDialog, QComboBox, QSlider, QListWidget, QStackedWidget, QListWidgetItem, QFormLayout, QTimeEdit, QLineEdit, QGroupBox)
from PyQt6.QtGui import QColor, QPixmap, QIcon, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTime, QTimer

from custom_dialogs import BaseDialog, HotkeyInputDialog, CustomMessageBox, APIKeyInputDialog, SingleKeyInputDialog
from resource_path import get_version
from config import (
                    DEFAULT_SYNC_INTERVAL, DEFAULT_LOCK_MODE_ENABLED, 
                    DEFAULT_NOTIFICATIONS_ENABLED, DEFAULT_NOTIFICATION_MINUTES,
                    DEFAULT_ALL_DAY_NOTIFICATION_ENABLED, DEFAULT_ALL_DAY_NOTIFICATION_TIME,
                    DEFAULT_NOTIFICATION_DURATION)

PASTEL_COLORS = {
    "기본": ["#C5504B", "#D24726", "#E36C09", "#70AD47", "#0F5298", "#7030A0", "#8064A2", "#B83DBA", "#44546A", "#595959"]
}
CUSTOM_COLOR_TEXT = "사용자 지정..."

class SettingsWindow(BaseDialog):
    transparency_changed = pyqtSignal(float)
    theme_changed = pyqtSignal(str)
    start_day_changed = pyqtSignal(int)
    hide_weekends_changed = pyqtSignal(bool)
    refresh_requested = pyqtSignal()

    def __init__(self, data_manager, settings, parent=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.data_manager = data_manager
        
        self.original_settings = settings
        self.temp_settings = copy.deepcopy(settings)
        self.changed_fields = set()

        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumSize(530, 620)
        
        # 저장된 위치로 창을 이동 (UI 초기화 전에)
        self.restore_position()
        
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
        self.nav_list.setFixedWidth(160)
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
        
        self.create_general_page()
        self.create_appearance_page()
        self.create_notifications_page()
        self.create_calendar_page()
        self.create_system_page()
        
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
        
        # 신호 연결: 실시간 업데이트를 위해
        self.data_manager.calendar_list_changed.connect(self.populate_calendar_list)
        self.data_manager.auth_manager.auth_state_changed.connect(self.update_account_status)
        
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
            QWidget#settings_page, QWidget#scroll_area_widget {{ background-color: {content_bg}; color: {general_text_color}; }}
            QScrollArea#settings_scroll_area {{ border: none; background-color: transparent; }}
            QWidget#bottom_container {{ background-color: {bottom_bg}; border-top: 1px solid {nav_border}; border-bottom-right-radius: 8px; }}
            QLabel#section_title {{ font-size: 18px; font-weight: bold; padding-top: 10px; padding-bottom: 10px; color: {section_title_fg}; }}
            QWidget#settings_page QScrollArea, QWidget#transparent_container {{ background-color: transparent; }}
            QWidget#settings_page QLabel:!#section_title {{ color: {general_text_color}; }}
            QWidget#settings_page QCheckBox {{ color: {general_text_color}; }}
        """
        self.setStyleSheet(qss)

    def _create_scrollable_page(self):
        scroll_area = QScrollArea()
        scroll_area.setObjectName("settings_scroll_area")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        content_widget.setObjectName("scroll_area_widget")
        
        layout = QVBoxLayout(content_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(25, 15, 25, 25)
        
        scroll_area.setWidget(content_widget)
        return scroll_area, layout

    def _create_section_label(self, text):
        label = QLabel(text)
        label.setObjectName("section_title")
        return label

    def create_general_page(self):
        """일반 설정 페이지"""
        scroll_area, layout = self._create_scrollable_page()
        self.nav_list.addItem(QListWidgetItem("⚙️ 일반"))
        
        # 프로그램 정보
        info_group = QGroupBox("프로그램 정보")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        info_layout = QFormLayout(info_group)
        info_layout.setVerticalSpacing(18)
        
        self.version_label = QLabel(f"v{get_version()}")
        info_layout.addRow("현재 버전:", self.version_label)
        
        # 업데이트 확인 버튼
        self.check_update_button = QPushButton("최신 버전 확인")
        self.check_update_button.clicked.connect(self.check_for_updates)
        info_layout.addRow("", self.check_update_button)
        
        # 자동 업데이트
        self.auto_update_checkbox = QCheckBox("자동 업데이트 확인")
        self.auto_update_checkbox.setChecked(self.temp_settings.get("auto_update_enabled", True))
        self.auto_update_checkbox.toggled.connect(lambda checked: (
            self.temp_settings.update({"auto_update_enabled": checked}),
            self._mark_as_changed("auto_update_enabled")
        ))
        info_layout.addRow("", self.auto_update_checkbox)
        
        layout.addWidget(info_group)
        layout.addSpacing(6)
        
        # Google 계정 연동
        google_group = QGroupBox("Google 계정 연동")
        google_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        google_layout = QVBoxLayout(google_group)
        google_layout.setSpacing(18)
        
        account_layout = QHBoxLayout()
        self.account_status_label = QLabel("상태 확인 중...")
        self.account_button = QPushButton("로그인")
        account_layout.addWidget(self.account_status_label, 1)
        account_layout.addWidget(self.account_button)
        self.account_button.clicked.connect(self.handle_account_button_click)
        google_layout.addLayout(account_layout)
        
        layout.addWidget(google_group)
        layout.addSpacing(6)

        # Gemini AI 연동
        ai_group = QGroupBox("Gemini AI 연동")
        ai_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        ai_layout = QFormLayout(ai_group)
        ai_layout.setVerticalSpacing(18)
        
        api_key_widget = QWidget()
        api_key_layout = QHBoxLayout(api_key_widget)
        api_key_layout.setContentsMargins(0,0,0,0)
        
        self.api_key_display = QLabel()
        self.add_api_key_button = QPushButton("API 키 등록")
        self.change_api_key_button = QPushButton("변경")
        self.reset_api_key_button = QPushButton("초기화")

        api_key_layout.addWidget(self.api_key_display, 1)
        api_key_layout.addWidget(self.add_api_key_button)
        api_key_layout.addWidget(self.change_api_key_button)
        api_key_layout.addWidget(self.reset_api_key_button)
        
        self.add_api_key_button.clicked.connect(self.open_api_key_dialog)
        self.change_api_key_button.clicked.connect(self.open_api_key_dialog)
        self.reset_api_key_button.clicked.connect(self.reset_api_key)

        ai_layout.addRow("API 키:", api_key_widget)
        layout.addWidget(ai_group)
        self.update_api_key_ui()

        self.stack.addWidget(scroll_area)

    def check_for_updates(self):
        """최신 버전 확인"""
        try:
            # auto_update_integration 모듈에서 업데이트 체커를 임시로 생성
            from auto_update_integration import AutoUpdateDialog
            update_dialog = AutoUpdateDialog(self)
            
            # 버튼을 비활성화하고 텍스트 변경
            self.check_update_button.setText("확인 중...")
            self.check_update_button.setEnabled(False)
            
            # 업데이트 확인 (수동)
            update_dialog.check_for_updates(silent=False)
            
            # 버튼 복원
            self.check_update_button.setText("최신 버전 확인")
            self.check_update_button.setEnabled(True)
            
        except Exception as e:
            self.check_update_button.setText("최신 버전 확인")
            self.check_update_button.setEnabled(True)
            CustomMessageBox.warning(self, "업데이트 확인 실패", f"업데이트 확인 중 오류가 발생했습니다:\n{e}")

    def create_appearance_page(self):
        """외관 설정 페이지"""
        scroll_area, layout = self._create_scrollable_page()
        self.nav_list.addItem(QListWidgetItem("🎨 외관"))

        # 테마 설정
        theme_group = QGroupBox("테마 및 투명도")
        theme_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        theme_layout = QFormLayout(theme_group)
        theme_layout.setVerticalSpacing(18)
        
        self.theme_combo = QComboBox()
        self.theme_options = { "dark": "어두운 테마", "light": "밝은 테마" }
        for value, text in self.theme_options.items(): 
            self.theme_combo.addItem(text, value)
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.temp_settings.get("theme", "dark")))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_layout.addRow("테마:", self.theme_combo)
        
        opacity_widget = QWidget()
        opacity_layout = QHBoxLayout(opacity_widget)
        opacity_layout.setContentsMargins(0,0,0,0)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(int(self.temp_settings.get("window_opacity", 0.95) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_label.setMinimumWidth(40)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)
        theme_layout.addRow("투명도:", opacity_widget)
        
        layout.addWidget(theme_group)
        layout.addSpacing(6)

        # 달력 표시 설정
        display_group = QGroupBox("달력 표시")
        display_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        display_layout = QFormLayout(display_group)
        display_layout.setVerticalSpacing(18)
        
        self.start_day_combo = QComboBox()
        self.start_day_combo.addItem("일요일", 6)
        self.start_day_combo.addItem("월요일", 0)
        self.start_day_combo.setCurrentIndex(self.start_day_combo.findData(self.temp_settings.get("start_day_of_week", 6)))
        self.start_day_combo.currentIndexChanged.connect(self.on_start_day_changed)
        display_layout.addRow("한 주의 시작:", self.start_day_combo)
        
        self.hide_weekends_checkbox = QCheckBox("주말(토, 일) 숨기기")
        self.hide_weekends_checkbox.setChecked(self.temp_settings.get("hide_weekends", False))
        self.hide_weekends_checkbox.stateChanged.connect(self.on_hide_weekends_changed)
        display_layout.addRow("", self.hide_weekends_checkbox)
        
        layout.addWidget(display_group)
        
        self.stack.addWidget(scroll_area)

    def create_notifications_page(self):
        """알림 설정 페이지"""
        scroll_area, layout = self._create_scrollable_page()
        self.nav_list.addItem(QListWidgetItem("🔔 알림"))

        # 기본 알림 설정
        basic_group = QGroupBox("기본 알림")
        basic_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setVerticalSpacing(12)
        
        self.notification_minutes_combo = QComboBox()
        minutes_options = {0: "정시", 1: "1분 전", 5: "5분 전", 10: "10분 전", 15: "15분 전", 30: "30분 전"}
        for minutes, text in minutes_options.items():
            self.notification_minutes_combo.addItem(text, minutes)
        self.notification_minutes_combo.setCurrentIndex(
            self.notification_minutes_combo.findData(self.temp_settings.get("notification_minutes", DEFAULT_NOTIFICATION_MINUTES))
        )
        self.notification_minutes_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("notification_minutes"))
        basic_layout.addRow("알림 시점:", self.notification_minutes_combo)
        
        self.notification_duration_combo = QComboBox()
        duration_options = {3: "3초", 5: "5초", 10: "10초", 0: "수동으로 닫기"}
        for seconds, text in duration_options.items():
            self.notification_duration_combo.addItem(text, seconds)
        self.notification_duration_combo.setCurrentIndex(
            self.notification_duration_combo.findData(self.temp_settings.get("notification_duration", DEFAULT_NOTIFICATION_DURATION))
        )
        self.notification_duration_combo.currentIndexChanged.connect(lambda: self._mark_as_changed("notification_duration"))
        basic_layout.addRow("표시 시간:", self.notification_duration_combo)
        
        self.notifications_checkbox = QCheckBox("알림 활성화")
        self.notifications_checkbox.setChecked(self.temp_settings.get("notifications_enabled", DEFAULT_NOTIFICATIONS_ENABLED))
        self.notifications_checkbox.toggled.connect(lambda checked: (
            self.temp_settings.update({"notifications_enabled": checked}),
            self._mark_as_changed("notifications_enabled")
        ))
        basic_layout.addRow("", self.notifications_checkbox)
        
        layout.addWidget(basic_group)
        layout.addSpacing(6)
        
        # 종일 일정 알림
        allday_group = QGroupBox("종일 일정 알림")
        allday_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        allday_layout = QFormLayout(allday_group)
        allday_layout.setVerticalSpacing(18)
        
        self.all_day_notification_time = QTimeEdit()
        default_time = QTime.fromString(self.temp_settings.get("all_day_notification_time", DEFAULT_ALL_DAY_NOTIFICATION_TIME), "hh:mm")
        self.all_day_notification_time.setTime(default_time)
        self.all_day_notification_time.timeChanged.connect(lambda: self._mark_as_changed("all_day_notification_time"))
        allday_layout.addRow("알림 시간:", self.all_day_notification_time)
        
        self.all_day_notification_checkbox = QCheckBox("종일 일정 알림 활성화")
        self.all_day_notification_checkbox.setChecked(self.temp_settings.get("all_day_notification_enabled", DEFAULT_ALL_DAY_NOTIFICATION_ENABLED))
        self.all_day_notification_checkbox.toggled.connect(lambda checked: (
            self.temp_settings.update({"all_day_notification_enabled": checked}),
            self._mark_as_changed("all_day_notification_enabled")
        ))
        allday_layout.addRow("", self.all_day_notification_checkbox)
        
        layout.addWidget(allday_group)
        
        self.stack.addWidget(scroll_area)

    def create_calendar_page(self):
        """캘린더 설정 페이지"""
        scroll_area, layout = self._create_scrollable_page()
        self.nav_list.addItem(QListWidgetItem("📅 캘린더"))
        
        # 캘린더 색상 설정
        color_group = QGroupBox("캘린더 색상 설정")
        color_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        color_layout = QVBoxLayout(color_group)
        color_layout.setSpacing(18)
        
        self.calendar_list_widget = QWidget()
        self.calendar_list_widget.setObjectName("transparent_container")
        self.calendar_list_layout = QVBoxLayout(self.calendar_list_widget)
        self.calendar_list_layout.setContentsMargins(0,0,0,0)
        self.calendar_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        color_layout.addWidget(self.calendar_list_widget)
        
        layout.addWidget(color_group)
        
        self.stack.addWidget(scroll_area)

    def create_system_page(self):
        """시스템 설정 페이지"""
        scroll_area, layout = self._create_scrollable_page()
        self.nav_list.addItem(QListWidgetItem("💻 시스템"))

        # 창 동작
        window_group = QGroupBox("창 동작")
        window_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        window_layout = QVBoxLayout(window_group)
        window_layout.setSpacing(18)
        
        self.lock_mode_checkbox = QCheckBox("잠금 모드 (드래그 및 크기 조절 비활성화)")
        self.lock_mode_checkbox.setChecked(self.temp_settings.get("lock_mode_enabled", DEFAULT_LOCK_MODE_ENABLED))
        self.lock_mode_checkbox.toggled.connect(lambda checked: (
            self.temp_settings.update({"lock_mode_enabled": checked}),
            self._mark_as_changed("lock_mode_enabled")
        ))
        window_layout.addWidget(self.lock_mode_checkbox)
        
        # 잠금 해제 키 설정 (잠금 모드 아래에 배치)
        unlock_key_layout = QHBoxLayout()
        unlock_key_layout.addSpacing(20)  # 들여쓰기
        unlock_key_label = QLabel("잠금 해제 키:")
        self.unlock_key_display = QLabel("설정되지 않음")
        self.unlock_key_button = QPushButton("설정")
        self.unlock_key_clear_button = QPushButton("해제")
        
        self.unlock_key_button.clicked.connect(self.set_unlock_key)
        self.unlock_key_clear_button.clicked.connect(self.clear_unlock_key)
        
        unlock_key_layout.addWidget(unlock_key_label)
        unlock_key_layout.addWidget(self.unlock_key_display, 1)
        unlock_key_layout.addWidget(self.unlock_key_button)
        unlock_key_layout.addWidget(self.unlock_key_clear_button)
        window_layout.addLayout(unlock_key_layout)
        self.update_unlock_key_display()
        
        layout.addWidget(window_group)
        layout.addSpacing(6)
        
        # 단축키
        hotkey_group = QGroupBox("글로벌 단축키")
        hotkey_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        hotkey_layout = QFormLayout(hotkey_group)
        hotkey_layout.setVerticalSpacing(18)
        
        # 표시/숨기기 기능이 없으므로 해당 단축키 제거
        
        # AI 단축키 추가
        ai_hotkey_widget = self.create_hotkey_input_widget("ai_add_event_hotkey")
        hotkey_layout.addRow("AI 일정 추가:", ai_hotkey_widget)
        
        layout.addWidget(hotkey_group)
        layout.addSpacing(6)
        
        # 시스템 시작
        startup_group = QGroupBox("시스템 시작")
        startup_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 18px; padding-top: 30px; padding-bottom: 36px; }")
        startup_layout = QFormLayout(startup_group)
        startup_layout.setVerticalSpacing(18)
        
        self.startup_checkbox = QCheckBox("Windows 시작 시 자동 실행")
        self.startup_checkbox.setChecked(self.temp_settings.get("start_on_boot", False))
        self.startup_checkbox.toggled.connect(lambda checked: (
            self.temp_settings.update({"start_on_boot": checked}),
            self._mark_as_changed("start_on_boot")
        ))
        startup_layout.addRow("", self.startup_checkbox)
        
        layout.addWidget(startup_group)
        
        self.stack.addWidget(scroll_area)


    def create_hotkey_input_widget(self, setting_key):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        
        display_widget = QLineEdit()
        display_widget.setReadOnly(True)
        display_widget.setPlaceholderText("단축키 없음")
        
        set_button = QPushButton("단축키 등록")
        set_button.clicked.connect(lambda: self.open_hotkey_dialog(setting_key, display_widget))
        
        clear_button = QPushButton("해제")
        clear_button.clicked.connect(lambda: self.clear_hotkey(setting_key, display_widget))

        layout.addWidget(display_widget)
        layout.addWidget(set_button)
        layout.addWidget(clear_button)
        
        hotkey = self.temp_settings.get(setting_key, "")
        display_widget.setText(hotkey)
        
        return container

    def create_single_key_input_widget(self, setting_key):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0,0,0,0)
        
        display_widget = QLineEdit()
        display_widget.setReadOnly(True)
        display_widget.setPlaceholderText("키 없음")
        
        set_button = QPushButton("키 등록")
        set_button.clicked.connect(lambda: self.open_single_key_dialog(setting_key, display_widget))
        
        clear_button = QPushButton("해제")
        clear_button.clicked.connect(lambda: self.clear_hotkey(setting_key, display_widget))

        layout.addWidget(display_widget)
        layout.addWidget(set_button)
        layout.addWidget(clear_button)
        
        key = self.temp_settings.get(setting_key, "")
        display_widget.setText(key.capitalize())
        
        return container

    def open_hotkey_dialog(self, setting_key, display_widget):
        dialog = HotkeyInputDialog(self, self.settings, self.pos())
        if dialog.exec():
            hotkey = dialog.get_hotkey()
            if not hotkey: return
            self.temp_settings[setting_key] = hotkey
            display_widget.setText(hotkey)
            self._mark_as_changed(setting_key)

    def open_single_key_dialog(self, setting_key, display_widget):
        dialog = SingleKeyInputDialog(self, self.settings, self.pos())
        if dialog.exec():
            key = dialog.get_key()
            if not key: return
            self.temp_settings[setting_key] = key
            display_widget.setText(key.capitalize())
            self._mark_as_changed(setting_key)

    def clear_hotkey(self, setting_key, display_widget):
        self.temp_settings[setting_key] = ""
        display_widget.setText("")
        self._mark_as_changed(setting_key)

    def open_api_key_dialog(self):
        dialog = APIKeyInputDialog(self, self.settings, self.pos())
        if dialog.exec():
            api_key = dialog.get_api_key()
            self.temp_settings['gemini_api_key'] = api_key
            self._mark_as_changed('gemini_api_key')
            self.update_api_key_ui()

    def reset_api_key(self):
        confirm = CustomMessageBox(self, "API 키 초기화", "정말로 API 키를 삭제하시겠습니까?", settings=self.settings)
        if confirm.exec():
            self.temp_settings['gemini_api_key'] = ""
            self._mark_as_changed('gemini_api_key')
            self.update_api_key_ui()

    def update_api_key_ui(self):
        api_key = self.temp_settings.get("gemini_api_key")
        if api_key:
            self.api_key_display.setText(f"**** **** **** {api_key[-4:]}")
            self.add_api_key_button.hide()
            self.change_api_key_button.show()
            self.reset_api_key_button.show()
        else:
            self.api_key_display.setText("등록된 키 없음")
            self.add_api_key_button.show()
            self.change_api_key_button.hide()
            self.reset_api_key_button.hide()

    def on_notifications_toggled(self, state):
        self._mark_as_changed("notifications_enabled"); is_checked = bool(state)
        self.notification_minutes_spinbox.setEnabled(is_checked); self.notification_duration_combo.setEnabled(is_checked)

    def on_all_day_notifications_toggled(self, state):
        self._mark_as_changed("all_day_notification_enabled"); is_checked = bool(state); self.all_day_notification_time_edit.setEnabled(is_checked)

    def rebuild_ui(self):
        self.update_account_status()
        self.populate_calendar_list()

    def update_account_status(self):
        if self.data_manager.auth_manager.is_logged_in():
            user_info = self.data_manager.auth_manager.get_user_info()
            self.account_status_label.setText(user_info.get('email', "정보 확인 불가")); self.account_button.setText("로그아웃")
        else:
            self.account_status_label.setText("연결되지 않음"); self.account_button.setText("로그인")

    def handle_account_button_click(self):
        if self.data_manager.auth_manager.is_logged_in(): 
            self.data_manager.auth_manager.logout()
            # 로그아웃 후 Google 캘린더만 제거하고 로컬 캘린더는 유지
            if self.data_manager.calendar_list_cache:
                from config import GOOGLE_CALENDAR_PROVIDER_NAME
                self.data_manager.calendar_list_cache = [
                    cal for cal in self.data_manager.calendar_list_cache 
                    if cal.get('provider') != GOOGLE_CALENDAR_PROVIDER_NAME
                ]
            self.update_account_status()
            self.populate_calendar_list()
        else: 
            self.data_manager.auth_manager.login()

    def populate_calendar_list(self):
        print("[DEBUG] populate_calendar_list 메서드 호출됨!")
        while self.calendar_list_layout.count():
            child = self.calendar_list_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.checkboxes.clear(); self.color_combos.clear()
        selected_calendars = self.temp_settings.get("selected_calendars", [])
        try:
            calendar_list = self.data_manager.get_all_calendars()
            if not calendar_list: 
                no_cal_label = QLabel("표시할 캘린더가 없습니다.\nGoogle 계정에 로그인하면 자동으로 캘린더 목록을 불러옵니다.")
                no_cal_label.setWordWrap(True)
                no_cal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.calendar_list_layout.addWidget(no_cal_label)
                return
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

    def on_start_day_changed(self):
        """시작요일 변경 시 실시간 미리보기"""
        self._mark_as_changed("start_day_of_week")
        start_day = self.start_day_combo.currentData()
        self.temp_settings["start_day_of_week"] = start_day
        self.start_day_changed.emit(start_day)

    def on_hide_weekends_changed(self):
        """주말표시 변경 시 실시간 미리보기"""
        self._mark_as_changed("hide_weekends")
        hide_weekends = self.hide_weekends_checkbox.isChecked()
        self.temp_settings["hide_weekends"] = hide_weekends
        self.hide_weekends_changed.emit(hide_weekends)

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
        self.temp_settings["start_day_of_week"] = self.start_day_combo.currentData()
        self.temp_settings["hide_weekends"] = self.hide_weekends_checkbox.isChecked()
        self.temp_settings["window_opacity"] = self.opacity_slider.value() / 100.0
        self.temp_settings["theme"] = self.theme_combo.currentData()
        self.temp_settings["lock_mode_enabled"] = self.lock_mode_checkbox.isChecked()
        self.temp_settings["start_on_boot"] = self.startup_checkbox.isChecked()
        # 알림 설정은 이미 각 위젯에서 temp_settings에 직접 저장되므로 별도 처리 불필요
        # (notifications_checkbox, notification_minutes_combo, notification_duration_combo 등)
        
        # 종일 일정 알림 시간만 별도 저장 (QTimeEdit)
        if hasattr(self, 'all_day_notification_time'):
            self.temp_settings["all_day_notification_time"] = self.all_day_notification_time.time().toString("HH:mm")
        
        self.original_settings.clear(); self.original_settings.update(self.temp_settings)
        
        # 설정 저장 후 1초 후 새로고침 신호 전송
        QTimer.singleShot(1000, self.refresh_requested.emit)
        
        self.done(1)
        
    def get_changed_fields(self):
        return list(self.changed_fields)

        # toggle visibility 관련 메서드들 제거됨 (기능이 존재하지 않음)

    def set_unlock_key(self):
        """잠금 해제 키 설정"""
        try:
            from custom_dialogs import SingleKeyInputDialog
            dialog = SingleKeyInputDialog(self)
            if dialog.exec() == 1:
                key = dialog.get_key()
                if key:
                    self.temp_settings["unlock_key"] = key
                    self._mark_as_changed("unlock_key")
                    self.update_unlock_key_display()
        except Exception as e:
            msg_dialog = CustomMessageBox(self, "잠금 해제 키 설정 실패", f"잠금 해제 키 설정 중 오류가 발생했습니다:\n{e}")
            msg_dialog.exec()

    def clear_unlock_key(self):
        """잠금 해제 키 해제"""
        self.temp_settings["unlock_key"] = ""
        self._mark_as_changed("unlock_key")
        self.update_unlock_key_display()

    def update_unlock_key_display(self):
        """잠금 해제 키 표시 업데이트"""
        key = self.temp_settings.get("unlock_key", "")
        self.unlock_key_display.setText(key.upper() if key else "설정되지 않음")