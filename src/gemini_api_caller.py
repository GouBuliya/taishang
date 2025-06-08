import logging
import os
import sys
import json
import traceback
import base64
import time
import datetime # 导入datetime模块

# Add the 'function' directory to sys.path for module imports
FUNCTION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "function")
if FUNCTION_DIR not in sys.path:
    sys.path.insert(0, FUNCTION_DIR)
print(f"DEBUG: sys.path: {sys.path}") # Add this line for debugging

# Import the newly modularized functions
from kline_pattern_analyzer import analyze_kline_patterns # 确保这里导入了函数
import get_transaction_history

cnt=0 # 全局计数器，用于计算API调用的总 chunk 数

# ===================== 全局配置与初始化 =====================
# 从config.json中读取配置
with open("config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]
EFFECTIVE_LOG_FILE = config["logs"]["effective_log_path"]

# 定义一个过滤器来忽略特定模块的警告
class NoGenaiTypesWarningFilter(logging.Filter):
    def filter(self, record):
        return not (record.name == 'google.genai.types' and record.levelno >= logging.WARNING)

# 配置主日志
stream_handler = logging.StreamHandler()
stream_handler.addFilter(NoGenaiTypesWarningFilter())

logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), stream_handler]
)

logger = logging.getLogger("GeminiQuant")

# 配置有效通信日志
effective_logger = logging.getLogger("EffectiveCommunication")
effective_logger.setLevel(logging.INFO)
effective_handler = logging.FileHandler(EFFECTIVE_LOG_FILE, mode='a', encoding='utf-8')
effective_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
effective_handler.setFormatter(effective_formatter)
effective_logger.addHandler(effective_handler)

# 设置 google.genai.types 模块的日志级别为 ERROR，以屏蔽非文本部分的警告
logging.getLogger('google.genai.types').setLevel(logging.ERROR)

MODULE_TAG = "[gemini_api_caller] "

# 全局变量，用于保存从文件中加载的初始数据
data_json = {}

# 全局计数器，用于限制 execute_python_code 的调用次数
execute_python_code_call_count = 0

# 新增：全局计数器，用于限制 get_time 的调用次数
get_time_call_count = 0

# 新增：全局计数器，用于限制 get_transaction_history 的调用次数
get_transaction_history_call_count = 0

# 新增：全局计数器，用于限制 analyze_kline_patterns 的调用次数
analyze_kline_patterns_call_count = 0

# 新增：全局计数器，用于限制 get_initial_data 的调用次数
get_initial_data_call_count = 0 # 新增计数器

# 新增：全局计时器字典
timing_data = {
    "gemini_api_call_times": [],
    "gettime_exec_time": 0.0,
    "gettransactionhistory_exec_time": 0.0,
    "executepythoncode_exec_times": [],
    "analyzeklinepatterns_exec_time": 0.0,
    "getinitialdata_exec_time": 0.0, # 新增计时
}

# 推荐用 GEMINI_API_KEY 作为环境变量名
api_key_index = 3
api_key_list = config["gemini_api_key_set"]
api_key_str="gemini_api_key_"+str(api_key_index)
API_KEY = api_key_list[api_key_str]
# 推荐Gemini模型名
DEFAULT_MODEL_NAME = config["MODEL_CONFIG"]["MODEL_NAME"]
SYSTEM_PROMPT_PATH = config["MODEL_CONFIG"]["SYSTEM_PROMPT_PATH"]

# ===================== 全局配置与初始化 END =====================

DEFAULT_TEMPERATURE = config["MODEL_CONFIG"]["default_temperature"]
DEFAULT_TOP_P = config["MODEL_CONFIG"]["default_top_p"]
DEFAULT_MAX_OUTPUT_TOKENS = config["MODEL_CONFIG"]["default_max_output_tokens"]
DEFAULT_THINKING_BUDGET = config["MODEL_CONFIG"]["default_thinking_budget"]
DEFAULT_INCLUDE_THOUGHTS = config["MODEL_CONFIG"]["default_include_thoughts"]

# ===================== Gemini API 调用主模块 =====================

from google import genai
from google.genai import types

