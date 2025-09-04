"""
로깅 설정 모듈
모든 디버그 출력을 통합 관리
"""
import logging
import sys
from pathlib import Path

def setup_logger():
    """로거 설정"""
    # 루트 로거 설정
    root_logger = logging.getLogger()
    
    # 이미 핸들러가 있으면 중복 추가 방지
    if root_logger.handlers:
        return root_logger
    
    # 로그 레벨 설정 (개발 시: DEBUG, 배포 시: INFO)
    root_logger.setLevel(logging.INFO)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 포매터 설정
    formatter = logging.Formatter(
        '[%(levelname)s] %(name)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    return root_logger

# 모듈별 로거 생성 함수
def get_logger(name):
    """모듈별 로거 가져오기"""
    return logging.getLogger(name)

# 전역 로거 초기화
setup_logger()