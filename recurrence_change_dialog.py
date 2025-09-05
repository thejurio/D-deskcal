# recurrence_change_dialog.py
"""
반복 일정 규칙 변경 시 사용자 선택 다이얼로그
"""

import logging
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton, QButtonGroup, QWidget
from PyQt6.QtCore import Qt
from custom_dialogs import BaseDialog

logger = logging.getLogger(__name__)

class RecurrenceChangeDialog(BaseDialog):
    """반복 일정 규칙 변경 시 사용자 선택을 받는 다이얼로그"""
    
    def __init__(self, parent=None, settings=None, pos=None, change_type="modify"):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.change_type = change_type  # "modify", "to_single", "to_recurring"
        self.selected_option = None
        
        self.setWindowTitle("반복 일정 변경")
        self.setMinimumWidth(400)
        
        self.initUI()
        
    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Background widget
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 제목과 설명
        if self.change_type == "modify":
            title_text = "반복 일정 규칙 변경"
            desc_text = "이 일정의 반복 규칙을 변경하려고 합니다.\n어떻게 적용하시겠습니까?"
        elif self.change_type == "to_single":
            title_text = "반복 일정을 단일 일정으로 변경"
            desc_text = "이 반복 일정을 일반 일정으로 변경하려고 합니다.\n어떻게 적용하시겠습니까?"
        elif self.change_type == "to_recurring":
            title_text = "일반 일정을 반복 일정으로 변경"
            desc_text = "이 일정에 반복 규칙을 추가하려고 합니다.\n계속하시겠습니까?"
        else:
            title_text = "반복 일정 변경"
            desc_text = "반복 일정을 변경하려고 합니다."
        
        # 제목
        title_label = QLabel(title_text)
        title_label.setObjectName("dialog_title")
        layout.addWidget(title_label)
        
        # 설명
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setObjectName("dialog_description")
        layout.addWidget(desc_label)
        
        # 선택 옵션들
        self.button_group = QButtonGroup()
        
        if self.change_type == "to_recurring":
            # 단일 → 반복: 확인만 필요
            self.create_simple_confirm_ui(layout)
        else:
            # 반복 규칙 변경 or 반복 → 단일: 이후/전체 선택 필요
            self.create_option_selection_UI(layout)
        
        # 버튼들
        self.create_buttons(layout)
        
    def create_simple_confirm_UI(self, layout):
        """단일 → 반복 변환 시 간단한 확인 UI"""
        confirm_label = QLabel("새로운 반복 일정이 생성됩니다.")
        confirm_label.setObjectName("dialog_info")
        layout.addWidget(confirm_label)
        
        # 기본값으로 'all' 설정
        self.selected_option = 'all'
        
    def create_option_selection_UI(self, layout):
        """반복 규칙 변경 시 선택 옵션 UI"""
        
        # 이후 모든 일정 변경
        self.future_radio = QRadioButton("이 일정 이후의 모든 일정 변경")
        self.future_radio.setObjectName("radio_option")
        self.button_group.addButton(self.future_radio, 0)
        layout.addWidget(self.future_radio)
        
        future_desc = QLabel("   현재 선택한 일정부터 이후의 모든 반복 일정이 변경됩니다.")
        future_desc.setObjectName("radio_description")
        layout.addWidget(future_desc)
        
        layout.addSpacing(10)
        
        # 모든 일정 변경
        self.all_radio = QRadioButton("모든 반복 일정 변경")
        self.all_radio.setObjectName("radio_option")
        self.button_group.addButton(self.all_radio, 1)
        layout.addWidget(self.all_radio)
        
        all_desc = QLabel("   처음부터 끝까지 모든 반복 일정이 변경됩니다.")
        all_desc.setObjectName("radio_description")
        layout.addWidget(all_desc)
        
        # 기본값: 이후 모든 일정
        self.future_radio.setChecked(True)
        
    def create_buttons(self, layout):
        """확인/취소 버튼 생성"""
        layout.addSpacing(10)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        self.ok_button = QPushButton("확인")
        self.cancel_button = QPushButton("취소")
        
        self.ok_button.setObjectName("primary_button")
        self.cancel_button.setObjectName("secondary_button")
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 버튼 연결
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
    def accept(self):
        """확인 버튼 클릭 시 선택된 옵션 저장"""
        if self.change_type == "to_recurring":
            self.selected_option = 'all'
        else:
            checked_button = self.button_group.checkedButton()
            if checked_button:
                button_id = self.button_group.id(checked_button)
                if button_id == 0:  # future_radio
                    self.selected_option = 'future'
                elif button_id == 1:  # all_radio
                    self.selected_option = 'all'
            else:
                self.selected_option = 'future'  # 기본값
        
        logger.info(f"RecurrenceChangeDialog: 선택된 옵션 = {self.selected_option}")
        super().accept()
        
    def get_selected_option(self):
        """선택된 옵션 반환"""
        return self.selected_option

