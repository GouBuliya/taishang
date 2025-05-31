import sys
import os
import subprocess
from psutil_check import is_telegram_bot_running

# 指定特定Python解释器
venv_python = "/usr/local/bin/python3.10"

def start_telegram_bot():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.join(base_dir, '..')
    bot_path = os.path.join(parent_dir, 'telegram_bot.py')
    if is_telegram_bot_running():
        print('Telegram Bot 已在运行，不再重复启动。')
        return
    subprocess.Popen([venv_python, bot_path])
    print('Telegram Bot 已启动。')
