# start.py
"""
一键启动 Gemini 金融智能体 GUI 的入口脚本。
自动激活虚拟环境并运行主界面。
"""
import os
import sys
import subprocess

def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    VENV_PYTHON = os.path.join(BASE_DIR, '.venv', 'bin', 'python3')
    GUI_PATH = os.path.join(BASE_DIR, 'code', 'quant_GUI.py')

    if not os.path.exists(VENV_PYTHON):
        print('未检测到虚拟环境，请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt')
        sys.exit(1)

    if not os.path.exists(GUI_PATH):
        print(f'未找到主界面文件: {GUI_PATH}')
        sys.exit(1)

    print(f"正在启动: {VENV_PYTHON} {GUI_PATH}")
    try:
        # 兼容Cookbook风格，支持环境变量传递
        env = os.environ.copy()
        # 支持命令行传递API Key（如有）
        if len(sys.argv) > 1 and sys.argv[1].startswith('AIza'):
            env['GEMINI_API_KEY'] = sys.argv[1]
            print(f"已通过命令行设置GEMINI_API_KEY: {sys.argv[1][:8]}...{sys.argv[1][-4:]}")
        result = subprocess.run([VENV_PYTHON, GUI_PATH], check=True, env=env)
        print(f"GUI进程已退出，返回码: {result.returncode}")
    except subprocess.CalledProcessError as e:
        print(f'启动GUI失败: {e}')
        sys.exit(e.returncode)
    except Exception as e:
        print(f'未知错误: {e}')
        sys.exit(2)

if __name__ == "__main__":
    main()
