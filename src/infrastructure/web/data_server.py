# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "selenium",
#     "undetected-chromedriver",
#     "flask",
#     "requests",
#     "python-okx",
#     "okx",
# ]
# ///

#使用方式：
#uv run --python 3.11 src/screenshot_server.py

import time
import os
from datetime import datetime
from selenium import webdriver # type: ignore
from selenium.webdriver.common.by import By # type: ignore
from selenium.webdriver.common.keys import Keys # type: ignore
from selenium.webdriver.common.action_chains import ActionChains # type: ignore
from selenium.webdriver.support.ui import WebDriverWait # type: ignore
from selenium.webdriver.support import expected_conditions as EC # type: ignore
import undetected_chromedriver as uc # type: ignore
import shutil
import subprocess
import gc
import logging
import json
from flask import Flask, request, jsonify # type: ignore
from selenium.common.exceptions import WebDriverException # type: ignore # Import WebDriverException
# 确保项目根目录在Python路径中（避免重复添加）
import sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.data.collectors.macro_factor_collector import get_fear_greed_index # Import the FGI function
from src.core.path_manager import path_manager
import threading # Import the threading module
from typing import Optional
import argparse

app = Flask(__name__)
driver: Optional[webdriver.Chrome] = None

# 从项目根目录加载配置
config_path = os.path.join(project_root, "config/config.json")
config = json.load(open(config_path, "r"))

TRADINGVIEW_URL = 'https://cn.tradingview.com/chart/mJjA2OR8/?symbol=OKX%3AETHUSD.P'
SAVE_DIR = path_manager.get_screenshots_path()
DEFAULT_USER_DATA_DIR = path_manager.get_browser_profile_path()
PROXY = config["proxy"]["http_proxy"]
LOG_FILE = path_manager.get_log_path("main_log")

# FGI 缓存
FGI_SERVER_CACHE: dict[str, int | float | None] = {"value": None, "timestamp": None}
FGI_SERVER_CACHE_DURATION = 900 # 缓存有效期 900 秒 (15 分钟)

