import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyperclip
import argparse
import undetected_chromedriver as uc
import sys # 导入sys模块
import shutil
import subprocess

# 配置
TRADINGVIEW_URL = 'https://cn.tradingview.com/chart/mJjA2OR8/?symbol=OKX%3AETHUSD.P'  # 你的超级图表链接，可自定义
SAVE_DIR = 'code/cache_screenshots'  # 修改为你想保存的目录
INTERVAL_MINUTES = 15
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache_screenshots')
CACHE_MAX = 15
VIRTUAL_ENV_PYTHON_PATH="/usr/local/bin/python3.10"
# 定义虚拟环境的Python路径，并确保使用它
# 在 Dockerfile 中，这个路径会被设置为 /app/venv/bin/python
# 在本地开发时，你可能需要根据实际虚拟环境路径进行调整
venv_python = os.environ.get("VIRTUAL_ENV_PYTHON_PATH", sys.executable)

# 获取当前脚本的绝对路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 将浏览器配置文件放在脚本所在目录下的 'chrome_profile' 文件夹中
DEFAULT_USER_DATA_DIR = os.path.join(SCRIPT_DIR, 'chrome_profile')


os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(DEFAULT_USER_DATA_DIR, exist_ok=True) # 确保配置文件目录存在

# 代理支持
parser = argparse.ArgumentParser()
parser.add_argument('--proxy', type=str, default=None, help='http://127.0.0.1:1080')
args, unknown = parser.parse_known_args()
proxy = args.proxy or os.environ.get('PROXY')

def clean_user_data_dir(user_data_dir):
    """
    清理Chrome用户配置目录下的缓存子目录，降低内存占用。
    """
    for sub in ['Cache', 'Code Cache', 'GPUCache', 'ShaderCache', 'GrShaderCache']:
        path = os.path.join(user_data_dir, sub)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                print(f'[DEBUG] 已清理缓存目录: {path}')
            except Exception as e:
                print(f'[WARNING] 清理缓存目录失败: {path}, {e}')

def create_driver(headless=True, user_data_dir=None):
    """
    创建并配置Chrome浏览器实例，使用undetected_chromedriver规避反爬虫。
    启动前自动清理用户配置目录下的缓存。
    """
    final_user_data_dir = user_data_dir if user_data_dir else DEFAULT_USER_DATA_DIR
    clean_user_data_dir(final_user_data_dir)
    chrome_options = uc.ChromeOptions()
    # chrome_options.binary_location = "/usr/bin/google-chrome"  # 建议注释掉，自动寻找chrome路径
    chrome_options.add_argument('--window-size=2560,1440')
    # chrome_options.add_argument('--disable-gpu') # 在有头模式下通常不需要禁用GPU
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # chrome_options.add_argument('user-agent=...') # 保持注释

    # 修改此处，优先使用传入的 user_data_dir，否则使用默认的同级目录
    chrome_options.add_argument(f'--user-data-dir={final_user_data_dir}')
    print(f'[DEBUG] 用户数据目录设置为: {final_user_data_dir}')

    prefs = {
        # 将下载目录也设在脚本同级目录下的 'downloads' 文件夹中
        "download.default_directory": os.path.join(SCRIPT_DIR, 'downloads'),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    os.makedirs(prefs["download.default_directory"], exist_ok=True) # 确保下载目录存在
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument('--disable-popup-blocking')
    if proxy:
        chrome_options.add_argument(f'--proxy-server={proxy}')
        print(f'[DEBUG] 已设置代理: {proxy}')
    print('[DEBUG] Chrome options:', chrome_options.arguments)
    try:
        driver = uc.Chrome(options=chrome_options, headless=headless, version_main=136)
    except Exception as e:
        print(f"[ERROR] 启动Chrome失败: {e}")
        import traceback
        traceback.print_exc()
        # 尝试用chrome_profile_copy覆盖chrome_profile
        try:
            src = os.path.join(SCRIPT_DIR, 'chrome_profile_copy')
            dst = final_user_data_dir
            print(f"[DEBUG] 尝试用{src}覆盖{dst}")
            if safe_rmtree(dst):
            shutil.copytree(src, dst)
            print(f"[DEBUG] 覆盖完成，重试启动Chrome...")
                driver = uc.Chrome(options=chrome_options, headless=headless, version_main=136)
            else:
                raise
        except Exception as e2:
            print(f"[ERROR] 第二次启动Chrome仍然失败: {e2}")
            traceback.print_exc()
            raise
    print(f"[DEBUG] 启动浏览器 (有头模式)") # 明确指出为有头模式
    time.sleep(2)
    print(f"[DEBUG] 跳转到目标页面: {TRADINGVIEW_URL}")
    driver.get(TRADINGVIEW_URL)
    time.sleep(3)
    print(f"[DEBUG] 当前页面: {driver.current_url}")
    return driver

def take_screenshot(driver):
    """
    仅使用快捷键（Ctrl+Alt+S）方式，适配Linux环境。
    保留清理旧图、检测新图、重试等机制。
    """
    try:
        # 使用 prefs 中设置的下载目录
        downloads_dir = os.path.join(SCRIPT_DIR, 'downloads')
        
        old_files = [f for f in os.listdir(downloads_dir) if f.startswith('ETHUSD.P_') and f.endswith('.png')]
        for f in old_files:
            try:
                os.remove(os.path.join(downloads_dir, f))
            except Exception as e:
                print(f'[WARNING] 删除旧截图失败: {f}, {e}')
        print(f'[DEBUG] 旧截图已清理，开始截图流程...')
        print(f'[DEBUG] 打开目标图表页...')
        # 移除JS注入，直接访问目标页
        driver.get(TRADINGVIEW_URL)
        print(f'[DEBUG] 等待5秒加载页面...')
        time.sleep(7)
        print(f'[DEBUG] 发送快捷键 Ctrl+Alt+S 触发下载图片...')
        try:
            body = driver.find_element(By.TAG_NAME, 'body')
            body.click()
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.key_down(Keys.CONTROL).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).key_up(Keys.CONTROL).perform()
            print('[DEBUG] 快捷键已发送')
        except Exception as e:
            print(f'[ERROR] 快捷键发送失败: {e}')
            return None
        # 等待下载完成，最多尝试3次，每次间隔3秒
        max_retry = 3
        for attempt in range(max_retry):
            time.sleep(3)
            now_ts = time.time()
            files = [f for f in os.listdir(downloads_dir) if f.startswith('ETHUSD.P_') and f.endswith('.png')]
            valid_files = []
            for f in files:
                fpath = os.path.join(downloads_dir, f)
                mtime = os.path.getmtime(fpath)
                # 检查文件创建时间是否在新截图操作之后（通常更可靠）
                # 或者检查文件修改时间是否在最近60秒内，防止识别旧文件
                if now_ts - mtime < 60 and os.path.getsize(fpath) > 1024: # 确保文件大小非零
                    valid_files.append((f, mtime))
            if valid_files:
                valid_files.sort(key=lambda x: x[1], reverse=True)
                latest_file = valid_files[0][0]
                src_path = os.path.join(downloads_dir, latest_file)
                now = datetime.now().strftime('%Y%m%d_%H%M%S')
                dst_path = os.path.join(SAVE_DIR, f'tradingview_clipboard_{now}.png')
                shutil.copy2(src_path, dst_path)
                print(f'[DEBUG] K线图片已保存: {dst_path}')
                return dst_path
            else:
                print(f'[WARNING] 第{attempt+1}次未检测到刚刚下载的K线图片，3秒后重试...')
        print('[ERROR] 连续3次未检测到刚刚下载的K线图片（请检查下载权限或快捷键是否生效）')
        return None
    except Exception as e:
        print(f'[ERROR] 保存K线图片失败: {e}')
        return None

