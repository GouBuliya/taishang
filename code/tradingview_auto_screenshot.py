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

# 配置
TRADINGVIEW_URL = 'https://cn.tradingview.com/chart/mJjA2OR8/?symbol=OKX%3AETHUSD.P'  # 你的超级图表链接，可自定义
SAVE_DIR = '/tmp/tradingview_screenshots'  # 修改为你想保存的目录
INTERVAL_MINUTES = 15
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache_screenshots')
CACHE_MAX = 15

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# 启动浏览器
chrome_options = uc.ChromeOptions()
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--disable-gpu')
# chrome_options.add_argument('--headless=new')  # 已注释，默认有头模式
# === 新增：复用本地Chrome用户profile，保证登录态 ===
USER_PROFILE_DIR = os.path.expanduser('~/.config/tradingview_chrome_profile')  # 建议用专用profile目录
chrome_options.add_argument(f'--user-data-dir={USER_PROFILE_DIR}')
chrome_options.add_argument('--profile-directory=Default')  # 如有多个profile可改为Profile 1等
chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
driver = uc.Chrome(options=chrome_options)
print(f"[DEBUG] 启动有头浏览器（undetected-chromedriver），chromedriver路径: {getattr(driver, 'capabilities', {}).get('chrome', {}).get('chromedriverVersion', '未知')}")

def main():
    print(f'[DEBUG] 打开目标图表页...')
    driver.get(TRADINGVIEW_URL)
    print('[DEBUG] 等待10秒加载页面...')
    time.sleep(10)
    print('[DEBUG] 直接全局发送Ctrl+Shift+S...')
    try:
        driver.switch_to.active_element.send_keys(Keys.CONTROL, Keys.SHIFT, 's')
        print('已发送Ctrl+Shift+S快捷键，截图已复制到剪贴板（如浏览器支持）')
    except Exception as e:
        print(f'[ERROR] 发送快捷键失败: {e}')
        driver.quit()
        return
    print('[DEBUG] 等待2秒以确保截图已生成...')
    time.sleep(2)
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(SAVE_DIR, f'tradingview_clipboard_{now}.png')
    # Linux下用xclip保存剪贴板图片
    try:
        check = os.system('xclip -selection clipboard -t image/png -o > /dev/null 2>&1')
        if check != 0:
            print('[ERROR] 剪贴板中无图片或xclip不支持image/png')
        else:
            os.system(f'xclip -selection clipboard -t image/png -o > "{filepath}"')
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f'[DEBUG] 剪切板图片已保存: {filepath}')
            else:
                print('[ERROR] 剪切板图片保存失败，文件为空')
    except Exception as e:
        print(f'[ERROR] 保存剪切板图片失败: {e}')
    print('[DEBUG] 关闭浏览器...')
    driver.quit()

if __name__ == '__main__':
    main()