logging.basicConfig(
    level=logging.INFO,
    format='[数据服务器][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuantScreenshotServer")

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(DEFAULT_USER_DATA_DIR, exist_ok=True)
downloads_dir = path_manager.get_downloads_path()
os.makedirs(downloads_dir, exist_ok=True)

def clean_user_data_dir(user_data_dir: str):
    """清理Chrome用户数据目录中的缓存子目录。"""
    for sub in ['Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'GrShaderCache']:
        path = os.path.join(user_data_dir, sub)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                logger.info(f'已清理缓存目录: {path}')
            except Exception as e:
                logger.error(f'清理缓存目录失败: {path}, {e}')

def safe_rmtree(path: str, max_retry: int = 3):
    """带重试机制的安全删除目录树功能。"""
    for i in range(max_retry):
        try:
            shutil.rmtree(path)
            return True
        except Exception as e:
            logger.error(f"第{i+1}次删除目录失败: {path}, {e}")
            time.sleep(1)
    logger.error(f"多次尝试后仍无法删除目录: {path}，请手动清理！")
    return False

def clean_memory_on_start():
    """在启动时尝试清理系统内存和缓存。"""
    logger.info('启动时主动清理内存...')
    gc.collect()
    try:
        os.system('sync; echo 3 > /proc/sys/vm/drop_caches')
        logger.info('已尝试释放 Linux 系统缓存')
    except Exception as e:
        logger.error(f'释放系统缓存失败: {e}')

def update_user_profile():
    """使用预设的干净profile覆盖当前的用户profile。"""
    src = path_manager.get_browser_profile_path("chrome_profile_copy")
    dst = path_manager.get_browser_profile_path("chrome_profile")
    if os.path.exists(src): 
        if os.path.exists(dst):
            safe_rmtree(dst)
        shutil.copytree(src, dst)
        logger.info(f'已用 {src} 覆盖 {dst}')
    else:
        logger.warning(f'chrome_profile_copy 不存在，跳过更新用户配置。请确保该目录存在，以便初始化。')

def _build_chrome_options() -> uc.ChromeOptions:
    """构建并返回Chrome浏览器选项。"""
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument('--window-size=800,600')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-application-cache')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument(f'--user-data-dir={DEFAULT_USER_DATA_DIR}')
    
    prefs = {
        "download.default_directory": downloads_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument('--disable-popup-blocking')
    
    if PROXY:
        chrome_options.add_argument(f'--proxy-server={PROXY}')
    
    logger.info(f'已构建Chrome选项，用户数据目录: {DEFAULT_USER_DATA_DIR}')
    return chrome_options

def initialize_browser(headless_mode: bool = True):
    """
    初始化或重新连接浏览器实例，增加重试机制处理连接错误。

    Args:
        headless_mode (bool): 是否以无头模式运行浏览器。默认为True。
    """
    global driver
    clean_memory_on_start()
    update_user_profile() 

    max_retries = 9999999 
    retry_delay = 5 

    for attempt in range(max_retries):
        logger.info(f"尝试启动新的Chrome浏览器 (第 {attempt + 1}次)...")
        clean_user_data_dir(DEFAULT_USER_DATA_DIR)
        chrome_options = _build_chrome_options()

        try:
            driver = uc.Chrome(options=chrome_options, headless=headless_mode, version_main=136)
            logger.info(f"已启动新的Chrome浏览器 (headless={headless_mode})，准备导航...")
            driver.get(TRADINGVIEW_URL)
            logger.info(f"成功导航到页面: {driver.current_url}")
            return True 
        except WebDriverException as e:
            logger.error(f"启动Chrome或导航时发生WebDriverException: {e}", exc_info=True)
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                if attempt > 0: 
                    retry_delay *= 2
                clean_memory_on_start()
                update_user_profile()
                time.sleep(retry_delay)
            else:
                logger.critical("达到最大重试次数，浏览器初始化失败。")
                return False 
        except Exception as e:
            logger.critical(f"启动Chrome时发生未知致命错误: {e}", exc_info=True)
            return False 

def _find_latest_screenshot(timeframe: str) -> Optional[str]:
    """在下载目录中查找最新的、有效的截图文件。"""
    now_ts = time.time()
    
    files = [f for f in os.listdir(downloads_dir) if f.startswith('ETHUSD.P_') and f.endswith('.png')]
    
    valid_files = []
    for f in files:
        fpath = os.path.join(downloads_dir, f)
        mtime = os.path.getmtime(fpath)
        if now_ts - mtime < 120 and os.path.getsize(fpath) > 1024:
            valid_files.append((f, mtime))
    
    if not valid_files:
        logger.warning(f"在下载目录中未找到 {timeframe}m 周期的有效截图。")
        return None
        
    valid_files.sort(key=lambda x: x[1], reverse=True)
    latest_file = valid_files[0][0]
    
    src_path = os.path.join(downloads_dir, latest_file)
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    dst_path = os.path.join(SAVE_DIR, f'tradingview_{timeframe}m_{now}.png')
    
    try:
        shutil.copy2(src_path, dst_path)
        return os.path.abspath(dst_path)
    except IOError as e:
        logger.error(f"复制截图文件失败: 从 {src_path} 到 {dst_path}，错误: {e}")
        return None

def set_timeframe_and_screenshot(timeframe: str) -> Optional[str]:
    """
    设置时间周期并进行截图。
    
    参数:
        timeframe: str - 需要设置的时间周期（如 "15" 表示15分钟周期）
    
    返回:
        str | None - 截图文件路径或None（如果失败）
    """
    global driver
    if not driver:
        logger.error("set_timeframe_and_screenshot调用时浏览器驱动无效。")
        return None

    try:
        body = driver.find_element(By.TAG_NAME, 'body')
        body.click()
        time.sleep(2) 

        actions = ActionChains(driver)
        actions.send_keys(timeframe)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        logger.info(f'已发送时间周期切换指令: {timeframe}')
        time.sleep(1)

        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).key_up(Keys.CONTROL).perform()
        logger.info(f'已为 {timeframe}m 周期触发截图快捷键')
        time.sleep(2)
        
        return _find_latest_screenshot(timeframe)
        
    except Exception as e:
        logger.error(f'设置 {timeframe}m 周期或截图时发生异常: {e}', exc_info=True)
        return None

def take_screenshot_action():
    """
    执行多个时间周期的截图操作并返回文件路径。
    """
    global driver
    if not driver:
        logger.error("浏览器实例未初始化或已失效。")
        return None

    try:
        old_files = [f for f in os.listdir(downloads_dir) if f.startswith('ETHUSD.P_') and f.endswith('.png')]
        for f in old_files:
            try:
                os.remove(os.path.join(downloads_dir, f))
            except Exception as e:
                logger.error(f'删除旧截图失败: {f}, {e}')
        logger.info('旧截图已清理，开始截图流程...')

        if driver.current_url != TRADINGVIEW_URL and not driver.current_url.startswith("https://cn.tradingview.com/chart/"):
            logger.info(f'当前页面不是目标页面，重新导航到: {TRADINGVIEW_URL}')
            driver.get(TRADINGVIEW_URL)
            try:
                logger.info('等待页面加载完成...')
                WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.ID, "chart-page-content"))
                )
                logger.info('页面加载完成，关键元素可见。')
                time.sleep(5) 
            except Exception as e:
                logger.error(f'等待页面加载超时或元素未找到: {e}')
                return None

        timeframes = ["15", "60", "240"]  # 15分钟、1小时、4小时
        screenshots = {}
        
        for tf in timeframes:
            filepath = set_timeframe_and_screenshot(tf)
            if filepath:
                screenshots[tf] = filepath
                logger.info(f'{tf}分钟周期截图成功: {filepath}')
            else:
            #尝试重试：
                logger.error(f'{tf}分钟周期截图失败尝试重试...')
                filepath = set_timeframe_and_screenshot(tf)
                if filepath:
                    screenshots[tf] = filepath
                    logger.info(f'重试成功: {filepath}')
                else:
                    logger.error(f'{tf}分钟周期截图重试失败，跳过此周期')
        logger.info('所有时间周期的截图操作已完成。')
        if screenshots:
            return {
                "status": "success",
                "screenshots": screenshots
            }
        else:
            logger.error('所有时间周期的截图均失败')
            return None

    except Exception as e:
        logger.error(f'截图过程中发生错误: {e}')
        return None

