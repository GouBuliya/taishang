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

app = Flask(__name__)

# Load configuration
config = json.load(open("/root/codespace/taishang/config/config.json", "r"))

# Configuration
TRADINGVIEW_URL = 'https://cn.tradingview.com/chart/mJjA2OR8/?symbol=OKX%3AETHUSD.P'
SAVE_DIR = config["cache_screenshot_path"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_USER_DATA_DIR = os.path.join(SCRIPT_DIR, 'chrome_profile')
PROXY = config["proxy"]["http_proxy"]
LOG_FILE = config["main_log_path"]

# Global driver instance
driver = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[截图服务器][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuantScreenshotServer")

# Ensure directories exist
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
    if os.path.exists(src): # Only copy if chrome_profile_copy exists
        if os.path.exists(dst):
            safe_rmtree(dst)
        shutil.copytree(src, dst)
        logger.info(f'已用 {src} 覆盖 {dst}')
    else:
        logger.warning(f'chrome_profile_copy 不存在，跳过更新用户配置。请确保该目录存在，以便初始化。')

def initialize_browser():
    """
    初始化或重新连接浏览器实例。
    """
    global driver
    clean_memory_on_start()
    update_user_profile() # Update profile on initial launch

    logger.info("启动新的Chrome浏览器...")
    clean_user_data_dir(DEFAULT_USER_DATA_DIR) # Clean cache before new launch
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument('--window-size=800,600')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
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
    except Exception as e:
        logger.error(f"启动Chrome失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def take_screenshot_action():
    """
    执行截图操作并返回文件路径。
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
        logger.info(f'旧截图已清理，开始截图流程...')
        
        # 确保浏览器在正确的页面
        if driver.current_url != TRADINGVIEW_URL and not driver.current_url.startswith("https://cn.tradingview.com/chart/"):
            logger.info(f'当前页面不是目标页面，重新导航到: {TRADINGVIEW_URL}')
            driver.get(TRADINGVIEW_URL)
            time.sleep(5) # Give it time to load

        logger.info(f'等待0.5秒加载页面...')
        time.sleep(0.5) # Still wait for page elements to render after potential re-navigation

        logger.info(f'发送快捷键 Ctrl+Alt+S 触发下载图片...')
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            body.click()
            actions = ActionChains(driver)
            actions.key_down(Keys.CONTROL).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).key_up(Keys.CONTROL).perform()
            logger.info('快捷键已发送')
        except Exception as e:
            logger.error(f'快捷键发送失败: {e}')
            return None

        max_retry = 5 # Increased retry attempts
        for attempt in range(max_retry):
            time.sleep(0.5) # Increased sleep
            now_ts = time.time()
            files = [f for f in os.listdir(downloads_dir) if f.startswith('ETHUSD.P_') and f.endswith('.png')]
            valid_files = []
            for f in files:
                fpath = os.path.join(downloads_dir, f)
                mtime = os.path.getmtime(fpath)
                if now_ts - mtime < 120 and os.path.getsize(fpath) > 1024: # Increased time window
                    valid_files.append((f, mtime))
            if valid_files:
                valid_files.sort(key=lambda x: x[1], reverse=True)
                latest_file = valid_files[0][0]
                src_path = os.path.join(downloads_dir, latest_file)
                now = datetime.now().strftime('%Y%m%d_%H%M%S')
                dst_path = os.path.join(SAVE_DIR, f'tradingview_clipboard_{now}.png')
                shutil.copy2(src_path, dst_path)
                abs_dst_path = os.path.abspath(dst_path)
                logger.info(f'K线图片已保存: {abs_dst_path}')
                return abs_dst_path
            else:
                logger.warning(f'第{attempt+1}次未检测到刚刚下载的K线图片，{2 if attempt < max_retry - 1 else 0}秒后重试...')
        logger.error('连续多次未检测到刚刚下载的K线图片（请检查下载权限或快捷键是否生效）')
        return None
    except Exception as e:
        logger.error(f'保存K线图片失败: {e}')
        return None

@app.route('/screenshot', methods=['GET'])
def get_screenshot():
    logger.info("收到截图请求。")
    filepath = take_screenshot_action()
    if filepath:
        return jsonify({"status": "success", "filepath": filepath})
    else:
        return jsonify({"status": "error", "message": "截图失败"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    global driver
    if driver:
        try:
            driver.current_url # Attempt to access a driver property to check responsiveness
            return jsonify({"status": "ok", "message": "Browser is responsive"})
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return jsonify({"status": "error", "message": "Browser is not responsive", "error": str(e)}), 500
    else:
        return jsonify({"status": "initializing", "message": "Browser not initialized"}), 503

if __name__ == '__main__':
    logger.info("截图服务器正在启动...")
    # Clean up any residual chrome processes before starting for a clean slate
    try:
        subprocess.run(['pkill', '-9', 'chrome'], check=False)
        logger.info('已执行 pkill chrome')
    except Exception as e:
        logger.warning(f'pkill chrome 失败或没有运行中的Chrome进程: {e}')

    if initialize_browser():
        logger.info("浏览器初始化成功。")
        app.run(host='0.0.0.0', port=5002)
    else:
        logger.critical("浏览器初始化失败，服务器无法启动。") 