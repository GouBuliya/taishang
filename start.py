# start.py
"""
一键启动 Gemini 金融智能体 GUI 的入口脚本。
自动激活虚拟环境并运行主界面。
"""
import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python3')
GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')

if not os.path.exists(VENV_PYTHON):
    print('未检测到虚拟环境，请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt')
    sys.exit(1)

if not os.path.exists(GUI_PATH):
    print(f'未找到主界面文件: {GUI_PATH}')
    sys.exit(1)

try:
    subprocess.run([VENV_PYTHON, GUI_PATH], check=True)
except subprocess.CalledProcessError as e:
    print(f'启动GUI失败: {e}')
    sys.exit(e.returncode)
