import requests
import datetime
import json
import os 
from okx.api import Public  # type: ignore
import logging
from datetime import datetime, timezone, timedelta
import time
import concurrent.futures # 新增导入

config= json.load(open("config/config.json", "r"))

flag= config["okx"]["flag"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]
http_proxy = config["proxy"]["http_proxy"]
https_proxy = config["proxy"]["https_proxy"]
os.environ["http_proxy"] = http_proxy
os.environ["https_proxy"] = https_proxy
# 防止重复添加handler
if not logging.getLogger("GeminiQuant").handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[宏观因子模块][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

logger = logging.getLogger("GeminiQuant")

# 恐惧贪婪指数缓存
FGI_CACHE = {"value": None, "timestamp": None}
FGI_CACHE_DURATION = 300 # 缓存有效期 300 秒 (5 分钟)

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
    global FGI_CACHE
    current_time = time.time()

    # 检查缓存是否有效
    if FGI_CACHE["value"] is not None and FGI_CACHE["timestamp"] is not None and \
       (current_time - FGI_CACHE["timestamp"] < FGI_CACHE_DURATION):
        logger.info(f"从缓存中获取恐惧贪婪指数: {FGI_CACHE['value']}")
        return FGI_CACHE["value"]

    url = "https://api.alternative.me/fng/"
    try:
        logger.info("从外部 API 获取恐惧贪婪指数...")
        r = requests.get(url, timeout=10) # 增加超时时间，例如10秒
        r.raise_for_status() # 检查HTTP请求是否成功
        data = r.json()
        value = int(data['data'][0]['value'])
        
        # 更新缓存
        FGI_CACHE["value"] = value
        FGI_CACHE["timestamp"] = current_time

        return value
    except requests.exceptions.Timeout:
        logger.error("请求恐惧贪婪指数 API 超时。")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求恐惧贪婪指数 API 异常: {e}")
        return None
    except Exception as e:
        logger.error(f"获取恐惧贪婪指数异常: {e}")
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

def _run_factor_task(task_name, func):
    start_time = time.time()
    result = func()
    end_time = time.time()
    logger.info(f"{task_name} collection took {end_time - start_time:.4f} seconds.")
    return task_name, result

def get_fgi_from_server():
    """
    通过调用本地截图服务器的 /fgi 接口获取恐惧贪婪指数。
    """
    server_url = "http://127.0.0.1:5002/fgi"
    try:
        logger.info(f"正在请求截图服务器的 FGI 接口: {server_url}")
        response = requests.get(server_url, timeout=10) # 设置超时时间
        response.raise_for_status() # 检查HTTP请求是否成功

        data = response.json()
        if data.get("status") == "success" and "fgi" in data:
            fgi_value = data["fgi"]
            logger.info(f"从服务器获取 FGI 成功: {fgi_value}")
            return fgi_value
        else:
            logger.error(f"从服务器获取 FGI 失败或非预期响应: {data}")
            return None
    except requests.exceptions.Timeout:
        logger.error("请求截图服务器 FGI 接口超时。")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"无法连接到截图服务器 FGI 接口，请确保服务器正在运行在 {server_url}: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求截图服务器 FGI 接口异常: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"截图服务器 FGI 接口返回非JSON响应: {response.text if 'response' in locals() else '无响应内容'}")
        return None
    except Exception as e:
        logger.error(f"调用截图服务器 FGI 接口异常: {e}")
        return None

def collect_macro_factors():
    # 北京时间（东八区）
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz).replace(microsecond=0).isoformat()
    
    # 使用 ThreadPoolExecutor 并行收集数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_factor = {
            executor.submit(_run_factor_task, "Funding rate", get_okx_funding_rate): "funding_rate",
            executor.submit(_run_factor_task, "Fear & greed index", get_fgi_from_server): "FGI",
            executor.submit(_run_factor_task, "Open interest", get_okx_open_interest): "open_interest"
        }

        collected_factors = {}
        for future in concurrent.futures.as_completed(future_to_factor):
            task_name, result = future.result()
            # 根据 task_name 映射到最终字典的键
            if task_name == "Funding rate":
                # 只有在funding_rate为None时不加百分号
                collected_factors["funding_rate"] = f"{result}%" if result is not None else None
            elif task_name == "Fear & greed index":
                # 恐惧贪婪指数，字符串格式如"71/100"
                collected_factors["FGI"] = f"{result}/100" if result is not None else None
            elif task_name == "Open interest":
                collected_factors["open_interest"] = f"${result*100} million" if result is not None else None

    return {
        "factors": collected_factors
    }

if __name__ == "__main__":
    #代理

    try:
        result = collect_macro_factors()
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": f"宏观因子采集异常: {str(e)}"}, ensure_ascii=False))
