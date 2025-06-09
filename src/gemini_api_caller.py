import os
import json
import logging
import sys
import time
from google import genai
from google.genai import types

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

# 推荐用 GEMINI_API_KEY 作为环境变量名
api_key_index = 3
api_key_list = config["gemini_api_key_set"]
api_key_str="gemini_api_key_"+str(api_key_index)
API_KEY = api_key_list[api_key_str]

# 推荐Gemini模型名
DEFAULT_MODEL_NAME = config["MODEL_CONFIG"]["MODEL_NAME"]
SYSTEM_PROMPT_PATH = config["MODEL_CONFIG"]["SYSTEM_PROMPT_PATH"]

# 模型配置常量
DEFAULT_TEMPERATURE = config["MODEL_CONFIG"]["default_temperature"]
DEFAULT_TOP_P = config["MODEL_CONFIG"]["default_top_p"]
DEFAULT_MAX_OUTPUT_TOKENS = config["MODEL_CONFIG"]["default_max_output_tokens"]
DEFAULT_THINKING_BUDGET = config["MODEL_CONFIG"]["default_thinking_budget"]
DEFAULT_INCLUDE_THOUGHTS = config["MODEL_CONFIG"]["default_include_thoughts"]

# 全局对话历史
history = []
cnt = 0 # 全局计数器，用于计算API调用的总 chunk 数

def call_gemini_api_stream(
    prompt_text,
    system_prompt_path=None,
    tools=None,
    function_response_parts=None,
):
    """
    流式调用 Gemini API，支持文本输入、思考模式和函数调用。
    支持多轮对话（通过 history 全局变量）。
    """
    global cnt
    global history

    system_prompt_content = ""
    if system_prompt_path and os.path.exists(system_prompt_path):
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt_content = f.read().strip()
        if not system_prompt_content:
            logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {system_prompt_path}.")
    else:
        logger.warning(f"{MODULE_TAG}系统提示词文件未找到或未提供: {system_prompt_path}.")

    try:
        if not API_KEY:
            raise RuntimeError("未配置 GEMINI_API_KEY")

        # 配置Gemini API
        gemini_config = types.GenerateContentConfig(    
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            system_instruction=system_prompt_content,
            tools=tools
        )

        client = genai.Client(api_key=API_KEY)

        # 构建当前轮次的用户输入内容
        current_user_parts = []
        if prompt_text:
            current_user_parts.append(types.Part(text=prompt_text))
            history.append(types.Content(parts=current_user_parts, role="user"))

        # 更新对话历史
        if function_response_parts:
            history.append(types.Content(parts=function_response_parts, role="model"))

        # 调用API
        api_call_start_time = time.time()
        response = client.models.generate_content_stream(
            model=DEFAULT_MODEL_NAME,
            contents=history,
            config=gemini_config,
        )

        cnt += 1
        return response

    except Exception as e:
        logger.error(f"{MODULE_TAG}API调用异常: {str(e)}")
        raise

if __name__ == "__main__":
    # 设置代理
    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
    
    logger.info(f"初始化完成")