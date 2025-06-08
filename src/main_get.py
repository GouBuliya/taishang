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
import concurrent.futures
# from PIL import Image # 移除：不再需要PIL库

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


LOG_FILE = config["main_log_path"]
MODULE_TAG = "[main_collector] " # 更新模块标签，因为不再是宏观因子专属
logging.basicConfig(
    level=logging.WARNING,
    format='[数据收集总模块][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")


# ==============================================================================
# 移除：合并图片函数 (merge_images_vertically)
# ==============================================================================
# def merge_images_vertically(image_paths, output_path, quality=1):
#     """
#     垂直堆叠多张图片并保存，支持画质压缩。
#     """
#     # ... (此函数已移除) ...


# ==============================================================================
# 辅助函数 (未修改，但保留)
# ==============================================================================
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

# ==============================================================================
# 移除：run_tradingview_screenshot 函数
# ==============================================================================
# def run_tradingview_screenshot():
#     """
#     通过HTTP请求调用截图服务器，获取所有时间周期截图，并将其合并为一张JPEG图片。
#     """
#     # ... (此函数已移除) ...


# ==============================================================================
# main 函数 (已修改，移除截图相关逻辑)
# ==============================================================================
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
            # 移除截图任务
            # executor.submit(_run_task_with_timing, "screenshot", run_tradingview_screenshot): "screenshot",
            executor.submit(_run_task_with_timing, "indicators", collect_technical_indicators): "indicators",
            executor.submit(_run_task_with_timing, "factors", collect_macro_factors): "factors",
            executor.submit(_run_task_with_timing, "okx_positions", collect_positions_data): "okx_positions",
            executor.submit(_run_task_with_timing, "market_data", marketDataAPI.get_ticker, instId="ETH-USDT-SWAP"): "market_data"
        }

        results = {
            # 移除截图结果键
            # "screenshot": None,
            "indicators": None,
            "factors": None,
            "okx_positions": {}, # 默认空字典
            "market_data": None
        }

        for future in concurrent.futures.as_completed(future_to_task):
            task_name, result = future.result()
            results[task_name] = result
            # 移除截图模块的重试逻辑
            # if task_name == "screenshot" and not result:
            #     logger.error(f"截图模块运行失败，尝试重试3次...")
            #     for i in range(3):
            #         screenshot_path_retry = run_tradingview_screenshot()
            #         if screenshot_path_retry:
            #             results["screenshot"] = screenshot_path_retry
            #             logger.info(f"截图模块第{i+1}次重试成功，合并截图路径: {screenshot_path_retry}")
            #             break
            #         else:
            #             logger.error(f"截图模块第{i+1}次重试失败")

    # 处理 OKX 持仓数据，确保其为字典类型
    if not isinstance(results["okx_positions"], dict):
        logger.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {results['okx_positions']}")
        results["okx_positions"] = {}

    merged = {
        # 移除截图键
        # "screenshots": results["screenshot"] if results["screenshot"] else "",
        "indicators_main(非实时报价)": results["indicators"] if isinstance(results["indicators"], dict) else {},
        "factors_main": results["factors"] if isinstance(results["factors"], dict) else {},
        "data_summary(实时报价)": results["market_data"],
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
        # 移除截图模块的运行时间打印
        # if "screenshot_start" in module_timings and "screenshot_end" in module_timings:
        #     duration_screenshot = module_timings["screenshot_end"] - module_timings["screenshot_start"]
        #     print(f"截图模块运行时间: {duration_screenshot}")
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