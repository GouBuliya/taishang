# qwen_api_caller.py
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
DEFAULT_MODEL_NAME = "qvq-max"   # 可根据实际Qwen模型名调整
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
DEFAULT_MAX_OUTPUT_TOKENS = 24576

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
    - 强化user prompt，拼接markdown输出格式模板，强制AI严格按格式输出
    - 直接将系统提示词文本拼接到user prompt最前面，确保大模型一定接收到
    """
    messages = []
    sys_prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    # 直接拼接system prompt到user prompt最前面
    if not prompt_text or (isinstance(prompt_text, str) and not prompt_text.strip()):
        prompt_text = "请分析当前市场趋势"
    # 拼接markdown格式模板
    markdown_format = """请严格仅用如下markdown格式输出（所有英文内容请翻译为中文，所有字段都必须有值，无数据请输出N/A）：\n\n## 标的：{symbol}\n#### 主周期：{timeframe}\n#### 当前时间：{timestamp}\n#### 市场状态：{MARKET}\n<!-- 重要 输出的所有的英文文本信息都要翻译成中文-->
#### 交易策略：\n{operation.strategy}\n#### 量化特征值：\n{quant_features_output}\n#### 量化特征值分析：\n##### 低阶反思：\n- 短期分析：{short_term_reason}\n- 中期分析：{mid_term_reason}\n- 长期分析：{long_term_reason}\n- 成交量分布分析：{vp_analysis}\n- 成交量分析：{volume_analysis}\n- 价格行为分析：{price_action}\n- 指标分析：{indicators_analysis}\n##### 高级策略：\n{summary}\n- 入场条件：{entry_condition}\n- 止损价：{stop_loss}\n- 止盈目标：{take_profit}\n- 风险管理：{risk_management}\n- 持仓操作：{position_action}\n#### 胜率与期望收益计算：\n- 胜率：{operation.expected_winrate}\n- 期望收益：{operation.expected_return}\n---\n$$\\boxed{{\\begin{{aligned}}&\\underbrace{{z}}_{{\\text{{对数几率}}}}\\;=\\; w_0 \\;+\\; \\sum_{{i=1}}^{{n}} w_i X_i, \\[6pt] &\\underbrace{{p}}_{{\\text{{胜率}}}}\\;=\\;\\sigma(z)\\;=\\;\\frac{{1}}{{1 + e^{{-z}}}}, \\[6pt] &\\underbrace{{\\mathbb{{E}}[R]}}_{{\\text{{期望收益}}}}\\;=\\; p \\times \\underbrace{{\\biggl(\\frac{{\\mathrm{{TP}}-\\mathrm{{Entry}}}}{{\\mathrm{{Entry}}}}\\biggr)}}_{{R_{{gain}}}}\\;- (1-p)\\times \\underbrace{{\\biggl(\\frac{{\\mathrm{{Entry}}-\\mathrm{{SL}}}}{{\\mathrm{{Entry}}}}\\biggr)}}_{{R_{{loss}}}}.\\end{{aligned}}}}$$ \n---\n% > 注意：公式中的 Entry、SL、TP 等为变量，实际输出时请用具体数值替换。\n- 胜率公式：$p=\\sigma(z)=\\frac{{1}}{{1+e^{{-z}}}}$\n- 期望收益公式：$\\mathbb{{E}}[R]=p\\cdot R_{{gain}} - (1-p)\\cdot R_{{loss}}$\n#### 自检与一致性校验：\n- 检查结果：{self_check}\n- 内部协调：{internal_coordination}\n- 逻辑验证：{logic_validation}\n- 合理性验证：{rationality_validation}\n#### 数据整理：\n- 数据格式：{data_format}\n- 数据完整性：{data_integrity}  \n#### 数据来源：\n{data_source}\n#### 交易操作：\n{operation.comment}\n- 操作类型：{operation.type}\n- 挂单价：{operation.price}\n- 止损价：{operation.stop_loss}\n- 止盈目标：{operation.take_profit}\n- 仓位大小：{operation.size}\n- 预计胜率：{operation.expected_winrate}\n- 期望收益：{operation.expected_return}\n- 风险收益比：{operation.trade_RR_ratio}\n- AI信心度：{operation.confidence}\n- 信号强度：{operation.signal_strength}\n- 风险评估：{risk_assessment}\n"""
    # 拼接system prompt和markdown模板到user prompt
    user_prompt = f"{sys_prompt.strip() if sys_prompt else ''}\n\n{prompt_text}\n\n{markdown_format}"
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

