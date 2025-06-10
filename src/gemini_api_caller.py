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
# 移除所有现有的处理器
for handler in effective_logger.handlers[:]:
    effective_logger.removeHandler(handler)
# 只添加文件处理器
effective_handler = logging.FileHandler(EFFECTIVE_LOG_FILE, mode='a', encoding='utf-8')
effective_formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
effective_handler.setFormatter(effective_formatter)
effective_logger.addHandler(effective_handler)
effective_logger.propagate = False
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
    system_prompt_path=None,
):
    """调用 Gemini API 的流式接口

    Args:
        prompt_text: 用户输入的文本
        system_prompt_path: 系统提示词文件路径
    """
    global cnt
    system_prompt_content = ""
    if system_prompt_path and os.path.exists(system_prompt_path):
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt_content = f.read().strip()
        if not system_prompt_content:
             logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {system_prompt_path}.")
    else:
         logger.warning(f"{MODULE_TAG}系统提示词文件未找到或未提供: {system_prompt_path}.")

    # 添加 JSON 格式要求到提示中

    
    system_prompt_content = system_prompt_content

    try:
        # Gemini API 配置
        gemini_config = types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            system_instruction=system_prompt_content,
            thinking_config={
                "include_thoughts": DEFAULT_INCLUDE_THOUGHTS, # 取消注释此行
                "thinking_budget": DEFAULT_THINKING_BUDGET,
            },
            tools=[types.Tool(code_execution=types.ToolCodeExecution())]
        )

        api_call_start_time = time.time()
        response = client.models.generate_content_stream(
            model=DEFAULT_MODEL_NAME,
            contents=prompt_text,
            config=gemini_config,
        )
        # 处理响应流
        output_buffer = []
        model_response_parts = [] # 用于收集模型本轮的完整响应（文本+函数调用）
        collected_thought_text_for_current_turn = [] # 新增：用于收集本轮的思考摘要文本

        for chunk in response:
            cnt += 1
            
            
            # 如果没有函数调用，检查是否有文本
            if chunk.text:  # 使用 if chunk.text 更加 Pythonic
                # print(chunk.text, end="", flush=True)
                output_buffer.append(chunk.text)
                # 将文本添加到模型响应部分
                model_response_parts.append(types.Part(text=chunk.text))
                effective_logger.info(f"[Model Response]: {chunk.text}")
                print(f"\033[32m{chunk.text}\033[0m")  # 蓝颜色的字
                yield {"text": chunk.text}  # 立即返回当前文本部分
            else:
                # 尝试从非文本/非函数调用部分中捕获思考摘要
                # 优先从 chunk.parts 中获取文本，其次从 chunk.candidates.content.parts 中获取
                if hasattr(chunk, 'parts') and chunk.parts:
                    for part in chunk.parts:
                        if hasattr(part, 'text') and part.text:
                            collected_thought_text_for_current_turn.append(part.text)
                            print(part.text)
                            yield {"thought": part.text}  # 立即返回当前思考部分
                            effective_logger.info(f"{part.text}")  # 恢复注释此行
                elif hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        # 确保 candidate.content 不为 None
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        collected_thought_text_for_current_turn.append(part.text)
                                        print(part.text)

                                        yield {"thought": part.text}  # 立即返回当前思考部分
                                        effective_logger.info(f"{part.text}")  # 恢复注释此行
                                    if part.executable_code is not None:
                                        effective_logger.info(f"[Executable Code]: {part.executable_code.code}")
                                        print(f"\033[32m{part.executable_code.code}\033[0m")  # 绿颜色的字

                                        yield {"executable_code": part.executable_code.code}  # 立即返回可执行代码部分
                                    if part.code_execution_result is not None:
                                        effective_logger.info(f"[Code Execution Result]: {part.code_execution_result.output}")
                                        print(f"\033[32m{part.code_execution_result.output}\033[0m")  # 绿颜色的字

                                        yield {"executable_code": part.code_execution_result.output}  # 立即返回代码执行结果部分

        api_call_end_time = time.time()
        timing_data["gemini_api_call_times"].append(api_call_end_time - api_call_start_time)

        # 尝试解析完整响应为 JSON
        complete_response = "".join(output_buffer)
        try:
            # 如果响应包含在 ```json``` 中，提取 JSON 部分
            if "```json" in complete_response:
                json_start = complete_response.find("```json") + 7
                json_end = complete_response.rfind("```")
                json_str = complete_response[json_start:json_end].strip()
                json.loads(json_str)  # 验证 JSON 格式
        except json.JSONDecodeError as e:
            logger.error(f"{MODULE_TAG}响应不是有效的 JSON 格式: {str(e)}")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}API调用异常: {str(e)}\n{tb}")
        return {"error": f"{str(e)}\n{tb}"}



