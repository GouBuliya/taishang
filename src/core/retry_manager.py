# src/core/retry_manager.py
import time
import logging
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger("GeminiQuant")

def retry(max_tries: int = 3, delay_seconds: float = 1, backoff: float = 2, exceptions: tuple = (Exception,)):
    """
    重试装饰器，实现指数退避重试机制
    
    Args:
        max_tries: 最大尝试次数
        delay_seconds: 初始延迟时间（秒）
        backoff: 退避因子
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay_seconds
            
            for attempt in range(max_tries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_tries - 1:
                        logger.error(f"重试失败，已达到最大尝试次数 {max_tries}: {e}")
                        raise e
                    
                    logger.warning(f"第 {attempt + 1} 次尝试失败: {e}，{current_delay:.1f}秒后重试")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
            # 这行代码理论上不会执行到，但为了类型安全添加
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

class RetryManager:
    """重试管理器类"""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """
        使用指数退避重试执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        last_exception = None
        delay = 1.0
        
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self.max_retries - 1:
                    logger.error(f"重试管理器：已达到最大重试次数 {self.max_retries}")
                    raise e
                
                logger.warning(f"重试管理器：第 {attempt + 1} 次尝试失败: {e}，{delay}秒后重试")
                time.sleep(delay)
                delay *= self.backoff_factor
        
        if last_exception:
            raise last_exception 