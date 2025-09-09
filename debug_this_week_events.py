#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이번 주 일정 편집 문제 디버깅 스크립트

2025-09-09 (월) - 이번 주 일정 생성/편집이 안되는 문제 원인 파악
"""

import datetime
import sys
import os
import logging
from dateutil import tz

# 프로젝트 루트 디렉토리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import *
from data_manager import DistanceBasedCachingManager

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_this_week.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def analyze_this_week_dates():
    """이번 주 날짜 범위 분석"""
    logger.info("=== 이번 주 날짜 분석 시작 ===")
    
    today = datetime.date.today()
    logger.info(f"오늘: {today} ({today.strftime('%A')})")
    
    # 이번 주의 시작과 끝 (월요일 기준)
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)
    logger.info(f"이번 주 (월~일): {start_of_week} ~ {end_of_week}")
    
    # 이번 주의 시작과 끝 (일요일 기준)
    days_since_sunday = (today.weekday() + 1) % 7
    start_of_week_sun = today - datetime.timedelta(days=days_since_sunday)
    end_of_week_sun = start_of_week_sun + datetime.timedelta(days=6)
    logger.info(f"이번 주 (일~토): {start_of_week_sun} ~ {end_of_week_sun}")
    
    # 문제가 되는 날짜들 개별 확인
    problem_dates = []
    for i in range(7):
        date = start_of_week + datetime.timedelta(days=i)
        problem_dates.append(date)
        logger.info(f"  {date} ({date.strftime('%A')})")
    
    return problem_dates

def test_event_creation_for_dates(dates):
    """특정 날짜들에 대해 이벤트 생성 테스트"""
    logger.info("=== 이벤트 생성 테스트 시작 ===")
    
    # 가상의 이벤트 데이터 생성 (로컬 캘린더용)
    for i, date in enumerate(dates):
        logger.info(f"\n--- {date} 테스트 ---")
        
        # 로컬 이벤트 데이터
        event_data_local = {
            'summary': f'디버깅 테스트 {date}',
            'description': f'이번 주 문제 디버깅용 - {date}',
            'start': {
                'dateTime': datetime.datetime.combine(date, datetime.time(10, 0)).isoformat(),
                'timeZone': 'Asia/Seoul'
            },
            'end': {
                'dateTime': datetime.datetime.combine(date, datetime.time(11, 0)).isoformat(),
                'timeZone': 'Asia/Seoul'
            },
            'provider': 'LocalCalendarProvider',
            'calendarId': 'local'
        }
        
        logger.info(f"로컬 이벤트 데이터: {event_data_local}")
        
        # Google 이벤트 데이터 (만약 Google 캘린더가 있다면)
        event_data_google = {
            'summary': f'구글 디버깅 테스트 {date}',
            'description': f'이번 주 문제 디버깅용 Google - {date}',
            'start': {
                'dateTime': datetime.datetime.combine(date, datetime.time(14, 0)).isoformat(),
                'timeZone': 'Asia/Seoul'
            },
            'end': {
                'dateTime': datetime.datetime.combine(date, datetime.time(15, 0)).isoformat(),
                'timeZone': 'Asia/Seoul'
            },
            'provider': 'GoogleCalendarProvider',
            'calendarId': 'primary'  # 기본값, 실제로는 설정에서 가져와야 함
        }
        
        logger.info(f"구글 이벤트 데이터: {event_data_google}")
        
        # 실제 이벤트 생성은 여기서는 시뮬레이션만 (실제 생성하면 중복 생성될 수 있음)
        logger.info("실제 생성은 시뮬레이션만 진행")

def analyze_data_manager_setup():
    """DataManager 초기화 및 상태 분석"""
    logger.info("=== DataManager 초기화 분석 ===")
    
    try:
        # 실제 데이터 매니저 없이 설정만 체크
        logger.info("설정 정보:")
        logger.info(f"  DEFAULT_SYNC_INTERVAL: {DEFAULT_SYNC_INTERVAL}")
        logger.info(f"  DEFAULT_NOTIFICATION_MINUTES: {DEFAULT_NOTIFICATION_MINUTES}")
        
        # 날짜 관련 설정 확인
        today = datetime.date.today()
        current_month_key = f"{today.year}-{today.month:02d}"
        logger.info(f"현재 월 키: {current_month_key}")
        
    except Exception as e:
        logger.error(f"DataManager 분석 중 오류: {e}", exc_info=True)

def check_timezone_conversion():
    """시간대 변환 관련 문제 확인"""
    logger.info("=== 시간대 변환 분석 ===")
    
    # 현재 시간을 여러 형식으로 확인
    now = datetime.datetime.now()
    logger.info(f"로컬 시간: {now}")
    logger.info(f"로컬 시간 ISO: {now.isoformat()}")
    
    # UTC 변환
    utc_now = datetime.datetime.now(tz.UTC)
    logger.info(f"UTC 시간: {utc_now}")
    logger.info(f"UTC 시간 ISO: {utc_now.isoformat()}")
    
    # KST 변환
    kst_tz = tz.gettz('Asia/Seoul')
    kst_now = datetime.datetime.now(kst_tz)
    logger.info(f"KST 시간: {kst_now}")
    logger.info(f"KST 시간 ISO: {kst_now.isoformat()}")
    
    # 이번 주 날짜들을 다양한 시간대로 변환 테스트
    today = datetime.date.today()
    test_datetime = datetime.datetime.combine(today, datetime.time(10, 0))
    
    logger.info(f"\n테스트 날짜/시간: {test_datetime}")
    
    # 시간대별 변환 테스트
    test_dt_kst = test_datetime.replace(tzinfo=kst_tz)
    test_dt_utc = test_dt_kst.astimezone(tz.UTC)
    
    logger.info(f"KST로 설정: {test_dt_kst}")
    logger.info(f"UTC로 변환: {test_dt_utc}")

def main():
    """메인 실행 함수"""
    logger.info("🚨 이번 주 일정 편집 문제 디버깅 시작")
    logger.info("=" * 60)
    
    try:
        # 1. 이번 주 날짜 분석
        problem_dates = analyze_this_week_dates()
        
        # 2. 시간대 변환 확인
        check_timezone_conversion()
        
        # 3. 데이터 매니저 설정 분석
        analyze_data_manager_setup()
        
        # 4. 이벤트 생성 테스트 (시뮬레이션)
        test_event_creation_for_dates(problem_dates)
        
        logger.info("=" * 60)
        logger.info("🎯 디버깅 스크립트 완료")
        logger.info("결과 분석을 위해 debug_this_week.log 파일을 확인하세요.")
        
    except Exception as e:
        logger.error(f"디버깅 스크립트 실행 중 오류: {e}", exc_info=True)

if __name__ == "__main__":
    main()