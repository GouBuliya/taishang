# src/main.py
"""
太熵量化交易系统主入口。

该脚本负责初始化Python环境，将项目根目录添加到sys.path，
然后调用核心控制器（main_controller）来启动整个应用程序。
"""
import sys
import os

# 确保项目根目录在sys.path中，以便进行绝对导入（避免重复添加）
# TODO: 考虑使用更现代的打包方式（如pyproject.toml和src布局），
# 这样可能就不再需要在代码中手动修改sys.path。
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.main_controller import main

if __name__ == "__main__":
    main() 