# 本文件用于作为主控脚本，依次调用技术指标采集和宏观因子采集脚本，合并输出为标准化JSON，供GUI等模块调用。

import subprocess
import os
import json
from datetime import datetime, timezone, timedelta
import re
import sys
from okx.api import Market  # type: ignore
import logging
import threading
import requests
import concurrent.futures # 新增导入

# 导入子模块
from technical_indicator_collector import collect_technical_indicators
from macro_factor_collector import collect_macro_factors
from get_positions import collect_positions_data

config = json.load(open("config/config.json", "r"))

http_proxy = config["proxy"]["http_proxy"]
https_proxy = config["proxy"]["https_proxy"]
os.environ["http_proxy"] = http_proxy
os.environ["https_proxy"] = https_proxy
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
flag="0"
marketDataAPI = Market(flag=flag)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]
MODULE_TAG = "[macro_factor_collector] "
logging.basicConfig(
    level=logging.INFO,
    format='[数据收集总模块][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")


def extract_first_json(text):
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        try:
            logging.debug(f"尝试解码从索引 {idx} 开始的文本: {text[idx:]}")
            obj, end = decoder.raw_decode(text[idx:])
            logging.debug(f"成功解码: {obj}, 结束位置: {end}")
            return obj
        except json.JSONDecodeError as e:
            logging.debug(f"解码失败 (索引 {idx}): {e}")
            idx += 1
    logging.debug("未找到有效JSON，返回None")
    return None

def run_tradingview_screenshot():
    """
    通过HTTP请求调用截图服务器，返回截图文件路径（如成功），否则返回 None。
    """
    screenshot_server_url = "http://127.0.0.1:5002/screenshot"
    try:
        logging.info(f"正在请求截图服务器: {screenshot_server_url}")
        response = requests.get(screenshot_server_url, timeout=60) # Increased timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        if data.get("status") == "success" and "filepath" in data:
            filepath = data["filepath"]
            logging.info(f"截图服务器返回成功，图片路径: {filepath}")
            return filepath
        else:
            logging.error(f"截图服务器返回错误或非预期响应: {data}")
            return None
    except requests.exceptions.Timeout:
        logging.error("请求截图服务器超时。")
        return None
    except requests.exceptions.ConnectionError as e:
        logging.error(f"无法连接到截图服务器，请确保服务器正在运行: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"请求截图服务器异常: {e}")
        return None
    except json.JSONDecodeError:
        logging.error(f"截图服务器返回非JSON响应: {response.text}")
        return None
    except Exception as e:
        logging.error(f"调用截图服务器异常: {e}")
        return None

if __name__ == "__main__":
    # 将所有print输出（除最后"完成"）改为logging，stdout只输出"完成"
    proxies = {
        "http": config["proxy"]["http_proxy"],
        "https": config["proxy"]["https_proxy"]
    }
    begin_time = datetime.now()
    module_timings = {} # 用于存储每个模块的运行时间

    def _run_task_with_timing(task_name, func, *args, **kwargs):
        start_time_key = f"{task_name}_start"
        end_time_key = f"{task_name}_end"
        module_timings[start_time_key] = datetime.now()
        
        result = None
        try:
            logging.info(f"{task_name} 模块运行中...")
            result = func(*args, **kwargs)
            logging.info(f"{task_name} 模块完成。")
        except Exception as e:
            logging.error(f"{task_name} 模块运行失败: {e}")
        finally:
            module_timings[end_time_key] = datetime.now()
        return task_name, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: # 设置最大线程数
        future_to_task = {
            executor.submit(_run_task_with_timing, "screenshot", run_tradingview_screenshot): "screenshot",
            executor.submit(_run_task_with_timing, "indicators", collect_technical_indicators): "indicators",
            executor.submit(_run_task_with_timing, "factors", collect_macro_factors): "factors",
            executor.submit(_run_task_with_timing, "okx_positions", collect_positions_data): "okx_positions",
            executor.submit(_run_task_with_timing, "market_data", marketDataAPI.get_ticker, instId="ETH-USDT-SWAP"): "market_data"
        }

        results = {
            "screenshot": None,
            "indicators": None,
            "factors": None,
            "okx_positions": {}, # 默认空字典
            "market_data": None
        }

        for future in concurrent.futures.as_completed(future_to_task):
            task_name, result = future.result()
            results[task_name] = result
            if task_name == "screenshot" and not result:
                logging.error(f"截图模块运行失败，尝试重试3次...")
                for i in range(3):
                    screenshot_path_retry = run_tradingview_screenshot()
                    if screenshot_path_retry:
                        results["screenshot"] = screenshot_path_retry
                        logging.info(f"截图模块第{i+1}次重试成功，截图路径: {screenshot_path_retry}")
                        break
                    else:
                        logging.error(f"截图模块第{i+1}次重试失败")

    # 处理 OKX 持仓数据，确保其为字典类型
    if not isinstance(results["okx_positions"], dict):
        logging.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {results['okx_positions']}")
        results["okx_positions"] = {}

    merged = {
        "clipboard_image_path": results["screenshot"] if results["screenshot"] else "",
        "indicators_main": results["indicators"] if isinstance(results["indicators"], dict) else {},
        "factors_main": results["factors"] if isinstance(results["factors"], dict) else {},
        "data_summary": results["market_data"],
        "okx_positions": results["okx_positions"],
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).astimezone(timezone(timedelta(hours=8))).isoformat() # 东八区时间
    }
    # 写入 data.json
    
    data_path = config["data_path"]
    tmp_path = data_path + ".tmp"
    try:
        # 先序列化，确保合法
        json_str = json.dumps(merged, ensure_ascii=False, indent=2)
        logging.info(f"merged: {json_str}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        os.replace(tmp_path, data_path)  # 原子性替换
        # 统一输出所有模块的运行时间
        logging.info("\n--- 模块运行时间统计 ---")
        if "screenshot_start" in module_timings and "screenshot_end" in module_timings:
            duration_screenshot = module_timings["screenshot_end"] - module_timings["screenshot_start"]
            logging.info(f"截图模块运行时间: {duration_screenshot}")
        if "indicators_start" in module_timings and "indicators_end" in module_timings:
            duration_indicators = module_timings["indicators_end"] - module_timings["indicators_start"]
            logging.info(f"技术指标模块运行时间: {duration_indicators}")
        if "factors_start" in module_timings and "factors_end" in module_timings:
            duration_factors = module_timings["factors_end"] - module_timings["factors_start"]
            logging.info(f"宏观因子模块运行时间: {duration_factors}")
        if "okx_positions_start" in module_timings and "okx_positions_end" in module_timings:
            duration_okx_positions = module_timings["okx_positions_end"] - module_timings["okx_positions_start"]
            logging.info(f"OKX 持仓模块运行时间: {duration_okx_positions}")
        logging.info("--------------------------")
        print("完成")  # 只输出完成
        end_time = datetime.now()
        duration = end_time - begin_time
        logging.info(f"总运行时间: {duration}")
    except Exception as e:
        logging.error(f"写入data.json失败: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
