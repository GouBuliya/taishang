import logging
import os
import sys
import json
import traceback
import base64
import random
import re
import time
# ===================== 全局配置与初始化 =====================

# 假设 config.json 路径正确且包含所需配置
config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r"))


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["ETH_log_path"]
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

MODULE_TAG = "[gemini_api_caller] "

API_KEY = config["GEMINI_API_KEY"]
DEFAULT_MODEL_NAME = "gemini-2.5-flash-preview-05-20" # 确保模型名正确且可用
SYSTEM_PROMPT_PATH = config["SYSTEM_PROMPT_PATH"]
SYSTEM_PROMPT = ""

SYSTEM_JSON_PATH = config["ETH_data_path"]
if os.path.exists(SYSTEM_PROMPT_PATH):
    with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
    if not SYSTEM_PROMPT:
        logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {SYSTEM_PROMPT_PATH}.")
else:
    logger.warning(f"{MODULE_TAG}系统提示词文件未找到: {SYSTEM_PROMPT_PATH}. SYSTEM_PROMPT 将为空。")
# ===================== 全局配置与初始化 END =====================

DEFAULT_TEMPERATURE = config["MODEL_CONFIG"]["default_temperature"]
DEFAULT_TOP_P = config["MODEL_CONFIG"]["default_top_p"]
DEFAULT_MAX_OUTPUT_TOKENS = config["MODEL_CONFIG"]["default_max_output_tokens"]
DEFAULT_THINKING_BUDGET = config["MODEL_CONFIG"]["default_thinking_budget"]
DEFAULT_INCLUDE_THOUGHTS = config["MODEL_CONFIG"]["default_include_thoughts"]

# ===================== Gemini API 调用主模块 =====================

from google import genai
from google.genai import types
from pydantic import BaseModel

# ================= tools =================

def get_transaction_history(target: str) -> dict:
    """
    Args:
        target: 目标（例如，'ETH-USDT'）
    Returns:
        最近3条交易历史记录 (JSON 格式)
    """
    import subprocess
    logger.info(f"{MODULE_TAG}运行get_transaction_history.py")
    try:
        # 假设 get_transaction_history.py 脚本会打印 JSON 格式的交易历史
        trade_log_process = subprocess.run(
            [config["python_path"]["global"], config["path"]["function_path"]["get_transaction_history"]],
            capture_output=True, text=True, timeout=360, check=True
        )
        trade_log = trade_log_process.stdout
        logger.info(f"{MODULE_TAG}获取最后3条交易纪录完成")
        # 尝试解析为JSON，如果脚本输出不是严格的JSON，这里可能需要调整
        try:
            res = json.loads(trade_log)
        except json.JSONDecodeError:
            res = {"transaction_history": trade_log.strip()} # 如果不是JSON，则作为字符串返回
        return {"transaction_history":res}
    except subprocess.CalledProcessError as e:
        logger.error(f"{MODULE_TAG}get_transaction_history.py 脚本执行失败: {e.stderr}")
        return {"error": f"脚本执行失败: {e.stderr}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_transaction_history 调用异常: {e}")
        return {"error": f"调用异常: {e}"}


# 修正后的 get_transaction_history_declaration
get_transaction_history_declaration = {
    "name": "get_transaction_history",
    "description": "获取最近3条交易历史记录",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {  # 参数名应与 Python 函数定义一致
                "type": "string",
                "description": "要获取交易历史记录的目标（例如，'ETH-USDT'）"
            },
        },
        "required": ["target"]  # 必需参数名
    }
}

def get_time(target: str) -> dict:
    """
    Args:
        target: 获取时间的上下文目标（例如，'当前时间'）
    Returns:
        当前时间 (JSON 格式)
    """
    import subprocess
    logger.info(f"{MODULE_TAG}运行get_time.py")
    try:
        # 假设 get_time.py 脚本会打印当前时间
        time_process = subprocess.run(
            [config["python_path"]["global"], config["path"]["function_path"]["get_time"]],
            capture_output=True, text=True, timeout=360, check=True
        )
        current_time = time_process.stdout.strip()
        logger.info(f"{MODULE_TAG}获取当前时间完成")
        res =  current_time
        return {"time":res}
    except subprocess.CalledProcessError as e:
        logger.error(f"{MODULE_TAG}get_time.py 脚本执行失败: {e.stderr}")
        return {"error": f"脚本执行失败: {e.stderr}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_time 调用异常: {e}")
        return {"error": f"调用异常: {e}"}


# 修正后的 get_time_declaration
get_time_declaration = {
    "name": "get_time",
    "description": "获取当前时间",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {  # 参数名应与 Python 函数定义一致
                "type": "string",
                "description": "获取时间的上下文目标（例如，'当前时间'）"
            },
        },
        "required": ["target"]  # 必需参数名
    }
}

# =======================================