# ===================== 函数调用工具定义框架 =====================

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
all_function_declarations.append(types.FunctionDeclaration(**get_transaction_history_declaration))
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

# ===================== 函数调用工具定义框架 END =====================
history=[]

def call_gemini_api_stream(
    prompt_text,
    system_prompt_path=None, # Renamed to clearly indicate it's a path
    tools=None,
    function_response_parts=None,
):
    """
    流式调用 Gemini API，支持文本输入、思考模式和函数调用。
    支持多轮对话（通过 history 全局变量）。
    注意：此函数在接收到文本或函数调用请求后会返回，需要外部循环处理多轮。
    """
    global cnt
    system_prompt_content = ""
    if system_prompt_path and os.path.exists(system_prompt_path):
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt_content = f.read().strip()
        if not system_prompt_content:
             logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {system_prompt_path}.")
    else:
         logger.warning(f"{MODULE_TAG}系统提示词文件未找到或未提供: {system_prompt_path}. SYSTEM_PROMPT 将为空。")


    try:
        _api_key = API_KEY
        if not _api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY")


        # 将 tools 参数传递给 GenerateContentConfig
        gemini_config = types.GenerateContentConfig(    
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_config={
                "include_thoughts": DEFAULT_INCLUDE_THOUGHTS,
                "thinking_budget": DEFAULT_THINKING_BUDGET,
            },
            system_instruction=system_prompt_content, # 使用读取的系统提示词内容
            tools=tools, # 传递工具列表
            tool_config={"function_calling_config": {"mode": "any"}},
        )
        client = genai.Client(api_key=_api_key)

        # 构建当前轮次的用户输入内容
        current_user_parts = []
        if prompt_text:
            logger.debug(f"{MODULE_TAG}Type of prompt_text: {type(prompt_text)}")
            logger.debug(f"{MODULE_TAG}Value of prompt_text: {prompt_text[:100]}...") # Log first 100 chars to avoid very long logs
            current_user_parts.append(types.Part(text=prompt_text))

        # 将上一轮的函数响应添加到历史中
        if function_response_parts:
            # function_response_parts 已经是 list of Content objects，直接扩展历史
            history.extend(function_response_parts)

        # 将当前用户输入添加到历史中
        if current_user_parts:
            history.append(types.Content(role="user", parts=current_user_parts))

        logger.debug(f"{MODULE_TAG}Type of history: {type(history)}")
        logger.debug(f"{MODULE_TAG}Length of history: {len(history)}")
        if history:
            logger.debug(f"{MODULE_TAG}Type of history[0]: {type(history[0])}")
            if hasattr(history[0], 'parts'):
                logger.debug(f"{MODULE_TAG}Type of history[0].parts: {type(history[0].parts)}")
                if history[0].parts and hasattr(history[0].parts[0], 'text'):
                    logger.debug(f"{MODULE_TAG}Value of history[0].parts[0].text: {str(history[0].parts[0].text)[:50]}...")

        api_call_start_time = time.time() # Start timing for Gemini API call
        response = client.models.generate_content_stream(
            model=DEFAULT_MODEL_NAME,
            contents=history, # 将整个历史对话内容传递给 API
            config=gemini_config,

        )

        output_buffer = []
        collected_function_calls = [] # 用于收集本轮的所有函数调用
        model_response_parts = [] # 用于收集模型本轮的完整响应（文本+函数调用）
        collected_thought_text_for_current_turn = [] # 新增：用于收集本轮的思考摘要文本

        # 迭代 chunk 处理流式输出和函数调用
        for chunk in response:
            # time.sleep(0.1) # 调试时可以添加此行
            cnt+=1
            if chunk.function_calls: # 使用 if chunk.function_calls 更加 Pythonic
                # 遍历 chunk.function_calls 列表，收集所有 FunctionCall 对象
                for func_call_obj in chunk.function_calls:
                    collected_function_calls.append(func_call_obj)
                # 将函数调用添加到模型响应部分
                model_response_parts.extend([types.Part(function_call=fc) for fc in chunk.function_calls])

            # 如果没有函数调用，检查是否有文本
            if chunk.text: # 使用 if chunk.text 更加 Pythonic
                print(chunk.text, end="", flush=True)
                output_buffer.append(chunk.text)
                # 将文本添加到模型响应部分
                model_response_parts.append(types.Part(text=chunk.text))
            else:
                # 尝试从非文本/非函数调用部分中捕获思考摘要
                # 优先从 chunk.parts 中获取文本，其次从 chunk.candidates.content.parts 中获取
                if hasattr(chunk, 'parts') and chunk.parts:
                    for part in chunk.parts:
                        if hasattr(part, 'text') and part.text:
                            collected_thought_text_for_current_turn.append(part.text)
                elif hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        # 确保 candidate.content 不为 None
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        collected_thought_text_for_current_turn.append(part.text)

        api_call_end_time = time.time()
        timing_data["gemini_api_call_times"].append(api_call_end_time - api_call_start_time) # Store API call time

        # 在处理完所有 chunk 后，如果收集到思考摘要，则统一记录
        if collected_thought_text_for_current_turn:
            thought_summary = ''.join(collected_thought_text_for_current_turn)
            logger.info(f"{MODULE_TAG}Captured full thought summary for this turn: {thought_summary}")
            effective_logger.info(f"[Thought Summary]: {thought_summary}") # 记录思考摘要到有效通信日志

        # 在处理完所有 chunk 后，将模型本轮的完整响应添加到历史中
        if model_response_parts:
            history.append(types.Content(role="model", parts=model_response_parts))

        # 在处理完所有 chunk 后，判断是返回函数调用列表还是文本
        if collected_function_calls:
            logger.info(f"{MODULE_TAG}模型请求调用多个函数: {len(collected_function_calls)} 个")
            effective_logger.info(f"[Function Calls]: {[{'name': fc.name, 'args': fc.args} for fc in collected_function_calls]}") # 记录函数调用到有效通信日志
            return {"function_calls": collected_function_calls} # 返回函数调用列表
        else:
            output_text = "".join(output_buffer)
            effective_logger.info(f"[Model Response]: {output_text}") # 记录模型回答到有效通信日志
            return {"text": output_text}


    except Exception as e:
        tb = traceback.format_exc()#获取异常信息
        return {"error": f"{e},tb:{tb}"}


