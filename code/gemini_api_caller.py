# gemini_api_caller.py
"""
使用gemini-2.5-flash-preview-05-20,
2025-05-25
"""
# Gemini 2.5 Flash API 兼容重构

import logging
import os
import sys
from google import genai
from PIL import Image
import json
import traceback
from google.genai import types as genai_types

try:
    from gemini_trade_advisor import build_prompt_from_json
except ImportError:
    try:
        from .gemini_trade_advisor import build_prompt_from_json
    except ImportError:
        import importlib.util, sys, os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, base_dir)
        spec = importlib.util.spec_from_file_location("gemini_trade_advisor", os.path.join(base_dir, "gemini_trade_advisor.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        build_prompt_from_json = mod.build_prompt_from_json

print("当前Python解释器:", sys.executable)
if hasattr(genai, '__version__'):
    print("google-genai 版本:", genai.__version__)
if hasattr(genai, '__file__'):
    print("google-genai 路径:", genai.__file__)

# ===================== 全局配置与初始化 =====================
# BASE_DIR: 当前脚本所在目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# LOG_FILE: 日志文件路径，所有日志将写入该文件
LOG_FILE = os.path.join(BASE_DIR, "../gemini_quant.log")

# 日志系统配置：INFO 级别，格式包含时间、级别、消息，输出到文件和控制台
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
# logger: 全局日志对象，方便模块内统一日志输出
logger = logging.getLogger("GeminiQuant")
# MODULE_TAG: 日志前缀，标记日志来源
MODULE_TAG = "[gemini_api_caller] "

# API_KEY: 从环境变量读取的 Gemini API 密钥，安全管理
API_KEY = os.environ.get("GEMINI_API_KEY")
# DEFAULT_MODEL_NAME: 默认 Gemini 2.5 Flash 模型名称
DEFAULT_MODEL_NAME = "models/gemini-2.5-flash-preview-05-20"
# SYSTEM_PROMPT_PATH: 系统提示词配置文件路径
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt_config.txt')
# SYSTEM_PROMPT: 读取到的系统提示词内容，影响 AI 推理风格和输出格式
SYSTEM_PROMPT = ""
if os.path.exists(SYSTEM_PROMPT_PATH):
    with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
    if not SYSTEM_PROMPT:
        logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {SYSTEM_PROMPT_PATH}.")
else:
    logger.warning(f"{MODULE_TAG}系统提示词文件未找到: {SYSTEM_PROMPT_PATH}. SYSTEM_PROMPT 将为空。")
# ===================== 全局配置与初始化 END =====================

DEFAULT_TEMPERATURE = 0.0 #温度
DEFAULT_TOP_P = 0.9 # top_p
DEFAULT_MAX_OUTPUT_TOKENS = 24576
# DEFAULT_MAX_THINKINGBUDGET = 24576
# DEFAULT_FREQUENCY_PENALTY = 1.0
# DEFAULT_PRESENCE_PENALTY = 0.2

# ===================== Gemini API 调用主模块 =====================
# 本模块负责：
# 1. 读取系统提示词（system_prompt_config.txt），配置全局参数
# 2. 提供 Gemini 2.5 Flash API 的同步与流式推理调用接口
# 3. 支持多模态输入（图片+文本），并自动处理 API Key
# 4. 日志记录与异常处理，保证链路健壮性
# 5. 供 Web/GUI/Telegram Bot 等多端统一调用

# 主要全局变量说明：
# - API_KEY: 从环境变量读取的 Gemini API 密钥，安全管理
# - DEFAULT_MODEL_NAME: 默认 Gemini 2.5 Flash 模型名称
# - SYSTEM_PROMPT: 系统级提示词，影响 AI 推理风格和输出格式
# - 日志配置: 统一输出到 gemini_quant.log，便于调试和追溯
# - 其它推理参数: temperature, top_p, max_output_tokens 等

# 主要函数说明：
# is_effective_content(d):
#   检查输入的字典是否包含有效内容，决定是否需要调用API。
#   典型用法：避免无效/空数据触发API调用，提升健壮性。

#
# call_gemini_api_stream(...):
#   流式调用 Gemini 2.5 Flash API，逐步 yield 内容块，支持降级为同步分块输出。
#   典型用法：Web端/GUI端实现流式输出体验。
#
# get_configured_model(...):
#   返回已配置好 API Key 和 system_instruction 的 GenerativeModel 实例。
#   典型用法：如需自定义模型或高级用法时直接获取模型对象。
#
# 所有函数均支持异常处理和日志输出，便于生产环境排查。

# 2.5 flash: API Key 需在每次创建 GenerativeModel 时传递


def call_gemini_api_stream(packaged_json, screenshot_path=None, api_key=None, model_name=None):
    """
    流式调用 Gemini 2.5 Flash API，支持文本+图片输入。
    采用完全单轮对话模式，每次调用都是独立的，不保存任何对话历史。
    每个请求只发送一条用户消息，得到一个AI响应。
    
    :param packaged_json: dict，主数据内容
    :param screenshot_path: str，图片路径，可为None
    :param api_key: str，API Key，优先级高于环境变量
    :param model_name: str，模型名，优先级高于默认
    :yield: str，每次推理返回的文本块
    """
    try:
        # 0. 检查packaged_json内容
        logger.info(f"{MODULE_TAG}收到packaged_json类型: {type(packaged_json)}, 内容预览: {str(packaged_json)[:500]}")
        if not packaged_json or not isinstance(packaged_json, dict):
            logger.error(f"{MODULE_TAG}packaged_json为空或类型错误: {type(packaged_json)}")
            yield "[错误] packaged_json为空或类型错误，无法生成prompt。"
            return
        # 1. 配置API Key
        _api_key = api_key or API_KEY
        if not _api_key:
            raise RuntimeError("未配置Gemini API Key")
        client = genai.Client(api_key=_api_key)

        # 2. 构造单轮查询内容
        prompt_text = build_prompt_from_json(packaged_json)
        logger.info(f"{MODULE_TAG}最终发送给AI的prompt_text: {prompt_text[:500]}")  # 只打印前500字防止刷屏
        parts = [genai_types.Part.from_text(text=prompt_text)]
        
        # 3. 添加图片（如果有）
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                img = Image.open(screenshot_path)
                img.verify()  # 检查图片有效性
                img = Image.open(screenshot_path).convert("RGB")  # 重新打开并转为RGB
                parts.append(genai_types.Part.from_image(image=img))
                logger.info(f"{MODULE_TAG}图片路径: {screenshot_path} 已成功加载并转为RGB")
            except Exception as e:
                logger.warning(f"{MODULE_TAG}图片加载失败: {e}，图片路径: {screenshot_path}")
        else:
            logger.info(f"{MODULE_TAG}未传递图片或图片不存在，screenshot_path={screenshot_path}")
        
        # 4. 构造单轮请求
        content = genai_types.Content(role='user', parts=parts)
        
        # 5. 配置参数并调用API
        config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS
            
        )
        
        response = client.models.generate_content_stream(
            model=model_name or DEFAULT_MODEL_NAME,
            config=config,
            contents=[content]  # 只发送单轮内容
        )
        
        # 6. 流式返回结果
        for chunk in response:
            if hasattr(chunk, "text") and chunk.text:
                yield chunk.text
        
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Gemini API调用异常: {e}\n{tb}")
        yield f"[Gemini API调用异常] {e}\nTraceback:\n{tb}"

def get_configured_model(model_name_str=None, system_instruction_text=None, api_key=None):
    """返回已配置好 API Key 和 system_instruction 的 GenerativeModel 实例"""
    _api_key = api_key or API_KEY
    if not _api_key:
        raise RuntimeError("未配置Gemini API Key")
    _model_name = model_name_str or DEFAULT_MODEL_NAME
    _sys_inst = system_instruction_text or SYSTEM_PROMPT
    client = genai.Client(api_key=_api_key)
    return client.models.get(_model_name, system_instruction=_sys_inst)

# is_effective_content 函数在您提供的代码中没有定义，如果需要，请根据您的业务逻辑添加
# def is_effective_content(d):
#     """检查输入的字典是否包含有效内容，决定是否需要调用API。"""
#     # 示例实现，请根据实际需求调整
#     return bool(d) and any(d.values())

__all__ = ["call_gemini_api_stream", "get_configured_model"] 

if __name__ == "__main__":
    # 这是一个简单的测试用例，您需要根据实际情况传入 packaged_json 和 screenshot_path
    # 例如：
    # test_json = {"user_query": "分析一下当前市场趋势"}
    # test_screenshot_path = "/path/to/your/screenshot.png" # 如果没有图片，可以设置为 None
    #
    # print("开始测试 Gemini API 流式调用...")
    # try:
    #     # 注意：这里的测试调用会直接打印流式结果，而不是累积
    #     for chunk in call_gemini_api_stream(test_json, screenshot_path=test_screenshot_path):
    #         print(chunk, end='') # 使用 end='' 避免额外换行
    #     print("\n\nGemini API 响应结束。")
    # except Exception as e:
    #     print(f"测试调用失败: {e}")
    
    print("请在 __main__ 块中提供测试参数，例如 call_gemini_api_stream({'query': 'hello'}, None)")