import time
import os
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import ImageGrab
import pyperclip
import argparse

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

def create_driver(headless=True):
    """
    创建并配置Chrome浏览器实例
    :param headless: 是否使用无头模式
    :return: 配置好的浏览器实例
    """
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-gpu')
    if headless:
        chrome_options.add_argument('--headless=new')
    
    USER_PROFILE_DIR = os.path.expanduser('~/.config/tradingview_chrome_profile')
    chrome_options.add_argument(f'--user-data-dir={USER_PROFILE_DIR}')
    chrome_options.add_argument('--profile-directory=Default')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    if proxy:
        chrome_options.add_argument(f'--proxy-server={proxy}')
        print(f'[DEBUG] 已设置代理: {proxy}')
    
    driver = uc.Chrome(options=chrome_options)
    mode = "无头" if headless else "有头"
    print(f"[DEBUG] 启动{mode}浏览器（undetected-chromedriver），chromedriver路径: {getattr(driver, 'capabilities', {}).get('chrome', {}).get('chromedriverVersion', '未知')}")
    return driver

def take_screenshot(driver):
    """
    尝试获取截图
    :param driver: 浏览器实例
    :return: 保存的文件路径或None（如果失败）
    """
    try:
        print(f'[DEBUG] 打开目标图表页...')
        driver.get(TRADINGVIEW_URL)
        print(f'[DEBUG] 等待5秒加载页面...')
        time.sleep(5)
        print(f'[DEBUG] 发送Ctrl+Shift+S快捷键，直到剪切板有图片为止...')
        has_img = wait_for_clipboard_image(driver)
        if not has_img:
            print('[ERROR] 剪切板始终无图片，已超时退出')
            return None
            
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(SAVE_DIR, f'tradingview_clipboard_{now}.png')
        # === 新增：保存剪切板图片到文件 ===
        save_cmd = f"xclip -selection clipboard -t image/png -o > '{filepath}'"
        ret = os.system(save_cmd)
        
        success = ret == 0 and os.path.exists(filepath) and os.path.getsize(filepath) > 0
        
        if success:
            print(f'[DEBUG] 剪切板图片已保存: {filepath}')
            if not driver.capabilities.get("goog:chromeOptions", {}).get("args", []).count("--headless=new"):
                print('[DEBUG] 有头模式下关闭当前标签页...')
                try:
                    driver.close()  # 只关闭当前标签页，不关闭整个浏览器
                except Exception as e:
                    print(f'[WARNING] 关闭标签页失败: {e}')
            return filepath
        else:
            print('[ERROR] 剪切板图片保存失败，文件为空或xclip命令失败')
            return None
    except Exception as e:
        print(f'[ERROR] 保存剪切板图片失败: {e}')
        return None

def wait_for_clipboard_image(driver, max_retry=12, interval=5):
    print('[DEBUG] wait_for_clipboard_image() called')
    for i in range(max_retry):
        # 检查剪切板是否有图片
        check = os.system('xclip -selection clipboard -t image/png -o > /dev/null 2>&1')
        if check == 0:
            print(f'[DEBUG] 剪切板检测到图片，第{i+1}次')
            return True
        print(f'[DEBUG] 剪切板无图片，第{i+1}次重试，5秒后再次发送快捷键...')
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
        # 首先尝试无头模式
        print("[DEBUG] 尝试使用无头模式截图...")
        driver = create_driver(headless=True)
        filepath = take_screenshot(driver)
        
        # 如果无头模式失败，切换到有头模式重试
        if not filepath:
            print("[DEBUG] 无头模式截图失败，切换到有头模式重试...")
            driver.quit()
            driver = create_driver(headless=False)
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

