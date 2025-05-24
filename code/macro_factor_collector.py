import requests
import datetime
import json
import os 
from okx.api import Public  # type: ignore
import logging

flag="0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "../gemini_quant.log")
MODULE_TAG = "[macro_factor_collector] "
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuant")

venv_python = "/usr/bin/python3"
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
        return None

def get_fear_greed_index():
    url = "https://api.alternative.me/fng/"
    r = requests.get(url)
    data = r.json()
    try:
        return int(data['data'][0]['value'])
    except Exception as e:
        # print("Error fetching fear & greed index:", e)
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
        return None

def get_market_factors():
    now = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    
    funding_rate = get_okx_funding_rate()
    fear_greed = get_fear_greed_index()
    open_interest = get_okx_open_interest()

    # 只有在funding_rate为None时不加百分号
    funding_rate_str = f"{funding_rate}%" if funding_rate is not None else None




    return {
        "timestamp": now,
        "factors": {
            "funding_rate": funding_rate_str,
            "fear_greed_index": fear_greed,
            "open_interest": open_interest
        }
    }

if __name__ == "__main__":
    try:
        result = get_market_factors()
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"宏观因子采集异常: {str(e)}"}, ensure_ascii=False))