# 模拟执行函数并返回结果的辅助函数
def execute_function_call(function_call: types.FunctionCall):
    """Simulates executing the requested function and returns the result in API-compatible format."""
    global analyze_kline_patterns_call_count # 声明全局变量
    global timing_data # 声明全局变量

    logger.info(f"{MODULE_TAG}调用 function: {function_call}")
    func_name = function_call.name
    func_args = function_call.args
    
    if func_name in function_map:
        logger.info(f"{MODULE_TAG}Executing function: {func_name} with args {func_args}")
        start_time = time.time() # Start timing for function execution
        try:
            # 调用实际的 Python 函数，注意参数需要正确传递
            if func_name == "place_order": # 示例，如果将来有这个工具
                result = function_map[func_name](**func_args, config_data=config) # Pass config_data
            elif func_name == "analyze_kline_patterns":
                analyze_kline_patterns_call_count += 1
                result = function_map[func_name](**func_args)
            elif func_name == "get_initial_data": # 新增：处理 get_initial_data
                result = function_map[func_name]() # 无需参数
            else:
                result = function_map[func_name](**func_args)
            
            logger.info(f"{MODULE_TAG}Function {func_name} executed successfully. Result: {result}")
            # 返回符合 Gemini API 期望的 function_response 结构
            effective_logger.info(f"[Function Response] from {func_name}: {result}") # 新增：记录函数返回值
            return types.Part.from_function_response(
                name=func_name,
                response={"result": result} # 您的实际函数返回值
            )
        except Exception as e:
            logger.error(f"{MODULE_TAG}Error executing function {func_name}: {e}")
            return types.Part.from_function_response(
                name=func_name,
                response={"error": f"Error executing function: {e}"}
            )
        finally:
            end_time = time.time()
            if func_name == "analyze_kline_patterns":
                timing_data["analyzeklinepatterns_exec_time"] += (end_time - start_time)
            elif func_name == "get_initial_data": # 新增：记录 get_initial_data 的耗时
                timing_data["getinitialdata_exec_time"] += (end_time - start_time)
    else:
        logger.warning(f"{MODULE_TAG}Requested function {func_name} not found in function_map.")
        return types.Part.from_function_response(
            name=func_name,
            response={"error": f"Function {func_name} not found"}
        )


