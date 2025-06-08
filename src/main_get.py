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
from get_data.technical_indicator_collector import collect_technical_indicators
from get_data.macro_factor_collector import collect_macro_factors
from get_data.get_positions import collect_positions_data

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
    level=logging.WARNING,
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
            logger.debug(f"尝试解码从索引 {idx} 开始的文本: {text[idx:]}")
            obj, end = decoder.raw_decode(text[idx:])
            logger.debug(f"成功解码: {obj}, 结束位置: {end}")
            return obj
        except json.JSONDecodeError as e:
            logger.debug(f"解码失败 (索引 {idx}): {e}")
            idx += 1
    logger.debug("未找到有效JSON，返回None")
    return None

def run_tradingview_screenshot():
    """
    通过HTTP请求调用截图服务器，返回包含所有时间周期截图路径的字典。
    
    返回:
        dict: 包含所有时间周期截图路径的字典，格式为：
        {
            "15m": "/path/to/15min.png",
            "1h": "/path/to/1hour.png",
            "4h": "/path/to/4hour.png"
        }
        如果失败则返回 None
    """
    screenshot_server_url = "http://127.0.0.1:5002/screenshot"
    try:
        logger.info(f"正在请求截图服务器: {screenshot_server_url}")
        response = requests.get(screenshot_server_url, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") == "success" and "screenshots" in data:
            screenshots = data["screenshots"]
            # 转换时间周期格式：15 -> 15m, 60 -> 1h, 240 -> 4h
            formatted_screenshots = {
                "15m": screenshots.get("15"),
                "1h": screenshots.get("60"),
                "4h": screenshots.get("240")
            }
            logger.info(f"截图服务器返回成功，获取到{len(screenshots)}个时间周期的截图")
            return formatted_screenshots
        else:
            logger.error(f"截图服务器返回错误或非预期响应: {data}")
            return None
    except requests.exceptions.Timeout:
        logger.error("请求截图服务器超时。")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"无法连接到截图服务器，请确保服务器正在运行: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求截图服务器异常: {e}")
        return None
    except json.JSONDecodeError:
        logger.error(f"截图服务器返回非JSON响应: {response.text if 'response' in locals() else '无响应内容'}")
        return None
    except Exception as e:
        logger.error(f"调用截图服务器异常: {e}")
        return None

def main():
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
            logger.info(f"{task_name} 模块运行中...")
            result = func(*args, **kwargs)
            logger.info(f"{task_name} 模块完成。")
        except Exception as e:
            logger.error(f"{task_name} 模块运行失败: {e}")
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
                logger.error(f"截图模块运行失败，尝试重试3次...")
                for i in range(3):
                    screenshot_path_retry = run_tradingview_screenshot()
                    if screenshot_path_retry:
                        results["screenshot"] = screenshot_path_retry
                        logger.info(f"截图模块第{i+1}次重试成功，截图路径: {screenshot_path_retry}")
                        break
                    else:
                        logger.error(f"截图模块第{i+1}次重试失败")

    # 处理 OKX 持仓数据，确保其为字典类型
    if not isinstance(results["okx_positions"], dict):
        logger.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {results['okx_positions']}")
        results["okx_positions"] = {}

    merged = {
        "screenshots": results["screenshot"] if results["screenshot"] else {},  # 现在是字典格式，包含所有时间周期的截图
        "indicators_main": results["indicators"] if isinstance(results["indicators"], dict) else {},
        "factors_main": results["factors"] if isinstance(results["factors"], dict) else {},
        "data_summary": results["market_data"],
        "okx_positions": results["okx_positions"],
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).astimezone(timezone(timedelta(hours=8))).isoformat()
    }
    # 写入 data.json
    data_path = config["data_path"]
    tmp_path = data_path + ".tmp"
    try:
        # 先序列化，确保合法
        json_str = json.dumps(merged, ensure_ascii=False, indent=2)
        logger.info(f"merged: {json_str}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        os.replace(tmp_path, data_path)  # 原子性替换
        # 统一输出所有模块的运行时间
        logger.info("\n--- 模块运行时间统计 ---")
        if "screenshot_start" in module_timings and "screenshot_end" in module_timings:
            duration_screenshot = module_timings["screenshot_end"] - module_timings["screenshot_start"]
            print(f"截图模块运行时间: {duration_screenshot}")
        if "indicators_start" in module_timings and "indicators_end" in module_timings:
            duration_indicators = module_timings["indicators_end"] - module_timings["indicators_start"]
            print(f"技术指标模块运行时间: {duration_indicators}")
        if "factors_start" in module_timings and "factors_end" in module_timings:
            duration_factors = module_timings["factors_end"] - module_timings["factors_start"]
            print(f"宏观因子模块运行时间: {duration_factors}")
        if "okx_positions_start" in module_timings and "okx_positions_end" in module_timings:
            duration_okx_positions = module_timings["okx_positions_end"] - module_timings["okx_positions_start"]
            print(f"OKX 持仓模块运行时间: {duration_okx_positions}")
        print("--------------------------")
        print("完成")  # 只输出完成
        end_time = datetime.now()
        duration = end_time - begin_time
        print(f"总运行时间: {duration}")
    except Exception as e:
        logger.error(f"写入data.json失败: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    main()
