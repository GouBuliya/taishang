# start.py
"""
一键启动 Gemini 金融智能体 GUI 的入口脚本。
自动激活虚拟环境并运行主界面。
支持 --test-gemini 命令行参数直接调用 Gemini API 进行链路测试。
"""
import os
import sys
import subprocess
import argparse
import platform

# 每次运行前自动设置环境变量（仅当前进程和子进程有效）
os.environ['GEMINI_API_KEY'] = "AIzaSyBcXoWRghWP1I83qVCDfOddZ7P-lpJg4zk"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if platform.system() == "Windows":
    VENV_PYTHON = os.path.join(BASE_DIR, '.venv', 'Scripts', 'python.exe')
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')
    ADD_DATA_SEP = ';'
elif platform.system() == "Darwin":  # macOS
    VENV_PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python3')
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')
    ADD_DATA_SEP = ':'
else:
    VENV_PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python3')
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')
    ADD_DATA_SEP = ':'

parser = argparse.ArgumentParser(description='Gemini 金融智能体启动器')
parser.add_argument('--test-gemini', type=str, help='直接调用 Gemini API，参数为JSON字符串')
parser.add_argument('--image', type=str, default=None, help='图片路径')
parser.add_argument('--model', type=str, default=None, help='Gemini模型名')
parser.add_argument('--api-key', type=str, default=None, help='Gemini API Key')
args = parser.parse_args()

if args.test_gemini:
    sys.path.insert(0, os.path.join(BASE_DIR, 'code'))
    from gemini_api_caller import call_gemini_api
    import json
    try:
        packaged_json = json.loads(args.test_gemini)
    except Exception as e:
        print(f'JSON解析失败: {e}')
        sys.exit(1)
    try:
        result = call_gemini_api(
            packaged_json=packaged_json,
            model_name=args.model if args.model else None,
            screenshot_path=args.image,
            api_key=args.api_key
        )
        print('Gemini API 返回:')
        print(result)
    except Exception as e:
        print(f'Gemini API 调用失败: {e}')
        sys.exit(1)
    sys.exit(0)

if not os.path.exists(VENV_PYTHON):
    print('未检测到虚拟环境，请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt')
    sys.exit(1)

if not os.path.exists(GUI_PATH):
    print(f'未找到主界面文件: {GUI_PATH}')
    sys.exit(1)

try:
    print(f"正在启动: {VENV_PYTHON} {GUI_PATH}")
    result = subprocess.run([VENV_PYTHON, GUI_PATH], check=True)
    print(f"GUI进程已退出，返回码: {result.returncode}")
except subprocess.CalledProcessError as e:
    print(f'启动GUI失败: {e}')
    sys.exit(e.returncode)
except Exception as e:
    print(f'未知错误: {e}')
    sys.exit(2)