__all__ = ["call_gemini_api_stream"]



#工具自检
def tool_self_check():
    """
    工具自检函数，检查所有工具是否正常工作。
    """
    logger.info(f"{MODULE_TAG}开始工具自检...")

    # 检查 get_initial_data 工具 (新增)
    try:
        get_initial_data_result = get_initial_data()
        logger.info(f"{MODULE_TAG}get_initial_data 工具自检结果: {get_initial_data_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_initial_data 工具自检失败: {e}")

    # 检查 get_time 工具
    try:
        get_time_result = gettime("gettime")
        logger.info(f"{MODULE_TAG}get_time 工具自检结果: {get_time_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_time 工具自检失败: {e}")
    
    # 检查 get_transaction_history 工具
    try:
        get_transaction_history_result = gettransactionhistory("ETH-USDT") # 提供一个目标参数
        logger.info(f"{MODULE_TAG}get_transaction_history 工具自检结果: {get_transaction_history_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_transaction_history 工具自检失败: {e}")
    
    # 检查 executepythoncode 工具
    try:
        executepythoncode_result = executepythoncode("print('Hello, world!')")
        logger.info(f"{MODULE_TAG}executepythoncode 工具自检结果: {executepythoncode_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}executepythoncode 工具自检失败: {e}")
    
    # 检查 analyze_kline_patterns 工具 (使用模拟数据)
    try:
        mock_kline_data = [
            {"timestamp": "2025-06-07T11:00:00+00:00", "open": 2493.72, "high": 2495.39, "low": 2491.13, "close": 2492.88, "volume": 145236.19, "RSI": 32.34, "MACD_macd": -5.51, "MACD_signal": -4.49, "ATR": 7.69, "ADX": 30.83, "Stoch_K": 7.65, "Stoch_D": 15.36, "StochRSI_K": 41.73, "StochRSI_D": 45.46, "BB_upper": 2522.57, "BB_middle": 2505.20, "BB_lower": 2487.83, "EMA5": 2495.39, "EMA21": 2503.21, "EMA55": 2509.73, "EMA144": 2513.04, "EMA200": 2513.57, "VWAP": 2513.87},
            {"timestamp": "2025-06-07T11:15:00+00:00", "open": 2492.88, "high": 2499.86, "low": 2492.05, "close": 2495.70, "volume": 336244.84, "RSI": 36.60, "MACD_macd": -5.30, "MACD_signal": -4.23, "ATR": 8.17, "ADX": 30.73, "Stoch_K": 17.12, "Stoch_D": 15.87, "StochRSI_K": 44.42, "StochRSI_D": 40.75, "BB_upper": 2524.04, "BB_middle": 2506.54, "BB_lower": 2489.04, "EMA5": 2496.64, "EMA21": 2504.24, "EMA55": 2510.36, "EMA144": 2513.32, "EMA200": 2513.78, "VWAP": 2514.05},
            # 确保有足够的K线数据，至少15条，这里只是示例15条
            {"timestamp": "2025-06-07T11:30:00+00:00", "open": 2495.70, "high": 2500.00, "low": 2494.00, "close": 2498.50, "volume": 200000.00, "RSI": 40.00, "MACD_macd": -5.00, "MACD_signal": -4.00, "ATR": 8.50, "ADX": 31.00, "Stoch_K": 25.00, "Stoch_D": 20.00, "StochRSI_K": 50.00, "StochRSI_D": 45.00, "BB_upper": 2525.00, "BB_middle": 2507.00, "BB_lower": 2490.00, "EMA5": 2497.50, "EMA21": 2505.00, "EMA55": 2511.00, "EMA144": 2514.00, "EMA200": 2514.00, "VWAP": 2514.50},
            {"timestamp": "2025-06-07T11:45:00+00:00", "open": 2498.50, "high": 2505.00, "low": 2497.00, "close": 2503.00, "volume": 300000.00, "RSI": 45.00, "MACD_macd": -4.50, "MACD_signal": -3.50, "ATR": 9.00, "ADX": 32.00, "Stoch_K": 35.00, "Stoch_D": 30.00, "StochRSI_K": 60.00, "StochRSI_D": 55.00, "BB_upper": 2528.00, "BB_middle": 2509.00, "BB_lower": 2492.00, "EMA5": 2499.00, "EMA21": 2506.00, "EMA55": 2512.00, "EMA144": 2515.00, "EMA200": 2515.00, "VWAP": 2515.50},
            {"timestamp": "2025-06-07T12:00:00+00:00", "open": 2503.00, "high": 2510.00, "low": 2502.00, "close": 2508.00, "volume": 400000.00, "RSI": 50.00, "MACD_macd": -4.00, "MACD_signal": -3.00, "ATR": 9.50, "ADX": 33.00, "Stoch_K": 45.00, "Stoch_D": 40.00, "StochRSI_K": 70.00, "StochRSI_D": 65.00, "BB_upper": 2530.00, "BB_middle": 2511.00, "BB_lower": 2494.00, "EMA5": 2505.00, "EMA21": 2508.00, "EMA55": 2513.00, "EMA144": 2516.00, "EMA200": 2516.00, "VWAP": 2516.50},
            {"timestamp": "2025-06-07T12:15:00+00:00", "open": 2508.00, "high": 2515.00, "low": 2507.00, "close": 2512.00, "volume": 500000.00, "RSI": 55.00, "MACD_macd": -3.50, "MACD_signal": -2.50, "ATR": 10.00, "ADX": 34.00, "Stoch_K": 55.00, "Stoch_D": 50.00, "StochRSI_K": 80.00, "StochRSI_D": 75.00, "BB_upper": 2532.00, "BB_middle": 2513.00, "BB_lower": 2496.00, "EMA5": 2509.00, "EMA21": 2510.00, "EMA55": 2514.00, "EMA144": 2517.00, "EMA200": 2517.00, "VWAP": 2517.50},
            {"timestamp": "2025-06-07T12:30:00+00:00", "open": 2512.00, "high": 2518.00, "low": 2511.00, "close": 2516.00, "volume": 600000.00, "RSI": 60.00, "MACD_macd": -3.00, "MACD_signal": -2.00, "ATR": 10.50, "ADX": 35.00, "Stoch_K": 65.00, "Stoch_D": 60.00, "StochRSI_K": 90.00, "StochRSI_D": 85.00, "BB_upper": 2534.00, "BB_middle": 2515.00, "BB_lower": 2498.00, "EMA5": 2513.00, "EMA21": 2512.00, "EMA55": 2515.00, "EMA144": 2518.00, "EMA200": 2518.00, "VWAP": 2518.50},
            {"timestamp": "2025-06-07T12:45:00+00:00", "open": 2516.00, "high": 2522.00, "low": 2515.00, "close": 2520.00, "volume": 700000.00, "RSI": 65.00, "MACD_macd": -2.50, "MACD_signal": -1.50, "ATR": 11.00, "ADX": 36.00, "Stoch_K": 75.00, "Stoch_D": 70.00, "StochRSI_K": 100.00, "StochRSI_D": 95.00, "BB_upper": 2536.00, "BB_middle": 2517.00, "BB_lower": 2500.00, "EMA5": 2517.00, "EMA21": 2514.00, "EMA55": 2516.00, "EMA144": 2519.00, "EMA200": 2519.00, "VWAP": 2519.50},
            {"timestamp": "2025-06-07T13:00:00+00:00", "open": 2520.00, "high": 2525.00, "low": 2519.00, "close": 2523.00, "volume": 800000.00, "RSI": 70.00, "MACD_macd": -2.00, "MACD_signal": -1.00, "ATR": 11.50, "ADX": 37.00, "Stoch_K": 85.00, "Stoch_D": 80.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2538.00, "BB_middle": 2519.00, "BB_lower": 2502.00, "EMA5": 2520.00, "EMA21": 2516.00, "EMA55": 2517.00, "EMA144": 2520.00, "EMA200": 2520.00, "VWAP": 2520.50},
            {"timestamp": "2025-06-07T13:15:00+00:00", "open": 2523.00, "high": 2528.00, "low": 2522.00, "close": 2526.00, "volume": 900000.00, "RSI": 75.00, "MACD_macd": -1.50, "MACD_signal": -0.50, "ATR": 12.00, "ADX": 38.00, "Stoch_K": 95.00, "Stoch_D": 90.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2540.00, "BB_middle": 2521.00, "BB_lower": 2504.00, "EMA5": 2523.00, "EMA21": 2518.00, "EMA55": 2518.00, "EMA144": 2521.00, "EMA200": 2521.00, "VWAP": 2521.50},
            {"timestamp": "2025-06-07T13:30:00+00:00", "open": 2526.00, "high": 2530.00, "low": 2525.00, "close": 2529.00, "volume": 1000000.00, "RSI": 80.00, "MACD_macd": -1.00, "MACD_signal": 0.00, "ATR": 12.50, "ADX": 39.00, "Stoch_K": 100.00, "Stoch_D": 95.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2542.00, "BB_middle": 2523.00, "BB_lower": 2506.00, "EMA5": 2526.00, "EMA21": 2520.00, "EMA55": 2519.00, "EMA144": 2522.00, "EMA200": 2522.00, "VWAP": 2522.50},
            {"timestamp": "2025-06-07T13:45:00+00:00", "open": 2529.00, "high": 2533.00, "low": 2528.00, "close": 2532.00, "volume": 1100000.00, "RSI": 85.00, "MACD_macd": -0.50, "MACD_signal": 0.50, "ATR": 13.00, "ADX": 40.00, "Stoch_K": 100.00, "Stoch_D": 100.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2544.00, "BB_middle": 2525.00, "BB_lower": 2508.00, "EMA5": 2529.00, "EMA21": 2522.00, "EMA55": 2520.00, "EMA144": 2523.00, "EMA200": 2523.00, "VWAP": 2523.50},
            {"timestamp": "2025-06-07T14:00:00+00:00", "open": 2532.00, "high": 2535.00, "low": 2531.00, "close": 2534.00, "volume": 1200000.00, "RSI": 90.00, "MACD_macd": 0.00, "MACD_signal": 1.00, "ATR": 13.50, "ADX": 41.00, "Stoch_K": 100.00, "Stoch_D": 100.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2546.00, "BB_middle": 2527.00, "BB_lower": 2510.00, "EMA5": 2531.00, "EMA21": 2524.00, "EMA55": 2521.00, "EMA144": 2524.00, "EMA200": 2524.00, "VWAP": 2524.50},
            {"timestamp": "2025-06-07T14:15:00+00:00", "open": 2534.00, "high": 2537.00, "low": 2533.00, "close": 2536.00, "volume": 1300000.00, "RSI": 95.00, "MACD_macd": 0.50, "MACD_signal": 1.50, "ATR": 14.00, "ADX": 42.00, "Stoch_K": 100.00, "Stoch_D": 100.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2548.00, "BB_middle": 2529.00, "BB_lower": 2512.00, "EMA5": 2533.00, "EMA21": 2526.00, "EMA55": 2522.00, "EMA144": 2525.00, "EMA200": 2525.00, "VWAP": 2525.50},
            {"timestamp": "2025-06-07T14:30:00+00:00", "open": 2536.00, "high": 2539.00, "low": 2535.00, "close": 2538.00, "volume": 1400000.00, "RSI": 100.00, "MACD_macd": 1.00, "MACD_signal": 2.00, "ATR": 14.50, "ADX": 43.00, "Stoch_K": 100.00, "Stoch_D": 100.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2550.00, "BB_middle": 2531.00, "BB_lower": 2514.00, "EMA5": 2535.00, "EMA21": 2528.00, "EMA55": 2523.00, "EMA144": 2526.00, "EMA200": 2526.00, "VWAP": 2526.50},
            {"timestamp": "2025-06-07T14:45:00+00:00", "open": 2538.00, "high": 2541.00, "low": 2537.00, "close": 2540.00, "volume": 1500000.00, "RSI": 100.00, "MACD_macd": 1.50, "MACD_signal": 2.50, "ATR": 15.00, "ADX": 44.00, "Stoch_K": 100.00, "Stoch_D": 100.00, "StochRSI_K": 100.00, "StochRSI_D": 100.00, "BB_upper": 2552.00, "BB_middle": 2533.00, "BB_lower": 2516.00, "EMA5": 2537.00, "EMA21": 2530.00, "EMA55": 2524.00, "EMA144": 2527.00, "EMA200": 2527.00, "VWAP": 2527.50}
        ]
        analyze_kline_patterns_result = analyze_kline_patterns(mock_kline_data)
        logger.info(f"{MODULE_TAG}analyze_kline_patterns 工具自检结果: {analyze_kline_patterns_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}analyze_kline_patterns 工具自检失败: {e}")

    logger.info(f"{MODULE_TAG}工具自检完成")



