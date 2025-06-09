# 本文件用于作为主控脚本，依次调用技术指标采集和宏观因子采集脚本，合并输出为标准化JSON，供GUI等模块调用。

import subprocess
import os
import json
import time
from datetime import datetime, timezone, timedelta
import re
import sys
import logging
import threading
import requests
import concurrent.futures
from okx.api import Market  # type: ignore

# 确保function目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入子模块
from function.kline_pattern_analyzer import analyze_kline_patterns
from get_data.technical_indicator_collector import collect_technical_indicators
from get_data.macro_factor_collector import collect_macro_factors
from get_data.get_positions import collect_positions_data

# 初始化配置
config = json.load(open("config/config.json", "r"))

http_proxy = config["proxy"]["http_proxy"]
https_proxy = config["proxy"]["https_proxy"]
os.environ["http_proxy"] = http_proxy
os.environ["https_proxy"] = https_proxy

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]
MODULE_TAG = "[main_collector] "

# 日志配置
logging.basicConfig(
    level=logging.WARNING,
    format='[数据收集总模块][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

# 工具函数计数器
get_time_call_count = 0
get_transaction_history_call_count = 0
analyze_kline_patterns_call_count = 0
execute_python_code_call_count = 0

# 性能计时器
timing_data = {
    "gettime_exec_time": 0.0,
    "gettransactionhistory_exec_time": 0.0,
    "executepythoncode_exec_times": [],
    "analyzeklinepatterns_exec_time": 0.0,
}

# ===================== 工具函数定义 =====================

def analyze_kline_patterns_wrapper(kline_data_list: list) -> dict:
    """K线模式分析的封装函数"""
    global analyze_kline_patterns_call_count
    global timing_data
    
    analyze_kline_patterns_call_count += 1
    if analyze_kline_patterns_call_count > 5:  # 修改限制次数为5次，因为我们有3个时间周期需要分析
        logger.warning(f"{MODULE_TAG}K线分析调用次数超限")
        return {"error": "K线分析工具调用次数超限"}
        
    start_time = time.time()
    try:
        result = analyze_kline_patterns(kline_data_list)
        return {"patterns": result}
    except Exception as e:
        logger.error(f"{MODULE_TAG}K线分析异常: {e}")
        return {"error": str(e)}
    finally:
        timing_data["analyzeklinepatterns_exec_time"] += time.time() - start_time

def gettime(target: str = "当前时间") -> dict:
    """获取当前北京时间"""
    global get_time_call_count
    global timing_data
    
    get_time_call_count += 1
    if get_time_call_count > 2:
        return {"error": "获取时间工具调用次数超限"}
        
    start_time = time.time()
    try:
        utc_plus_8 = timezone(timedelta(hours=8))
        current_time = datetime.now(timezone.utc).astimezone(utc_plus_8)
        return {"time": str(current_time)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        timing_data["gettime_exec_time"] += time.time() - start_time

def executepythoncode(code: str) -> dict:
    """执行Python代码"""
    global execute_python_code_call_count
    global timing_data
    
    execute_python_code_call_count += 1
    if execute_python_code_call_count > 5:
        return {
            "stdout": "",
            "stderr": "代码执行工具调用次数超限",
            "returncode": 1
        }
        
    start_time = time.time()
    try:
        process = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=180,
            check=False
        )
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "returncode": process.returncode
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": 1
        }
    finally:
        timing_data["executepythoncode_exec_times"].append(time.time() - start_time)

def gettransactionhistory(target: str) -> dict:
    """获取最近的交易历史记录"""
    global get_transaction_history_call_count
    global timing_data
    
    get_transaction_history_call_count += 1
    if get_transaction_history_call_count > 2:
        return {"error": "获取交易历史工具调用次数超限"}
        
    start_time = time.time()
    try:
        from get_transaction_history import get_latest_transactions
        history = get_latest_transactions(config)
        return {"transaction_history": history}
    except Exception as e:
        return {"error": str(e)}
    finally:
        timing_data["gettransactionhistory_exec_time"] += time.time() - start_time

# 导出所有工具函数
__all__ = [
    "gettime",
    "executepythoncode",
    "gettransactionhistory",
    "analyze_kline_patterns_wrapper",
]

