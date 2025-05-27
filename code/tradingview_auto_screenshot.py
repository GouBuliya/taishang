import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import ImageGrab
import pyperclip
import argparse
import undetected_chromedriver as uc

# 配置
TRADINGVIEW_URL = 'https://cn.tradingview.com/chart/mJjA2OR8/?symbol=OKX%3AETHUSD.P'  # 你的超级图表链接，可自定义
SAVE_DIR = '/tmp/tradingview_screenshots'  # 修改为你想保存的目录
INTERVAL_MINUTES = 15
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache_screenshots')
CACHE_MAX = 15

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# 代理支持
parser = argparse.ArgumentParser()
parser.add_argument('--proxy', type=str, default=None, help='http://127.0.0.1:1080')
args, unknown = parser.parse_known_args()
proxy = args.proxy or os.environ.get('PROXY')

def create_driver(headless=False, user_data_dir=None):
    """
    创建并配置Chrome浏览器实例，使用undetected_chromedriver规避反爬虫。
    """
    chrome_options = uc.ChromeOptions()
    # chrome_options.binary_location = "/usr/bin/google-chrome"  # 建议注释掉，自动寻找chrome路径
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # chrome_options.add_argument('user-agent=...') # 保持注释
    if user_data_dir:
        chrome_options.add_argument(f'--user-data-dir={user_data_dir}')
    else:
        chrome_options.add_argument(f'--user-data-dir={os.path.expanduser("~/.config/tradingview_chrome_profile")}')
    prefs = {
        "download.default_directory": os.path.expanduser('~/Downloads'),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument('--disable-popup-blocking')
    if proxy:
        chrome_options.add_argument(f'--proxy-server={proxy}')
        print(f'[DEBUG] 已设置代理: {proxy}')
    print('[DEBUG] Chrome options:', chrome_options.arguments)
    try:
        driver = uc.Chrome(options=chrome_options, headless=False)  # 改为有头模式
    except Exception as e:
        print(f"[ERROR] 启动Chrome失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    print(f"[DEBUG] 启动无头浏览器（undetected_chromedriver）")
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
        downloads_dir = os.path.expanduser('~/Downloads')
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
        time.sleep(5)
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
                if now_ts - mtime < 60:
                    valid_files.append((f, mtime))
            if valid_files:
                valid_files.sort(key=lambda x: x[1], reverse=True)
                latest_file = valid_files[0][0]
                src_path = os.path.join(downloads_dir, latest_file)
                now = datetime.now().strftime('%Y%m%d_%H%M%S')
                dst_path = os.path.join(SAVE_DIR, f'tradingview_clipboard_{now}.png')
                import shutil
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
        # 检查剪切板是否有图片
        check = os.system('xclip -selection clipboard -t image/png -o > /dev/null 2>&1')
        if check == 0:
            print(f'[DEBUG] 剪切板检测到图片，第{i+1}次')
            return True
        print(f'[DEBUG] 剪切板无图片，第{i+1}次重试，{interval}秒后再次发送快捷键...')
        try:
            driver.switch_to.active_element.send_keys(Keys.CONTROL, Keys.SHIFT, 's')
        except Exception as e:
            print(f'[ERROR] 发送快捷键失败: {e}')
        time.sleep(interval)
    print('[DEBUG] wait_for_clipboard_image() 超时退出')
    return False

def main():
    filepath = None
    driver = None
    try:
        print("[DEBUG] 使用无头模式截图...")
        user_data_dir = os.path.expanduser("~/.config/tradingview_chrome_profile")
        if not os.path.exists(user_data_dir):
            print("[提示] 首次运行会自动创建浏览器配置目录，请在弹出的浏览器中手动登录 TradingView 并勾选保持登录，然后关闭浏览器后重新运行脚本。")
        driver = create_driver(headless=True, user_data_dir=user_data_dir)
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


# 所有子进程调用请用 venv_python 作为解释器
# 示例：如有子进程调用请用 venv_python 作为解释器
# subprocess.run([venv_python, 'other_script.py', ...])

