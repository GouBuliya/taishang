import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import subprocess
import time
import datetime
import requests
import logging
import json
from src.main_get import main as get_main
from src.auto_trader import main as auto_trade_main  # 添加自动交易模块导入
import datetime

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

def run_auto_trader():
    """
    运行自动交易系统。
    """
    logger.info("正在运行自动交易系统...")
    try:
        auto_trade_main()  # 直接调用auto_trader.py中的main函数
        logger.info("自动交易系统运行完成")
        return True
    except Exception as e:
        logger.error(f"运行自动交易系统时发生错误: {e}")
        logger.exception(e)  # 打印详细的异常堆栈
        return False

if __name__ == "__main__":
    # 1. 重启数据服务器
    server_process = restart_data_server()
    if server_process is None:
        logger.critical("数据服务器启动失败，主控脚本退出。")
        exit(1)

    # 2. 等待服务器启动完成并自检通过
    time.sleep(15) # Initial wait
    if not wait_for_server(HEALTH_ENDPOINT, timeout=120, retry_interval=10): # Increased timeout and interval
        logger.critical("数据服务器未能在规定时间内启动并自检通过，主控脚本退出。")
        exit(1)

    # 运行一次数据收集模块作为自检
    logger.info("服务器自检：运行数据收集模块 (main_get.py)...")
    get_main()
    logger.info("服务器自检：数据收集模块运行完成。")

    # 3. 循环运行数据收集、Gemini API调用和自动交易系统
    logger.info("开始循环运行数据收集、Gemini API调用和自动交易系统...")
    
    def should_run():
        """检查是否应该执行交易流程"""
        current_minute = datetime.datetime.now().minute
        return current_minute % 15 == 0

    last_run_minute = -1  # 用于记录上次运行时的分钟数
    
    while True:
        try:
            current_minute = datetime.datetime.now().minute
            
            # 只有在当前分钟数是15的倍数，且不是上一分钟刚运行过时，才执行
            if current_minute % 15 == 0 and current_minute != last_run_minute:
                logger.info(f"当前时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，开始执行交易流程")
                
                # 运行数据收集
                logger.info("正在运行数据收集模块 (main_get.py)...")
                get_main()
                logger.info("数据收集模块运行完成。")

                # 运行Gemini API调用
                if run_gemini_api_caller():
                    # 只有在Gemini API调用成功时才运行自动交易
                    run_auto_trader()
                else:
                    logger.error("由于Gemini API调用失败，跳过自动交易")
                    
                last_run_minute = current_minute  # 更新上次运行时间
                logger.info(f"交易流程执行完成，等待下一个15分钟间隔")

        except Exception as e:
            logger.error(f"主循环执行过程中发生错误: {e}")
            logger.exception(e)

        # 添加短暂延迟避免CPU过度使用
        time.sleep(10)  # 每10秒检查一次时间
