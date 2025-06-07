import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import subprocess
import time
import requests
import logging
import json
from src.main_get import main as get_main # Import the main function from main_get.py

# Configure logging (similar to other scripts for consistency)
config = json.load(open("config/config.json", "r"))
LOG_FILE = config["main_log_path"]

# Prevent duplicate handlers
if not logging.getLogger("GeminiQuant").handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[主控脚本][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

logger = logging.getLogger("GeminiQuant")

DATA_SERVER_URL = "http://127.0.0.1:5002"
HEALTH_ENDPOINT = f"{DATA_SERVER_URL}/health"

def wait_for_server(url, timeout=60, retry_interval=5):
    """
    等待指定的URL返回健康状态。
    """
    logger.info(f"正在等待服务器启动并响应健康检查: {url}")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=retry_interval) # Use retry_interval as request timeout
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    logger.info("服务器健康检查通过。")
                    return True
                else:
                    logger.warning(f"服务器返回非'ok'状态: {data.get('status')}")
            else:
                logger.warning(f"服务器返回非200状态码: {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.info(f"无法连接到服务器，等待 {retry_interval} 秒后重试...")
        except requests.exceptions.Timeout:
             logger.warning(f"健康检查请求超时，等待 {retry_interval} 秒后重试...")
        except Exception as e:
            logger.error(f"健康检查过程中发生未知错误: {e}")

        time.sleep(retry_interval)

    logger.error("等待服务器超时，服务器未能成功启动或响应健康检查。")
    return False

def restart_data_server():
    """
    重启数据服务器。
    """
    logger.info("正在重启数据服务器...")
    # 尝试杀死现有进程
    try:
        # Use pkill with -f to match the full command line
        subprocess.run(['pkill', '-f', 'src/data_server.py'], check=False)
        logger.info('已尝试杀死现有数据服务器进程。')
    except Exception as e:
        logger.warning(f'杀死数据服务器进程失败或没有运行中的进程: {e}')

    # 启动新的服务器进程
    # Use subprocess.Popen to run in the background
    try:
        # Assuming uv is in the PATH and the script is run from the workspace root
        server_process = subprocess.Popen(['uv', 'run', '--python', '3.11', 'src/data_server.py'])
        logger.info(f"已启动新的数据服务器进程，PID: {server_process.pid}")
        return server_process
    except Exception as e:
        logger.critical(f"启动数据服务器失败: {e}")
        return None

def run_gemini_api_caller():
    """
    运行 Gemini API 调用脚本。
    """
    logger.info("正在运行 Gemini API 调用脚本...")
    try:
        # Assuming uv is in the PATH and the script is run from the workspace root
        # Run in foreground, wait for completion
        result = subprocess.run(['uv', 'run', 'src/gemini_api_caller.py'], check=True)
        logger.info(f"Gemini API 调用脚本运行完成，返回码: {result.returncode}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Gemini API 调用脚本运行失败: {e}")
        return False
    except Exception as e:
        logger.error(f"运行 Gemini API 调用脚本时发生未知错误: {e}")
        return False

if __name__ == "__main__":
    # 1. 重启数据服务器
    server_process = restart_data_server()
    if server_process is None:
        logger.critical("数据服务器启动失败，主控脚本退出。")
        exit(1)

    # 2. 等待服务器启动完成并自检通过
    # Give the server a moment to start listening before health checks
    time.sleep(15) # Initial wait
    if not wait_for_server(HEALTH_ENDPOINT, timeout=120, retry_interval=10): # Increased timeout and interval
        logger.critical("数据服务器未能在规定时间内启动并自检通过，主控脚本退出。")
        # Optionally terminate the server process if it's still running
        # server_process.terminate()
        exit(1)

    # 运行一次数据收集模块作为自检
    logger.info("服务器自检：运行数据收集模块 (main_get.py)...")
    get_main()
    logger.info("服务器自检：数据收集模块运行完成。")

    # 3. 循环运行数据收集和 Gemini API 调用脚本
    logger.info("开始循环运行数据收集和 Gemini API 调用脚本...")
    while True:
        logger.info("正在运行数据收集模块 (main_get.py)...")
        get_main() # Call the main function from main_get.py
        logger.info("数据收集模块运行完成。")

        run_gemini_api_caller()
        # Add a delay before the next run
        time.sleep(60) # Run approximately every minute (adjust as needed)