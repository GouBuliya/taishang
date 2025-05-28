import os
import signal
import subprocess
import time
import psutil

# app.py的绝对路径
APP_PATH = os.path.join(os.path.dirname(__file__), 'code/web_gui/app.py')
PYTHON_EXEC = 'python3'

def kill_app_and_children():
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            if 'app.py' in cmdline:
                # 先杀子进程
                children = proc.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except Exception:
                        pass
                # 再杀本体
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed

def start_app():
    # 以nohup方式后台启动
    subprocess.Popen([PYTHON_EXEC, APP_PATH], stdout=open('app_stdout.log', 'a'), stderr=open('app_stderr.log', 'a'), preexec_fn=os.setpgrp)
    print(f"已重启: {PYTHON_EXEC} {APP_PATH}")

def main():
    print("正在查杀所有app.py相关进程...")
    killed = kill_app_and_children()
    print(f"已杀死 {killed} 个app.py相关进程。等待2秒...")
    time.sleep(2)
    print("正在重启app.py...")
    start_app()
    print("操作完成。日志见app_stdout.log/app_stderr.log")

if __name__ == '__main__':
    main() 