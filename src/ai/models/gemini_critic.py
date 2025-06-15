"""_summary_

    Returns:
        list: API 返回的输出数据
这是一个调用 Gemini Critic API 的脚本，主要功能是生成内容并处理响应。

"""
from google import genai
from google.genai import types

import json
with open("config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
import logging
import os
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

MODULE_TAG = "[Critic_api_caller] " 
client = genai.Client(api_key=config["gemini_api_key_set"]["gemini_api_key_4"])

def main(
    critic_data: dict
) -> list:
    """调用 Gemini Critic API 的主函数

    Args:
        critic_data: 结构化的谏官输入数据，包含：
                    - decision_maker_output: 决策者输出
                    - raw_market_data: 原始市场数据
                    - kline_images_context: K线图像上下文
                    - system_configs: 系统配置
                    - system_performance_summary: 系统性能摘要
                    - current_iteration_info: 当前迭代信息
                    - retrieved_external_context: 外部上下文（可选）
                    
                    为了向后兼容，也可以传入简单的字典数据

    Returns:
        list: API 返回的输出数据
    """
    output_buffer = []
    try:
        logger.info(f"{MODULE_TAG} Gemini Critic API caller started.")
        with open(config["MODEL_CONFIG"]["Critic_SYSTEM_PROMPT_PATH"], "r", encoding="utf-8") as f:
            logger.info(f"正在读取系统提示文件: {f.name}") # 改进日志信息
            system_prompt = f.read() # 直接读取文件内容作为字符串
        Config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=config["MODEL_CONFIG"]["critic_temperature"],
            max_output_tokens=config["MODEL_CONFIG"]["critic_max_output_tokens"],
            top_p=config["MODEL_CONFIG"]["critic_top_p"],
            tools=[types.Tool(code_execution=types.ToolCodeExecution)] # type: ignore
        )

        # 检查输入数据格式，确保向后兼容性
        if isinstance(critic_data, dict):
            # 检查是否是新的结构化格式
            if "decision_maker_output" in critic_data:
                logger.info(f"{MODULE_TAG}使用新的结构化谏官数据格式")
                prompt_text = json.dumps(critic_data, ensure_ascii=False, indent=4)
            else:
                logger.info(f"{MODULE_TAG}使用传统的简单数据格式（向后兼容）")
                prompt_text = json.dumps(critic_data, ensure_ascii=False, indent=4)
        else:
            logger.warning(f"{MODULE_TAG}输入数据格式异常，尝试直接序列化")
            prompt_text = json.dumps(critic_data, ensure_ascii=False, indent=4)

        response = client.models.generate_content_stream(
            model=config["MODEL_CONFIG"]["MODEL_NAME"], 
            config=Config,
            contents=prompt_text
        )
        import time
        import traceback
        model_response_parts=[]
        collected_thought_text_for_current_turn=[]
        tart_time = time.time()
        logger.info(f"{MODULE_TAG}开始调用API，模型: {config['MODEL_CONFIG']['MODEL_NAME']}, 配置: {Config}")
        for chunk in response:
            if chunk.text:  # 使用 if chunk.text 更加 Pythonic
                output_buffer.append(chunk.text)
                effective_logger.info(f"[Model Response]: {chunk.text}")
                print(f"\033[32m{chunk.text}\033[0m")  # 蓝颜色的字
            elif hasattr(chunk, 'candidates') and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                for part in candidate.content.parts:
                                    if part.executable_code is not None:
                                        effective_logger.info(f"[Executable Code]: {part.executable_code.code}")
                                        print(f"\033[32m{part.executable_code.code}\033[0m")  # 绿颜色的字
                                    if part.code_execution_result is not None:
                                        effective_logger.info(f"[Code Execution Result]: {part.code_execution_result.output}")
                                        print(f"\033[32m{part.code_execution_result.output}\033[0m")  # 绿颜色的字
        return output_buffer
    except Exception as e:
        logger.error(f"{MODULE_TAG}调用 Gemini Critic API 失败: {e}")
        logger.error(traceback.format_exc())
        raise
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        # 从配置文件中获取 prompt_text
        with open(config["logs"]["Controller_answer_path"], "r", encoding="utf-8") as f:
            prompt_text = json.load(f)
    except FileNotFoundError:
        logger.error(f"{MODULE_TAG}配置文件未找到，请检查路径: {config['logs']['Controller_answer_path']}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"{MODULE_TAG}解析配置文件失败: {e}")
        raise

    try:
        result = main(prompt_text)
        def check_json_format(data):
            try:
                json.dumps(data, ensure_ascii=False)
                return True
            except (TypeError, ValueError):
                return False
        if check_json_format(result):
            with open(config["logs"]["Critic_answer_path"], "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=4)
            logger.info(f"{MODULE_TAG}API 调用成功，结果已保存到 {config['logs']['Critic_answer_path']}")
        else:
            logger.error(f"{MODULE_TAG}API 返回的结果不是有效的 JSON 格式，无法保存。")
            raise ValueError("API 返回的结果不是有效的 JSON 格式。")

    except Exception as e:
        logger.error(f"{MODULE_TAG} An error occurred: {e}")
        raise