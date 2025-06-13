# src/trading/utils/retry.py
import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger("GeminiQuant")

def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 1.5):
    """
    交易API重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避因子
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):  # +1 表示第一次不是重试
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"交易API重试失败，已达到最大重试次数 {max_retries}: {e}")
                        raise e
                    
                    logger.warning(f"交易API第 {attempt + 1} 次调用失败: {e}，{current_delay:.1f}秒后重试")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    
            # 这行代码理论上不会执行到，但为了类型安全添加
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator 