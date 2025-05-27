# 本文件用于作为主控脚本，依次调用技术指标采集和宏观因子采集脚本，合并输出为标准化JSON，供GUI等模块调用。

import subprocess
import os
import json
from datetime import datetime, timezone
import re
import sys
from okx.api import Market  # type: ignore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
flag="0"
marketDataAPI = Market(flag=flag)

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

venv_python = "venv/bin/python"

def run_script(name, proxies=None):
    path = os.path.join(BASE_DIR, name)
    env = os.environ.copy()
    # 支持通过环境变量传递代理
    if proxies:
        if 'http' in proxies:
            env['http_proxy'] = proxies['http']
        if 'https' in proxies:
            env['https_proxy'] = proxies['https']
    try:
        result = subprocess.run(
            [venv_python, path],  # 强制使用虚拟环境解释器
            capture_output=True,
            text=True,
            env=env
        )
        stdout = result.stdout
        obj = extract_first_json(stdout)
        if obj is not None:
            return obj
        # 若无json，输出调试信息
        print(f"{name} 脚本输出内容：", result.stdout)
        print(f"{name} 脚本错误输出：", result.stderr)
        return None
    except Exception as e:
        print(f"运行{name}异常: {e}")
        return None

def run_tradingview_screenshot():
    """
    调用 tradingview_auto_screenshot.py，返回截图文件路径（如成功），否则返回 None。
    """
    path = os.path.join(BASE_DIR, "tradingview_auto_screenshot.py")
    try:
        result = subprocess.run(
            [venv_python, path],  # 强制使用虚拟环境解释器
            capture_output=True,
            text=True
        )
        # 在输出中查找 [DEBUG] 剪切板图片已保存: 路径
        for line in result.stdout.splitlines():
            if "剪切板图片已保存:" in line:
                filepath = line.split("剪切板图片已保存:")[-1].strip()
                if os.path.exists(filepath):
                    return filepath
        # 新增：如果没有找到，直接返回stdout最后一行（便于调试）
        if result.stdout.strip():
            return result.stdout.strip().splitlines()[-1]
        return None
    except Exception as e:
        print(f"运行tradingview_auto_screenshot.py异常: {e}")
        return None

if __name__ == "__main__":
    # 将所有print输出（除最后“完成”）改为logging，stdout只输出“完成”
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
    proxies = {
        "http": "http://127.0.0.1:1080",
        "https": "http://127.0.0.1:1080"
    }
    logging.info("截图模块运行中...")
    screenshot_path = run_tradingview_screenshot()
    logging.info(f"截图模块完成，截图路径: {screenshot_path}")
    logging.info("技术指标模块运行中...")
    indicators = run_script("technical_indicator_collector.py", proxies=proxies)
    logging.info(f"技术指标模块完成，结果: {indicators}")
    logging.info("宏观因子模块运行中...")
    factors = run_script("macro_factor_collector.py", proxies=proxies)
    logging.info(f"宏观因子模块完成，结果: {factors}")
    data = marketDataAPI.get_ticker(
        instId="ETH-USDT-SWAP"
    )
    merged = {
        "clipboard_image_path": screenshot_path if screenshot_path else "",
        "indicators": indicators if isinstance(indicators, dict) else {},
        "factors": factors if isinstance(factors, dict) else {},
        "data": data,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
    }
    # 写入 data.json
    data_path = os.path.join(BASE_DIR, "data.json")
    try:
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print("完成")  # 只输出完成
    except Exception as e:
        logging.error(f"失败: {e}")