@app.route('/screenshot', methods=['GET'])
def get_screenshot():
    logger.info("收到截图请求。")
    result = take_screenshot_action()
    if result and isinstance(result, dict):
        return jsonify(result)  
    else:
        return jsonify({"status": "error", "message": "截图失败"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    健康检查端点。
    
    返回服务器状态、浏览器状态和缓存信息。
    """
    global driver
    browser_status = "ok"
    details = "Browser is running."
    
    if driver is None:
        browser_status = "error"
        details = "Browser instance is not initialized."
    else:
        try:
            _ = driver.current_url
        except WebDriverException:
            browser_status = "error"
            details = "Browser session is not responsive. May need a restart."

    return jsonify({
        "status": "ok" if browser_status == "ok" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "browser": {
            "status": browser_status,
            "details": details
        },
        "fgi_cache": {
            "cached": FGI_SERVER_CACHE["value"] is not None,
            "timestamp": FGI_SERVER_CACHE["timestamp"],
            "expires_in_seconds": FGI_SERVER_CACHE_DURATION - (time.time() - FGI_SERVER_CACHE["timestamp"]) if FGI_SERVER_CACHE["timestamp"] else None
        }
    })

def prefetch_fgi_cache():
    """
    后台线程任务，用于预热和定期刷新FGI缓存。
    """
    def task():
        while True:
            try:
                logger.info("正在更新FGI缓存...")
                fgi_value = get_fear_greed_index()
                if fgi_value is not None:
                    FGI_SERVER_CACHE["value"] = fgi_value
                    FGI_SERVER_CACHE["timestamp"] = time.time()
                    logger.info(f"FGI缓存已更新，新值为: {fgi_value}")
                else:
                    logger.warning("未能获取FGI值，缓存未更新。")
            except Exception as e:
                logger.error(f"更新FGI缓存时发生错误: {e}")
            
            time.sleep(FGI_SERVER_CACHE_DURATION)
            
    thread = threading.Thread(target=task, daemon=True)
    thread.start()
    logger.info("FGI缓存预热线程已启动。")

@app.route('/fgi', methods=['GET'])
def get_fgi():
    """
    通过 GET 请求获取恐惧贪婪指数（FGI），使用缓存机制。
    """
    global FGI_SERVER_CACHE
    current_time = time.time()

    if FGI_SERVER_CACHE["value"] is not None and FGI_SERVER_CACHE["timestamp"] is not None and \
       (current_time - FGI_SERVER_CACHE["timestamp"] < FGI_SERVER_CACHE_DURATION):
        logger.info(f"从服务器缓存中获取恐惧贪婪指数: {FGI_SERVER_CACHE['value']}")
        return jsonify({"status": "success", "fgi": FGI_SERVER_CACHE["value"]})

    logger.info("缓存无效，从源获取恐惧贪婪指数...")
    fgi_value = get_fear_greed_index()

    if fgi_value is not None:
        # 更新缓存
        FGI_SERVER_CACHE["value"] = fgi_value
        FGI_SERVER_CACHE["timestamp"] = current_time
        logger.info(f"成功获取并更新缓存的 FGI: {fgi_value}")
        return jsonify({"status": "success", "fgi": fgi_value})
    else:
        logger.error("从源获取 FGI 失败。")
        return jsonify({"status": "error", "message": "获取恐惧贪婪指数失败"}), 500

def main():
    """
    服务器主入口函数。
    """
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Data Server for Trading System')
    parser.add_argument('--head', action='store_false', dest='headless', help='Run browser in headed mode (visible UI).')
    parser.set_defaults(headless=True)
    args = parser.parse_args()

    if initialize_browser(headless_mode=args.headless):
        logger.info("浏览器初始化成功。")
        prefetch_fgi_cache()
        app.run(host='0.0.0.0', port=5002)
    else:
        logger.critical("浏览器初始化失败，无法启动Flask服务器。")
        sys.exit(1)

if __name__ == '__main__':
    logger.info("截图服务器正在启动...")
    http_proxy = config["proxy"]["http_proxy"]
    https_proxy = config["proxy"]["https_proxy"]
    os.environ["http_proxy"] = http_proxy
    os.environ["https_proxy"] = https_proxy

    try:
        subprocess.run(['pkill', '-9', 'chrome'], check=False)
        logger.info('已执行 pkill chrome')
    except Exception as e:
        logger.warning(f'pkill chrome 失败或没有运行中的Chrome进程: {e}')

    main()
