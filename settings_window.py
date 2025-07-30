# settings_window.py
import copy
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QHBoxLayout,
                             QColorDialog, QComboBox, QSlider, QSizePolicy,
                             QListWidget, QStackedWidget, QListWidgetItem, QFormLayout)
from PyQt6.QtGui import QColor, QPixmap, QIcon, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from custom_dialogs import BaseDialog
from config import DEFAULT_SYNC_INTERVAL

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
        
        # 원본 설정을 보존하고, 변경사항은 복사본에 임시 저장합니다.
        self.original_settings = settings
        self.temp_settings = copy.deepcopy(settings)

        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumSize(750, 550)
        
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
        self.nav_list.setFixedWidth(180)
        self.nav_list.setFont(QFont("Malgun Gothic", 11))
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
        self.create_account_page()
        self.create_calendars_page()
        self.create_appearance_page()
        self.create_general_page()
        
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)
        self.data_manager.calendar_list_changed.connect(self.rebuild_ui)
        self.rebuild_ui()
        self.set_stylesheet()

    def set_stylesheet(self):
        is_dark = self.temp_settings.get("theme", "dark") == "dark"
        margin_color = "rgb(30, 30, 30)" if is_dark else "#FAFAFA"
        content_bg = "#3C3C3C" if is_dark else "#FFFFFF"
        nav_bg = "#2E2E2E" if is_dark else "#F5F5F5"
        nav_border = "#444" if is_dark else "#DCDCDC"
        nav_item_selected_bg = "#0078D7"
        nav_item_selected_fg = "#FFFFFF"
        nav_item_hover_bg = "#4A4A4A" if is_dark else "#E0E0E0"
        bottom_bg = nav_bg
        section_title_fg = "#E0E0E0" if is_dark else "#111111"
        qss = f"""
            QWidget#settings_margin_background {{ background-color: {margin_color}; border-radius: 12px; }}
            QWidget#settings_content_background {{ border-radius: 8px; }}
            QListWidget#settings_nav {{ background-color: {nav_bg}; border-right: 1px solid {nav_border}; outline: 0px; border-top-left-radius: 8px; border-bottom-left-radius: 8px; }}
            QListWidget#settings_nav::item {{ padding: 15px; border: none; }}
            QListWidget#settings_nav::item:selected {{ background-color: {nav_item_selected_bg}; color: {nav_item_selected_fg}; font-weight: bold; }}
            QListWidget#settings_nav::item:hover:!selected {{ background-color: {nav_item_hover_bg}; }}
            QWidget#settings_page {{ background-color: {content_bg}; border-top-right-radius: 8px; }}
            QWidget#bottom_container {{ background-color: {bottom_bg}; border-top: 1px solid {nav_border}; border-bottom-right-radius: 8px; }}
            QLabel#section_title {{ font-size: 18px; font-weight: bold; padding-top: 10px; padding-bottom: 15px; color: {section_title_fg}; }}
        """
        self.setStyleSheet(qss)

    def _create_section_label(self, text):
        label = QLabel(text)
        label.setObjectName("section_title")
        return label

    def create_account_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setContentsMargins(25, 15, 25, 25)
        self.nav_list.addItem(QListWidgetItem("👤 계정"))
        layout.addWidget(self._create_section_label("Google 계정 연동"))
        account_layout = QHBoxLayout(); self.account_status_label = QLabel("상태 확인 중..."); self.account_button = QPushButton("로그인")
        account_layout.addWidget(self.account_status_label, 1); account_layout.addWidget(self.account_button)
        layout.addLayout(account_layout)
        self.account_button.clicked.connect(self.handle_account_button_click)
        self.stack.addWidget(page)
    
    def create_calendars_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setContentsMargins(25, 15, 25, 25)
        self.nav_list.addItem(QListWidgetItem("🗓️ 캘린더"))
        layout.addWidget(self._create_section_label("캘린더 표시 및 색상 설정"))
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        layout.addWidget(scroll_area)
        self.calendar_list_widget = QWidget(); self.calendar_list_layout = QVBoxLayout(self.calendar_list_widget)
        self.calendar_list_layout.setContentsMargins(0,0,0,0); self.calendar_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.calendar_list_widget)
        self.stack.addWidget(page)

    def create_appearance_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop); layout.setContentsMargins(25, 15, 25, 25)
        self.nav_list.addItem(QListWidgetItem("🎨 화면"))
        
        layout.addWidget(self._create_section_label("테마"))
        form_layout_theme = QFormLayout(); self.theme_combo = QComboBox()
        self.theme_options = { "dark": "어두운 테마", "light": "밝은 테마" }
        for value, text in self.theme_options.items(): self.theme_combo.addItem(text, value)
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(self.temp_settings.get("theme", "dark")))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        form_layout_theme.addRow("테마 선택:", self.theme_combo); layout.addLayout(form_layout_theme)
        
        layout.addWidget(self._create_section_label("투명도"))
        form_layout_opacity = QFormLayout(); opacity_widget = QWidget(); opacity_layout = QHBoxLayout(opacity_widget)
        opacity_layout.setContentsMargins(0,0,0,0); self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100); self.opacity_slider.setValue(int(self.temp_settings.get("window_opacity", 0.95) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%"); self.opacity_label.setMinimumWidth(40)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider); opacity_layout.addWidget(self.opacity_label)
        form_layout_opacity.addRow("전체 투명도:", opacity_widget); layout.addLayout(form_layout_opacity)

        layout.addWidget(self._create_section_label("달력 표시"))
        form_layout_display = QFormLayout(); self.start_day_combo = QComboBox()
        self.start_day_combo.addItem("일요일", 6); self.start_day_combo.addItem("월요일", 0)
        self.start_day_combo.setCurrentIndex(self.start_day_combo.findData(self.temp_settings.get("start_day_of_week", 6)))
        form_layout_display.addRow("한 주의 시작:", self.start_day_combo)
        self.hide_weekends_checkbox = QCheckBox("주말(토, 일) 숨기기")
        self.hide_weekends_checkbox.setChecked(self.temp_settings.get("hide_weekends", False))
        form_layout_display.addRow(self.hide_weekends_checkbox)
        layout.addLayout(form_layout_display)
        self.stack.addWidget(page)

    def create_general_page(self):
        page = QWidget(); page.setObjectName("settings_page"); layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 15, 25, 25); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_list.addItem(QListWidgetItem("⚙️ 일반"))
        layout.addWidget(self._create_section_label("데이터 소스"))
        self.local_calendar_checkbox = QCheckBox("로컬 캘린더 사용 (calendar.db)")
        self.local_calendar_checkbox.setChecked(self.temp_settings.get("use_local_calendar", True))
        layout.addWidget(self.local_calendar_checkbox)
        layout.addWidget(self._create_section_label("동기화"))
        form_layout_sync = QFormLayout(); self.sync_interval_combo = QComboBox()
        self.sync_options = { 0: "사용 안 함", 1: "1분", 5: "5분", 15: "15분", 30: "30분", 60: "1시간" }
        for minutes, text in self.sync_options.items(): self.sync_interval_combo.addItem(text, minutes)
        self.sync_interval_combo.setCurrentIndex(self.sync_interval_combo.findData(self.temp_settings.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL)))
        form_layout_sync.addRow("자동 동기화 주기:", self.sync_interval_combo)
        layout.addLayout(form_layout_sync)
        self.stack.addWidget(page)

    def rebuild_ui(self):
        self.update_account_status()
        self.populate_calendar_list()

    def update_account_status(self):
        if self.data_manager.auth_manager.is_logged_in():
            user_info = self.data_manager.auth_manager.get_user_info()
            self.account_status_label.setText(user_info.get('email', "정보 확인 불가"))
            self.account_button.setText("로그아웃")
        else:
            self.account_status_label.setText("연결되지 않음")
            self.account_button.setText("로그인")

    def handle_account_button_click(self):
        if self.data_manager.auth_manager.is_logged_in(): self.data_manager.auth_manager.logout()
        else: self.data_manager.auth_manager.login()

    def populate_calendar_list(self):
        while self.calendar_list_layout.count():
            child = self.calendar_list_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.checkboxes.clear(); self.color_combos.clear()
        selected_calendars = self.temp_settings.get("selected_calendars", [])
        try:
            calendar_list = self.data_manager.get_all_calendars()
            if not calendar_list:
                 self.calendar_list_layout.addWidget(QLabel("표시할 캘린더가 없습니다.\nGoogle 계정에 로그인하여 캘린더를 불러오세요."))
                 return
            if not selected_calendars and calendar_list:
                primary_cal = next((cal for cal in calendar_list if cal.get('primary')), calendar_list[0])
                selected_calendars = [primary_cal['id']]
            for calendar in calendar_list:
                cal_id = calendar["id"]; row_layout = QHBoxLayout(); checkbox = QCheckBox()
                checkbox.setChecked(cal_id in selected_calendars); self.checkboxes[cal_id] = checkbox
                color_combo = self.create_color_combo(cal_id, calendar['backgroundColor']); self.color_combos[cal_id] = color_combo
                color_combo.activated.connect(lambda idx, c_id=cal_id: self.handle_color_change(c_id, idx))
                name_label = QLabel(calendar["summary"]); name_label.setWordWrap(True)
                row_layout.addWidget(checkbox); row_layout.addWidget(color_combo); row_layout.addWidget(name_label, 1)
                self.calendar_list_layout.addLayout(row_layout)
        except Exception as e:
            self.calendar_list_layout.addWidget(QLabel(f"캘린더 목록 로드 실패:\n{e}"))

    def on_opacity_changed(self, value):
        self.temp_settings["window_opacity"] = value / 100.0
        self.opacity_label.setText(f"{value}%")
        self.transparency_changed.emit(self.temp_settings["window_opacity"])

    def on_theme_changed(self, text):
        selected_theme_name = self.theme_combo.currentData()
        self.temp_settings["theme"] = selected_theme_name
        self.theme_changed.emit(selected_theme_name)
        self.set_stylesheet()

    def create_color_icon(self, color_hex):
        pixmap = QPixmap(16, 16); pixmap.fill(QColor(color_hex)); return QIcon(pixmap)

    def create_color_combo(self, cal_id, default_color):
        combo = QComboBox(); combo.setIconSize(QSize(16, 16)); combo.setMinimumWidth(20); combo.setMaxVisibleItems(5)
        current_color = self.temp_settings.get("calendar_colors", {}).get(cal_id, default_color)
        for color in PASTEL_COLORS["기본"]: combo.addItem(self.create_color_icon(color), "", userData=color)
        if current_color not in PASTEL_COLORS["기본"]: combo.insertItem(0, self.create_color_icon(current_color), "", userData=current_color)
        combo.addItem(CUSTOM_COLOR_TEXT)
        index = combo.findData(current_color)
        if index != -1: combo.setCurrentIndex(index)
        return combo

    def handle_color_change(self, cal_id, index):
        combo = self.color_combos[cal_id]
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
        self.temp_settings["use_local_calendar"] = self.local_calendar_checkbox.isChecked()
        self.temp_settings["selected_calendars"] = [cal_id for cal_id, cb in self.checkboxes.items() if cb.isChecked()]
        self.temp_settings.setdefault("calendar_colors", {}).update({cal_id: combo.currentData() for cal_id, combo in self.color_combos.items() if combo.currentData()})
        if "calendar_emojis" in self.temp_settings: del self.temp_settings["calendar_emojis"]
        self.temp_settings["sync_interval_minutes"] = self.sync_interval_combo.currentData()
        self.temp_settings["start_day_of_week"] = self.start_day_combo.currentData()
        self.temp_settings["hide_weekends"] = self.hide_weekends_checkbox.isChecked()
        self.temp_settings["window_opacity"] = self.opacity_slider.value() / 100.0
        self.temp_settings["theme"] = self.theme_combo.currentData()
        
        self.original_settings.clear()
        self.original_settings.update(self.temp_settings)
        self.accept()
