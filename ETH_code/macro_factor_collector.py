import requests
import datetime
import json
import os 
from okx.api import Public  # type: ignore
import logging
from datetime import datetime, timezone, timedelta

flag="0"

config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r"))


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["ETH_log_path"]
MODULE_TAG = "[macro_factor_collector] "
logging.basicConfig(
    level=logging.INFO,
    format='[宏观因子模块][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")






venv_python = config["python_path"]["global"]
# subprocess.run([venv_python, 'other_script.py', ...])

def get_okx_funding_rate():
    publicDataAPI = Public(flag=flag)
    result = publicDataAPI.get_funding_rate(
        instId="ETH-USDT-SWAP",
    )
    try:
        # fundingRate 可能是字符串，需先转为float
        rate = float(result['data'][0]['fundingRate'])
        # 保留4位小数，转为百分比
        return round(rate * 100, 4)  # 例如0.00018 -> 0.0180
    except Exception as e:
        # print("Error fetching funding rate:", e)
        logger.error(f"Error fetching funding rate: {e}")
        return None

def get_fear_greed_index():
    url = "https://api.alternative.me/fng/"
    r = requests.get(url)
    data = r.json()
    try:
        return int(data['data'][0]['value'])
    except Exception as e:
        # print("Error fetching fear & greed index:", e)
        logger.error(f"Error fetching fear & greed index: {e}")
        return None

def get_okx_open_interest():
    publicDataAPI = Public(flag=flag)
    # 只传 instType 和 instId，去掉 instFamily，避免参数错误
    result = publicDataAPI.get_open_interest(
        instType="SWAP",
        instId="ETH-USDT-SWAP",
    )
    try:
        return float(result['data'][0]['oi'])
    except Exception as e:
            # print("Error fetching open interest:", e)
        logger.error(f"Error fetching open interest: {e}")
        return None

def get_market_factors():
    # 北京时间（东八区）
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).replace(microsecond=0).isoformat()
    
    funding_rate = get_okx_funding_rate()
    fear_greed = get_fear_greed_index()
    open_interest = get_okx_open_interest()

    # 只有在funding_rate为None时不加百分号
    funding_rate_str = f"{funding_rate}%" if funding_rate is not None else None




    return {
        "factors": {
            "funding_rate": funding_rate_str,
            "FGI": f"{fear_greed}/100" if fear_greed is not None else None,
            "open_interest": f"${open_interest*100} million" if open_interest is not None else None
        }
    }

if __name__ == "__main__":
    logger.info(f"{MODULE_TAG} 开始采集宏观因子...")
    try:
        result = get_market_factors()
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"宏观因子采集异常: {str(e)}"}, ensure_ascii=False))
