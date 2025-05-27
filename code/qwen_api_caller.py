"""
使用qwen
2025-05-25
"""

import logging
import os
import sys
import json
import traceback
from PIL import Image

try:
    from qwen_trade_advisor import build_prompt_from_json
except ImportError:
    try:
        from .qwen_trade_advisor import build_prompt_from_json
    except ImportError:
        import importlib.util, sys, os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, base_dir)
        spec = importlib.util.spec_from_file_location("qwen_trade_advisor", os.path.join(base_dir, "qwen_trade_advisor.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        build_prompt_from_json = mod.build_prompt_from_json

# ===================== 全局配置与初始化 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "../qwen_quant.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("QwenQuant")
MODULE_TAG = "[qwen_api_caller] "

# 3. 推荐用 DASHSCOPE_API_KEY 作为环境变量名（兼容官方文档）
API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
# 官方推荐Qwen3系列模型名，支持深度思考链路
DEFAULT_MODEL_NAME = "qwen-max"  # 强烈建议用官方推荐模型
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt_config.txt')
SYSTEM_PROMPT = ""
if os.path.exists(SYSTEM_PROMPT_PATH):
    with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
    if not SYSTEM_PROMPT:
        logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {SYSTEM_PROMPT_PATH}.")
else:
    logger.warning(f"{MODULE_TAG}系统提示词文件未找到: {SYSTEM_PROMPT_PATH}. SYSTEM_PROMPT 将为空。")
# ===================== 全局配置与初始化 END =====================

DEFAULT_TEMPERATURE = 0.0
DEFAULT_TOP_P = 0.9
DEFAULT_MAX_OUTPUT_TOKENS = 8192  # 百炼Plus/Max支持的最大输出Token数（官方当前上限8192）
DEFAULT_THINKING_BUDGET = 5  # 百炼API支持的最高思考预算为5

# ===================== qwen API 调用主模块 =====================
# 适配qwen的API调用，假设有qwen官方SDK或API HTTP接口

from openai import OpenAI
import base64

def build_messages(prompt_text, screenshot_path=None, system_prompt=None):
    """
    构造符合OpenAI兼容API的messages结构。
    - content字段：无图片时为字符串，有图片时为list（text+image_url）
    - role必须为user
    - 若prompt_text为空，自动填充默认内容，避免API 400错误
    - 支持自定义system_prompt
    - 直接将系统提示词文本拼接到user prompt最前面，确保大模型一定接收到
    """
    messages = []
    sys_prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    # 直接拼接system prompt到user prompt最前面
    if not prompt_text or (isinstance(prompt_text, str) and not prompt_text.strip()):
        prompt_text = "请分析当前市场趋势"
    # 只拼接 system prompt 和原始 prompt_text，不再拼接 markdown 模板
    user_prompt = f"{sys_prompt.strip() if sys_prompt else ''}\n\n{prompt_text}\n/think"
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        user_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
        ]
    else:
        user_content = user_prompt
    messages.append({"role": "user", "content": user_content})
    return messages

def call_qwen_api_stream(
    packaged_json, 
    screenshot_path=None, 
    model_name=None, 
    system_prompt=None,
    enable_thinking=True,  # 默认始终开启思考模式
    enable_search=False,
    search_options=None,
    api_key=None
):
    """
    流式调用 Qwen API，支持文本+图片输入。
    每次调用都是新的对话（无历史上下文）。
    新增参数：
        enable_thinking: 是否开启深度思考链路
        enable_search: 是否开启联网新闻检索
        search_options: dict, 传递给API的检索细节参数
        api_key: 可选，优先使用传入的API KEY
    """
    try:
        _api_key = api_key or API_KEY
        if not _api_key:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY 或 QWEN_API_KEY")
        prompt_text = build_prompt_from_json(packaged_json)
        # --- 热加载 system_prompt_config.txt ---
        if system_prompt is None:
            system_prompt_path = os.path.join(BASE_DIR, "system_prompt_config.txt")
            if os.path.exists(system_prompt_path):
                with open(system_prompt_path, 'r', encoding='utf-8') as f:
                    system_prompt = f.read().strip()
            else:
                system_prompt = ""
        # --- END ---
        client = OpenAI(
            api_key=_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        messages = build_messages(prompt_text, screenshot_path, system_prompt=system_prompt)
        extra_body = {}
        # 强制开启思考模式（无论传参如何，始终生效）
        extra_body["enable_thinking"] = True
        extra_body["thinking_budget"] = DEFAULT_THINKING_BUDGET  # 使用全局默认预算
        if enable_search:
            extra_body["enable_search"] = True
        if search_options:
            extra_body["search_options"] = search_options
        max_tokens = 8192
        stream = client.chat.completions.create(
            model=model_name or DEFAULT_MODEL_NAME,
            messages=messages,
            stream=True,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=max_tokens,
            extra_body=extra_body if extra_body else None
        )
        # 优化：只提取 content 字段中的文本信息
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Qwen API调用异常: {e}\n{tb}")
        yield f"[Qwen API调用异常] {e}\nTraceback:\n{tb}"

__all__ = ["call_qwen_api_stream"]

if __name__ == "__main__":
    # 示例main函数：只调用Qwen API流式接口并打印结果
    os.environ["QWEN_API_KEY"] = "sk-2f17c724d71e448fac1b20ac1c8e09db"  # 替换成你的 API KEY
    API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")  # 立即刷新全局变量
    # 读取 data.json 内容
    data_json_path = os.path.join(BASE_DIR, "data.json")
    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)
    # 获取图片路径
    screenshot_path = data_json.get("clipboard_image_path")
    # 读取 system_prompt_config.txt 内容
    system_prompt_path = os.path.join(BASE_DIR, "system_prompt_config.txt")
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()
    print("开始测试 Qwen API 流式调用...")
    for text in call_qwen_api_stream(data_json, screenshot_path=screenshot_path, system_prompt=system_prompt):
        print(text, end="", flush=True) # 逐字打印，更接近流式效果
    print("\nQwen API 流式调用结束。")