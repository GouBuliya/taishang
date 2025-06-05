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

    logging.info("截图模块运行中...")
    module_timings["screenshot_start"] = datetime.now()
    #重试3次
    for i in range(3):
        screenshot_path = run_tradingview_screenshot()
        if screenshot_path:
            break
        else:
            logging.error(f"截图模块第{i+1}次运行失败")
    
    module_timings["screenshot_end"] = datetime.now()
    logging.info(f"截图模块完成，截图路径: {screenshot_path}")

    logging.info("技术指标模块运行中...")
    module_timings["indicators_start"] = datetime.now()
    indicators_output = collect_technical_indicators()
    module_timings["indicators_end"] = datetime.now()
    logging.info(f"技术指标模块完成，结果类型: {type(indicators_output)}")

    logging.info("宏观因子模块运行中...")
    module_timings["factors_start"] = datetime.now()
    factors_output = collect_macro_factors()
    module_timings["factors_end"] = datetime.now()
    logging.info(f"宏观因子模块完成，结果类型: {type(factors_output)}")

    logging.info("OKX 持仓模块运行中...")
    module_timings["okx_positions_start"] = datetime.now()
    okx_positions = collect_positions_data()
    module_timings["okx_positions_end"] = datetime.now()
    # 尝试解析 OKX 持仓脚本的输出，确保结果是字典类型
    if not isinstance(okx_positions, dict):
        # 如果解析失败或结果不是字典，记录警告并使用空字典
        logging.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {okx_positions}")
        okx_positions = {}
    logging.info(f"OKX 持仓模块完成，结果类型: {type(okx_positions)}")
    
    data = marketDataAPI.get_ticker(
        instId="ETH-USDT-SWAP"
    )
    
    
    merged = {
        "clipboard_image_path": screenshot_path if screenshot_path else "",
        "indicators_main": indicators_output if isinstance(indicators_output, dict) else {},
        "factors_main": factors_output if isinstance(factors_output, dict) else {},
        "data_summary": data,
        "okx_positions": okx_positions ,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).astimezone(timezone(timedelta(hours=8))).isoformat() # 东八区时间

    }
    # 写入 data.json
    end_time = datetime.now()
    duration = end_time - begin_time
    logging.info(f"总运行时间: {duration}")
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
    except Exception as e:
        logging.error(f"写入data.json失败: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
