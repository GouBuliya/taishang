import logging
import os
import sys
import json
import traceback
import base64
import random
import re
import time
# 引入 MCP 相关的 HTTP 客户端
import asyncio # 用于异步操作
import httpx # <--- 新增：用于异步 HTTP 请求

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
from pydantic import BaseModel # 仍在此处，但在此代码中未使用

# ================= 本地 tools (保持不变) =================
def get_transaction_history(target: str) -> dict:
    """
    Args:
        target: 目标（例如，'ETH-USDT'）
    Returns:
        最近3条交易历史记录 (JSON 格式)
    """
    import subprocess
    logger.info(f"{MODULE_TAG}运行本地 get_transaction_history.py")
    try:
        trade_log_process = subprocess.run(
            [config["python_path"]["global"], config["path"]["function_path"]["get_transaction_history"]],
            capture_output=True, text=True, timeout=360, check=True
        )
        trade_log = trade_log_process.stdout
        logger.info(f"{MODULE_TAG}本地获取最后3条交易纪录完成")
        try:
            res = json.loads(trade_log)
        except json.JSONDecodeError:
            res = {"transaction_history": trade_log.strip()}
        return {"transaction_history":res, "source": "local"} # 添加 source
    except subprocess.CalledProcessError as e:
        logger.error(f"{MODULE_TAG}本地 get_transaction_history.py 脚本执行失败: {e.stderr}")
        return {"error": f"本地脚本执行失败: {e.stderr}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}本地 get_transaction_history 调用异常: {e}")
        return {"error": f"本地调用异常: {e}"}