def call_gemini_api_stream(
    prompt_text,
    screenshot_path=None,
    system_prompt=None,
):
    """
    流式调用 Gemini API，支持文本+图片输入，并处理函数调用。
    每次调用都是新的对话（无历史上下文），但内部会处理多轮函数调用。
    """
    try:
        _api_key = API_KEY
        if not _api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY")

        # 修正后的工具声明
        tools = types.Tool(function_declarations=[get_transaction_history_declaration, get_time_declaration])

        gemini_config = types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_config={
                "include_thoughts": DEFAULT_INCLUDE_THOUGHTS,
                "thinking_budget": DEFAULT_THINKING_BUDGET,
            },
            system_instruction=system_prompt,
            tools=[tools],
                    gemini_config = types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_config={
                "include_thoughts": DEFAULT_INCLUDE_THOUGHTS,
                "thinking_budget": DEFAULT_THINKING_BUDGET,
            },
            system_instruction=system_prompt,
            tools=[tools],
            tools_config=types.ToolsConfig(
                function_calling_config=types.FunctionCallingConfig(mode="parallel")
            )
        )
        )
        # gemini_config["automatic_function_calling"]={"disable": True}
        client = genai.Client(api_key=_api_key)

        # 准备初始内容
        initial_contents = []
        
        # 添加一个初始文本部分
        initial_contents.append(types.Part(text="用户输入：")) # 添加一个引导文本部分

        if screenshot_path:
            try:
                logger.info(f"{MODULE_TAG}图片导入开始:{screenshot_path}")
                with open(screenshot_path, "rb") as f:
                    image_bytes = f.read()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                # 将图片的base64编码添加到内容中
                image_part = types.Part(
                    inline_data=types.Blob(
                        mime_type='image/png', # 假设图片是png格式
                        data=image_base64
                    )
                )
                initial_contents.append(image_part)
                logger.info(f"{MODULE_TAG}图片导入完成并添加到内容列表")
            except Exception as e:
                logger.error(f"{MODULE_TAG}图片处理失败: {e}")
                # 如果图片导入失败，不中断流程，继续只用文本

        # 将 prompt_text 中的数据转换为文本部分
        if isinstance(prompt_text, dict):
            for key, value in prompt_text.items():
                # 截图路径已经处理过了，跳过
                if key != "clipboard_image_path":
                    initial_contents.append(types.Part(text=f"{key}: {value}"))
        else:
             # 如果 prompt_text 不是字典，作为普通文本处理
             initial_contents.append(types.Part(text=prompt_text))

        # 初始化对话历史
        history = [
            types.Content(parts=initial_contents, role="user")
        ]

        final_output_text = ""
        max_turns = 10  # 设置最大交互轮次，防止无限循环
#增加重试机制

        for turn in range(max_turns):
            logger.info(f"{MODULE_TAG}开始第 {turn + 1} 轮 Gemini API 调用...")
            try:
                response_stream = client.models.generate_content_stream(
                    model=DEFAULT_MODEL_NAME,
                    contents=history,
                    config=gemini_config
                )

                current_turn_text_chunks = []#本轮的文本
                function_calls_to_execute = []#本轮的函数调用
                has_text_in_this_turn = False#本轮是否有文本
                has_function_calls_in_this_turn = False#本轮是否有函数调用

                # 遍历流式响应的每个块
                for chunk in response_stream:
                    
                    if chunk.text:
                        current_turn_text_chunks.append(chunk.text)#将本轮的文本添加到本轮的文本列表中
                        print(f"chunk.text:{chunk.text}\n", end="", flush=True)
                        has_text_in_this_turn = True
                    if chunk.function_calls:
                        function_calls_to_execute.extend(chunk.function_calls)#将本轮的函数调用添加到本轮的函数调用列表中
                        print(f"chunk.function_calls:{chunk.function_calls}\n", end="", flush=True)
                        has_function_calls_in_this_turn = True

                # 将模型本轮的响应（文本或函数调用）添加到历史中
                if has_function_calls_in_this_turn:
                    """
                    模型请求调用函数
                    将本轮的函数调用添加到历史中
                    执行函数并准备工具响应
                    将工具响应添加到历史中
                    继续循环，将工具响应发送回模型，等待最终答案
                    """
                    model_parts = [types.Part(function_call=fc) for fc in function_calls_to_execute]#将本轮的函数调用添加到本轮的函数调用列表中
                    history.append(types.Content(parts=model_parts, role="model"))#将本轮的函数调用添加到历史中

                    # 执行函数并准备工具响应
                    tool_responses_parts = []
                    for fc in function_calls_to_execute:
                        function_name = fc.name
                        # 将 protobuf map 转换为 Python 字典
                        args = {k: v for k, v in fc.args.items()}
                        logger.info(f"{MODULE_TAG}执行工具: {function_name}，参数: {args}")
                        try:
                            # 通过 globals() 访问当前模块中的函数
                            if function_name in globals() and callable(globals()[function_name]):
                                tool_result = globals()[function_name](**args)
                                tool_responses_parts.append(types.Part(function_response=types.FunctionResponse(name=function_name, response=tool_result)))
                                logger.info(f"{MODULE_TAG}工具 {function_name} 执行成功。结果: {tool_result}")
                            else:
                                error_msg = f"函数 {function_name} 未找到或不可调用。"
                                tool_responses_parts.append(types.Part(function_response=types.FunctionResponse(name=function_name, response={"error": error_msg})))
                                logger.error(f"{MODULE_TAG}{error_msg}")
                        except Exception as e:
                            tb = traceback.format_exc()
                            error_msg = f"执行工具 {function_name} 时发生错误: {e}\n{tb}"
                            tool_responses_parts.append(types.Part(function_response=types.FunctionResponse(name=function_name, response={"error": error_msg})))
                            logger.error(f"{MODULE_TAG}{error_msg}")
                    
                    # 将工具响应添加到历史中
                    history.append(types.Content(parts=tool_responses_parts, role="tool"))
                    # 继续循环，将工具响应发送回模型，等待最终答案
                    continue
                elif has_text_in_this_turn:
                    # 模型返回了文本，这可能是最终答案
                    model_text_response = "".join(current_turn_text_chunks)
                    history.append(types.Content(parts=[types.Part(text=model_text_response)], role="model"))
                    final_output_text = model_text_response
                    # 如果只有文本返回，通常意味着对话结束
                    break
                else:
                    # 没有文本也没有函数调用，可能是流结束或意外的空响应
                    logger.warning(f"{MODULE_TAG}第 {turn + 1} 轮未收到文本或函数调用。")
                    break

            except Exception as e:
                tb = traceback.format_exc()
                logger.error(f"{MODULE_TAG}Gemini API 调用异常: {e}\n{tb}")
                return f"[Gemini API 调用异常] {e}\nTraceback:\n{tb}"

        return final_output_text

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Gemini API 调用初始化或外部异常: {e}\n{tb}")
        return f"[Gemini API 调用初始化或外部异常] {e}\nTraceback:\n{tb}"

