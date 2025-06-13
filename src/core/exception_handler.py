# src/core/exception_handler.py
import logging
import traceback
import sys
from typing import Any, Optional, Type

logger = logging.getLogger("GeminiQuant")

class TaishangException(Exception):
    """太熵系统自定义异常基类"""
    pass

class DataCollectionError(TaishangException):
    """数据收集异常"""
    pass

class AIModelError(TaishangException):
    """AI模型异常"""
    pass

class TradingError(TaishangException):
    """交易异常"""
    pass

class ConfigurationError(TaishangException):
    """配置异常"""
    pass

def handle_exception(exc_type: Type[BaseException], exc_value: BaseException, exc_traceback: Optional[Any]) -> None:
    """
    全局异常处理器
    
    Args:
        exc_type: 异常类型
        exc_value: 异常值
        exc_traceback: 异常追踪
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # 保持KeyboardInterrupt的默认行为
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
        
    # 记录未捕获的异常
    logger.critical(
        "发生未捕获的异常",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    
    # 根据异常类型采取不同的处理策略
    if isinstance(exc_value, TaishangException):
        logger.error(f"太熵系统异常: {exc_value}")
    else:
        logger.error(f"系统异常: {exc_value}")

def setup_global_exception_handler():
    """设置全局异常处理器"""
    sys.excepthook = handle_exception
    logger.info("全局异常处理器已设置")

def log_and_raise(exception: Exception, message: str = "") -> None:
    """
    记录异常并重新抛出
    
    Args:
        exception: 要处理的异常
        message: 额外的错误信息
    """
    full_message = f"{message}: {exception}" if message else str(exception)
    logger.error(full_message, exc_info=True)
    raise exception

def safe_execute(func, default_return=None, error_message=""):
    """
    安全执行函数，捕获异常并返回默认值
    
    Args:
        func: 要执行的函数
        default_return: 出错时的默认返回值
        error_message: 错误日志前缀
        
    Returns:
        函数执行结果或默认值
    """
    try:
        return func()
    except Exception as e:
        if error_message:
            logger.error(f"{error_message}: {e}", exc_info=True)
        else:
            logger.error(f"安全执行失败: {e}", exc_info=True)
        return default_return 