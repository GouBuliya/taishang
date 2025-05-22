# 本文件用于作为主控脚本，依次调用技术指标采集和宏观因子采集脚本，合并输出为标准化JSON，供GUI等模块调用。

import subprocess
import os
import json
from datetime import datetime, timezone
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

def run_script(name):
    path = os.path.join(BASE_DIR, name)
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True
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

if __name__ == "__main__":
    indicators = run_script("technical_indicator_collector.py")
    factors = run_script("macro_factor_collector.py")

    if indicators and factors and isinstance(indicators, dict) and isinstance(factors, dict):
        merged = {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
            "indicators": indicators,
            "factors": factors
        }
        print(json.dumps(merged, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"error": "技术指标或宏观因子采集失败"}, ensure_ascii=False))
