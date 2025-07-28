from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QHBoxLayout,
                             QColorDialog, QComboBox, QSlider)
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal

from custom_dialogs import BaseDialog # BaseDialog import
from config import DEFAULT_SYNC_INTERVAL

# --- 미리 정의된 상수들은 그대로 둡니다. ---
PASTEL_COLORS = {
    "기본": ["#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff", "#e4e4e4", "#f1f1f1"]
}
EMOJI_LIST = ["없음", "💻", "😊", "🎂", "💪", "✈️", "🗓️", "❤️", "🎓", "🎉", "🔥", "⚽"]
CUSTOM_COLOR_TEXT = "사용자 지정..."

class SettingsWindow(BaseDialog):
    transparency_changed = pyqtSignal(float)
    theme_changed = pyqtSignal(str) # 테마 변경 신호 추가

    # --- ▼▼▼ __init__ 메서드의 파라미터가 변경되었습니다. ▼▼▼ ---
    def __init__(self, data_manager, settings, parent=None, pos=None):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.data_manager = data_manager # service 대신 data_manager를 저장합니다.
        # self.settings는 BaseDialog에서 처리
        
        self.use_local_calendar = self.settings.get("use_local_calendar", True)
        self.selected_calendars = self.settings.get("selected_calendars", [])
        self.calendar_colors = self.settings.get("calendar_colors", {}).copy()
        self.calendar_emojis = self.settings.get("calendar_emojis", {}).copy()

        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(500) # 최소 높이 추가
        
        # 다이얼로그 자체에 메인 레이아웃을 설정합니다.
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # 여백 제거

        # 배경 위젯 추가 (둥근 모서리 및 배경색 적용을 위해)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)

        # 실제 콘텐츠 레이아웃
        content_layout = QVBoxLayout(background_widget)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_layout.addWidget(scroll_area)
        
        scroll_content = QWidget()
        self.layout = QVBoxLayout(scroll_content)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(scroll_content)

        self.local_calendar_checkbox = QCheckBox("로컬 캘린더 사용 (calendar.db)")
        self.local_calendar_checkbox.setChecked(self.use_local_calendar)
        self.layout.addWidget(self.local_calendar_checkbox)
        self.layout.addWidget(QLabel("-" * 50))

        # --- ▼▼▼ [신규] Google 계정 연동 UI 추가 ▼▼▼ ---
        self.layout.addWidget(QLabel("Google 계정 연동:"))
        account_layout = QHBoxLayout()
        self.account_status_label = QLabel("상태 확인 중...")
        self.account_button = QPushButton("로그인")
        account_layout.addWidget(self.account_status_label, 1)
        account_layout.addWidget(self.account_button)
        self.layout.addLayout(account_layout)
        self.account_button.clicked.connect(self.handle_account_button_click)
        # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

        self.layout.addWidget(QLabel("-" * 50))
        self.layout.addWidget(QLabel("표시할 캘린더, 색상, 이모티콘을 설정하세요:"))

        self.checkboxes = {}
        self.color_combos = {}
        self.emoji_combos = {}

        # --- 동기화 설정 UI 추가 ---
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
        current_text = self.sync_options.get(current_interval, "5분")
        self.sync_interval_combo.setCurrentText(current_text)

        sync_layout.addWidget(self.sync_interval_combo)
        self.layout.addLayout(sync_layout)

        # --- 시작 요일 설정 UI 추가 ---
        self.layout.addWidget(QLabel("-" * 50))
        start_day_layout = QHBoxLayout()
        start_day_layout.addWidget(QLabel("한 주의 시작 요일:"))
        self.start_day_combo = QComboBox()
        self.start_day_options = {
            6: "일요일", # calendar.SUNDAY
            0: "월요일"  # calendar.MONDAY
        }
        for value, text in self.start_day_options.items():
            self.start_day_combo.addItem(text, value)
        
        current_start_day = self.settings.get("start_day_of_week", 6) # 기본값 일요일
        self.start_day_combo.setCurrentText(self.start_day_options.get(current_start_day, "일요일"))

        start_day_layout.addWidget(self.start_day_combo)
        self.layout.addLayout(start_day_layout)

        # --- 테마 설정 UI 추가 ---
        self.layout.addWidget(QLabel("-" * 50))
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("테마 설정:"))
        self.theme_combo = QComboBox()
        self.theme_options = {
            "dark": "어두운 테마",
            "light": "밝은 테마"
        }
        for value, text in self.theme_options.items():
            self.theme_combo.addItem(text, value)
        
        current_theme = self.settings.get("theme", "dark")
        self.theme_combo.setCurrentText(self.theme_options.get(current_theme, "어두운 테마"))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)

        theme_layout.addWidget(self.theme_combo)
        self.layout.addLayout(theme_layout)
        # --- 여기까지 테마 설정 UI 추가 ---
        
        # --- 투명도 설정 UI 추가 ---
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
        # --- 여기까지 투명도 설정 UI 추가 ---

        self.layout.addWidget(QLabel("-" * 50))

        self.calendar_list_widget = QWidget() # 캘린더 목록을 담을 위젯
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

        # DataManager의 신호를 UI 새로고침에 연결
        self.data_manager.calendar_list_changed.connect(self.rebuild_ui)
        # 초기 UI 빌드
        self.rebuild_ui()

    def rebuild_ui(self):
        """인증 상태 및 캘린더 목록에 따라 UI를 다시 빌드합니다."""
        self.update_account_status()
        self.populate_calendar_list()

    def update_account_status(self):
        """Google 계정 연동 상태를 UI에 업데이트합니다."""
        if self.data_manager.auth_manager.is_logged_in():
            email = self.data_manager.auth_manager.get_user_info()
            if email:
                self.account_status_label.setText(f"{email} (연결됨)")
            else:
                self.account_status_label.setText("연결됨 (정보 확인 불가)")
            self.account_button.setText("로그아웃")
        else:
            self.account_status_label.setText("연결되지 않음")
            self.account_button.setText("로그인")

    def handle_account_button_click(self):
        """로그인/로그아웃 버튼 클릭을 처리합니다."""
        if self.data_manager.auth_manager.is_logged_in():
            self.data_manager.auth_manager.logout()
        else:
            self.data_manager.auth_manager.login()
        # auth_state_changed 신호가 DataManager를 통해 rebuild_ui를 호출할 것임

    def populate_calendar_list(self):
        """캘린더 목록 UI를 다시 만듭니다."""
        # 기존 위젯들 삭제
        while self.calendar_list_layout.count():
            child = self.calendar_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.checkboxes = {}
        self.color_combos = {}
        self.emoji_combos = {}

        try:
            calendar_list = self.data_manager.get_all_calendars()
            
            if not calendar_list:
                 self.calendar_list_layout.addWidget(QLabel("표시할 캘린더가 없습니다."))
            
            # 로그인 안했을 때 selected_calendars에 구글 캘린더가 남아있는 경우 필터링
            if not self.data_manager.auth_manager.is_logged_in():
                local_cal_id = next((c['id'] for c in calendar_list if c['provider'] == 'LocalCalendarProvider'), None)
                self.selected_calendars = [local_cal_id] if local_cal_id else []

            if not self.selected_calendars and calendar_list:
                primary_cal_id = next((cal['id'] for cal in calendar_list if cal.get('primary')), None)
                if primary_cal_id: self.selected_calendars = [primary_cal_id]

            for calendar in calendar_list:
                cal_id = calendar["id"]
                row_layout = QHBoxLayout()

                color_combo = self.create_color_combo(cal_id, calendar['backgroundColor'])
                self.color_combos[cal_id] = color_combo
                color_combo.activated.connect(lambda _, c_id=cal_id: self.handle_color_change(c_id))

                name_label = QLabel(calendar["summary"])
                name_label.setWordWrap(True)

                emoji_combo = QComboBox()
                for emoji in EMOJI_LIST: emoji_combo.addItem(emoji)
                current_emoji = self.calendar_emojis.get(cal_id, "없음")
                if current_emoji: emoji_combo.setCurrentText(current_emoji)
                self.emoji_combos[cal_id] = emoji_combo
                
                checkbox = QCheckBox()
                checkbox.setChecked(cal_id in self.selected_calendars)
                self.checkboxes[cal_id] = checkbox
                
                row_layout.addWidget(color_combo)
                row_layout.addWidget(name_label, 1)
                row_layout.addWidget(emoji_combo)
                self.calendar_list_layout.addLayout(row_layout)

        except Exception as e:
            label = QLabel(f"캘린더 목록 로드 실패:\n{e}")
            label.setWordWrap(True)
            self.calendar_list_layout.addWidget(label)

    def on_opacity_changed(self, value):
        """슬라이더 값이 변경될 때 호출됩니다."""
        main_opacity = value / 100.0
        self.opacity_label.setText(f"{value}%")
        
        self.transparency_changed.emit(main_opacity)
        
        dialog_opacity = main_opacity + (1 - main_opacity) * 0.85
        self.setWindowOpacity(dialog_opacity)

    def on_theme_changed(self, text):
        """테마 콤보박스 값이 변경될 때 호출됩니다."""
        selected_theme_name = self.theme_combo.currentData()
        self.theme_changed.emit(selected_theme_name)

    # create_color_icon, create_color_combo, handle_color_change, save_and_close 메서드는 변경사항 없습니다.
    def create_color_icon(self, color_hex):
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color_hex))
        return QIcon(pixmap)
    def create_color_combo(self, cal_id, default_color):
        combo = QComboBox()
        current_color = self.calendar_colors.get(cal_id, default_color)
        if current_color not in PASTEL_COLORS["기본"]:
            combo.addItem(self.create_color_icon(current_color), current_color)
        for color in PASTEL_COLORS["기본"]:
            combo.addItem(self.create_color_icon(color), color)
        combo.addItem(CUSTOM_COLOR_TEXT)
        combo.setCurrentText(current_color)
        return combo
    def handle_color_change(self, cal_id):
        combo = self.color_combos[cal_id]
        if combo.currentText() == CUSTOM_COLOR_TEXT:
            current_color = QColor(self.calendar_colors.get(cal_id, "#FFFFFF"))
            new_color = QColorDialog.getColor(current_color, self, "색상 선택")
            if new_color.isValid():
                hex_color = new_color.name()
                if combo.findText(hex_color) == -1:
                    combo.insertItem(0, self.create_color_icon(hex_color), hex_color)
                combo.setCurrentText(hex_color)
    def save_and_close(self):
        self.settings["use_local_calendar"] = self.local_calendar_checkbox.isChecked()
        self.settings["selected_calendars"] = [cal_id for cal_id, cb in self.checkboxes.items() if cb.isChecked()]
        for cal_id, combo in self.color_combos.items():
            self.calendar_colors[cal_id] = combo.currentText()
        self.settings["calendar_colors"] = self.calendar_colors
        for cal_id, combo in self.emoji_combos.items():
            selected_emoji = combo.currentText()
            self.calendar_emojis[cal_id] = selected_emoji if selected_emoji != "없음" else ""
        self.settings["calendar_emojis"] = self.calendar_emojis
        
        # 동기화 주기 설정 저장
        selected_interval_minutes = self.sync_interval_combo.currentData()
        self.settings["sync_interval_minutes"] = selected_interval_minutes

        # 투명도 설정 저장
        self.settings["window_opacity"] = self.opacity_slider.value() / 100.0

        # 테마 설정 저장
        self.settings["theme"] = self.theme_combo.currentData()

        self.accept()