get_transaction_history_declaration = {
    "name": "get_transaction_history",
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

def get_time(target: str) -> dict:
    """
    Args:
        target: 获取时间的上下文目标（例如，'当前时间'）
    Returns:
        当前时间 (JSON 格式)
    """
    import subprocess
    logger.info(f"{MODULE_TAG}运行本地 get_time.py")
    try:
        time_process = subprocess.run(
            [config["python_path"]["global"], config["path"]["function_path"]["get_time"]],
            capture_output=True, text=True, timeout=360, check=True
        )
        current_time = time_process.stdout.strip()
        logger.info(f"{MODULE_TAG}本地获取当前时间完成")
        res =  current_time
        return {"time":res, "source": "local"} # 添加 source
    except subprocess.CalledProcessError as e:
        logger.error(f"{MODULE_TAG}本地 get_time.py 脚本执行失败: {e.stderr}")
        return {"error": f"本地脚本执行失败: {e.stderr}"}
    except Exception as e:
        logger.error(f"{MODULE_TAG}本地 get_time 调用异常: {e}")
        return {"error": f"本地调用异常: {e}"}

get_time_declaration = {
    "name": "get_time",
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
# ================= 本地 tools END =================

# ================= MCP Server 配置 =================
MCP_SERVER_URL = "http://127.0.0.1:3000" # 你的 0xAuto OKX MCP 服务器地址和端口
# ===================================================

# ===================== HttpClientSession 类定义 =====================
class HttpClientSession:
    """
    一个用于与 0xAuto OKX MCP 服务器交互的客户端会话，
    将其功能作为 Gemini 工具暴露。
    """
    def __init__(self, url: str):
        self.url = url
        # 使用 httpx.AsyncClient 进行异步 HTTP 请求，并设置超时
        self._client = httpx.AsyncClient(timeout=60.0)
        self._tool_declarations = [] # 用于存储从 MCP 服务器获取的工具声明

    async def initialize(self):
        """从 MCP 服务器获取工具声明。"""
        try:
            # 假设 MCP 服务器在 /tools 端点暴露其工具声明
            response = await self._client.get(f"{self.url}/tools")
            response.raise_for_status() # 如果状态码是 4xx 或 5xx，则抛出异常
            tools_data = response.json()
            
            if not isinstance(tools_data, list):
                raise ValueError("MCP server /tools endpoint did not return a list.")

            # 将原始字典转换为 types.FunctionDeclaration 对象
            self._tool_declarations = [types.FunctionDeclaration(**tool_def) for tool_def in tools_data]
            logger.info(f"{MODULE_TAG}从 MCP 服务器获取了 {len(self._tool_declarations)} 个工具声明。")
        except httpx.RequestError as e:
            logger.error(f"{MODULE_TAG}连接 MCP 服务器 {self.url} 时出错: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"{MODULE_TAG}解码 MCP 服务器工具响应时出错: {e}。响应内容: {response.text if 'response' in locals() else 'N/A'}")
            raise
        except Exception as e:
            logger.error(f"{MODULE_TAG}MCP 工具初始化期间发生意外错误: {e}")
            raise

    def to_proto(self) -> types.Tool:
        """
        返回 Gemini 的 Tool proto 对象。
        此方法允许 HttpClientSession 直接作为工具传递给 Gemini。
        """
        return types.Tool(function_declarations=self._tool_declarations)

    async def run_tools(self, function_call) -> dict:
        """
        通过 MCP 服务器执行远程工具调用。
        当 Gemini 决定使用此会话提供的工具时，会调用此方法。
        """
        function_name = function_call.name
        # 将 protobuf map 转换为 Python 字典
        args = {k: v for k, v in function_call.args.items()}

        try:
            # 假设 MCP 服务器有一个执行工具的端点，例如 /execute_tool
            response = await self._client.post(
                f"{self.url}/execute_tool",
                json={"function_name": function_name, "args": args}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"{MODULE_TAG}MCP 工具 '{function_name}' 执行成功。结果: {result}")
            return result
        except httpx.RequestError as e:
            logger.error(f"{MODULE_TAG}在 MCP 服务器上调用远程工具 '{function_name}' 时出错: {e}")
            return {"error": f"MCP 服务器通信错误: {e}"}
        except json.JSONDecodeError as e:
            logger.error(f"{MODULE_TAG}解码远程工具 '{function_name}' 的响应时出错: {e}。响应内容: {response.text if 'response' in locals() else 'N/A'}")
            return {"error": f"MCP 服务器返回无效 JSON 响应: {e}"}
        except Exception as e:
            logger.error(f"{MODULE_TAG}远程工具 '{function_name}' 执行期间发生意外错误: {e}")
            return {"error": f"远程工具执行期间发生意外错误: {e}"}
# ===================== HttpClientSession 类定义 END =====================


async def call_gemini_api_stream( # 函数改为异步
    prompt_text,
    screenshot_path=None,
    system_prompt=None,
):
    """
    流式调用 Gemini API，支持文本+图片输入，并处理函数调用（本地或通过远程 0xAuto OKX MCP 服务器）。
    每次调用都是新的对话（无历史上下文），但内部会处理多轮函数调用。
    """
    try:
        _api_key = API_KEY
        if not _api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY")

        # 1. 初始化 MCP HTTP 客户端会话
        # 这会连接到 MCP 服务器，并获取其提供的工具声明
        logger.info(f"{MODULE_TAG}尝试连接到 0xAuto OKX MCP 服务器: {MCP_SERVER_URL}")
        mcp_session = HttpClientSession(url=MCP_SERVER_URL)
        mcp_tools_available = False
        try:
            await mcp_session.initialize() # 异步初始化会话，获取工具定义
            logger.info(f"{MODULE_TAG}成功从 0xAuto OKX MCP 服务器获取工具声明。")
            mcp_tools_available = True
        except Exception as e:
            logger.warning(f"{MODULE_TAG}无法连接到 0xAuto OKX MCP 服务器或获取工具: {e}. 将仅使用本地工具。")
            # traceback.print_exc() # 如果需要更详细的连接错误信息，可以取消注释

        # 2. 组合所有工具声明（本地 + 远程 MCP）
        # 将本地工具声明封装在一个 Tool 对象中
        local_tools_declaration = types.Tool(
            function_declarations=[get_transaction_history_declaration, get_time_declaration]
        )

        # # 构建要传递给 Gemini 的工具列表
        tools_for_gemini = [local_tools_declaration]
        if mcp_tools_available:
            # 如果 MCP 服务器可用，将 mcp_session 也加入工具列表
            # mcp_session 对象会自动提供它从服务器获取的工具声明
            tools_for_gemini.append(mcp_session)
            logger.info(f"{MODULE_TAG}将本地工具和 0xAuto OKX MCP 服务器工具一并提供给 Gemini。")
        else:
            logger.info(f"{MODULE_TAG}仅将本地工具提供给 Gemini。")

        gemini_config = types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_config={
                "include_thoughts": DEFAULT_INCLUDE_THOUGHTS,
                "thinking_budget": DEFAULT_THINKING_BUDGET,
            },
            system_instruction=system_prompt,
            tools=tools_for_gemini, # 传入组合后的工具列表
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )
        )
        
        client = genai.Client(api_key=_api_key)

        # 准备初始内容 (此处代码保持不变)
        initial_contents = []
        initial_contents.append(types.Part(text="用户输入：")) 

        if screenshot_path:
            try:
                logger.info(f"{MODULE_TAG}图片导入开始:{screenshot_path}")
                with open(screenshot_path, "rb") as f:
                    image_bytes = f.read()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                image_part = types.Part(
                    inline_data=types.Blob(
                        mime_type='image/png', 
                        data=image_base64
                    )
                )
                initial_contents.append(image_part)
                logger.info(f"{MODULE_TAG}图片导入完成并添加到内容列表")
            except Exception as e:
                logger.error(f"{MODULE_TAG}图片处理失败: {e}")

        if isinstance(prompt_text, dict):
            for key, value in prompt_text.items():
                if key != "clipboard_image_path":
                    initial_contents.append(types.Part(text=f"{key}: {value}"))
        else:
             initial_contents.append(types.Part(text=prompt_text))

        history = [
            types.Content(parts=initial_contents, role="user")
        ]

        final_output_text = ""
        max_turns = 10  # 设置最大交互轮次，防止无限循环

        for turn in range(max_turns):
            logger.info(f"{MODULE_TAG}开始第 {turn + 1} 轮 Gemini API 调用...")
            try:
                response_stream = client.models.generate_content_stream(
                    model=DEFAULT_MODEL_NAME,
                    contents=history,
                    config=gemini_config
                )

                current_turn_text_chunks = []
                function_calls_to_execute = []
                has_text_in_this_turn = False
                has_function_calls_in_this_turn = False

                for chunk in response_stream:
                    if chunk.text:
                        current_turn_text_chunks.append(chunk.text)
                        print(f"chunk.text:{chunk.text}\n", end="", flush=True)
                        has_text_in_this_turn = True
                    if chunk.function_calls:
                        function_calls_to_execute.extend(chunk.function_calls)
                        print(f"chunk.function_calls:{chunk.function_calls}\n", end="", flush=True)
                        has_function_calls_in_this_turn = True

                if has_function_calls_in_this_turn:
                    model_parts = [types.Part(function_call=fc) for fc in function_calls_to_execute]
                    history.append(types.Content(parts=model_parts, role="model"))

                    tool_responses_parts = []
                    for fc in function_calls_to_execute:
                        function_name = fc.name
                        args = {k: v for k, v in fc.args.items()} # 将 protobuf map 转换为 Python 字典
                        
                        logger.info(f"{MODULE_TAG}模型请求调用工具: {function_name}，参数: {args}")
                        
                        try:
                            tool_result = None
                            # 3. **核心逻辑：判断是本地工具还是远程 MCP 工具**
                            if function_name == "get_transaction_history":
                                logger.info(f"{MODULE_TAG}执行本地工具: get_transaction_history")
                                tool_result = get_transaction_history(**args)
                            elif function_name == "get_time":
                                logger.info(f"{MODULE_TAG}执行本地工具: get_time")
                                tool_result = get_time(**args)
                            elif function_name.startswith("okx_") and mcp_tools_available:
                                # 如果函数名以 "okx_" 开头，并且 MCP 服务器可用，则认为是 OKX MCP 工具
                                logger.info(f"{MODULE_TAG}执行远程 0xAuto OKX MCP 工具: {function_name}")
                                # 通过 MCP 会话异步执行远程函数调用
                                tool_result = await mcp_session.run_tools(fc)
                            elif not mcp_tools_available:
                                error_msg = f"工具 {function_name} 未知或 MCP 服务器不可用。"
                                tool_result = {"error": error_msg}
                                logger.error(f"{MODULE_TAG}{error_msg}")
                            else:
                                # 这是 MCP 服务器可用但找不到匹配的工具的情况
                                error_msg = f"MCP 服务器上工具 {function_name} 未知。"
                                tool_result = {"error": error_msg}
                                logger.error(f"{MODULE_TAG}{error_msg}")

                            tool_responses_parts.append(types.Part(function_response=types.FunctionResponse(name=function_name, response=tool_result)))
                            logger.info(f"{MODULE_TAG}工具 {function_name} 执行完成。结果: {tool_result}")
                        except Exception as e:
                            tb = traceback.format_exc()
                            error_msg = f"执行工具 {function_name} 时发生错误: {e}\n{tb}"
                            tool_responses_parts.append(types.Part(function_response=types.FunctionResponse(name=function_name, response={"error": error_msg})))
                            logger.error(f"{MODULE_TAG}{error_msg}")
                    
                    history.append(types.Content(parts=tool_responses_parts, role="tool"))
                    continue
                elif has_text_in_this_turn:
                    model_text_response = "".join(current_turn_text_chunks)
                    history.append(types.Content(parts=[types.Part(text=model_text_response)], role="model"))
                    final_output_text = model_text_response
                    break
                else:
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

# ===================== 主运行逻辑 (异步化) =====================
async def main(): 
    # 设置代理（如果需要）
    # os.environ['HTTP_PROXY'] = config["proxy"]["http_proxy"]
    # os.environ['HTTPS_PROXY'] = config["proxy"]["https_proxy"]
    
    start_time = time.time()
    
    logger.info(f"{MODULE_TAG}开始本地工具自检...")
    # 保留本地工具的自检
    try:
        logger.info(f"{MODULE_TAG}get_transaction_history 自检结果: {get_transaction_history('ETH-USDT')}")
        logger.info(f"{MODULE_TAG}get_transaction_history 自检完成")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_transaction_history 自检失败: {e}")
    try:
        logger.info(f"{MODULE_TAG}get_time 自检结果: {get_time('当前时间')}")
        logger.info(f"{MODULE_TAG}get_time 自检完成")
    except Exception as e:
        logger.error(f"{MODULE_TAG}get_time 自检失败: {e}")
    logger.info(f"{MODULE_TAG}本地工具自检完成。")


    data_json_path = SYSTEM_JSON_PATH

    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)

    prompt_text = data_json
    logger.info(f"prompt_text 导入完成: {prompt_text}")

    screenshot_path = data_json.get("clipboard_image_path")
    logger.info(f"screenshot_path 导入完成, path:{screenshot_path}")

    system_prompt_path = SYSTEM_PROMPT_PATH
    logger.info(f"system_prompt_path 导入完成, path:{system_prompt_path}")
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    logger.info("开始 Gemini API 流式调用...")
    max_retries = 3
    output_data = None 
    
    for attempt in range(max_retries): 
        try:
            response = await call_gemini_api_stream( 
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
            logger.error(f"Gemini API 调用失败，尝试重试 ({attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1: 
                logger.error("所有重试均已失败。")
                output_data = response # 保存最后一次的原始响应，即使不是JSON
            await asyncio.sleep(2) 

    end_time = time.time()
    logger.info(f"Gemini API 调用完成，耗时: {end_time - start_time} 秒")
    
    try:
        if output_data is not None:
            if isinstance(output_data, dict) or isinstance(output_data, list):
                with open(config["ETH_gemini_answer_path"], "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=4, ensure_ascii=False)
                print(f"已将解析后的输出内容保存到 {config['ETH_gemini_answer_path']}")
            else:
                with open(config["ETH_gemini_answer_path"].replace(".json", ".txt"), "w", encoding="utf-8") as f:
                    f.write(str(output_data)) 
                print(f"响应不是有效的 JSON，已保存为文本文件到 {config['ETH_gemini_answer_path'].replace('.json', '.txt')}")
        else:
            logger.error("未获取到有效的 Gemini 响应数据。")

    except json.JSONDecodeError as e:
        logger.error(f"无法将 Gemini 响应解析为 JSON (保存前): {e}")
        logger.error(f"原始响应内容 (尝试解析前):\n{response}")
        with open(config["ETH_gemini_answer_path"].replace(".json", ".txt"), "w", encoding="utf-8") as f:
            f.write(str(output_data)) 
        print(f"响应不是有效的 JSON，已保存为文本文件到 {config['ETH_gemini_answer_path'].replace('.json', '.txt')}")
    except Exception as e:
        logger.error(f"保存文件时发生未知错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())