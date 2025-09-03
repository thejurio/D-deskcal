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
            
            # RRULE 파싱
            rule = rrulestr(rrule_string, dtstart=start_datetime)
            
            # 간단한 텍스트 변환 로직
            if 'FREQ=DAILY' in rrule_string:
                if 'COUNT=' in rrule_string:
                    count = self._extract_count(rrule_string)
                    return f"매일 {count}회 반복"
                else:
                    return "매일 반복"
            elif 'FREQ=WEEKLY' in rrule_string:
                if 'COUNT=' in rrule_string:
                    count = self._extract_count(rrule_string)
                    return f"매주 {count}회 반복"
                else:
                    return "매주 반복"
            elif 'FREQ=MONTHLY' in rrule_string:
                if 'COUNT=' in rrule_string:
                    count = self._extract_count(rrule_string)
                    return f"매월 {count}회 반복"
                else:
                    return "매월 반복"
            elif 'FREQ=YEARLY' in rrule_string:
                if 'COUNT=' in rrule_string:
                    count = self._extract_count(rrule_string)
                    return f"매년 {count}회 반복"
                else:
                    return "매년 반복"
            else:
                return "사용자 정의 반복"
                
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