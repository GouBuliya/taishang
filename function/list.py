
# --- 新增：获取初始信息工具 ---
def get_initial_data() -> dict:
    """
    获取系统启动时加载的初始交易环境和市场信息。
    此工具不接受任何参数，并返回加载的JSON数据。
    """
    global get_initial_data_call_count
    global timing_data
    get_initial_data_call_count += 1

    # 根据需要设置调用次数限制
    if get_initial_data_call_count > 2: # 通常初始数据只获取一次
        logger.warning(f"{MODULE_TAG}get_initial_data 调用次数超限，已达到 {get_initial_data_call_count} 次。")
        return {"error": "获取初始数据工具调用次数超限，请尝试其他方式获取。"}

    start_time = time.time()
    try:
        global data_json
        # 如果 data_json 尚未加载，则在这里加载
        if not data_json:
            data_json_path = config["data_path"]
            with open(data_json_path, "r", encoding="utf-8") as f:
                data_json = json.load(f)
            logger.info(f"{MODULE_TAG}初始数据从文件加载完成: {data_json_path}")
        
        res_str = json.dumps(data_json, indent=2, ensure_ascii=False)
        logger.info(f"{MODULE_TAG}模块获取初始数据完成")
        return {"initial_data": res_str, "source": "local_module"}
    except FileNotFoundError:
        logger.error(f"{MODULE_TAG}初始数据文件未找到: {config['data_path']}")
        return {"error": f"初始数据文件未找到: {config['data_path']}"}
    except json.JSONDecodeError:
        logger.error(f"{MODULE_TAG}解码初始数据 JSON 失败: {config['data_path']}")
        return {"error": f"解码初始数据 JSON 失败: {config['data_path']}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}调用 get_initial_data 异常: {e}")
        return {"error": f"模块调用异常: {e}"}
    finally:
        end_time = time.time()
        timing_data["getinitialdata_exec_time"] += (end_time - start_time)

get_initial_data_declaration = {
    "name": "get_initial_data",
    "description": "获取系统启动时加载的初始交易环境和市场信息，这些信息以JSON格式提供，供后续分析和决策使用。此工具不接受任何参数。",
    "parameters": {
        "type": "object",
        "properties": {}, # 没有参数
        "required": []    # 没有必需参数
    }
}
# --- 新增工具结束 ---


analyze_kline_patterns_declaration = {
    "name": "analyze_kline_patterns",
    "description": "对给定时间周期的K线数据进行数值化模式识别和技术指标分析。此工具将替代对K线图的视觉判断，直接从数值数据中提取K线形态、布林带、EMA排列、RSI和MACD的特征。",
    "parameters": {
        "type": "object",
        "properties": {
            "kline_data_list": {
                "type": "array",
                "description": "包含K线数据的列表，每项是一个字典。列表应包含至少15条K线，以确保指标计算的完整性。每条K线字典应包含 'open', 'high', 'low', 'close', 'volume' 以及 'RSI', 'MACD_macd', 'MACD_signal', 'BB_upper', 'BB_middle', 'BB_lower', 'EMA5', 'EMA21', 'EMA55', 'EMA144', 'EMA200' 等指标。",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string"},
                        "open": {"type": "number"},
                        "high": {"type": "number"},
                        "low": {"type": "number"},
                        "close": {"type": "number"},
                        "volume": {"type": "number"},
                        "RSI": {"type": "number"},
                        "MACD_macd": {"type": "number"},
                        "MACD_signal": {"type": "number"},
                        "ATR": {"type": "number"},
                        "ADX": {"type": "number"},
                        "Stoch_K": {"type": "number"},
                        "Stoch_D": {"type": "number"},
                        "StochRSI_K": {"type": "number"},
                        "StochRSI_D": {"type": "number"},
                        "BB_upper": {"type": "number"},
                        "BB_middle": {"type": "number"},
                        "BB_lower": {"type": "number"},
                        "EMA5": {"type": "number"},
                        "EMA21": {"type": "number"},
                        "EMA55": {"type": "number"},
                        "EMA144": {"type": "number"},
                        "EMA200": {"type": "number"},
                        "VWAP": {"type": "number"}
                    },
                    "required": ["timestamp", "open", "high", "low", "close", "volume", "RSI", "MACD_macd", "MACD_signal", "BB_upper", "BB_middle", "BB_lower", "EMA5", "EMA21", "EMA55", "EMA144", "EMA200"]
                }
            }
        },
        "required": ["kline_data_list"]
    }
}


def gettransactionhistory(target: str) -> dict:
    """
    Args:
        target: 目标（例如，'ETH-USDT'）
    Returns:
        最近3条交易历史记录 (JSON 格式)
    """
    global get_transaction_history_call_count
    global timing_data
    get_transaction_history_call_count += 1

    if get_transaction_history_call_count > 2:
        logger.warning(f"{MODULE_TAG}gettransactionhistory 调用次数超限，已达到 {get_transaction_history_call_count} 次。")
        return {"error": "获取交易历史工具调用次数超限，请尝试其他方式获取。"}

    start_time = time.time() # Start timing
    try:
        res_json_str = get_transaction_history.get_latest_transactions(config) # Pass the global config
        logger.info(f"{MODULE_TAG}模块获取最后3条交易纪录完成")

        try:
            res = json.loads(res_json_str)
        except json.JSONDecodeError:
            res = {"transaction_history": res_json_str.strip()}
            
        return {"transaction_history":res, "source": "local_module"}
    except ImportError as e:
        logger.error(f"{MODULE_TAG}导入 get_transaction_history 模块失败: {e}")
        return {"error": f"导入模块失败: {e}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}调用 get_transaction_history.get_latest_transactions 异常: {e}")
        return {"error": f"模块调用异常: {e}"}
    finally:
        end_time = time.time()
        timing_data["gettransactionhistory_exec_time"] += (end_time - start_time)