def wait_for_clipboard_image(driver, max_retry=3, interval=2):
    print('[DEBUG] wait_for_clipboard_image() called')
    for i in range(max_retry):
        # 检查剪切板是否有图片 (xclip 在 Docker 环境中可能需要额外配置)
        # 在 Docker 中运行 Selenium/Chrome 通常不直接访问宿主机剪切板，
        # 如果需要，可能要考虑X服务器/VNC或特殊Selenium配置
        check = os.system('xclip -selection clipboard -t image/png -o > /dev/null 2>&1')
        if check == 0:
            print(f'[DEBUG] 剪切板检测到图片，第{i+1}次')
            return True
        print(f'[DEBUG] 剪切板无图片，第{i+1}次重试，{interval}秒后再次发送快捷键...')
        try:
            # 确保在正确的元素上发送快捷键，或者直接发送到body
            body = driver.find_element(By.TAG_NAME, 'body')
            body.send_keys(Keys.CONTROL, Keys.ALT, 's') # 统一使用Ctrl+Alt+S
        except Exception as e:
            print(f'[ERROR] 发送快捷键失败: {e}')
        time.sleep(interval)
    print('[DEBUG] wait_for_clipboard_image() 超时退出')
    return False

def clear_save_dir(save_dir):
    """
    清空保存截图的目录。
    """
    if os.path.exists(save_dir):
        for f in os.listdir(save_dir):
            fpath = os.path.join(save_dir, f)
            try:
                if os.path.isfile(fpath) or os.path.islink(fpath):
                    os.unlink(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
            except Exception as e:
                print(f'[WARNING] 删除文件失败: {fpath}, {e}')

def safe_rmtree(path, max_retry=3):
    for i in range(max_retry):
        try:
            shutil.rmtree(path)
            return True
        except Exception as e:
            print(f"[WARNING] 第{i+1}次删除目录失败: {path}, {e}")
            time.sleep(1)
    print(f"[ERROR] 多次尝试后仍无法删除目录: {path}，请手动清理！")
    return False

def main():
    filepath = None
    driver = None
    # 启动前清空保存目录
    clear_save_dir(SAVE_DIR)
    # 启动前杀掉所有chrome进程
    try:
        subprocess.run(['pkill', '-9', 'chrome'], check=False)
        print('[DEBUG] 已执行 pkill chrome')
    except Exception as e:
        print(f'[WARNING] pkill chrome 失败: {e}')
    # 强制检查当前运行的Python解释器是否是指定的venv_python
    if sys.executable != venv_python:
        print(f"[CRITICAL ERROR] 当前脚本运行的Python解释器不是指定的虚拟环境解释器！")
        print(f"Expected: {venv_python}")
        print(f"Actual: {sys.executable}")
        print("请确保通过 `/app/venv/bin/python your_script.py` 或正确配置了PATH环境变量来运行脚本。")
        sys.exit(1) # 强制退出，因为运行环境不符

    try:
        print("[DEBUG] 启动浏览器进行截图 (有头模式)...") # 更新调试信息
        # user_data_dir 参数将使用上面定义的 DEFAULT_USER_DATA_DIR
        driver = create_driver(headless=True, user_data_dir=DEFAULT_USER_DATA_DIR) # 将headless设置为False
        filepath = take_screenshot(driver)
        return filepath
    finally:
        if driver:
            print('[DEBUG] 关闭浏览器...')
            driver.quit()

if __name__ == '__main__':
    print('[DEBUG] __main__ 入口被执行')
    result = main()
    if result:
        print(result)
    else:
        print('截图失败')