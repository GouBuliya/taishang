import requests
import datetime
import json

def get_okx_funding_rate():
    url = "https://www.okx.com/api/v5/public/funding-rate?instId=ETH-USDT-SWAP"
    r = requests.get(url)
    data = r.json()
    try:
        return float(data['data'][0]['fundingRate'])
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
    url = "https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=ETH-USDT-SWAP"
    r = requests.get(url)
    data = r.json()
    try:
        return float(data['data'][0]['oi'])  # ✅ 修正字段名为 'oi'
    except Exception as e:
        # print("Error fetching open interest:", e)
        return None

def get_market_factors():
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    
    funding_rate = get_okx_funding_rate()
    fear_greed = get_fear_greed_index()
    open_interest = get_okx_open_interest()

    return {
        "timestamp": now,
        "factors": {
            "funding_rate": funding_rate,
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