if __name__ == "__main__":

    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
    
    start_time = time.time()
    SYSTEM_JSON_PATH = config["data_path"] # Moved here as it's only used in __main__
    SYSTEM_PROMPT_PATH = config["MODEL_CONFIG"]["SYSTEM_PROMPT_PATH"] # Ensure this is available

    # 在主程序开始时，先加载一次 data_json 到全局变量中，以便 get_initial_data 工具能访问
    # 或者让 get_initial_data 在被调用时才加载，这取决于你的设计偏好。
    # 这里我们让它在调用时加载，确保惰性加载和隔离。
    # with open(SYSTEM_JSON_PATH, "r", encoding="utf-8") as f:
    #     data_json = json.load(f)
    # logger.info(f"初始 prompt_text 导入完成") # 这行现在不合适，因为不是直接导入提示词

    tool_self_check()
    #清空logs/think_log.md
    with open(EFFECTIVE_LOG_FILE, "w", encoding="utf-8") as f:
        f.truncate(0)
    
    logger.info("开始与 Gemini API 进行多轮交互...")

    # 初始用户输入，不再是 data_json 的内容，而是引导模型调用工具的文本
    initial_user_query = "请先通过获取最新的初始市场和交易环境信息，以便开始分析和决策。"
    current_prompt_text = initial_user_query # 第一轮发送这个引导提示

    max_turns = 12 # 设置最大交互轮数，防止无限循环
    function_response_parts = []

    for turn in range(max_turns):
        logger.info(f"--- 第 {turn + 1} 轮 API 调用 ---\n")
        
        # 只有在第一轮才发送 initial_user_query
        prompt_to_send = current_prompt_text if turn == 0 else ""

        # 动态构建本轮可用的工具列表
        current_all_function_declarations = list(all_function_declarations) # 复制原始声明，避免修改全局变量
        
        tools_to_remove_names = []
        if len(current_all_function_declarations)==0:
            logger.info(f"{MODULE_TAG}本轮可用工具列表为空。")

        # 根据调用次数限制移除工具
        if get_time_call_count >= 2:
            tools_to_remove_names.append("gettime")
        # 修正：如果希望get_transaction_history第一次能用，这里应为 >= 2 (表示已用2次)
        if get_transaction_history_call_count >= 2: 
            tools_to_remove_names.append("gettransactionhistory")
        if execute_python_code_call_count >= 3:
            tools_to_remove_names.append("executepythoncode")
        if analyze_kline_patterns_call_count >= 1: # 通常 K 线分析可能只需要一次
            tools_to_remove_names.append("analyze_kline_patterns")
        if get_initial_data_call_count >= 2: # 初始数据通常只需要获取一次
            tools_to_remove_names.append("get_initial_data")
        
        if tools_to_remove_names:
            original_declarations_len = len(current_all_function_declarations)
            current_all_function_declarations = [
                decl for decl in current_all_function_declarations
                if decl.name not in tools_to_remove_names
            ]
            if len(current_all_function_declarations) < original_declarations_len:
                logger.info(f"{MODULE_TAG}已从本轮可用工具中移除: {tools_to_remove_names}")
        
        # 重新构建本轮的 available_tools
        current_available_tools = [types.Tool(function_declarations=current_all_function_declarations)]

        result = call_gemini_api_stream(
            prompt_text=prompt_to_send,
            system_prompt_path=SYSTEM_PROMPT_PATH,
            tools=current_available_tools, # 传递动态构建的工具列表
            function_response_parts=function_response_parts
        )

        current_prompt_text = "" # 清空，确保后续只通过函数响应推动对话
        function_response_parts.clear() # 清空，准备接收新的函数响应

        if "function_calls" in result and result["function_calls"]:
            # 模型请求调用一个或多个函数
            list_of_func_calls = result["function_calls"]
            logger.info(f"{MODULE_TAG}接收到 {len(list_of_func_calls)} 个函数调用请求。")

            # 模拟执行所有函数并收集结果
            for func_call_obj in list_of_func_calls:
                logger.info(f"{MODULE_TAG}模拟执行函数: {func_call_obj.name} 参数: {func_call_obj.args}")
                response_part = execute_function_call(func_call_obj) # execute_function_call 应该返回 Part
                # 将函数执行结果作为用户角色内容添加到历史中
                function_response_parts.append(types.Content(role="user", parts=[response_part]))
            
            logger.info(f"{MODULE_TAG}所有函数执行结果已添加到历史，准备下一轮调用。")

            continue # 继续下一轮循环，将更新后的历史发送给模型

        elif "text" in result:
            # 收到最终文本响应
            final_response = result["text"]
            logger.info(f"{MODULE_TAG}收到最终模型响应，交互结束。")

            # 尝试解析 JSON（假设最终响应是 JSON）
            try:
                json_response = final_response.replace("```json", "").replace("```", "")
                output_data = json.loads(json_response)
                output_file_path = config["gemini_answer_path"]
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=4, ensure_ascii=False)
                print(f"{MODULE_TAG}已将解析后的输出内容保存到 {output_file_path}")
            except json.JSONDecodeError as e:
                logger.error(f"{MODULE_TAG}解析最终响应为 JSON 失败: {e}")
                print(f"{MODULE_TAG}错误：无法解析最终模型响应为 JSON。")
                print(f"""原始响应内容：
{final_response}""")

            break # Exit the loop as we received the final text response

        elif "error" in result:
            # API 调用发生错误
            logger.error(f"""{MODULE_TAG}API 调用发生错误:
{result}""")
            # 如果是429错误，可以考虑换API_KEY，这里暂时只记录错误
            break # 发生错误通常停止交互

    else:
        logger.warning(f"{MODULE_TAG}达到最大交互轮数 ({max_turns})，交互结束。可能未收到最终响应。")
        print(f"{MODULE_TAG}警告：达到最大交互轮数 ({max_turns})，交互结束。可能未收到最终响应。请检查模型行为或增加最大轮数。")

    end_time = time.time()
    logger.info(f"总运行时间: {round((end_time - start_time) / 60, 2)} 分钟")

    # 新增：输出所有计时数据
    print("\n--- 性能计时数据 ---")
    print(f"gettime 函数总耗时: {timing_data['gettime_exec_time']:.4f} 秒")
    print(f"gettransactionhistory 函数总耗时: {timing_data['gettransactionhistory_exec_time']:.4f} 秒")
    print(f"executepythoncode 函数每次耗时: {[f'{t:.4f}秒' for t in timing_data['executepythoncode_exec_times']]}")
    print(f"analyze_kline_patterns 函数总耗时: {timing_data['analyzeklinepatterns_exec_time']:.4f} 秒")
    print(f"get_initial_data 函数总耗时: {timing_data['getinitialdata_exec_time']:.4f} 秒") # 新增打印
    print(f"Gemini API 调用每次耗时: {[f'{t:.4f}秒' for t in timing_data['gemini_api_call_times']]}")
    print(f"总程序运行时间: {round((end_time - start_time)/60,2)} 分钟{round((end_time - start_time)%60,2)} 秒")
    print(f"总请求次数: {cnt}")
    print("--------------------\n")