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
from typing import Dict, Any, List, Optional, Callable
from src.core.path_manager import path_manager
from src.core.config_loader import load_config

# 确保项目根目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入子模块
from src.data.analysis.kline_pattern_analyzer import analyze_kline_patterns
from src.data.collectors.technical_indicator_collector import collect_technical_indicators
from src.data.collectors.macro_factor_collector import collect_macro_factors
from src.data.collectors.get_positions import collect_positions_data

# 全局配置
config = load_config()
PROJECT_ROOT = path_manager.project_root
LOG_FILE = path_manager.get_log_path("main_log")
MODULE_TAG = "[main_collector] "

# 日志配置
# TODO: 日志配置也可以考虑集中管理，避免在多个模块中重复设置。
logging.basicConfig(
    level=logging.WARNING,
    format='[数据收集总模块][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

# ===================== 性能和调用计数 =====================
# TODO: 使用类来封装状态是管理这些全局变量的更好方法。
# 例如，可以创建一个 `CollectorStats` 类来跟踪调用次数和执行时间。
# 这将消除对全局变量的需求，使代码更易于测试和维护。

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
# TODO: 这些工具函数与数据收集的核心逻辑耦合在一起，并且修改全局状态。
# 理想情况下，它们应该被重构为无状态的、可独立测试的函数。

def analyze_kline_patterns_wrapper(kline_data_list: list) -> dict:
    """K线模式分析的封装函数"""
    global analyze_kline_patterns_call_count
    global timing_data
    
        
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
    
        
    start_time = time.time()
    try:
        utc_plus_8 = timezone(timedelta(hours=8))
        current_time = datetime.now(timezone.utc).astimezone(utc_plus_8)
        return {"time": str(current_time)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        timing_data["gettime_exec_time"] += time.time() - start_time


def gettransactionhistory(target: str) -> dict:
    """获取最近的交易历史记录"""
    # TODO: 将导入语句移到文件顶部，以符合PEP8规范并提高代码的可读性。
    # 在函数内部导入通常是为了避免循环依赖或延迟加载，但在这里似乎没有必要。
    global get_transaction_history_call_count
    global timing_data
    
        
    start_time = time.time()
    try:
        from src.trading.api.get_transaction_history import get_latest_transactions
        history = get_latest_transactions(config)
        return {"transaction_history": history}
    except Exception as e:
        return {"error": str(e)}
    finally:
        timing_data["gettransactionhistory_exec_time"] += time.time() - start_time

# 导出所有工具函数
__all__ = [
    "gettime",
    "gettransactionhistory",
    "analyze_kline_patterns_wrapper",
]

def _analyze_and_prepare_kline_data(indicators_result: Optional[Dict[str, List[Dict]]]) -> Dict[str, Any]:
    """
    分析技术指标数据中的K线模式。

    Args:
        indicators_result: 从 collect_technical_indicators 获取的技术指标数据。

    Returns:
        处理后的K线模式字典。
    """
    if not indicators_result:
        logger.error(f"{MODULE_TAG}技术指标数据为空，跳过K线模式分析")
        return {tf: {} for tf in ["15m", "1h", "4h"]}

    kline_patterns_all = {}
    logger.info(f"{MODULE_TAG}开始分析K线模式，时间周期列表: {list(indicators_result.keys())}")

    for tf_key, klines in indicators_result.items():
        logger.info(f"{MODULE_TAG}正在分析 {tf_key} 周期的K线数据，数据条数: {len(klines) if isinstance(klines, list) else 'Invalid'}")
        if not isinstance(klines, list) or not klines:
            logger.warning(f"{MODULE_TAG}时间周期 {tf_key} 没有可用的K线数据")
            kline_patterns_all[tf_key] = {}
            continue
        
        try:
            pattern_result = analyze_kline_patterns_wrapper(klines)
            logger.info(f"{MODULE_TAG}{tf_key}周期模式分析结果类型: {type(pattern_result)}")
            
            if isinstance(pattern_result, dict):
                if "patterns" in pattern_result:
                    kline_patterns_all[tf_key] = pattern_result["patterns"]
                    logger.info(f"{MODULE_TAG}成功分析 {tf_key} 周期的K线模式")
                elif "error" in pattern_result:
                    logger.error(f"{MODULE_TAG}{tf_key}周期分析失败: {pattern_result['error']}")
                    kline_patterns_all[tf_key] = {}
                else:
                    logger.warning(f"{MODULE_TAG}{tf_key}周期返回格式异常: {pattern_result}")
                    kline_patterns_all[tf_key] = {}
            else:
                logger.error(f"{MODULE_TAG}{tf_key}周期返回非字典类型: {type(pattern_result)}")
                kline_patterns_all[tf_key] = {}
        except Exception as e:
            logger.error(f"{MODULE_TAG}分析时间周期 {tf_key} 的K线模式时发生错误: {str(e)}", exc_info=True)
            kline_patterns_all[tf_key] = {}
    return kline_patterns_all


def _filter_and_trim_indicator_data(indicators_data: Dict[str, Any], view_num: int = 10) -> Dict[str, Any]:
    """
    筛选和修剪技术指标数据。

    Args:
        indicators_data: 原始技术指标数据。
        view_num: 每个时间周期要保留的最新K线数量。

    Returns:
        处理后的技术指标数据。
    """
    # TODO: 这些要移除的键应该被外部化到配置文件中，而不是硬编码。
    # 这将使得在不修改代码的情况下调整指标集成为可能。
    keys_to_remove = ["StochRSI_K", "StochRSI_D", "Stoch_K", "Stoch_D", "EMA144", "EMA200",
                      "ADX", "BB_upper", "BB_lower", "BB_middle", "MACD_Signal", "MACD_Hist"]
                      
    trimmed_data = {}
    for tf_key, klines in indicators_data.items():
        if not isinstance(klines, list):
            trimmed_data[tf_key] = klines
            continue
        
        # 筛选指标
        filtered_klines = []
        for kline in klines:
            if isinstance(kline, dict):
                for key in keys_to_remove:
                    kline.pop(key, None)
            filtered_klines.append(kline)
        
        # 保留最新的K线
        if len(filtered_klines) > view_num:
            trimmed_data[tf_key] = filtered_klines[-view_num:]
        else:
            trimmed_data[tf_key] = filtered_klines
            
    return trimmed_data


def collect_and_save_data(data_collectors: Dict[str, Callable[[], Any]], save_path: str) -> Dict[str, Any]:
    """
    并行执行所有数据收集器，并将结果合并、保存。

    Args:
        data_collectors (Dict[str, Callable[[], Any]]): 一个字典，键是数据名称，值是数据收集函数。
        save_path (str): 保存合并后数据的JSON文件路径。

    Returns:
        Dict[str, Any]: 包含所有收集到的数据的字典。
    """
    collected_data = {}
    timings = {}

    # 使用线程池并行执行数据收集
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_name = {executor.submit(func): name for name, func in data_collectors.items()}
        for future in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[future]
            start_time = time.time()
            try:
                result = future.result()
                collected_data[name] = result
                logger.info(f"成功收集 '{name}' 数据")
            except Exception as e:
                logger.error(f"收集 '{name}' 数据时出错: {e}", exc_info=True)
            finally:
                end_time = time.time()
                timings[name] = end_time - start_time

    # --- 5. 获取截图 (可选) ---
    logger.info("开始获取截图...")
    screenshot_config = config.get("screenshots")
    if screenshot_config and isinstance(screenshot_config, dict) and screenshot_config.get("timeframes"):
        timeframes = screenshot_config["timeframes"]
        if isinstance(timeframes, list) and timeframes:
            try:
                # 确保服务正在运行
                time.sleep(2)
                
                # 构建请求URL
                timeframes_str = ",".join(map(str, timeframes))
                screenshot_url = f"http://127.0.0.1:8888/screenshot?timeframes={timeframes_str}"
                
                logger.info(f"向截图服务发送请求: {screenshot_url}")
                response = requests.get(screenshot_url, timeout=120)
                response.raise_for_status()
                
                screenshot_data = response.json()
                if screenshot_data and screenshot_data.get("status") == "success":
                    collected_data["screenshots"] = screenshot_data.get("screenshots", {})
                    logger.info(f"成功获取截图，文件信息: {screenshot_data.get('screenshots')}")
                else:
                    logger.error(f"截图失败: {screenshot_data.get('message', '无详细错误信息')}")
            except requests.exceptions.RequestException as e:
                logger.error(f"调用截图服务失败: {e}")
            except Exception as e:
                logger.error(f"处理截图时发生未知错误: {e}")
        else:
            logger.warning("配置文件中的 'screenshots.timeframes' 为空或格式不正确，跳过截图。")
    else:
        logger.info("配置文件中未找到或未启用截图配置 ('screenshots.timeframes')，跳过截图。")


    # --- 6. 保存所有收集的数据 ---
    logger.info("所有数据收集完毕，正在保存...")
    try:
        # 使用 path_manager 来获取完整路径
        output_path = path_manager.get_data_path("collected_data.json")
        # 先序列化，确保合法
        json_str = json.dumps(collected_data, ensure_ascii=False, indent=2)
        logger.info(f"collected_data: {json_str}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info(f"{MODULE_TAG}所有数据已成功收集并保存到 {output_path}")

        # 输出运行时间统计
        logger.info("\n--- 模块运行时间统计 ---")
        for task_name in ["indicators", "factors", "okx_positions", "current_time"]:
            start_key = f"{task_name}_start"
            end_key = f"{task_name}_end"
            if start_key in timings and end_key in timings:
                duration = timings[end_key] - timings[start_key]
                print(f"{task_name} 模块运行时间: {duration}")
        print("--------------------------")
        print("完成")
        end_time = datetime.now()
        duration = end_time - begin_time
        print(f"总运行时间: {duration}")

    except Exception as e:
        logger.error(f"{MODULE_TAG}保存合并数据失败: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

    return collected_data

def main():
    """主函数：收集所有数据并合并输出为标准化JSON"""
    proxies = {
        "http": config["proxy"]["http_proxy"],
        "https": config["proxy"]["https_proxy"]
    }
    begin_time = datetime.now()
    module_timings = {} # 用于存储每个模块的运行时间

    def _run_task_with_timing(task_name, func, *args, **kwargs):
        """运行任务并记录开始和结束时间"""
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
            
            # 2. 对每个时间周期的数据进行K线模式分析
            kline_patterns_all = _analyze_and_prepare_kline_data(indicators_result)
            
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
                "tools_timing": timing_data,
            }

        except Exception as e:
            logger.error(f"{MODULE_TAG}任务执行失败: {e}")
            results = {
                "indicators": None,
                "factors": None,
                "okx_positions": {},
                "current_time": None,
                "kline_patterns": None,
                "tools_timing": timing_data,
            }
            kline_patterns_all = {}

    # 处理结果
    if not isinstance(results["okx_positions"], dict):
        logger.warning(f"OKX 持仓脚本输出非 JSON 字典格式或解析失败: {results['okx_positions']}")
        results["okx_positions"] = {}

    # 合并所有数据
    # K线模式数据已经在前面的步骤中处理完成
    if not isinstance(results["kline_patterns"], dict):
        logger.warning(f"{MODULE_TAG}K线模式分析结果格式异常，使用空字典代替")
        results["kline_patterns"] = {"15m": {}, "1h": {}, "4h": {}}

    # 处理技术指标数据
    if isinstance(results["indicators"], dict):
        results["indicators"] = _filter_and_trim_indicator_data(results["indicators"])

    # 获取所有截图文件路径
    screenshots_dir = os.path.join(PROJECT_ROOT, "data", "screenshots")
    def screenshots():
        """获取屏幕截图的函数"""
        def get_screenshots():
            """获取屏幕截图的函数,自带check"""
            try:
                from src.data.collectors.tradingview_auto_screenshot import main as screenshot_main
                res_path = screenshot_main()
                def check():
                    """检查截图路径是否有效"""
                    if not res_path or not isinstance(res_path, dict):
                        logger.error("获取屏幕截图失败，返回结果无效")
                        return False
                    for key, path in res_path.items():
                        if not os.path.exists(path):
                            logger.error(f"截图文件不存在: {path}")
                            return False
                    return True
                if not check():
                    logger.error("获取屏幕截图失败，返回结果无效尝试重试")
                    time.sleep(1)
                    res_path = screenshot_main()  # 再次尝试获取截图
                if not check():
                    logger.error("获取屏幕截图失败，重试后仍然无效")
                    return {}
                logger.info(f"获取屏幕截图成功，返回结果: {res_path}")
                return res_path
            except Exception as e:
                logger.error(f"获取屏幕截图失败: {e}")
                return {}

        screenshots=get_screenshots()
        if screenshots is not None and isinstance(screenshots, dict):
            logger.info(f"获取屏幕截图成功，包含 {len(screenshots)} 个时间周期的截图")
        else:
            logger.error("获取屏幕截图失败，使用空字典代替")
            screenshots = {}
        return screenshots
    
    merged = {
        "screenshots": screenshots(),  # --new
        "indicators_main(非实时报价)": results["indicators"],# --debug
        "factors_main": results["factors"] if isinstance(results["factors"], dict) else {},
        "okx_positions": results["okx_positions"],
        "current_time": results["current_time"]["time"] if isinstance(results["current_time"], dict) and "time" in results["current_time"] else "",
        "kline_patterns(analyze_kline_patterns)": results["kline_patterns"],
        "tools_performance": results["tools_timing"],
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).astimezone(timezone(timedelta(hours=8))).isoformat()
    }

    # 保存合并后的数据到文件 - 使用配置文件中定义的路径
    output_path = os.path.join(PROJECT_ROOT, config["data_path"])
    try:
        # 先序列化，确保合法
        json_str = json.dumps(merged, ensure_ascii=False, indent=2)
        logger.info(f"merged: {json_str}")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        logger.info(f"{MODULE_TAG}所有数据已成功收集并保存到 {output_path}")

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
        logger.error(f"{MODULE_TAG}保存合并数据失败: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == "__main__":
    main()