def call_qwen_api(
    packaged_json, 
    screenshot_path=None, 
    model_name=None, 
    system_prompt=None,
    enable_thinking=False,
    enable_search=False,
    search_options=None,
    api_key=None
):
    """
    同步调用 Qwen API，返回完整回复。
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
        client = OpenAI(
            api_key=_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        messages = build_messages(prompt_text, screenshot_path, system_prompt=system_prompt)
        # 构造额外参数
        extra_body = {}
        if enable_thinking:
            extra_body["enable_thinking"] = True
        if enable_search:
            extra_body["enable_search"] = True
        if search_options:
            extra_body["search_options"] = search_options
        response = client.chat.completions.create(
            model=model_name or DEFAULT_MODEL_NAME,
            messages=messages,
            temperature=0.0,
            extra_body=extra_body if extra_body else None
        )
        # 支持 reasoning_content 输出
        if hasattr(response.choices[0].message, "reasoning_content") and response.choices[0].message.reasoning_content:
            return {
                "reasoning_content": response.choices[0].message.reasoning_content,
                "content": response.choices[0].message.content
            }
        return response.choices[0].message.content
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Qwen API调用异常: {e}\n{tb}")
        return f"[Qwen API调用异常] {e}\nTraceback:\n{tb}"

def call_qwen_api_stream(
    packaged_json, 
    screenshot_path=None, 
    model_name=None, 
    system_prompt=None,
    enable_thinking=False,
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
        client = OpenAI(
            api_key=_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        messages = build_messages(prompt_text, screenshot_path, system_prompt=system_prompt)
        extra_body = {}
        if enable_thinking:
            extra_body["enable_thinking"] = True
        if enable_search:
            extra_body["enable_search"] = True
        if search_options:
            extra_body["search_options"] = search_options
        stream = client.chat.completions.create(
            model=model_name or DEFAULT_MODEL_NAME,
            messages=messages,
            stream=True,
            temperature=0.0,
            extra_body=extra_body if extra_body else None
        )
        # 修正流式输出逻辑：缓冲reasoning_content，遇到标点（句号、换行、逗号、分号、冒号、问号、叹号）时才yield
        buffer = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    buffer += delta.reasoning_content
                    # 判断是否遇到分句标点
                    while True:
                        # 查找第一个分句标点
                        import re
                        m = re.search(r'[。！？；,，\n]', buffer)
                        if m:
                            idx = m.end()
                            to_yield = buffer[:idx]
                            buffer = buffer[idx:]
                            yield {"reasoning_content": to_yield}
                        else:
                            break
                if hasattr(delta, "content") and delta.content:
                    yield {"content": delta.content}
        # 最后还有残留buffer也输出
        if buffer:
            yield {"reasoning_content": buffer}
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Qwen API调用异常: {e}\n{tb}")
        yield f"[Qwen API调用异常] {e}\nTraceback:\n{tb}"

__all__ = ["call_qwen_api_stream", "call_qwen_api"]

if __name__ == "__main__":
    # 示例main函数：直接调用Qwen API并打印结果
    os.environ["QWEN_API_KEY"] = "sk-2f17c724d71e448fac1b20ac1c8e09db"  # 硬编码API KEY
    API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")  # 立即刷新全局变量
    # 读取 data.json 内容
    data_json_path = os.path.join(BASE_DIR, "get_data/data.json")
    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)
    # 获取图片路径
    screenshot_path = data_json.get("clipboard_image_path")
    # 读取 system_prompt_config.txt 内容
    system_prompt_path = os.path.join(BASE_DIR, "system_prompt_config.txt")
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()
    # 直接将 data.json 作为 content 传递
    prompt_text = json.dumps(data_json, ensure_ascii=False, indent=2)
    messages = build_messages(prompt_text, screenshot_path, system_prompt=system_prompt)
    print("最终messages结构:")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    print("开始测试 Qwen API 同步调用...")
    reply = call_qwen_api(data_json, screenshot_path=screenshot_path, system_prompt=system_prompt)
    print("同步调用结果：")
    print(reply)
    print("\n开始测试 Qwen API 流式调用...")
    for chunk in call_qwen_api_stream(data_json, screenshot_path=screenshot_path, system_prompt=system_prompt):
        print(chunk, end='')
    print("\nQwen API 流式调用结束。")