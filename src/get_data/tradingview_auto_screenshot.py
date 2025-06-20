import os
import json
import logging
import requests # Import the requests library

# Load configuration
config = json.load(open("config/config.json", "r"))
http_proxy = config["proxy"]["http_proxy"]
https_proxy = config["proxy"]["https_proxy"]
os.environ["http_proxy"] = http_proxy
os.environ["https_proxy"] = https_proxy
# Configuration
SAVE_DIR = config["cache_screenshot_path"]

# Get current script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[截图客户端][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(config["main_log_path"], mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuantScreenshotClient")

# Ensure save directory exists
os.makedirs(SAVE_DIR, exist_ok=True)

def main():
    screenshot_server_url = "http://127.0.0.1:5002/screenshot"
    screenshots = {}

    try:
        logger.info(f"正在请求截图服务器: {screenshot_server_url}")
        response = requests.get(screenshot_server_url, timeout=90)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") == "success" and "screenshots" in data:
            screenshots = data["screenshots"]
            logger.info(f"截图服务器返回成功，获取到{len(screenshots)}个时间周期的截图")
            for timeframe, filepath in screenshots.items():
                logger.info(f"{timeframe}分钟周期的图片路径: {filepath}")
        else:
            logger.error(f"截图服务器返回错误或非预期响应: {data}")

    except requests.exceptions.Timeout:
        logger.error("请求截图服务器超时。")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"无法连接到截图服务器，请确保服务器正在运行在 {screenshot_server_url}: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"请求截图服务器异常: {e}")
    except json.JSONDecodeError:
        logger.error(f"截图服务器返回非JSON响应: {response.text if 'response' in locals() else '无响应内容'}")
    except Exception as e:
        logger.error(f"调用截图服务器异常: {e}")

    return screenshots

if __name__ == '__main__':
    logger.info('__main__ 入口被执行 (客户端模式)')
    result = main()
    if result:
        print(json.dumps(result))  # 将字典格式化为JSON字符串输出
    else:
        logger.error('截图失败')