import psutil
import os

def is_telegram_bot_running():
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = ' '.join(p.info['cmdline'])
            if 'telegram_bot.py' in cmdline and str(os.getpid()) != str(p.info['pid']):
                return True
        except Exception:
            continue
    return False
