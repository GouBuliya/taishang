import logging
import os
import sys
import json
import traceback
import base64
import time

# Add the 'function' directory to sys.path for module imports
FUNCTION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "function")
if FUNCTION_DIR not in sys.path:
    sys.path.insert(0, FUNCTION_DIR)
print(f"DEBUG: sys.path: {sys.path}") # Add this line for debugging

# Import the newly modularized functions
import get_transaction_history

# ===================== 全局配置与初始化 =====================
# 从config.json中读取配置
with open("config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]
EFFECTIVE_LOG_FILE = config["main_log_path"]

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

# 全局计数器，用于限制 execute_python_code 的调用次数
execute_python_code_call_count = 0

# 新增：全局计数器，用于限制 get_time 的调用次数
get_time_call_count = 0

# 新增：全局计数器，用于限制 get_transaction_history 的调用次数
get_transaction_history_call_count = 0

# 新增：全局计时器字典
timing_data = {
    "image_upload_time": 0.0,
    "gemini_api_call_times": [],
    "gettime_exec_time": 0.0,
    "gettransactionhistory_exec_time": 0.0,
    "executepythoncode_exec_times": [],
}

# 推荐用 GEMINI_API_KEY 作为环境变量名
API_KEY = config["gemini_api_key_set"]["gemini_api_key_1"]
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

    if get_transaction_history_call_count > 1:
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
    global get_time_call_count
    global timing_data
    get_time_call_count += 1

    if get_time_call_count > 1:
        logger.warning(f"{MODULE_TAG}gettime 调用次数超限，已达到 {get_time_call_count} 次。")
        return {"error": "获取时间工具调用次数超限，请尝试其他方式获取。"}

    start_time = time.time() # Start timing
    try:
        current_time =  start_time
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

    if execute_python_code_call_count > 2:
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
    "description": "Executes arbitrary Python code provided as a string. This tool is useful for performing calculations, processing data, or running any standard Python logic. It returns a dictionary containing the standard output (stdout), standard error (stderr), and the return code of the execution. The code should be provided as a single string in the 'code' parameter.",
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

#============调用函数==========
all_function_declarations = []

# 将其他单独的函数声明使用 append 方法添加，确保它们是 FunctionDeclaration 对象
all_function_declarations.append(types.FunctionDeclaration(**get_transaction_history_declaration))
all_function_declarations.append(types.FunctionDeclaration(**get_time_declaration))
all_function_declarations.append(types.FunctionDeclaration(**executepythoncode_declaration))

# 模拟函数执行的映射
# 将函数声明的名称映射到实际的 Python 函数
function_map = {
    "gettransactionhistory": gettransactionhistory,
    "gettime": gettime,
    "executepythoncode": executepythoncode,
}

# ===================== 函数调用工具定义框架 END =====================
history=[]

def call_gemini_api_stream(
    prompt_text,
    screenshot_path=None,
    system_prompt_path=None, # Renamed to clearly indicate it's a path
    tools=None,
    function_response_parts=None,
):
    """
    流式调用 Gemini API，支持文本+图片输入、思考模式和函数调用。
    支持多轮对话（通过 history 全局变量）。
    注意：此函数在接收到文本或函数调用请求后会返回，需要外部循环处理多轮。
    """
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
        image = None
        if screenshot_path:
            try:
                logger.info(f"{MODULE_TAG}图片导入开始:{screenshot_path}")
                upload_start_time = time.time() # Start timing for image upload
                image = client.files.upload(file=screenshot_path)
                upload_end_time = time.time()
                timing_data["image_upload_time"] = upload_end_time - upload_start_time # Store image upload time
                logger.info(f"{MODULE_TAG}图片导入完成")
            except Exception as e:
                logger.error(f"{MODULE_TAG}图片导入失败: {e}")
                image = None

        # 构建当前轮次的用户输入内容
        current_user_parts = []
        if image:
            logger.debug(f"{MODULE_TAG}Type of image object: {type(image)}")
            logger.debug(f"{MODULE_TAG}Image URI: {image.uri}") # 添加此行以调试 URI
            current_user_parts.append(types.Part(file_data=types.FileData(file_uri=image.uri))) # 确保 File 对象被正确封装为 Part，使用 file_data 参数
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
            # 检查是否有函数调用请求
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
        logger.error(f"{MODULE_TAG}Gemini API调用异常: {e}\n{tb}")
        return {"error": f"""[Gemini API调用异常] {e}
Traceback:
{tb}"""}


# 模拟执行函数并返回结果的辅助函数
def execute_function_call(function_call: types.FunctionCall):
    """Simulates executing the requested function and returns the result in API-compatible format."""
    logger.info(f"{MODULE_TAG}调用 function: {function_call}")
    func_name = function_call.name
    func_args = function_call.args
    
    if func_name in function_map:
        logger.info(f"{MODULE_TAG}Executing function: {func_name} with args {func_args}")
        try:
            # 调用实际的 Python 函数，注意参数需要正确传递
            # For place_order, we need to pass the config object
            if func_name == "place_order":
                result = function_map[func_name](**func_args, config_data=config) # Pass config_data
            else:
                result = function_map[func_name](**func_args)
            logger.info(f"{MODULE_TAG}Function {func_name} executed successfully. Result: {result}")
            # 返回符合 Gemini API 期望的 function_response 结构
            # 文档示例格式：{'functionResponse': {'name': '...', 'response': {...}}}
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
    # 检查 get_time 工具
    try:
        get_time_result = get_time()
        logger.info(f"{MODULE_TAG}get_time 工具自检结果: {get_time_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_time 工具自检失败: {e}")
    # 检查 get_transaction_history 工具
    try:
        get_transaction_history_result = get_transaction_history()
        logger.info(f"{MODULE_TAG}get_transaction_history 工具自检结果: {get_transaction_history_result}")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_transaction_history 工具自检失败: {e}")
    
    



if __name__ == "__main__":

    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

    start_time = time.time()
    SYSTEM_JSON_PATH = config["data_path"] # Moved here as it's only used in __main__
    SYSTEM_PROMPT_PATH = config["MODEL_CONFIG"]["SYSTEM_PROMPT_PATH"] # Ensure this is available


    data_json_path = SYSTEM_JSON_PATH

    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)

    # 初始用户输入，包含文本和图片信息
    initial_prompt_text = json.dumps(data_json, indent=2, ensure_ascii=False)
    logger.info(f"初始 prompt_text 导入完成") # Avoid printing potentially large json to log
    screenshot_path = data_json.get("clipboard_image_path")
    logger.info(f"screenshot_path 导入完成, path:{screenshot_path}")


    logger.info("开始与 Gemini API 进行多轮交互...")

    # 初始化对话历史
    current_prompt_text = initial_prompt_text # Use initial prompt for the first turn
    current_screenshot_path = screenshot_path # Use initial screenshot for the first turn
    max_turns = 6 # 设置最大交互轮数，防止无限循环
    function_response_parts = []

    for turn in range(max_turns):
        logger.info(f"--- 第 {turn + 1} 轮 API 调用 ---\n")
        prompt_to_send = current_prompt_text if turn == 0 else ""
        screenshot_to_send = current_screenshot_path if turn == 0 else None

        # 动态构建本轮可用的工具列表
        current_all_function_declarations = list(all_function_declarations) # 复制原始声明，避免修改全局变量
        
        tools_to_remove_names = []
        if len(current_all_function_declarations)==0:
            logger.info(f"{MODULE_TAG}本轮可用工具列表为空。")
        if get_time_call_count >= 1:
            tools_to_remove_names.append("gettime")
        if get_transaction_history_call_count >= 1:
            tools_to_remove_names.append("gettransactionhistory")
        if execute_python_code_call_count >= 2:
            tools_to_remove_names.append("executepythoncode")

        if tools_to_remove_names:
            original_declarations_len = len(current_all_function_declarations)
            current_all_function_declarations = [
                decl for decl in current_all_function_declarations
                if decl.name not in tools_to_remove_names # 使用字典的 "name" 键进行过滤
            ]
            if len(current_all_function_declarations) < original_declarations_len:
                logger.info(f"{MODULE_TAG}已从本轮可用工具中移除: {tools_to_remove_names}")
        
        # 重新构建本轮的 available_tools
        current_available_tools = [types.Tool(function_declarations=current_all_function_declarations)]

        result = call_gemini_api_stream(
            prompt_text=prompt_to_send,
            screenshot_path=screenshot_to_send,
            system_prompt_path=SYSTEM_PROMPT_PATH,
            tools=current_available_tools, # 传递动态构建的工具列表
            function_response_parts=function_response_parts
        )

        current_screenshot_path = None
        current_prompt_text = ""
        function_response_parts.clear()

        if "function_calls" in result and result["function_calls"]:
            # 模型请求调用一个或多个函数
            list_of_func_calls = result["function_calls"]
            logger.info(f"{MODULE_TAG}接收到 {len(list_of_func_calls)} 个函数调用请求。")

            # 将模型请求的所有 function_calls 添加到历史
            # 每个 function_call 都是一个 Part
            model_parts = [fc for fc in list_of_func_calls]
            # 模拟执行所有函数并收集结果
            for func_call_obj in list_of_func_calls:
                logger.info(f"{MODULE_TAG}模拟执行函数: {func_call_obj.name} 参数: {func_call_obj.args}")
                response_part = execute_function_call(func_call_obj) # execute_function_call 应该返回 Part
                function_response_parts.append(types.Content(role="user", parts=[response_part])) # 直接添加 Content 对象
            
            # 将所有函数执行结果添加到历史
            logger.info(f"{MODULE_TAG}所有函数执行结果已添加到历史，准备下一轮调用。")

            # 继续下一轮循环，将更新后的历史发送给模型
            continue # Go to the next iteration of the loop

        elif "text" in result:
            # 收到最终文本响应
            final_response = result["text"]
            logger.info(f"{MODULE_TAG}收到最终模型响应，交互结束。")
            # 可以选择将最终响应添加到历史，但这通常不是必需的

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
{result['error']}""")
            print(f"""{MODULE_TAG}API 调用发生错误:
{result['error']}""")
            break # Exit the loop on error

    else:
        logger.warning(f"{MODULE_TAG}达到最大交互轮数 ({max_turns})，交互结束。可能未收到最终响应。")
        print(f"{MODULE_TAG}警告：达到最大交互轮数 ({max_turns})，交互结束。可能未收到最终响应。请检查模型行为或增加最大轮数。")

    end_time = time.time()
    logger.info(f"总运行时间: {round((end_time - start_time) / 60, 2)} 分钟")

    # 新增：输出所有计时数据
    print("\n--- 性能计时数据 ---")
    print(f"图片上传总耗时: {timing_data['image_upload_time']:.4f} 秒")
    print(f"gettime 函数总耗时: {timing_data['gettime_exec_time']:.4f} 秒")
    print(f"gettransactionhistory 函数总耗时: {timing_data['gettransactionhistory_exec_time']:.4f} 秒")
    print(f"executepythoncode 函数每次耗时: {[f'{t:.4f}秒' for t in timing_data['executepythoncode_exec_times']]}")
    print(f"Gemini API 调用每次耗时: {[f'{t:.4f}秒' for t in timing_data['gemini_api_call_times']]}")
    print(f"总程序运行时间: {end_time - start_time:.4f} 秒")
    print("--------------------\n")
