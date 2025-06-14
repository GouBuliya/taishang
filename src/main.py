# src/main.py
"""
太熵量化交易系统主入口。

该脚本负责初始化Python环境，将项目根目录添加到sys.path，
然后调用核心控制器（main_controller）来启动整个应用程序。
"""
import sys
import os

# 确保项目根目录在sys.path中，以便正确导入模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.main_controller import main as main_controller_main
from src.core.exception_handler import setup_global_exception_handler

def main():
    """
    系统主入口。
    为了统一和简化维护，此入口现在直接调用核心控制器。
    """
    # 设置全局异常处理
    setup_global_exception_handler()
    
    # 直接调用新的主控制器
    main_controller_main()

if __name__ == "__main__":
    main() 