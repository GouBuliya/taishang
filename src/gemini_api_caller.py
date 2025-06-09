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
api_key_index = 1
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

# ===================== 函数调用工具定义框架 END =====================
history=[]
_api_key = API_KEY
if not _api_key:
    logger.error("未配置 GEMINI_API_KEY")
client = genai.Client(api_key=_api_key)

def call_gemini_api_stream(
    prompt_text,
    system_prompt_path=None, # Renamed to clearly indicate it's a path
    # tools=None,
    function_response_parts=None,
):

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

        # 将 tools 参数传递给 GenerateContentConfig
        gemini_config = types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_config={
                "include_thoughts": DEFAULT_INCLUDE_THOUGHTS, # 取消注释此行
                "thinking_budget": DEFAULT_THINKING_BUDGET,
            },
            system_instruction=system_prompt_content, # 使用读取的系统提示词内容
            tools=[types.Tool(code_execution=types.ToolCodeExecution)] # Assuming tools are needed
        )

        # 构建当前轮次的用户输入内容


        api_call_start_time = time.time() # Start timing for Gemini API call
        response = client.models.generate_content_stream(
            model=DEFAULT_MODEL_NAME,
            contents=prompt_text, # 将整个历史对话内容传递给 API
            config=gemini_config,

        )

        output_buffer = []
        collected_function_calls = [] # 用于收集本轮的所有函数调用
        model_response_parts = [] # 用于收集模型本轮的完整响应（文本+函数调用）
        collected_thought_text_for_current_turn = [] # 新增：用于收集本轮的思考摘要文本

        # 迭代 chunk 处理流式输出和函数调用
        for chunk in response:
            # time.sleep(0.5) # 调试时可以添加此行
            cnt += 1

            # 如果没有函数调用，检查是否有文本
            if chunk.text:  # 使用 if chunk.text 更加 Pythonic
                print(chunk.text, end="", flush=True)
                output_buffer.append(chunk.text)
                # 将文本添加到模型响应部分
                model_response_parts.append(types.Part(text=chunk.text))
                effective_logger.info(f"[Model Response]: {chunk.text}")
                yield {"text": chunk.text}  # 立即返回当前文本部分
            else:
                # 尝试从非文本/非函数调用部分中捕获思考摘要
                # 优先从 chunk.parts 中获取文本，其次从 chunk.candidates.content.parts 中获取
                if hasattr(chunk, 'parts') and chunk.parts:
                    for part in chunk.parts:
                        if hasattr(part, 'text') and part.text:
                            collected_thought_text_for_current_turn.append(part.text)
                            yield {"thought": part.text}  # 立即返回当前思考部分
                            # logger.info(f"{part.text}")
                            # effective_logger.info(f"{part.text}")  # 恢复注释此行
                elif hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        # 确保 candidate.content 不为 None
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        collected_thought_text_for_current_turn.append(part.text)
                                        yield {"thought": part.text}  # 立即返回当前思考部分
                                        # logger.info(f"{part.text}")
                                        # effective_logger.info(f"{part.text}")  # 恢复注释此行
                                    if part.executable_code is not None:
                                        effective_logger.info(f"[Executable Code]: {part.executable_code.code}")
                                        yield {"executable_code": part.executable_code.code}  # 立即返回可执行代码部分
                                    if part.code_execution_result is not None:
                                        effective_logger.info(f"[Code Execution Result]: {part.code_execution_result.output}")
                                        yield {"executable_code": part.code_execution_result.output}  # 立即返回代码执行结果部分


        api_call_end_time = time.time()
        timing_data["gemini_api_call_times"].append(api_call_end_time - api_call_start_time) # Store API call time

        # 在处理完所有 chunk 后，如果收集到思考摘要，则统一记录
        # if collected_thought_text_for_current_turn:
        #     thought_summary = ''.join(collected_thought_text_for_current_turn)
            # logger.info(f"{MODULE_TAG}Captured full thought summary for this turn: {thought_summary}")
            # effective_logger.info(f"[Thought Summary]: {thought_summary}") # 记录思考摘要到有效通信日志

        # 在处理完所有 chunk 后，将模型本轮的完整响应添加到历史中
        # if model_response_parts:
        #     history.append(types.Content(role="model", parts=model_response_parts))

        # 在处理完所有 chunk 后，判断是返回函数调用列表还是文本

        # output_text = "".join(output_buffer)
        # effective_logger.info(f"[Model Response]: {output_text}fenfe") # 记录模型回答到有效通信日志
        # return {"text": output_text}


    except Exception as e:
        tb = traceback.format_exc()#获取异常信息
        return {"error": f"{e},tb:{tb}"}



__all__ = ["call_gemini_api_stream"]




if __name__ == "__main__":

    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

    start_time = time.time()
    SYSTEM_JSON_PATH = config["data_path"] # Moved here as it's only used in __main__
    SYSTEM_PROMPT_PATH = config["MODEL_CONFIG"]["SYSTEM_PROMPT_PATH"] # Ensure this is available
    logger.info(f"api-key{API_KEY}")
    # 在主程序开始时，先加载一次 data_json 到全局变量中，以便 get_initial_data 工具能访问
    # 或者让 get_initial_data 在被调用时才加载，这取决于你的设计偏好。
    # 这里我们让它在调用时加载，确保惰性加载和隔离。
    initial_user_query = ""

    with open(SYSTEM_JSON_PATH, "r", encoding="utf-8") as f:
        data_json = json.load(f)
    logger.info(f"初始 prompt_text 导入完成: {data_json}") # 这行现在不合适，因为不是直接导入提示词

    # tool_self_check() # 移除了工具自检的调用
    #清空logs/think_log.md
    with open(EFFECTIVE_LOG_FILE, "w", encoding="utf-8") as f:
        f.truncate(0)



    logger.info("开始与 Gemini API 进行多轮交互...")

    # 初始用户输入，不再是 data_json 的内容，而是引导模型调用工具的文本


    current_prompt_text = initial_user_query # 第一轮发送这个引导提示

    function_response_parts = []
    def call_get_initial_data():
        result = call_gemini_api_stream(
            prompt_text=current_prompt_text,
            system_prompt_path=SYSTEM_PROMPT_PATH,
            # tools=current_available_tools, # 传递动态构建的工具列表
            function_response_parts=function_response_parts
        )
        output_data= []
        for chunk in result:
            if "text" in chunk:
                print(chunk["text"], end="", flush=True)
                output_data.append(chunk["text"])
                # 将当前轮次的文本响应添加到 function_response_parts
                function_response_parts.append(types.Part(text=chunk["text"]))
            elif "thought" in chunk:
                # 处理思考摘要
                thought_text = chunk["thought"]
                print(f"\n[Thought]: {thought_text}", flush=True)
                effective_logger.info(f"{thought_text}")
                effective_handler.flush() # 新增：强制刷新日志文件
            elif "executable_code" in chunk:
                logger.info(f"{MODULE_TAG}收到可执行代码: {chunk['executable_code']}")
            elif "error" in chunk:
                # 处理错误信息
                error_message = chunk["error"]
                print(f"\n[Error]: {error_message}", flush=True)
                logger.error(f"{MODULE_TAG}调用 Gemini API 时发生错误: {error_message}")
                return None
        output_text = "".join(output_data)
        effective_logger.info(f"[Model Response]: {output_text}") # 记录模型回答到有效通信日志
        return output_text

    result = call_get_initial_data() # 调用获取初始数据的函数
    # 收到最终文本响应
    final_response = result
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
        print(f"""原始响应内容：{final_response}""")


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