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

config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r"))


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
flag="0"
marketDataAPI = Market(flag=flag)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["ETH_log_path"]
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
            obj, end = decoder.raw_decode(text[idx:])
            return obj
        except json.JSONDecodeError:
            idx += 1
    return None

venv_python = config["python_path"]["global"]

def run_script(name, proxies=None):
    path = os.path.join(BASE_DIR, name)
    env = os.environ.copy()
    # 先不传代理，排查网络问题
    # if proxies:
    #     if 'http' in proxies:
    #         env['http_proxy'] = proxies['http']
    #     if 'https' in proxies:
    #         env['https_proxy'] = proxies['https']
    try:
        result = subprocess.run(
            [venv_python, path],
            capture_output=True,
            text=True,
            env=env,
            cwd=BASE_DIR  # 保证子模块在同一目录下运行
        )
        # 日志映射
       
        if result.stdout is not None:
            # 尝试解析 JSON 输出
            json_output = extract_first_json(result.stdout)
            if json_output is not None:
                return json_output
            else:
                logging.warning(f"{name} 输出非 JSON 格式: {result.stdout.strip()}")
                return {} # 返回空字典，避免None
        return {} # 没有输出也返回空字典
    except Exception as e:
        logging.error(f"运行{name}异常: {e}")
        return {} # 异常时返回空字典

def run_tradingview_screenshot():
    """
    调用 tradingview_auto_screenshot.py，返回截图文件路径（如成功），否则返回 None。
    """
    path = os.path.join(BASE_DIR, "tradingview_auto_screenshot.py")
    try:
        result = subprocess.run(
            [config["python_path"]["venv_selenium"], path],  # 强制使用虚拟环境解释器
            capture_output=True,
            text=True
        )
        # 日志映射
        if result.stdout:
            for line in result.stdout.splitlines():
                logging.info(f"[tradingview_auto_screenshot.py][stdout] {line}")
        if result.stderr:
            for line in result.stderr.splitlines():
                logging.error(f"[tradingview_auto_screenshot.py][stderr] {line}")
        for line in result.stdout.splitlines():
            if "剪切板图片已保存:" in line:
                filepath = line.split("剪切板图片已保存:")[-1].strip()
                if os.path.exists(filepath):
                    return filepath
        if result.stdout.strip():
            return result.stdout.strip().splitlines()[-1]
        return None
    except Exception as e:
        logging.error(f"运行tradingview_auto_screenshot.py异常: {e}")
        return None

if __name__ == "__main__":
    # 将所有print输出（除最后"完成"）改为logging，stdout只输出"完成"
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
    proxies = {
        "http": config["proxy"]["http_proxy"],
        "https": config["proxy"]["https_proxy"]
    }
    begin_time = datetime.now()
    logging.info("截图模块运行中...")
    screenshot_path = run_tradingview_screenshot()
    logging.info(f"截图模块完成，截图路径: {screenshot_path}")
    logging.info("技术指标模块运行中...")
    indicators_output = run_script("technical_indicator_collector.py", proxies=proxies)
    logging.info(f"技术指标模块完成，结果类型: {type(indicators_output)}")
    logging.info("宏观因子模块运行中...")
    factors_output = run_script("macro_factor_collector.py", proxies=proxies)
    logging.info(f"宏观因子模块完成，结果类型: {type(factors_output)}")
    logging.info("OKX 持仓模块运行中...")
    okx_process = subprocess.run(
            [config["python_path"]["venv_okx"], "get_positions.py"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR  # 保证子模块在同一目录下运行
        )
    # 尝试解析 OKX 持仓脚本的输出，确保结果是字典类型
    okx_positions_raw = okx_process.stdout if okx_process.stdout else ""
    okx_positions = extract_first_json(okx_positions_raw)
    if not isinstance(okx_positions, dict):
        # 如果解析失败或结果不是字典，记录警告并使用空字典
        logging.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {okx_positions_raw.strip()}")
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
    data_path = config["ETH_data_path"]
    tmp_path = data_path + ".tmp"
    try:
        # 先序列化，确保合法
        json_str = json.dumps(merged, ensure_ascii=False, indent=2)
        logging.info(f"merged: {json_str}")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        os.replace(tmp_path, data_path)  # 原子性替换
        print("完成")  # 只输出完成
    except Exception as e:
        logging.error(f"写入data.json失败: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
