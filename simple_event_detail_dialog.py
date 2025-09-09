# simple_event_detail_dialog.py
"""
간단하고 확실하게 작동하는 이벤트 상세보기 다이얼로그
BaseDialog를 상속하여 다른 다이얼로그와 통일성 확보
"""

import datetime
import re
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QFrame, QMessageBox, QWidget, QTextEdit, QScrollArea, QTextBrowser)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from custom_dialogs import BaseDialog
from event_detail_texts import get_text, get_weekday_text
from rrule_parser import RRuleParser

class SimpleEventDetailDialog(BaseDialog):
    """간단하고 확실한 이벤트 상세보기 다이얼로그"""
    
    # 시그널 정의
    event_edited = pyqtSignal(dict)
    event_deleted = pyqtSignal(str)
    
    def __init__(self, event_data, data_manager, main_widget, parent=None):
        print(f"[DEBUG] SimpleEventDetailDialog 초기화 시작")
        
        # 안전한 parent 설정 - None으로 초기화하여 Segfault 방지
        settings = getattr(main_widget, 'settings', None) if main_widget else None
        
        # BaseDialog 초기화 시 parent를 None으로 설정하여 안전성 확보
        super().__init__(parent=None, settings=settings)
        
        self.setWindowTitle(get_text("window_title"))
        self.setModal(True)
        # 창 크기를 400x515으로 변경 (15px 증가)
        self.setFixedSize(400, 515)
        
        self.event_data = event_data
        self.data_manager = data_manager
        self.main_widget = main_widget
        self.original_event_id = event_data.get('id')
        
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
    
    def mouseReleaseEvent(self, event):
        """마우스 드래그 종료 이벤트 핸들러 - 크기 고정 추가"""
        super().mouseReleaseEvent(event)
        # 드래그 종료 시 현재 크기로 고정 (지오메트리 오류 방지)
        current_size = self.size()
        self.setFixedSize(current_size)
    
    def get_dialog_key(self):
        """각 다이얼로그 타입별로 고유 키를 반환합니다."""
        return self.__class__.__name__
    
    # BaseDialog에서 상속받은 위치 관리 기능을 사용하므로 제거됨
    
    def init_ui(self):
        """간단한 UI 초기화"""
        print("[DEBUG] UI 초기화 시작")
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 위젯 생성 (BaseDialog 패턴을 따름)
        background_widget = QWidget()
        background_widget.setObjectName("event_detail_background")
        main_layout.addWidget(background_widget)
        
        # 실제 내용 레이아웃 - 간격 줄임
        content_layout = QVBoxLayout(background_widget)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(8)
        
        # 다이얼로그 자체에도 오브젝트 이름 설정
        self.setObjectName("event_detail_dialog")
        
        print(f"[DEBUG] 다이얼로그 오브젝트 이름 설정: event_detail_dialog")
        
        # 제목 - 테마 파일의 스타일 사용 (하드코딩 폰트 제거)
        self.title_label = QLabel(get_text("loading_title"))
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("event_detail_title")
        content_layout.addWidget(self.title_label)
        
        # 정보 영역을 스크롤 가능하게 만들기
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setObjectName("event_detail_scroll")
        
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)  # 간격 줄임
        
        # 정보 컨테이너들 - 초기에는 모두 숨김 (텍스트는 테마 파일에서 가져옴)
        self.date_container = self._create_info_section(get_text("date_label"), "", single_line=True)
        self.time_container = self._create_info_section(get_text("time_label"), "", single_line=True)
        self.recurrence_container = self._create_info_section(get_text("recurrence_label"), "", single_line=True)
        self.description_container = self._create_info_section(get_text("description_label"), "", single_line=False, max_lines=3)
        self.calendar_container = self._create_info_section(get_text("calendar_label"), "", single_line=True)
        
        info_layout.addWidget(self.date_container)
        info_layout.addWidget(self.time_container)
        info_layout.addWidget(self.recurrence_container)
        info_layout.addWidget(self.description_container)
        info_layout.addWidget(self.calendar_container)
        
        # 신축성 공간을 info_layout에 추가하여 내용을 위쪽에 정렬
        info_layout.addStretch()
        
        scroll_area.setWidget(info_widget)
        content_layout.addWidget(scroll_area)
        
        # 버튼 영역 - 간격 줄임
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # 버튼들 - 테마 파일의 스타일 사용, 높이를 70%로 줄임 (32px → 22px)
        self.edit_btn = QPushButton(get_text("edit_button"))
        self.edit_btn.setObjectName("event_detail_edit_button")
        self.edit_btn.setFixedHeight(22)  # 버튼 높이 70%로 줄임
        self.edit_btn.clicked.connect(self._edit_event)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton(get_text("delete_button"))
        self.delete_btn.setObjectName("event_detail_delete_button")
        self.delete_btn.setFixedHeight(22)  # 버튼 높이 70%로 줄임
        self.delete_btn.clicked.connect(self._delete_event)
        button_layout.addWidget(self.delete_btn)
        
        self.close_btn = QPushButton(get_text("close_button"))
        self.close_btn.setObjectName("event_detail_close_button")
        self.close_btn.setFixedHeight(22)  # 버튼 높이 70%로 줄임
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        content_layout.addLayout(button_layout)
        
        print("[DEBUG] UI 초기화 완료")
    
    def _create_info_section(self, label_text, content_text="", single_line=True, max_lines=1):
        """정보 섹션 생성"""
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)  # 라벨과 내용 간격 줄임
        
        # 라벨 - 테마 파일 스타일 사용 (하드코딩 폰트 제거)
        label = QLabel(label_text)
        label.setObjectName("event_detail_label")
        layout.addWidget(label)
        
        # 내용 - 단일줄 vs 다중줄 처리
        if single_line or max_lines == 1:
            # 단일줄 처리 (날짜, 시간, 캘린더)
            content = QLabel(content_text)
            content.setWordWrap(False)
            content.setObjectName("event_detail_content")
            # 텍스트가 길면 생략 부호 표시
            content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(content)
            container.content_label = content
        else:
            # 다중줄 처리 (설명) - QTextBrowser 사용하여 링크 처리
            content = QTextBrowser()
            content.setObjectName("event_detail_content")
            content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            # 최대 줄 수에 따른 높이 설정 - 3줄이 잘리지 않도록 충분히 늘림, 5픽셀 추가 증가
            content.setMaximumHeight(max_lines * 25 + 35)  # 줄 높이를 25px로 늘리고 여백 35px 추가 (10px 추가 증가)
            content.setMinimumHeight(90)  # 최소 높이도 10픽셀 추가 늘림
            
            # QTextBrowser는 자동으로 외부 링크를 처리함
            content.setOpenExternalLinks(True)
            
            layout.addWidget(content)
            container.content_label = content
        
        # 초기에는 숨김
        container.hide()
        
        return container
    
    
    def _convert_text_to_html_with_links(self, text):
        """텍스트에서 URL을 찾아 HTML 링크로 변환"""
        if not text:
            return text
            
        # HTML 이스케이프 처리
        import html
        text = html.escape(text)
            
        # URL 패턴 (http, https, www로 시작하는 URL)
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+)'
        
        def replace_url(match):
            url = match.group(1)
            if not url.startswith('http'):
                url = 'http://' + url
            return f'<a href="{url}">{match.group(1)}</a>'
        
        # URL을 링크로 변환
        html_text = re.sub(url_pattern, replace_url, text)
        
        # 줄바꿈을 <br>로 변환
        html_text = html_text.replace('\n', '<br>')
        
        # 간단한 스타일 추가 (주황빛 빨강으로 고정)
        styled_html = f'''
        <style>
            a {{ color: #FF5722 !important; text-decoration: underline; }}
            a:hover {{ color: #FF8A80 !important; }}
            a:visited {{ color: #D84315 !important; }}
        </style>
        {html_text}
        '''
        
        return styled_html
    
    # _get_button_font 메서드 제거 - 테마 파일에서 관리
    
    def load_event_data(self):
        """이벤트 데이터 로드"""
        try:
            print("[DEBUG] 이벤트 데이터 로드 시작")
            print(f"[DEBUG] 이벤트 데이터: {self.event_data}")
            
            if not self.event_data:
                print("[ERROR] 이벤트 데이터가 없습니다")
                return
            
            # 제목 설정 - summary 또는 subject에서
            title = self.event_data.get('summary') or self.event_data.get('subject', get_text("no_title"))
            self.title_label.setText(title)
            print(f"[DEBUG] 제목 설정: {title}")
            
            # 날짜 정보 로드
            self._load_date_info()
            
            # 시간 정보 로드  
            self._load_time_info()
            
            # 반복 규칙 로드
            self._load_recurrence_info()
            
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
                
                # 날짜 형식은 텍스트 파일에서 가져옴
                if end_date and end_date != start_date:
                    date_format = get_text("date_range_format")
                    return f"{start_date.strftime(get_text('date_format'))} ~ {end_date.strftime(get_text('date_format'))}"
                else:
                    weekday = get_weekday_text(start_date.weekday())
                    return f"{start_date.strftime(get_text('date_format'))} ({weekday})"
                    
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
                    return f"{start_dt.strftime(get_text('time_format'))} ~ {end_dt.strftime(get_text('time_format'))}"
                else:
                    return start_dt.strftime(get_text('time_format'))
            else:
                # dateTime이 없으면 종일 이벤트
                return get_text("all_day")
                
        except Exception as e:
            print(f"[ERROR] 시간 문자열 파싱 실패: {e}")
            return get_text("all_day")
    
    def _load_recurrence_info(self):
        """반복 규칙 정보 로드"""
        try:
            recurrence_rule = None
            recurrence_text = "반복 안 함"  # 기본값
            
            print("[DEBUG] ========== 반복 규칙 정보 로드 시작 ==========")
            print(f"[DEBUG] Event data keys: {list(self.event_data.keys())}")
            
            # 다양한 위치에서 반복 규칙 찾기
            if 'body' in self.event_data:
                body = self.event_data['body']
                print(f"[DEBUG] Body keys: {list(body.keys())}")
                # recurrence 배열에서 RRULE 찾기 (Google Calendar 형식)
                if 'recurrence' in body and body['recurrence']:
                    recurrence_rule = body['recurrence'][0]  # 첫 번째 규칙 사용
                    print(f"[DEBUG] OK body.recurrence에서 규칙 발견: {recurrence_rule}")
                else:
                    print("[DEBUG] WARN body.recurrence 없음 또는 비어있음")
            else:
                print("[DEBUG] WARN 'body' 키가 없음")
            
            # 직접 recurrence 필드 확인
            if not recurrence_rule and 'recurrence' in self.event_data and self.event_data['recurrence']:
                recurrence_rule = self.event_data['recurrence'][0]
                print(f"[DEBUG] OK recurrence 필드에서 규칙 발견: {recurrence_rule}")
            
            # rrule 필드 확인 (로컬 캘린더 등)
            if not recurrence_rule and 'rrule' in self.event_data and self.event_data['rrule']:
                recurrence_rule = f"RRULE:{self.event_data['rrule']}"
                print(f"[DEBUG] OK rrule 필드에서 규칙 발견: {recurrence_rule}")
            
            # originalId가 있으면 반복 일정의 인스턴스일 가능성
            if not recurrence_rule and 'originalId' in self.event_data:
                print("[DEBUG] OK originalId 발견 - 반복 일정의 인스턴스")
                recurrence_text = "반복 일정의 인스턴스"
            
            # 반복 규칙이 있으면 파싱해서 사용자 친화적 텍스트 생성
            if recurrence_rule:
                try:
                    parser = RRuleParser()
                    
                    # 시작 날짜 정보 가져오기
                    start_datetime = None
                    if 'body' in self.event_data and 'start' in self.event_data['body']:
                        start_info = self.event_data['body']['start']
                    elif 'start' in self.event_data:
                        start_info = self.event_data['start']
                    else:
                        start_info = None
                    
                    if start_info:
                        start_str = start_info.get('dateTime', start_info.get('date'))
                        if start_str:
                            try:
                                start_datetime = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                            except:
                                start_datetime = datetime.datetime.now()
                    
                    if not start_datetime:
                        start_datetime = datetime.datetime.now()
                    
                    # RRULE을 사용자 친화적 텍스트로 변환
                    recurrence_text = parser.rrule_to_text(recurrence_rule, start_datetime)
                    print(f"[DEBUG] OK 반복 규칙 텍스트 생성: {recurrence_text}")
                    
                except Exception as e:
                    print(f"[DEBUG] WARN 반복 규칙 파싱 실패: {e}")
                    recurrence_text = "반복 일정"
            
            print(f"[DEBUG] 최종 recurrence_text: '{recurrence_text}'")
            
            # 반복 정보가 실제로 있는 경우에만 표시 ("반복 안 함"은 표시하지 않음)
            if recurrence_text and recurrence_text.strip() and recurrence_text != "반복 안 함":
                self.recurrence_container.content_label.setText(recurrence_text)
                self.recurrence_container.show()
                print(f"[DEBUG] OK 반복 규칙 표시 완료: {recurrence_text}")
            else:
                print(f"[DEBUG] WARN 일반 일정이므로 반복 섹션 숨김")
            
            print(f"[DEBUG] ========== 반복 규칙 정보 로드 완료 ==========")
            
        except Exception as e:
            print(f"[ERROR] 반복 규칙 정보 로드 실패: {e}")
            # 오류 시에는 반복 섹션을 숨김 (일반 일정으로 처리)
            try:
                if hasattr(self, 'recurrence_container'):
                    print(f"[DEBUG] WARN 예외 발생으로 반복 섹션 숨김")
            except Exception as e2:
                print(f"[ERROR] 예외 처리 중에도 오류: {e2}")
            import traceback
            traceback.print_exc()
    
    def _load_description(self):
        """설명 로드"""
        try:
            description = None
            
            print("[DEBUG] ========== 설명 정보 로드 시작 ==========")
            print(f"[DEBUG] Event data keys: {list(self.event_data.keys())}")
            
            # 다양한 속성에서 설명 찾기
            if 'body' in self.event_data:
                body = self.event_data['body']
                print(f"[DEBUG] Body keys: {list(body.keys())}")
                
                # 다양한 필드 이름 확인
                desc_fields = ['body', 'bodyPreview', 'content', 'description']
                for field in desc_fields:
                    if field in body and body[field]:
                        description = body[field]
                        print(f"[DEBUG] OK body.{field}에서 설명 발견: {description[:100]}...")
                        break
                    else:
                        print(f"[DEBUG] WARN body.{field} 없음 또는 비어있음")
            else:
                print("[DEBUG] WARN 'body' 키가 없음")
            
            # 직접 속성도 확인
            if not description:
                desc_fields = ['body', 'bodyPreview', 'content', 'description']
                for field in desc_fields:
                    if field in self.event_data and self.event_data[field]:
                        description = self.event_data[field]
                        print(f"[DEBUG] OK 직접 {field}에서 설명 발견: {description[:100]}...")
                        break
                    else:
                        print(f"[DEBUG] WARN 직접 {field} 없음 또는 비어있음")
            
            print(f"[DEBUG] 최종 description: {description[:100] if description else 'None'}...")
            
            if description and description.strip():
                # 하이퍼링크가 포함된 HTML로 변환
                html_description = self._convert_text_to_html_with_links(description.strip())
                
                # QTextBrowser나 QTextEdit인 경우 setHtml 사용
                if isinstance(self.description_container.content_label, (QTextEdit, QTextBrowser)):
                    self.description_container.content_label.setHtml(html_description)
                    print(f"[DEBUG] OK QTextBrowser에 HTML 설정")
                else:
                    self.description_container.content_label.setText(description.strip())
                    print(f"[DEBUG] OK QLabel에 텍스트 설정")
                    
                self.description_container.show()
                print(f"[DEBUG] OK 설명 컨테이너 표시 완료")
            else:
                print("[DEBUG] WARN 설명이 없거나 빈 문자열 - 숨김")
            
            print(f"[DEBUG] ========== 설명 정보 로드 완료 ==========")
            
        except Exception as e:
            print(f"[ERROR] 설명 로드 실패: {e}")
            # 오류 시에도 기본값 시도
            try:
                if hasattr(self, 'description_container'):
                    print(f"[DEBUG] 예외 처리 - 설명 없음으로 숨김")
            except Exception as e2:
                print(f"[ERROR] 예외 처리 중에도 오류: {e2}")
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
                            print(f"[DEBUG] OK 캘린더 정보 찾음: {calendar_name}")
                            break
                else:
                    print("[DEBUG] WARN data_manager에 get_all_calendars 메서드가 없음")
            except Exception as e:
                print(f"[DEBUG] WARN get_all_calendars 호출 중 오류: {e}")
            
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
                    print(f"[DEBUG] OK 특별 캘린더 처리: {calendar_name}")
                elif calendar_id.endswith('@gmail.com') and not calendar_id.startswith('family') and not '#' in calendar_id:
                    # 개인 구글 캘린더 (이메일 형태)
                    calendar_name = f"{calendar_id.split('@')[0]}"
                    calendar_color = self.event_data.get('color', '#4285F4')
                    calendar_found = True
                    print(f"[DEBUG] OK 개인 캘린더 처리: {calendar_name}")
            
            # organizer 정보 활용 (최종 폴백)
            if not calendar_found and 'organizer' in self.event_data:
                organizer = self.event_data['organizer']
                if organizer.get('displayName'):
                    calendar_name = organizer.get('displayName')
                    calendar_color = self.event_data.get('color', '#4285F4')
                    calendar_found = True
                    print(f"[DEBUG] OK organizer 정보 사용: {calendar_name}")
            
            # 캘린더 정보 표시 로직
            print(f"[DEBUG] ========== 캘린더 표시 로직 시작 ==========")
            print(f"[DEBUG] calendar_name: '{calendar_name}', calendar_found: {calendar_found}")
            
            final_display_text = None
            final_color = '#4285F4'  # 기본 색상
            
            if calendar_name and calendar_name.strip():
                # 캘린더 이름과 함께 시각적 구분을 위한 색상 바 추가
                display_text = calendar_name.strip()
                
                # 캘린더 타입 정보가 있으면 추가 표시 - 실제 구글 캘린더 속성 확인
                if all_calendars:
                    for cal in all_calendars:
                        if cal.get('id') == calendar_id:
                            # 구글 캘린더 API에서 오는 실제 속성들 확인
                            if cal.get('primary', False):
                                display_text += get_text("primary_calendar")
                            elif cal.get('accessRole') in ['owner', 'writer', 'reader']:
                                if cal.get('accessRole') == 'reader':
                                    display_text += get_text("reader_calendar")
                                elif cal.get('accessRole') == 'writer':
                                    display_text += get_text("writer_calendar")
                            break
                
                final_display_text = display_text
                final_color = calendar_color or '#4285F4'
                print(f"[DEBUG] OK 캘린더 이름 있음: '{final_display_text}'")
            else:
                # 최후의 폴백 - 항상 뭔가는 표시
                print(f"[DEBUG] WARN 캘린더 이름 없음 - 폴백 사용")
                final_display_text = get_text("unknown_calendar")
                final_color = self.event_data.get('color', '#4285F4')
            
            # 항상 캘린더 정보 표시 (폴백 포함)
            if final_display_text:
                self.calendar_container.content_label.setText(final_display_text)
                
                # 캘린더 색상 바 추가
                content_label = self.calendar_container.content_label
                content_label.setStyleSheet(f"""
                    QLabel#event_detail_content {{
                        border-left: 4px solid {final_color};
                    }}
                """)
                
                self.calendar_container.show()
                print(f"[DEBUG] OK 캘린더 표시 완료: '{final_display_text}', 색상: {final_color}")
            else:
                print(f"[ERROR] WARN final_display_text가 비어있음 - 강제로 기본값 표시")
                self.calendar_container.content_label.setText("캘린더")
                self.calendar_container.show()
            
            print(f"[DEBUG] ========== 캘린더 표시 로직 완료 ==========")
            
            # 읽기 전용 캘린더 확인 및 편집 버튼 비활성화
            self._check_and_disable_edit_for_readonly_calendar(all_calendars, calendar_id)
            
        except Exception as e:
            print(f"[ERROR] 캘린더 정보 로드 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _check_and_disable_edit_for_readonly_calendar(self, all_calendars, calendar_id):
        """읽기 전용 캘린더인지 확인하고 편집 버튼 비활성화"""
        try:
            is_readonly = False
            
            # 캘린더 목록에서 accessRole이 'reader'인지 확인
            for calendar in all_calendars:
                if calendar.get('id') == calendar_id:
                    access_role = calendar.get('accessRole')
                    print(f"[DEBUG] 캘린더 {calendar_id}의 accessRole: {access_role}")
                    
                    if access_role == 'reader':
                        is_readonly = True
                        print(f"[DEBUG] 읽기 전용 캘린더 감지: {calendar_id}")
                    break
            
            # 읽기 전용 캘린더인 경우 편집 버튼 비활성화
            if is_readonly:
                self.edit_btn.setEnabled(False)
                self.edit_btn.setToolTip("읽기 전용 캘린더는 편집할 수 없습니다")
                print(f"[DEBUG] 편집 버튼 비활성화 완료 (읽기 전용 캘린더)")
            else:
                # 편집 가능한 캘린더인 경우 버튼 활성화 (기본값)
                self.edit_btn.setEnabled(True)
                self.edit_btn.setToolTip("")
                print(f"[DEBUG] 편집 버튼 활성화 (편집 가능 캘린더)")
                
        except Exception as e:
            print(f"[ERROR] 읽기 전용 캘린더 확인 중 오류: {e}")
            # 오류 시 기본적으로 편집 허용
            self.edit_btn.setEnabled(True)
    
    def _edit_event(self):
        """일정 편집 - 메인위젯의 편집 시스템 사용"""
        try:
            if hasattr(self.main_widget, 'is_interaction_unlocked') and not self.main_widget.is_interaction_unlocked():
                return
            
            # 메인위젯의 open_event_editor 사용 (컨텍스트메뉴와 동일한 방식)
            if self.main_widget and hasattr(self.main_widget, 'open_event_editor'):
                print(f"[DEBUG] SimpleEventDetailDialog: 메인위젯의 open_event_editor 호출")
                self.main_widget.open_event_editor(self.event_data)
                
                # 편집 창이 열린 후 상세보기 창은 닫기
                self.close()
            else:
                print(f"[ERROR] 메인위젯에서 open_event_editor를 찾을 수 없음")
                QMessageBox.warning(self, "오류", "편집 기능을 사용할 수 없습니다.")
                
        except Exception as e:
            print(f"[ERROR] 일정 편집 중 오류: {e}")
            QMessageBox.warning(self, "오류", f"일정 편집 중 오류가 발생했습니다: {str(e)}")
    
    def _delete_event(self):
        """일정 삭제 - 컨텍스트메뉴와 동일한 삭제 확인창 사용"""
        try:
            if hasattr(self.main_widget, 'is_interaction_unlocked') and not self.main_widget.is_interaction_unlocked():
                return
            
            # 컨텍스트메뉴와 동일한 삭제 확인 다이얼로그 사용
            from event_editor_window import EventEditorWindow
            chosen_mode = EventEditorWindow.show_delete_confirmation(
                self.event_data, self, self.main_widget.settings
            )

            if chosen_mode:
                # 사용자가 삭제를 확정했을 경우, DataManager 호출
                event_to_delete = self.event_data.copy()

                # DataManager가 'body' 키를 포함하는 래핑된 딕셔너리를 예상하므로,
                # 'body' 키가 없는 경우 데이터 구조를 맞춰줍니다.
                if 'body' not in event_to_delete:
                     event_to_delete = {
                        'calendarId': self.event_data.get('calendarId'),
                        'provider': self.event_data.get('provider'),
                        'body': self.event_data
                     }
                
                self.data_manager.delete_event(event_to_delete, deletion_mode=chosen_mode)
                self.event_deleted.emit(self.original_event_id)
                self.accept()
                
        except Exception as e:
            print(f"[ERROR] 일정 삭제 처리 중 오류: {e}")
            QMessageBox.warning(self, "오류", f"일정 삭제 처리 중 오류가 발생했습니다: {str(e)}")