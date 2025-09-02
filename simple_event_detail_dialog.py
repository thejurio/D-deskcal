# simple_event_detail_dialog.py
"""
간단하고 확실하게 작동하는 이벤트 상세보기 다이얼로그
BaseDialog 문제를 해결하기 위해 QDialog 직접 상속
"""

import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QFrame, QMessageBox, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

class SimpleEventDetailDialog(QDialog):
    """간단하고 확실한 이벤트 상세보기 다이얼로그"""
    
    # 시그널 정의
    event_edited = pyqtSignal(dict)
    event_deleted = pyqtSignal(str)
    
    def __init__(self, event_data, data_manager, main_widget, parent=None):
        super().__init__(parent)
        
        print(f"[DEBUG] SimpleEventDetailDialog 초기화 시작")
        
        self.setWindowTitle("일정 상세보기")
        self.setModal(True)
        # 창 크기를 70%로 조정 (원래 600 → 420)
        self.setFixedSize(420, 500)
        
        # 창 제목표시줄 숨기기 + 항상 위에 표시
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        self.event_data = event_data
        self.data_manager = data_manager
        self.main_widget = main_widget
        self.original_event_id = event_data.get('id')
        
        # 마우스 드래그를 위한 변수 초기화
        self.oldPos = None
        
        # 다크모드 확인
        self.is_dark_mode = main_widget.settings.get('dark_mode', False) if main_widget and hasattr(main_widget, 'settings') else False
        
        print(f"[DEBUG] 다크모드: {self.is_dark_mode}")
        print(f"[DEBUG] 현재 테마: {'dark' if self.is_dark_mode else 'light'}")
        
        self.init_ui()
        self.load_event_data()
        
        # 저장된 위치로 창을 이동 (UI 초기화 후에)
        self.restore_position()
        
        print(f"[DEBUG] SimpleEventDetailDialog 초기화 완료")
    
    def showEvent(self, event):
        """창이 나타날 때 최상위에 오도록 보장합니다."""
        super().showEvent(event)
        print(f"[DEBUG] SimpleEventDetailDialog showEvent - 최상위로 올림")
        
        # 창이 보일 때 확실히 최상위에 올리기 (지연 실행으로 드래그 간섭 방지)
        QTimer.singleShot(1, self.ensure_on_top)
        
        print(f"[DEBUG] SimpleEventDetailDialog 최상위 설정 예약 완료")
    
    def ensure_on_top(self):
        """이 다이얼로그가 다른 다이얼로그들 위에 나타나도록 보장합니다."""
        print(f"[DEBUG] SimpleEventDetailDialog ensure_on_top 호출 - 최상위로 올림")
        
        # 창을 최상위로 올리고 활성화 (플래그 변경 없이)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        
        # setWindowFlags 호출을 완전히 제거하여 중복 창 문제 방지
        # WindowStaysOnTopHint는 이미 __init__에서 설정되었음
        
        print(f"[DEBUG] SimpleEventDetailDialog 최상위 설정 완료 (플래그 변경 없음)")
    
    def mousePressEvent(self, event):
        """마우스 드래그를 위한 이벤트 핸들러"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint() if hasattr(event.globalPosition(), 'toPoint') else event.globalPosition()
            # 드래그 시작 시 크기 제약 완화 (지오메트리 오류 방지)
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)  # Qt 최대값

    def mouseMoveEvent(self, event):
        """마우스 드래그 이벤트 핸들러"""
        if self.oldPos and event.buttons() == Qt.MouseButton.LeftButton:
            current_pos = event.globalPosition().toPoint() if hasattr(event.globalPosition(), 'toPoint') else event.globalPosition()
            delta = current_pos - self.oldPos
            
            # 새로운 위치 계산
            new_x = self.x() + delta.x()
            new_y = self.y() + delta.y()
            
            # 최소 이동 거리 체크 (성능 향상 및 중복 방지)
            if abs(delta.x()) > 1 or abs(delta.y()) > 1:
                self.move(new_x, new_y)
                self.oldPos = current_pos

    def mouseReleaseEvent(self, event):
        """마우스 드래그 종료 이벤트 핸들러"""
        self.oldPos = None
        # 드래그 종료 시 현재 크기로 고정 (지오메트리 오류 방지)
        current_size = self.size()
        self.setFixedSize(current_size)
    
    def get_dialog_key(self):
        """각 다이얼로그 타입별로 고유 키를 반환합니다."""
        return self.__class__.__name__
    
    def save_position(self):
        """현재 창의 위치를 설정에 저장합니다."""
        if not self.main_widget or not hasattr(self.main_widget, 'settings'):
            print(f"[DEBUG] {self.get_dialog_key()} main_widget 또는 settings가 없어서 위치 저장 건너뜀")
            return
        
        try:
            from settings_manager import load_settings, save_settings
            
            dialog_key = self.get_dialog_key()
            current_settings = load_settings()
            
            if 'dialog_positions' not in current_settings:
                current_settings['dialog_positions'] = {}
            
            position = {'x': self.x(), 'y': self.y()}
            current_settings['dialog_positions'][dialog_key] = position
            
            print(f"[DEBUG] {dialog_key} 위치 저장: {position}")
            save_settings(current_settings)
            print(f"[DEBUG] {dialog_key} 위치 저장 완료!")
            
        except Exception as e:
            print(f"[ERROR] {self.get_dialog_key()} 위치 저장 실패: {e}")
    
    def restore_position(self):
        """저장된 위치에서 창을 엽니다."""
        if not self.main_widget or not hasattr(self.main_widget, 'settings'):
            print(f"[DEBUG] {self.get_dialog_key()} main_widget 또는 settings가 없어서 위치 복원 건너뜀")
            return
        
        try:
            from settings_manager import load_settings
            
            dialog_key = self.get_dialog_key()
            current_settings = load_settings()
            
            if 'dialog_positions' in current_settings and dialog_key in current_settings['dialog_positions']:
                pos_data = current_settings['dialog_positions'][dialog_key]
                print(f"[DEBUG] {dialog_key} 저장된 위치로 이동: {pos_data}")
                self.move(pos_data['x'], pos_data['y'])
            else:
                print(f"[DEBUG] {dialog_key} 저장된 위치 없음")
                
        except Exception as e:
            print(f"[ERROR] {self.get_dialog_key()} 위치 복원 실패: {e}")
    
    def closeEvent(self, event):
        """창을 닫을 때 위치를 저장합니다."""
        print(f"[DEBUG] {self.get_dialog_key()} closeEvent 호출됨")
        self.save_position()
        super().closeEvent(event)
    
    def init_ui(self):
        """간단한 UI 초기화"""
        print("[DEBUG] UI 초기화 시작")
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 테마 파일의 스타일을 사용하도록 오브젝트 이름 설정
        self.setObjectName("event_detail_dialog")
        
        print(f"[DEBUG] 다이얼로그 오브젝트 이름 설정: event_detail_dialog")
        
        # 제목 - 테마 파일의 스타일 사용
        self.title_label = QLabel("제목을 불러오는 중...")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("event_detail_title")
        main_layout.addWidget(self.title_label)
        
        # 정보 영역
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(12)
        
        # 정보 컨테이너들 - 초기에는 모두 숨김
        self.date_container = self._create_info_section("날짜", "")
        self.time_container = self._create_info_section("시간", "")
        self.description_container = self._create_info_section("설명", "")
        self.calendar_container = self._create_info_section("캘린더", "")
        
        info_layout.addWidget(self.date_container)
        info_layout.addWidget(self.time_container)
        info_layout.addWidget(self.description_container)
        info_layout.addWidget(self.calendar_container)
        
        main_layout.addWidget(info_widget)
        
        # 신축성 공간
        main_layout.addStretch()
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 버튼들 - 테마 파일의 스타일 사용
        self.edit_btn = QPushButton("편집")
        self.edit_btn.setFont(self._get_button_font())
        self.edit_btn.setMinimumHeight(45)
        self.edit_btn.setObjectName("event_detail_edit_button")
        self.edit_btn.clicked.connect(self._edit_event)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("삭제")
        self.delete_btn.setFont(self._get_button_font())
        self.delete_btn.setMinimumHeight(45)
        self.delete_btn.setObjectName("event_detail_delete_button")
        self.delete_btn.clicked.connect(self._delete_event)
        button_layout.addWidget(self.delete_btn)
        
        self.close_btn = QPushButton("닫기")
        self.close_btn.setFont(self._get_button_font())
        self.close_btn.setMinimumHeight(45)
        self.close_btn.setObjectName("event_detail_close_button")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)
        
        print("[DEBUG] UI 초기화 완료")
    
    def _create_info_section(self, label_text, content_text=""):
        """정보 섹션 생성"""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 라벨 - 테마 파일 스타일 사용
        label = QLabel(label_text)
        label_font = QFont()
        label_font.setPointSize(11)
        label_font.setBold(True)
        label.setFont(label_font)
        label.setObjectName("event_detail_label")
        layout.addWidget(label)
        
        # 내용 - 테마 파일 스타일 사용
        content = QLabel(content_text)
        content.setWordWrap(True)
        content_font = QFont()
        content_font.setPointSize(11)
        content.setFont(content_font)
        content.setObjectName("event_detail_content")
        content.setMinimumHeight(40)
        layout.addWidget(content)
        
        # 내용 라벨을 찾기 쉽도록 속성 설정
        container.content_label = content
        
        # 초기에는 숨김
        container.hide()
        
        return container
    
    def _get_button_font(self):
        """버튼 폰트 - 적절한 크기 (15pt)"""
        font = QFont()
        font.setPointSize(10)  # 15 → 10pt로 조정
        font.setBold(True)
        return font
    
    def load_event_data(self):
        """이벤트 데이터 로드"""
        try:
            print("[DEBUG] 이벤트 데이터 로드 시작")
            print(f"[DEBUG] 이벤트 데이터: {self.event_data}")
            
            if not self.event_data:
                print("[ERROR] 이벤트 데이터가 없습니다")
                return
            
            # 제목 설정 - summary 또는 subject에서
            title = self.event_data.get('summary') or self.event_data.get('subject', '제목 없음')
            self.title_label.setText(title)
            print(f"[DEBUG] 제목 설정: {title}")
            
            # 날짜 정보 로드
            self._load_date_info()
            
            # 시간 정보 로드  
            self._load_time_info()
            
            # 설명 로드
            self._load_description()
            
            # 캘린더 정보 로드
            self._load_calendar_info()
            
            print("[DEBUG] 이벤트 데이터 로드 완료")
            
        except Exception as e:
            print(f"[ERROR] 이벤트 데이터 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_date_info(self):
        """날짜 정보 로드"""
        try:
            # 다양한 데이터 구조를 지원
            start_info = None
            end_info = None
            
            # body.start/end 방식 시도
            if 'body' in self.event_data:
                body = self.event_data['body']
                start_info = body.get('start')
                end_info = body.get('end')
            # 직접 start/end 방식 시도
            elif 'start' in self.event_data:
                start_info = self.event_data.get('start')
                end_info = self.event_data.get('end')
            
            print(f"[DEBUG] start_info: {start_info}")
            print(f"[DEBUG] end_info: {end_info}")
            
            if start_info:
                date_text = self._parse_date_string(start_info, end_info)
                if date_text:
                    self.date_container.content_label.setText(date_text)
                    self.date_container.show()
                    print(f"[DEBUG] 날짜 설정: {date_text}")
                    return
            
            print("[DEBUG] 날짜 정보 없음 - 숨김")
            
        except Exception as e:
            print(f"[ERROR] 날짜 정보 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_date_string(self, start_info, end_info):
        """날짜 문자열 파싱"""
        try:
            start_date = None
            
            # 다양한 형식 지원
            if isinstance(start_info, dict):
                if 'date' in start_info:
                    start_date = datetime.datetime.fromisoformat(start_info['date']).date()
                elif 'dateTime' in start_info:
                    start_date = datetime.datetime.fromisoformat(start_info['dateTime'].replace('Z', '+00:00')).date()
            elif isinstance(start_info, str):
                # ISO 형식 문자열 직접 파싱
                if 'T' in start_info:
                    start_date = datetime.datetime.fromisoformat(start_info.replace('Z', '+00:00')).date()
                else:
                    start_date = datetime.datetime.fromisoformat(start_info).date()
            
            if start_date:
                # 종료 날짜도 확인
                end_date = None
                if end_info:
                    if isinstance(end_info, dict):
                        if 'date' in end_info:
                            end_date = datetime.datetime.fromisoformat(end_info['date']).date()
                        elif 'dateTime' in end_info:
                            end_date = datetime.datetime.fromisoformat(end_info['dateTime'].replace('Z', '+00:00')).date()
                    elif isinstance(end_info, str):
                        if 'T' in end_info:
                            end_date = datetime.datetime.fromisoformat(end_info.replace('Z', '+00:00')).date()
                        else:
                            end_date = datetime.datetime.fromisoformat(end_info).date()
                
                # 날짜 문자열 생성
                if end_date and end_date != start_date:
                    return f"{start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}"
                else:
                    weekdays = ['월', '화', '수', '목', '금', '토', '일']
                    weekday = weekdays[start_date.weekday()]
                    return f"{start_date.strftime('%Y년 %m월 %d일')} ({weekday})"
                    
        except Exception as e:
            print(f"[ERROR] 날짜 문자열 파싱 실패: {e}")
            
        return None
    
    def _load_time_info(self):
        """시간 정보 로드"""
        try:
            # 다양한 데이터 구조를 지원
            start_info = None
            end_info = None
            
            if 'body' in self.event_data:
                body = self.event_data['body']
                start_info = body.get('start')
                end_info = body.get('end')
            elif 'start' in self.event_data:
                start_info = self.event_data.get('start')
                end_info = self.event_data.get('end')
            
            time_text = self._parse_time_string(start_info, end_info)
            
            if time_text:
                self.time_container.content_label.setText(time_text)
                self.time_container.show()
                print(f"[DEBUG] 시간 설정: {time_text}")
            else:
                print("[DEBUG] 시간 정보 없음 - 숨김")
            
        except Exception as e:
            print(f"[ERROR] 시간 정보 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _parse_time_string(self, start_info, end_info):
        """시간 문자열 파싱"""
        try:
            start_dt = None
            
            # 시작 시간 파싱
            if isinstance(start_info, dict) and 'dateTime' in start_info:
                start_dt = datetime.datetime.fromisoformat(start_info['dateTime'].replace('Z', '+00:00'))
            elif isinstance(start_info, str) and 'T' in start_info:
                start_dt = datetime.datetime.fromisoformat(start_info.replace('Z', '+00:00'))
            
            if start_dt:
                # 종료 시간 파싱
                end_dt = None
                if isinstance(end_info, dict) and 'dateTime' in end_info:
                    end_dt = datetime.datetime.fromisoformat(end_info['dateTime'].replace('Z', '+00:00'))
                elif isinstance(end_info, str) and 'T' in end_info:
                    end_dt = datetime.datetime.fromisoformat(end_info.replace('Z', '+00:00'))
                
                if end_dt:
                    return f"{start_dt.strftime('%H:%M')} ~ {end_dt.strftime('%H:%M')}"
                else:
                    return start_dt.strftime('%H:%M')
            else:
                # dateTime이 없으면 종일 이벤트
                return "종일"
                
        except Exception as e:
            print(f"[ERROR] 시간 문자열 파싱 실패: {e}")
            return "종일"
    
    def _load_description(self):
        """설명 로드"""
        try:
            description = None
            
            # 다양한 속성에서 설명 찾기
            if 'body' in self.event_data:
                body = self.event_data['body']
                description = body.get('body') or body.get('bodyPreview') or body.get('content')
            
            # 직접 속성도 확인
            if not description:
                description = (self.event_data.get('body') or 
                             self.event_data.get('bodyPreview') or
                             self.event_data.get('content') or
                             self.event_data.get('description'))
            
            if description and description.strip():
                self.description_container.content_label.setText(description.strip())
                self.description_container.show()
                print(f"[DEBUG] 설명 설정: {description[:50]}...")
            else:
                print("[DEBUG] 설명 없음 - 숨김")
            
        except Exception as e:
            print(f"[ERROR] 설명 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_calendar_info(self):
        """캘린더 정보 로드 (이름과 색상 정보 포함)"""
        try:
            calendar_id = self.event_data.get('calendarId')
            calendar_name = None
            calendar_color = None
            calendar_type = None
            
            print(f"[DEBUG] === 캘린더 정보 로드 시작 ===")
            print(f"[DEBUG] 찾고 있는 캘린더 ID: {calendar_id}")
            
            # data_manager에서 캘린더 정보 가져오기 (올바른 메서드 사용)
            calendar_found = False
            all_calendars = []
            
            try:
                if hasattr(self.data_manager, 'get_all_calendars'):
                    all_calendars = self.data_manager.get_all_calendars(fetch_if_empty=False) or []
                    print(f"[DEBUG] data_manager.get_all_calendars() 호출 결과: {len(all_calendars)}개")
                    
                    if all_calendars:
                        print("[DEBUG] 사용 가능한 캘린더 목록:")
                        for i, cal in enumerate(all_calendars):
                            print(f"[DEBUG]   [{i}] ID: {cal.get('id')}, Name: {cal.get('name')}, Summary: {cal.get('summary')}")
                    
                    # 캘린더 ID로 검색
                    for calendar in all_calendars:
                        if calendar.get('id') == calendar_id:
                            calendar_name = (calendar.get('name') or 
                                           calendar.get('summary') or 
                                           calendar.get('displayName'))
                            calendar_color = calendar.get('backgroundColor', calendar.get('color', '#4285F4'))
                            calendar_type = calendar.get('kind', calendar.get('type', ''))
                            calendar_found = True
                            print(f"[DEBUG] ✅ 캘린더 정보 찾음: {calendar_name}")
                            break
                else:
                    print("[DEBUG] ❌ data_manager에 get_all_calendars 메서드가 없음")
            except Exception as e:
                print(f"[DEBUG] ❌ get_all_calendars 호출 중 오류: {e}")
            
            # 캘린더 정보를 찾지 못했을 때 폴백 로직
            if not calendar_found and calendar_id:
                print(f"[DEBUG] 캘린더 정보를 찾지 못함, 폴백 시도...")
                
                # 1. 특별 캘린더 ID 처리
                special_calendars = {
                    'local_calendar': '로컬 캘린더',
                }
                
                if calendar_id in special_calendars:
                    calendar_name = special_calendars[calendar_id]
                    calendar_color = self.event_data.get('color', '#4285F4')
                    calendar_found = True
                    print(f"[DEBUG] ✅ 특별 캘린더 처리: {calendar_name}")
                elif calendar_id.endswith('@gmail.com') and not calendar_id.startswith('family') and not '#' in calendar_id:
                    # 개인 구글 캘린더 (이메일 형태)
                    calendar_name = f"{calendar_id.split('@')[0]}"
                    calendar_color = self.event_data.get('color', '#4285F4')
                    calendar_found = True
                    print(f"[DEBUG] ✅ 개인 캘린더 처리: {calendar_name}")
            
            # organizer 정보 활용 (최종 폴백)
            if not calendar_found and 'organizer' in self.event_data:
                organizer = self.event_data['organizer']
                if organizer.get('displayName'):
                    calendar_name = organizer.get('displayName')
                    calendar_color = self.event_data.get('color', '#4285F4')
                    calendar_found = True
                    print(f"[DEBUG] ✅ organizer 정보 사용: {calendar_name}")
            
            if calendar_name and calendar_name.strip():
                # 캘린더 이름과 함께 시각적 구분을 위한 색상 바 추가
                display_text = calendar_name.strip()
                
                # 캘린더 타입 정보가 있으면 추가 표시 - 실제 구글 캘린더 속성 확인
                if all_calendars:
                    for cal in all_calendars:
                        if cal.get('id') == calendar_id:
                            # 구글 캘린더 API에서 오는 실제 속성들 확인
                            if cal.get('primary', False):
                                display_text += " (기본)"
                            elif cal.get('accessRole') in ['owner', 'writer', 'reader']:
                                if cal.get('accessRole') == 'reader':
                                    display_text += " (읽기전용)"
                                elif cal.get('accessRole') == 'writer':
                                    display_text += " (편집가능)"
                            break
                
                self.calendar_container.content_label.setText(display_text)
                
                # 캘린더 색상이 있으면 색상 바를 추가하여 시각적 구분
                if calendar_color:
                    content_label = self.calendar_container.content_label
                    content_label.setStyleSheet(f"""
                        QLabel#event_detail_content {{
                            border-left: 4px solid {calendar_color};
                        }}
                    """)
                
                self.calendar_container.show()
                print(f"[DEBUG] 캘린더 설정: {display_text}, 색상: {calendar_color}")
            else:
                # 최후의 폴백
                print(f"[DEBUG] ❌ 모든 방법으로 캘린더 이름을 찾지 못함")
                calendar_name = "알 수 없는 캘린더"
                calendar_color = self.event_data.get('color', '#4285F4')
                
                self.calendar_container.content_label.setText(calendar_name)
                content_label = self.calendar_container.content_label
                content_label.setStyleSheet(f"""
                    QLabel#event_detail_content {{
                        border-left: 4px solid {calendar_color};
                    }}
                """)
                self.calendar_container.show()
                print(f"[DEBUG] 최종 폴백 표시: {calendar_name} (색상: {calendar_color})")
            
        except Exception as e:
            print(f"[ERROR] 캘린더 정보 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _edit_event(self):
        """일정 편집"""
        try:
            if not self.main_widget.is_interaction_unlocked():
                return
            
            from event_editor_window import EventEditorWindow
            
            editor = EventEditorWindow(
                mode='edit',
                data=self.event_data,
                calendars=getattr(self.data_manager, 'calendars', None),
                settings=getattr(self.main_widget, 'settings', None) if self.main_widget else None,
                parent=self,
                data_manager=self.data_manager
            )
            
            # 편집창을 열기 전에 상세창 닫기
            self.accept()
            
            if editor.exec() == QDialog.DialogCode.Accepted:
                updated_event = editor.get_event_data()
                self.event_edited.emit(updated_event)
                
        except Exception as e:
            QMessageBox.warning(self, "오류", f"일정 편집 중 오류가 발생했습니다: {str(e)}")
    
    def _delete_event(self):
        """일정 삭제"""
        try:
            if not self.main_widget.is_interaction_unlocked():
                return
            
            event_title = self.event_data.get('summary', '제목 없음')
            
            reply = QMessageBox.question(
                self,
                "일정 삭제",
                f"'{event_title}' 일정을 삭제하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.data_manager.delete_event(self.event_data)
                self.event_deleted.emit(self.original_event_id)
                self.accept()
                
        except Exception as e:
            QMessageBox.warning(self, "오류", f"일정 삭제 중 오류가 발생했습니다: {str(e)}")