get_transaction_history_declaration = {
    "name": "gettransactionhistory",
    "description": "获取最近3条交易历史记录 (本地执行)",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "要获取交易历史记录的目标（例如，'ETH-USDT'）"
            },
        },
        "required": ["target"]
    }
}

def gettime(target: str) -> dict:
    """
    Args:
        target: 获取时间的上下文目标（例如，'当前时间'）
    Returns:
        当前时间 (JSON 格式)
    """

    def get_beijing_time_offset():
    # 定义 UTC+8 小时偏移量
        utc_plus_8 = datetime.timezone(datetime.timedelta(hours=8))

    # 获取当前 UTC 时间
        utc_now = datetime.datetime.now(datetime.timezone.utc)

    # 将 UTC 时间转换为 UTC+8 时间
        beijing_now = utc_now.astimezone(utc_plus_8)

        return beijing_now
    
    global get_time_call_count
    global timing_data
    get_time_call_count += 1

    if get_time_call_count > 2:
        logger.warning(f"{MODULE_TAG}gettime 调用次数超限，已达到 {get_time_call_count} 次。")
        return {"error": "获取时间工具调用次数超限，请尝试其他方式获取。"}

    start_time = time.time() # Start timing
    try:
        current_time =  get_beijing_time_offset() #北京时间
        logger.info(f"{MODULE_TAG}模块获取当前时间完成")
        res =  str(current_time)
        return {"time":res, "source": "local_module"}
    except ImportError as e:
        logger.error(f"{MODULE_TAG}导入 get_time 模块失败: {e}")
        return {"error": f"导入模块失败: {e}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}调用 get_time.get_current_time 异常: {e}")
        return {"error": f"模块调用异常: {e}"}
    finally:
        end_time = time.time()
        timing_data["gettime_exec_time"] += (end_time - start_time)

get_time_declaration = {
    "name": "gettime",
    "description": "获取当前时间 (本地执行)",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "获取时间的上下文目标（例如，'当前时间'）"
            },
        },
        "required": ["target"]
    }
}

def executepythoncode(code: str) -> dict:
    """
    Executes the given Python code string in a separate process.
    Important: The code execution tool can only be used in win rate and expected return calculations and decision position calculations and trading operations. The standard number of uses is 2 times, and the maximum number of uses allowed is 2 times.
    Args:
        code: The Python code to execute as a string.

    Returns:
        A dictionary containing the execution result (stdout, stderr, returncode).
    """
    global execute_python_code_call_count
    global timing_data
    execute_python_code_call_count += 1

    if execute_python_code_call_count > 5:
        logger.warning(f"{MODULE_TAG}executepythoncode 调用次数超限，已达到 {execute_python_code_call_count} 次。")
        return {
            "stdout": "",
            "stderr": "代码执行工具调用次数超限，请尝试口算完成。",
            "returncode": 1, # Indicate an error
            "source": "local_execution_limit_exceeded"
        }

    import subprocess
    import sys
    logger.info(f"{MODULE_TAG}Executing Python code:\n{code}")
    start_time = time.time() # Start timing
    try:
        # Use sys.executable to ensure the same Python interpreter is used
        process = subprocess.run([sys.executable, "-c", code],
                                 capture_output=True,
                                 text=True,
                                 timeout=180, # Set a timeout to prevent infinite loops
                                 check=False) # Don't raise exception on non-zero exit code

        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "returncode": process.returncode,
            "source": "local_execution"
        }
    except Exception as e:
        logger.error(f"{MODULE_TAG}Error executing Python code: {e}")
        return {
            "stdout": "",
            "stderr": str(e),
            "returncode": 1,
            "source": "local_execution"
        }
    finally:
        end_time = time.time()
        timing_data["executepythoncode_exec_times"].append(end_time - start_time)

executepythoncode_declaration = {
    "name": "executepythoncode",
    "description": "Executes arbitrary Python code provided as a string. This tool is useful for performing calculations, processing data, or running any standard Python logic. It returns a dictionary containing the standard output (stdout), standard error (stderr), and the return code of the execution. The code should be provided as a single string in the 'code' parameter.如果tools list存在你需要的工具你不能使用code来解决",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute as a string."
            },
        },
        "required": ["code"]
    }
}

#============调用函数声明==========
all_function_declarations = []

# 将其他单独的函数声明使用 append 方法添加，确保它们是 FunctionDeclaration 对象
all_function_declarations.append(types.FunctionDeclaration(**get_initial_data_declaration)) # 新增
# all_function_declarations.append(types.FunctionDeclaration(**get_transaction_history_declaration))
all_function_declarations.append(types.FunctionDeclaration(**get_time_declaration))
all_function_declarations.append(types.FunctionDeclaration(**executepythoncode_declaration))
all_function_declarations.append(types.FunctionDeclaration(**analyze_kline_patterns_declaration))

# 模拟函数执行的映射
# 将函数声明的名称映射到实际的 Python 函数
function_map = {
    "get_initial_data": get_initial_data, # 新增
    "gettransactionhistory": gettransactionhistory,
    "gettime": gettime,
    "executepythoncode": executepythoncode,
    "analyze_kline_patterns": analyze_kline_patterns,
}
