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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import shutil
import subprocess
import gc
import logging
import json
from flask import Flask, request, jsonify
from selenium.common.exceptions import WebDriverException # Import WebDriverException
from get_data.macro_factor_collector import get_fear_greed_index # Import the FGI function
import threading # Import the threading module

app = Flask(__name__)

config = json.load(open("config/config.json", "r"))

TRADINGVIEW_URL = 'https://cn.tradingview.com/chart/mJjA2OR8/?symbol=OKX%3AETHUSD.P'
SAVE_DIR = config["cache_screenshot_path"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_USER_DATA_DIR = os.path.join(SCRIPT_DIR, 'chrome_profile')
PROXY = config["proxy"]["http_proxy"]
LOG_FILE = config["main_log_path"]

# FGI 缓存
FGI_SERVER_CACHE: dict[str, int | float | None] = {"value": None, "timestamp": None}
FGI_SERVER_CACHE_DURATION = 900 # 缓存有效期 900 秒 (15 分钟)

driver = None

logging.basicConfig(
    level=logging.INFO,
    format='[截图服务器][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuantScreenshotServer")

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(DEFAULT_USER_DATA_DIR, exist_ok=True)
downloads_dir = os.path.join(SCRIPT_DIR, 'downloads')
os.makedirs(downloads_dir, exist_ok=True)

def clean_user_data_dir(user_data_dir):
    for sub in ['Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'GrShaderCache']:
        path = os.path.join(user_data_dir, sub)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                logger.info(f'已清理缓存目录: {path}')
            except Exception as e:
                logger.error(f'清理缓存目录失败: {path}, {e}')

def safe_rmtree(path, max_retry=3):
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
    logger.info('启动时主动清理内存...')
    gc.collect()
    try:
        os.system('sync; echo 3 > /proc/sys/vm/drop_caches')
        logger.info('已尝试释放 Linux 系统缓存')
    except Exception as e:
        logger.error(f'释放系统缓存失败: {e}')

def update_user_profile():
    src = os.path.join(SCRIPT_DIR, 'chrome_profile_copy')
    dst = os.path.join(SCRIPT_DIR, 'chrome_profile')
    if os.path.exists(src): 
        if os.path.exists(dst):
            safe_rmtree(dst)
        shutil.copytree(src, dst)
        logger.info(f'已用 {src} 覆盖 {dst}')
    else:
        logger.warning(f'chrome_profile_copy 不存在，跳过更新用户配置。请确保该目录存在，以便初始化。')

def initialize_browser():
    """
    初始化或重新连接浏览器实例，增加重试机制处理连接错误。
    """
    global driver
    clean_memory_on_start()
    update_user_profile() 

    max_retries = 9999999 
    retry_delay = 5 

    for attempt in range(max_retries):
        logger.info(f"尝试启动新的Chrome浏览器 (第 {attempt + 1}/{max_retries} 次)...")
        clean_user_data_dir(DEFAULT_USER_DATA_DIR) # Clean cache before new launch
        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument('--window-size=800,600')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-application-cache') 
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f'--user-data-dir={DEFAULT_USER_DATA_DIR}')
        logger.info(f'用户数据目录设置为: {DEFAULT_USER_DATA_DIR}')
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
            logger.info(f'已设置代理: {PROXY}')
        logger.info(f'Chrome选项: {chrome_options.arguments}')

        try:
            driver = uc.Chrome(options=chrome_options, headless=True, version_main=136)
            logger.info(f"已启动新的Chrome浏览器 (headless=True)")
            logger.info(f"跳转到目标页面: {TRADINGVIEW_URL}")
            driver.get(TRADINGVIEW_URL)
            logger.info(f"当前页面: {driver.current_url}")
            return True 
        except WebDriverException as e:
            logger.error(f"启动Chrome或导航失败 (连接错误): {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                if attempt > 0: 
                    retry_delay *= 2
                logger.info(f"重试 {attempt + 1}/{max_retries}...")
                clean_memory_on_start()
                update_user_profile()

                time.sleep(retry_delay)
            else:
                logger.error("达到最大重试次数，浏览器初始化失败。")
                return False 
        except Exception as e:
            logger.error(f"启动Chrome失败 (未知错误): {e}")
            import traceback
            traceback.print_exc()
            return False 

def set_timeframe_and_screenshot(timeframe: str) -> str | None:
    """
    设置时间周期并进行截图
    
    参数:
        timeframe: str - 需要设置的时间周期（如 "15" 表示15分钟周期）
    
    返回:
        str | None - 截图文件路径或None（如果失败）
    """
    global driver
    try:
        body = driver.find_element(By.TAG_NAME, 'body')
        body.click()
        time.sleep(2) 

        actions = ActionChains(driver)
        for digit in timeframe:
            actions.send_keys(digit)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        time.sleep(1)  

        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).key_up(Keys.CONTROL).perform()
        logger.info(f'已为{timeframe}分钟周期触发截图')
        time.sleep(0.5)  
        now_ts = time.time()
        files = [f for f in os.listdir(downloads_dir) if f.startswith('ETHUSD.P_') and f.endswith('.png')]
        valid_files = []
        for f in files:
            fpath = os.path.join(downloads_dir, f)
            mtime = os.path.getmtime(fpath)
            if now_ts - mtime < 120 and os.path.getsize(fpath) > 1024:
                valid_files.append((f, mtime))
        
        if valid_files:
            valid_files.sort(key=lambda x: x[1], reverse=True)
            latest_file = valid_files[0][0]
            src_path = os.path.join(downloads_dir, latest_file)
            now = datetime.now().strftime('%Y%m%d_%H%M%S')
            dst_path = os.path.join(SAVE_DIR, f'tradingview_{timeframe}m_{now}.png')
            shutil.copy2(src_path, dst_path)
            return os.path.abspath(dst_path)
        
        return None
    except Exception as e:
        logger.error(f'设置{timeframe}分钟周期或截图失败: {e}')
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
                time.sleep(2) 
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
                logger.error(f'{tf}分钟周期截图失败')
            time.sleep(2)

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
    global driver
    if driver:
        try:
            driver.current_url 
            return jsonify({"status": "ok", "message": "Browser is responsive"})
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return jsonify({"status": "error", "message": "Browser is not responsive", "error": str(e)}), 500
    else:
        return jsonify({"status": "initializing", "message": "Browser not initialized"}), 503

def prefetch_fgi_cache():
    """
    在单独的线程中调用 get_fear_greed_index() 来预先填充缓存。
    """
    global FGI_SERVER_CACHE
    logger.info("启动 FGI 缓存预加载线程...")
    fgi_value = get_fear_greed_index() 

    if fgi_value is not None:
        FGI_SERVER_CACHE["value"] = fgi_value
        FGI_SERVER_CACHE["timestamp"] = time.time()
        logger.info(f"FGI 缓存预加载成功，值: {fgi_value}")
    else:
        logger.error("FGI 缓存预加载失败。")

    logger.info("FGI 缓存预加载线程完成。")

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

if __name__ == '__main__':
    logger.info("截图服务器正在启动...")
    # Clean up any residual chrome processes before starting for a clean slate
    http_proxy = config["proxy"]["http_proxy"]
    https_proxy = config["proxy"]["https_proxy"]
    os.environ["http_proxy"] = http_proxy
    os.environ["https_proxy"] = https_proxy

    try:
        subprocess.run(['pkill', '-9', 'chrome'], check=False)
        logger.info('已执行 pkill chrome')
    except Exception as e:
        logger.warning(f'pkill chrome 失败或没有运行中的Chrome进程: {e}')

    fgi_thread = threading.Thread(target=prefetch_fgi_cache)
    fgi_thread.start()
    logger.info("已启动 FGI 缓存预加载线程。")
    if initialize_browser():
        logger.info("浏览器初始化成功。")
       

        app.run(host='0.0.0.0', port=5002)
    else:
        logger.critical("浏览器初始化失败，服务器无法启动。")