__all__ = ["call_gemini_api_stream"]




if __name__ == "__main__":
    start_time = time.time()
    SYSTEM_JSON_PATH = config["data_path"]
    SYSTEM_PROMPT_PATH = config["MODEL_CONFIG"]["SYSTEM_PROMPT_PATH"]
    logger.info(f"api-key{API_KEY}")

    # 加载数据作为提示词
    with open(SYSTEM_JSON_PATH, "r", encoding="utf-8") as f:
        data_json = json.load(f)
    logger.info("系统数据加载完成")
    
    # 将 data_json 转换为字符串作为提示词
    current_prompt_text = json.dumps(data_json, ensure_ascii=False, indent=4)
    # logger.info(f"初始提示词设置完成: \n{current_prompt_text}")

    # 清空日志文件
    with open(EFFECTIVE_LOG_FILE, "w", encoding="utf-8") as f:
        f.truncate(0)

    logger.info("开始与 Gemini API 进行交互...")

    def call_get_initial_data():
        """调用 Gemini API 并处理响应"""
        response_parts = []
        
        try:
            result = call_gemini_api_stream(
                prompt_text=current_prompt_text,
                system_prompt_path=SYSTEM_PROMPT_PATH,
            )
            
            if not result:
                logger.error(f"{MODULE_TAG}未获得API响应")
                return ""
                
            for chunk in result:
                if "text" in chunk:
                    response_parts.append(chunk["text"])
                elif "executable_code" in chunk:
                    logger.info(f"{MODULE_TAG}收到可执行代码: {chunk['executable_code']}")
                elif "code_result" in chunk:
                    logger.info(f"{MODULE_TAG}代码执行结果: {chunk['code_result']}")
                elif "error" in chunk:
                    error_message = chunk["error"]
                    logger.error(f"{MODULE_TAG}API响应错误: {error_message}")
                    
            output_text = "".join(response_parts)
            # effective_logger.info(f"[Model Response]: {output_text}")
            return output_text
            
        except Exception as e:
            logger.error(f"{MODULE_TAG}处理响应时发生异常: {str(e)}", exc_info=True)
            return ""

    # 获取模型响应
    result = call_get_initial_data()
    
    if result:
        logger.info(f"{MODULE_TAG}收到最终模型响应")
        try:
            # 尝试提取和解析 JSON
            if "```json" in result:
                json_start = result.find("```json") + 7
                json_end = result.rfind("```")
                json_text = result[json_start:json_end].strip()
            else:
                json_text = result.strip()

            output_data = json.loads(json_text)
            output_file_path = config["gemini_answer_path"]
            
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            print(f"{MODULE_TAG}已将解析后的输出内容保存到 {output_file_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"{MODULE_TAG}解析响应为JSON失败: {str(e)}")
            print(f"{MODULE_TAG}错误：无法解析模型响应为JSON")
            print(f"原始响应内容：{result}")
    else:
        logger.error(f"{MODULE_TAG}未获得有效响应")

    # 输出统计信息
    end_time = time.time()
    run_time = end_time - start_time
    
    print("\n--- 性能统计 ---")
    print(f"Gemini API 调用耗时: {[f'{t:.4f}秒' for t in timing_data['gemini_api_call_times']]}")
    print(f"总运行时间: {run_time/60:.2f}分钟{run_time%60:.2f}秒")
    print(f"API调用次数: {cnt}")
    print("--------------")