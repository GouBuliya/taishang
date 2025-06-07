from functools import wraps
import time
from typing import Callable, Any

def retry_on_error(max_retries: int = 3, delay: float = 1.0) -> Callable:
    """
    装饰器：在发生错误时重试函数
    :param max_retries: 最大重试次数
    :param delay: 重试间隔（秒）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:  # 如果还有重试机会
                        time.sleep(delay)
                        continue
            raise last_error  # 重试用尽后，抛出最后一次的错误
        return wrapper
    return decorator
