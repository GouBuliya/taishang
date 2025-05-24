# start.py
"""
一键启动 Gemini 金融智能体 GUI 的入口脚本。
自动激活虚拟环境并运行主界面。
"""
import os
import sys
import subprocess
import argparse
import platform
import logging

# 每次运行前自动设置环境变量（仅当前进程和子进程有效）  
os.environ['GEMINI_API_KEY'] = "AIzaSyAP8WsfGTPJ2TOB8Hlnqcby6VZzlUXMQpg"
# === 新增：设置代理环境变量 ===
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:1080'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:1080'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "gemini_quant.log")
MODULE_TAG = "[start] "
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuant")

if platform.system() == "Windows":
    VENV_PYTHON = "python"
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')
    ADD_DATA_SEP = ';'
elif platform.system() == "Darwin":  # macOS
    VENV_PYTHON = "python3"
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')
    ADD_DATA_SEP = ':'
else:
    VENV_PYTHON = "python3"
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')
    ADD_DATA_SEP = ':'

parser = argparse.ArgumentParser(description='Gemini 金融智能体启动器')
# === 移除 Gemini API 相关命令行参数和直连逻辑 ===

# 启动前清空旧日志文件
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.truncate(0)

if not os.path.exists(GUI_PATH):
    logger.error(MODULE_TAG + f'未找到主界面文件: {GUI_PATH}')
    print(f'未找到主界面文件: {GUI_PATH}')
    sys.exit(1)

try:
    logger.info(MODULE_TAG + f"正在启动: {VENV_PYTHON} {GUI_PATH}")
    result = subprocess.run([VENV_PYTHON, GUI_PATH], check=True)
    logger.info(MODULE_TAG + f"GUI进程已退出，返回码: {result.returncode}")
    print(f"GUI进程已退出，返回码: {result.returncode}")
except subprocess.CalledProcessError as e:
    logger.error(MODULE_TAG + f'启动GUI失败: {e}')
    print(f'启动GUI失败: {e}')
    sys.exit(e.returncode)
except Exception as e:
    logger.error(MODULE_TAG + f'未知错误: {e}')
    print(f'未知错误: {e}')
    sys.exit(2)
