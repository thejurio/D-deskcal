# safety_wrapper.py
"""
안전한 메소드 실행을 위한 데코레이터 및 유틸리티
프로그램의 갑작스러운 종료를 방지하기 위한 예외 처리 래퍼들
"""

import functools
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


def safe_execute(
    default_return: Any = None,
    log_level: str = "error",
    reraise: bool = False,
    context: Optional[str] = None
):
    """
    안전한 메소드 실행을 위한 데코레이터
    
    Args:
        default_return: 예외 발생 시 반환할 기본값
        log_level: 로깅 레벨 ("debug", "info", "warning", "error", "critical")
        reraise: True일 경우 예외를 다시 발생시킴
        context: 추가 컨텍스트 정보
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_name = func.__name__
                class_name = ""
                
                # 메소드인 경우 클래스 이름 추출
                if args and hasattr(args[0], '__class__'):
                    class_name = f"{args[0].__class__.__name__}."
                
                error_context = context or f"{class_name}{func_name}"
                error_msg = f"Exception in {error_context}: {type(e).__name__}: {e}"
                
                # 지정된 레벨로 로깅
                log_func = getattr(logger, log_level, logger.error)
                log_func(error_msg, exc_info=True)
                
                if reraise:
                    raise
                
                return default_return
        return wrapper
    return decorator


def safe_thread_execute(
    default_return: Any = None,
    context: Optional[str] = None
):
    """
    스레드에서 안전한 실행을 위한 데코레이터
    스레드 내부에서 발생한 예외로 인한 프로그램 종료를 방지
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                func_name = func.__name__
                error_context = context or f"Thread execution: {func_name}"
                
                logger.error(
                    f"Thread exception in {error_context}: {type(e).__name__}: {e}",
                    exc_info=True
                )
                
                return default_return
        return wrapper
    return decorator


def safe_cleanup(func: Callable) -> Callable:
    """
    정리(cleanup) 작업을 위한 안전한 실행 데코레이터
    정리 작업 중 예외가 발생해도 다른 정리 작업이 계속될 수 있도록 함
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = func.__name__
            class_name = ""
            
            if args and hasattr(args[0], '__class__'):
                class_name = f"{args[0].__class__.__name__}."
            
            logger.warning(
                f"Cleanup exception in {class_name}{func_name}: {type(e).__name__}: {e}",
                exc_info=True
            )
            # 정리 작업은 예외를 다시 발생시키지 않음
            return None
    return wrapper


def safe_signal_handler(func: Callable) -> Callable:
    """
    PyQt 시그널 핸들러를 위한 안전한 실행 데코레이터
    시그널 처리 중 예외가 발생해도 프로그램이 종료되지 않도록 함
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = func.__name__
            class_name = ""
            
            if args and hasattr(args[0], '__class__'):
                class_name = f"{args[0].__class__.__name__}."
            
            logger.error(
                f"Signal handler exception in {class_name}{func_name}: {type(e).__name__}: {e}",
                exc_info=True
            )
            # 시그널 핸들러는 예외를 다시 발생시키지 않음
            return None
    return wrapper


class SafeContextManager:
    """
    예외 발생 시에도 안전하게 종료되는 컨텍스트 매니저
    """
    
    def __init__(self, enter_func: Callable, exit_func: Callable, context: str = "SafeContext"):
        self.enter_func = enter_func
        self.exit_func = exit_func
        self.context = context
        self.entered = False
    
    def __enter__(self):
        try:
            result = self.enter_func() if self.enter_func else None
            self.entered = True
            return result
        except Exception as e:
            logger.error(f"Exception entering {self.context}: {e}", exc_info=True)
            self.entered = False
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.entered and self.exit_func:
            try:
                self.exit_func()
            except Exception as e:
                logger.warning(f"Exception exiting {self.context}: {e}", exc_info=True)
        
        # 원래 예외가 있으면 그것을 우선시 (False 반환)
        return False