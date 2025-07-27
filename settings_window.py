from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QScrollArea, QWidget, QHBoxLayout,
                             QColorDialog, QComboBox)
from PyQt6.QtGui import QColor, QPixmap, QIcon
from PyQt6.QtCore import Qt
from config import DEFAULT_SYNC_INTERVAL

# --- 미리 정의된 상수들은 그대로 둡니다. ---
PASTEL_COLORS = {
    "기본": ["#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff", "#e4e4e4", "#f1f1f1"]
}
EMOJI_LIST = ["없음", "💻", "😊", "🎂", "💪", "✈️", "🗓️", "❤️", "🎓", "🎉", "🔥", "⚽"]
CUSTOM_COLOR_TEXT = "사용자 지정..."

class SettingsWindow(QDialog):
    # --- ▼▼▼ __init__ 메서드의 파라미터가 변경되었습니다. ▼▼▼ ---
    def __init__(self, data_manager, settings, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager # service 대신 data_manager를 저장합니다.
        self.settings = settings
        
        self.use_local_calendar = self.settings.get("use_local_calendar", True)
        self.selected_calendars = self.settings.get("selected_calendars", [])
        self.calendar_colors = self.settings.get("calendar_colors", {}).copy()
        self.calendar_emojis = self.settings.get("calendar_emojis", {}).copy()
        self.oldPos = None # 창 드래그를 위한 변수 초기화

        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(500) # 최소 높이 추가
        
        # --- ▼▼▼ 프레임리스 윈도우 설정 추가 ▼▼▼ ---
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 다이얼로그 자체에 메인 레이아웃을 설정합니다.
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # 여백 제거

        # 배경 위젯 추가 (둥근 모서리 및 배경색 적용을 위해)
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        # 스타일시트에서 QDialog의 배경이 아닌, 이 위젯의 배경을 제어하도록 변경할 수 있습니다.
        # background_widget.setStyleSheet("background-color: #353535; border-radius: 10px;")
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
        self.layout.addWidget(QLabel("-" * 50)) # 구분선 추가

        self.layout.addWidget(QLabel("표시할 캘린더, 색상, 이모티콘을 설정하세요:"))

        self.checkboxes = {}
        self.color_combos = {}
        self.emoji_combos = {}

        # --- 동기화 설정 UI 추가 ---
        self.layout.addWidget(QLabel("-" * 50))
        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("자동 동기화 주기:"))
        self.sync_interval_combo = QComboBox()
        # (값, 표시 텍스트) 쌍으로 저장
        self.sync_options = {
            0: "사용 안 함",
            1: "1분",
            5: "5분",
            15: "15분",
            30: "30분",
            60: "1시간"
        }
        for minutes, text in self.sync_options.items():
            self.sync_interval_combo.addItem(text, minutes)
        
        # 현재 설정값 불러오기
        current_interval = self.settings.get("sync_interval_minutes", DEFAULT_SYNC_INTERVAL) # 기본값 5분
        current_text = self.sync_options.get(current_interval, "5분")
        self.sync_interval_combo.setCurrentText(current_text)

        sync_layout.addWidget(self.sync_interval_combo)
        self.layout.addLayout(sync_layout)
        self.layout.addWidget(QLabel("-" * 50))
        # --- 여기까지 동기화 설정 UI 추가 ---

        try:
            # --- ▼▼▼ 캘린더 목록을 가져오는 방식이 변경되었습니다. ▼▼▼ ---
            calendar_list = self.data_manager.get_all_calendars()
            
            if not calendar_list and self.data_manager.providers:
                 self.layout.addWidget(QLabel("Google 계정에 연결되었으나\n캘린더를 불러오지 못했습니다."))
            elif not self.data_manager.providers:
                 self.layout.addWidget(QLabel("Google 계정이 연결되지 않았습니다."))
            
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
                row_layout.addWidget(checkbox)
                self.layout.addLayout(row_layout)

        except Exception as e:
            self.layout.addWidget(QLabel(f"캘린더 목록 로드 실패:\n{e}"))

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject) # reject()는 창을 닫고 변경사항을 버립니다.
        button_layout.addWidget(self.cancel_button)

        content_layout.addLayout(button_layout)

    # --- ▼▼▼ 창 드래그 이동을 위한 이벤트 핸들러 추가 ▼▼▼ ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.oldPos = None
    # --- ▲▲▲ 여기까지 추가 ▲▲▲ ---

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

        self.accept()