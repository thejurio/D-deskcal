# rrule_parser.py
import datetime
from dateutil.rrule import rrule, rrulestr
from dateutil.parser import parse as dateutil_parse
import logging

logger = logging.getLogger(__name__)

class RRuleParser:
    """RRULE 문자열을 파싱하고 반복 날짜를 생성하는 클래스"""
    
    def parse_google_rrule(self, rrule_string, start_datetime, max_instances=50):
        """
        Google Calendar의 RRULE 문자열을 파싱하여 반복 날짜들을 반환
        
        Args:
            rrule_string (str): RRULE 문자열 (예: "FREQ=DAILY;COUNT=5")
            start_datetime (datetime): 시작 날짜/시간
            max_instances (int): 생성할 최대 인스턴스 수
            
        Returns:
            list: datetime 객체들의 리스트
        """
        try:
            # RRULE 문자열 정규화 (RRULE: 접두사가 없으면 추가)
            if not rrule_string.startswith('RRULE:'):
                rrule_string = 'RRULE:' + rrule_string
            
            logger.info(f"Parsing RRULE: {rrule_string} with start: {start_datetime}")
            
            # RRULE 파싱
            rule = rrulestr(rrule_string, dtstart=start_datetime)
            
            # 반복 날짜들 생성 (최대 인스턴스 수 제한)
            recurring_dates = list(rule[:max_instances])
            
            logger.info(f"Generated {len(recurring_dates)} recurring dates")
            
            return recurring_dates
            
        except Exception as e:
            logger.error(f"Failed to parse RRULE '{rrule_string}': {e}")
            # 파싱 실패 시 시작 날짜만 반환 (단일 일정으로 처리)
            return [start_datetime]
    
    def rrule_to_text(self, rrule_string, start_datetime):
        """
        RRULE 문자열을 사용자가 읽기 쉬운 텍스트로 변환
        
        Args:
            rrule_string (str): RRULE 문자열
            start_datetime (datetime): 시작 날짜/시간
            
        Returns:
            str: 사용자가 읽기 쉬운 반복 규칙 텍스트
        """
        try:
            if not rrule_string:
                return "반복 안 함"
            
            # RRULE 문자열 정규화
            if not rrule_string.startswith('RRULE:'):
                rrule_string = 'RRULE:' + rrule_string
            
            # RRULE 파싱은 텍스트 변환에 필요하지 않으므로 문자열 분석만 사용
            
            # 기본 반복 주기 텍스트 생성
            base_text = ""
            interval = self._extract_interval(rrule_string)
            
            if 'FREQ=DAILY' in rrule_string:
                if interval > 1:
                    base_text = f"{interval}일마다"
                else:
                    base_text = "매일"
            elif 'FREQ=WEEKLY' in rrule_string:
                if interval > 1:
                    base_text = f"{interval}주마다"
                else:
                    base_text = "매주"
                # 요일 정보 추가
                weekdays = self._extract_weekdays(rrule_string)
                if weekdays:
                    base_text += f" {weekdays}"
            elif 'FREQ=MONTHLY' in rrule_string:
                if interval > 1:
                    base_text = f"{interval}개월마다"
                else:
                    base_text = "매월"
            elif 'FREQ=YEARLY' in rrule_string:
                if interval > 1:
                    base_text = f"{interval}년마다"
                else:
                    base_text = "매년"
            else:
                base_text = "사용자 정의"
            
            # 종료 조건 추가
            if 'COUNT=' in rrule_string:
                count = self._extract_count(rrule_string)
                return f"{base_text}, {count}회"
            elif 'UNTIL=' in rrule_string:
                until_date = self._extract_until_date(rrule_string)
                if until_date:
                    return f"{base_text}, {until_date}까지 반복"
                else:
                    return f"{base_text} 반복"
            else:
                return f"{base_text} 반복"
                
        except Exception as e:
            logger.error(f"Failed to convert RRULE to text: {e}")
            return "반복 일정"
    
    def _extract_count(self, rrule_string):
        """RRULE 문자열에서 COUNT 값 추출"""
        try:
            parts = rrule_string.split(';')
            for part in parts:
                if part.startswith('COUNT='):
                    return part.split('=')[1]
        except:
            pass
        return "여러"
    
    def _extract_interval(self, rrule_string):
        """RRULE 문자열에서 INTERVAL 값 추출"""
        try:
            parts = rrule_string.split(';')
            for part in parts:
                if part.startswith('INTERVAL='):
                    return int(part.split('=')[1])
        except:
            pass
        return 1
    
    def _extract_until_date(self, rrule_string):
        """RRULE 문자열에서 UNTIL 날짜 추출하고 한국어 형식으로 변환"""
        try:
            parts = rrule_string.split(';')
            for part in parts:
                if part.startswith('UNTIL='):
                    until_str = part.split('=')[1]
                    # UNTIL 형식: 20251225T235959Z
                    if len(until_str) >= 8:
                        year = until_str[:4]
                        month = until_str[4:6]
                        day = until_str[6:8]
                        return f"{year}년 {int(month)}월 {int(day)}일"
        except Exception as e:
            logger.error(f"Failed to parse UNTIL date: {e}")
        return None
    
    def _extract_weekdays(self, rrule_string):
        """RRULE 문자열에서 BYDAY 값 추출하고 한국어로 변환"""
        weekday_map = {
            'MO': '월요일', 'TU': '화요일', 'WE': '수요일', 'TH': '목요일',
            'FR': '금요일', 'SA': '토요일', 'SU': '일요일'
        }
        
        try:
            parts = rrule_string.split(';')
            for part in parts:
                if part.startswith('BYDAY='):
                    days_str = part.split('=')[1]
                    days = days_str.split(',')
                    korean_days = []
                    for day in days:
                        # BYSETPOS가 있는 경우 숫자 제거 (예: -1SU -> SU)
                        clean_day = day.lstrip('-1234')
                        if clean_day in weekday_map:
                            korean_days.append(weekday_map[clean_day])
                    
                    if korean_days:
                        if len(korean_days) == 1:
                            return korean_days[0]
                        else:
                            return ', '.join(korean_days)
        except Exception as e:
            logger.error(f"Failed to parse weekdays: {e}")
        
        return ""