def main():
    """主函数：收集所有数据并合并输出为标准化JSON"""
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
        try:
            logger.info(f"{task_name} 模块运行中...")
            result = func(*args, **kwargs)
            logger.info(f"{task_name} 模块完成。")
            return result
        except Exception as e:
            logger.error(f"{MODULE_TAG}{task_name} 模块运行失败: {e}")
            return None
        finally:
            module_timings[end_time_key] = datetime.now()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        try:
            # 1. 首先获取技术指标数据
            logger.info(f"{MODULE_TAG}开始获取技术指标数据...")
            indicators_result = _run_task_with_timing("indicators", collect_technical_indicators)
            print(f"{MODULE_TAG}技术指标数据获取完成，结果类型: {type(indicators_result)}")
            if not indicators_result:
                logger.error(f"{MODULE_TAG}获取技术指标数据失败")
                return
            
            # 2. 对每个时间周期的数据进行K线模式分析
            kline_patterns_all = {}
            logger.info(f"{MODULE_TAG}开始分析K线模式，时间周期列表: {list(indicators_result.keys())}")
            
            if not indicators_result:
                logger.error(f"{MODULE_TAG}技术指标数据为空，跳过K线模式分析")
                kline_patterns_all = {tf: {} for tf in ["15m", "1h", "4h"]}
            else:
                for tf_key, klines in indicators_result.items():
                    logger.info(f"{MODULE_TAG}正在分析 {tf_key} 周期的K线数据，数据条数: {len(klines) if isinstance(klines, list) else 'Invalid'}")
                    if not isinstance(klines, list) or not klines:
                        logger.warning(f"{MODULE_TAG}时间周期 {tf_key} 没有可用的K线数据")
                        kline_patterns_all[tf_key] = {}
                        continue
                    
                    try:
                        pattern_result = analyze_kline_patterns_wrapper(klines)
                        logger.info(f"{MODULE_TAG}{tf_key}周期模式分析结果类型: {type(pattern_result)}, 内容: {pattern_result}")
                        
                        if isinstance(pattern_result, dict):
                            if "patterns" in pattern_result:
                                kline_patterns_all[tf_key] = pattern_result["patterns"]
                                logger.info(f"{MODULE_TAG}成功分析 {tf_key} 周期的K线模式，包含 {len(pattern_result['patterns'])} 个指标")
                            elif "error" in pattern_result:
                                logger.error(f"{MODULE_TAG}{tf_key}周期分析失败: {pattern_result['error']}")
                                kline_patterns_all[tf_key] = {}
                            else:
                                logger.warning(f"{MODULE_TAG}{tf_key}周期返回格式异常，既无patterns也无error: {pattern_result}")
                                kline_patterns_all[tf_key] = {}
                        else:
                            logger.error(f"{MODULE_TAG}{tf_key}周期返回非字典类型: {type(pattern_result)}")
                            kline_patterns_all[tf_key] = {}
                    except Exception as e:
                        logger.error(f"{MODULE_TAG}分析时间周期 {tf_key} 的K线模式时发生错误: {str(e)}", exc_info=True)
                        kline_patterns_all[tf_key] = {}
            
            # 3. 并行执行其他任务
            factors_future = executor.submit(_run_task_with_timing, "factors", collect_macro_factors)
            positions_future = executor.submit(_run_task_with_timing, "okx_positions", collect_positions_data)
            time_future = executor.submit(_run_task_with_timing, "current_time", gettime)

            # 4. 收集所有结果
            results = {
                "indicators": indicators_result,
                "factors": factors_future.result(),
                "okx_positions": positions_future.result() or {},
                "current_time": time_future.result(),
                "kline_patterns": kline_patterns_all,
                "tools_timing": timing_data
            }
            
        except Exception as e:
            logger.error(f"{MODULE_TAG}任务执行失败: {e}")
            results = {
                "indicators": None,
                "factors": None,
                "okx_positions": {},
                "current_time": None,
                "kline_patterns": None,
                "tools_timing": timing_data
            }
            kline_patterns_all = {}

    # 处理结果
    if not isinstance(results["okx_positions"], dict):
        logger.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {results['okx_positions']}")
        results["okx_positions"] = {}

    # 合并所有数据
    # K线模式数据已经在前面的步骤中收集完成，这里直接使用
    if not isinstance(results["kline_patterns"], dict):
        logger.warning(f"{MODULE_TAG}K线模式分析结果格式异常")
        results["kline_patterns"] = {
            "15m": {},
            "1h": {},
            "4h": {}
        }

    # 处理技术指标数据 - 直接使用collect_technical_indicators的结果
    indicators_data = {}
    if isinstance(results["indicators"], dict):
        indicators_data = results["indicators"]
    #保留每个时间周期最新的15条k线
    view_num=10
    for tf_key, klines in indicators_data.items():
        if isinstance(klines, list) and len(klines) > view_num:
            indicators_data[tf_key] = klines[-view_num:]

    # 筛选掉不需要的指标
    keys_to_remove = ["StochRSI_K", "StochRSI_D", "Stoch_K", "Stoch_D", "EMA144", "EMA200",
                      "ADX", "BB_upper", "BB_lower", "BB_middle", "MACD_Signal", "MACD_Hist"]
    for tf_key, klines in indicators_data.items():
        if isinstance(klines, list):
            for kline in klines:
                if isinstance(kline, dict):
                    for key in keys_to_remove:
                        kline.pop(key, None) # 使用 pop(key, None) 避免 key 不存在时出错

    # 对数值进行四舍五入以减少文本量
    price_keys = ["open", "high", "low", "close", "BB_upper", "BB_middle", "BB_lower", "EMA5", "EMA21", "EMA55", "VWAP"]
    indicator_keys = ["RSI", "ATR", "MACD"]

    for tf_key, klines in indicators_data.items():
        if isinstance(klines, list):
            for kline in klines:
                if isinstance(kline, dict):
                    for key, value in kline.items():
                        if isinstance(value, float):
                            if key in price_keys:
                                kline[key] = round(value, 2)
                            elif key in indicator_keys:
                                kline[key] = round(value, 3)
                            # 对于 volume 等其他数值，可以根据需要决定是否四舍五入或保留小数位数
                            # 目前保持原样

    print(results["indicators"])
    merged = {
        "indicators_main(非实时报价)": indicators_data,
        "factors_main": results["factors"] if isinstance(results["factors"], dict) else {},
        "okx_positions": results["okx_positions"],
        "current_time": results["current_time"]["time"] if isinstance(results["current_time"], dict) and "time" in results["current_time"] else "",
        "kline_patterns": results["kline_patterns"],
        "tools_performance": results["tools_timing"],
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

        # 输出运行时间统计
        logger.info("\n--- 模块运行时间统计 ---")
        for task_name in ["indicators", "factors", "okx_positions", "current_time"]:
            start_key = f"{task_name}_start"
            end_key = f"{task_name}_end"
            if start_key in module_timings and end_key in module_timings:
                duration = module_timings[end_key] - module_timings[start_key]
                print(f"{task_name} 模块运行时间: {duration}")
        print("--------------------------")
        print("完成")
        end_time = datetime.now()
        duration = end_time - begin_time
        print(f"总运行时间: {duration}")

    except Exception as e:
        logger.error(f"写入data.json失败: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    main()