class RecurrenceConversionDialog(BaseDialog):
    """반복 일정 변환 전용 다이얼로그"""
    
    def __init__(self, parent=None, settings=None, pos=None, 
                 from_recurring=True, event_title=""):
        super().__init__(parent=parent, settings=settings, pos=pos)
        self.from_recurring = from_recurring
        self.event_title = event_title
        self.selected_option = None
        
        title = "반복 일정 변경" if from_recurring else "반복 일정 추가"
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        
        self.initUI()
        
    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        background_widget = QWidget()
        background_widget.setObjectName("dialog_background")
        main_layout.addWidget(background_widget)
        
        layout = QVBoxLayout(background_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        if self.from_recurring:
            # 반복 → 단일
            title_text = f"'{self.event_title}' 반복 일정 변경"
            desc_text = "이 반복 일정을 일반 일정으로 변경하려고 합니다."
            
            title_label = QLabel(title_text)
            title_label.setObjectName("dialog_title")
            layout.addWidget(title_label)
            
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            
            # 선택 옵션
            self.button_group = QButtonGroup()
            
            # 이 일정만 변경
            self.instance_radio = QRadioButton("이 일정만 일반 일정으로 변경")
            self.button_group.addButton(self.instance_radio, 0)
            layout.addWidget(self.instance_radio)
            
            instance_desc = QLabel("   현재 선택한 일정만 반복에서 제외하고 일반 일정으로 변경합니다.")
            instance_desc.setObjectName("radio_description")
            layout.addWidget(instance_desc)
            
            layout.addSpacing(5)
            
            # 이후 모든 일정 변경
            self.future_radio = QRadioButton("이후 모든 일정을 일반 일정으로 변경")
            self.button_group.addButton(self.future_radio, 1)
            layout.addWidget(self.future_radio)
            
            future_desc = QLabel("   현재 일정부터 이후의 모든 반복을 중단하고 일반 일정으로 변경합니다.")
            future_desc.setObjectName("radio_description")
            layout.addWidget(future_desc)
            
            layout.addSpacing(5)
            
            # 모든 일정 변경
            self.all_radio = QRadioButton("모든 반복 일정을 일반 일정으로 변경")
            self.button_group.addButton(self.all_radio, 2)
            layout.addWidget(self.all_radio)
            
            all_desc = QLabel("   전체 반복 일정을 삭제하고 하나의 일반 일정으로 변경합니다.")
            all_desc.setObjectName("radio_description")
            layout.addWidget(all_desc)
            
            # 기본값: 이 일정만
            self.instance_radio.setChecked(True)
            
        else:
            # 단일 → 반복
            title_text = f"'{self.event_title}' 반복 일정 추가"
            desc_text = "이 일정에 반복 규칙을 추가하여 반복 일정으로 변경합니다.\n계속하시겠습니까?"
            
            title_label = QLabel(title_text)
            title_label.setObjectName("dialog_title")
            layout.addWidget(title_label)
            
            desc_label = QLabel(desc_text)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            
            info_label = QLabel("기존 일정이 반복 일정으로 변환됩니다.")
            info_label.setObjectName("dialog_info")
            layout.addWidget(info_label)
            
            # 자동으로 'all' 선택
            self.selected_option = 'all'
            
        # 버튼들
        layout.addSpacing(15)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        self.ok_button = QPushButton("확인")
        self.cancel_button = QPushButton("취소")
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
    def accept(self):
        if self.from_recurring:
            checked_button = self.button_group.checkedButton()
            if checked_button:
                button_id = self.button_group.id(checked_button)
                if button_id == 0:  # instance
                    self.selected_option = 'instance'
                elif button_id == 1:  # future
                    self.selected_option = 'future'
                elif button_id == 2:  # all
                    self.selected_option = 'all'
            else:
                self.selected_option = 'instance'  # 기본값
        else:
            self.selected_option = 'all'
            
        logger.info(f"RecurrenceConversionDialog: 선택된 옵션 = {self.selected_option}")
        super().accept()
        
    def get_selected_option(self):
        return self.selected_option