__all__ = ["call_gemini_api_stream"]

if __name__ == "__main__":
    # 设置代理（如果需要）
    # os.environ['HTTP_PROXY'] = config["proxy"]["http_proxy"]
    # os.environ['HTTPS_PROXY'] = config["proxy"]["https_proxy"]
    #计时
    start_time = time.time()
    # tools自检
    logger.info(f"{MODULE_TAG}开始自检")
    try:
        # 传入一个示例 target
        logger.info(f"{MODULE_TAG}get_transaction_history 自检结果: {get_transaction_history('ETH-USDT')}")
        logger.info(f"{MODULE_TAG}get_transaction_history 自检完成")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_transaction_history 自检失败: {e}")
    try:
        # 传入一个示例 target
        logger.info(f"{MODULE_TAG}get_time 自检结果: {get_time('当前时间')}")
        logger.info(f"{MODULE_TAG}get_time 自检完成")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_time 自检失败: {e}")

    data_json_path = SYSTEM_JSON_PATH

    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)

    # prompt_text 可以是用户输入的原始文本，也可以是结构化数据
    # 这里为了演示，使用 data_json 中的 user_query
    prompt_text = data_json
    logger.info(f"prompt_text 导入完成: {prompt_text}")

    screenshot_path = data_json.get("clipboard_image_path")
    logger.info(f"screenshot_path 导入完成, path:{screenshot_path}")

    system_prompt_path = SYSTEM_PROMPT_PATH
    logger.info(f"system_prompt_path 导入完成, path:{system_prompt_path}")
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    logger.info("开始 Gemini API 流式调用...")
    # 调用修改后的函数
    max_retries = 3
    temp=True
    while temp==True and max_retries>0:#如果失败重试
        try:
            response = call_gemini_api_stream(
            prompt_text=prompt_text,
            screenshot_path=screenshot_path,
            system_prompt=system_prompt,
            )
            print("\n--- 最终 Gemini 响应 ---")
            print(response)
            response_cleaned = response.replace("```json", "").replace("```", "").strip()
            output_data = json.loads(response_cleaned)
            break
        except Exception as e:
            logger.error(f"Gemini API 调用失败，重试第 {max_retries} 次: {e}")
            temp=False
            max_retries-=1
            continue
    # 尝试解析 JSON 并保存
    end_time = time.time()
    logger.info(f"Gemini API 调用完成，耗时: {end_time - start_time} 秒")
    try:
        # 去除可能的 markdown 格式
        
        with open(config["ETH_gemini_answer_path"], "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"已将解析后的输出内容保存到 {config['ETH_gemini_answer_path']}")
    except json.JSONDecodeError as e:
        logger.error(f"无法将 Gemini 响应解析为 JSON: {e}")
        logger.error(f"原始响应内容:\n{response}")
        # 如果不是JSON，直接保存为文本文件
        with open(config["ETH_gemini_answer_path"].replace(".json", ".json"), "w", encoding="utf-8") as f:
            f.write(response)
        print(f"响应不是有效的 JSON，已保存为文本文件到 {config['ETH_gemini_answer_path'].replace('.json', '.json')}")
    except Exception as e:
        logger.error(f"保存文件时发生未知错误: {e}")