# gemini_trade_advisor.py
"""
调用 Gemini 多模态 API，根据 K 线图片和宏观因子 JSON，返回结构化交易建议。
"""
import os
import json
from PIL import Image
import google.generativeai as genai
from google.generativeai import types as genai_types
from datetime import datetime
# from code.system_prompt_config import SYSTEM_INSTRUCTION

def load_image(image_path):
    """加载图片为 Gemini API 可用格式"""
    return Image.open(image_path)

def build_prompt_from_json(info_json):
    """
    将 GUI 整合的 json 信息转为 Gemini 所需的文本 prompt
    """
    # 主要字段示例：标的、周期、情绪、持仓、指标等
    text_lines = []
    if 'symbol' in info_json:
        text_lines.append(f"标的：{info_json['symbol']}")
    if 'period' in info_json:
        text_lines.append(f"周期：{info_json['period']}")
    if 'market_sentiment' in info_json:
        text_lines.append(f"市场情绪：{info_json['market_sentiment']}")
    if 'funding_rate' in info_json:
        text_lines.append(f"Funding Rate：{info_json['funding_rate']}")
    if 'open_interest' in info_json:
        text_lines.append(f"Open Interest：{info_json['open_interest']}")
    if 'volmex_iv' in info_json:
        text_lines.append(f"Volmex IV：{info_json['volmex_iv']}")
    # 持仓信息
    if info_json.get('is_empty'):
        text_lines.append("当前持仓：无")
    else:
        pos_dir = info_json.get('direction', '')
        pos_amt = info_json.get('position_amount', '')
        open_price = info_json.get('open_price', '')
        if pos_dir and open_price:
            text_lines.append(f"当前持仓：{pos_dir}单 {pos_amt}，入场价 {open_price}")
    # 其它补充
    if 'macro_factors' in info_json:
        text_lines.append(f"宏观因子：{info_json['macro_factors']}")
    if 'script_output' in info_json:
        text_lines.append(f"脚本输出：{info_json['script_output']}")
    return '\n'.join(text_lines)

def call_gemini_advisor(image_path, info_json, api_key):
    """
    主函数：调用 Gemini API，返回结构化交易建议
    :param image_path: K线图片路径
    :param info_json: GUI 整合的 json 信息
    :param api_key: Gemini API Key
    :return: Gemini 返回的 JSON 交易建议
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model="gemini-2.5-pro-preview-0514",  # 使用 Gemini 2.5 Pro Preview 05-14
        system_instruction=SYSTEM_INSTRUCTION
    )
    # 构造 prompt
    prompt_text = build_prompt_from_json(info_json)
    img = load_image(image_path)
    # 调用 Gemini
    response = model.generate_content([
        genai_types.content.ContentPart.text(prompt_text),
        genai_types.content.ContentPart.image(img)
    ],
    generation_config=genai_types.GenerationConfig(temperature=0.0, top_p=1.0, top_k=1, max_output_tokens=2048))
    # 解析 Gemini 返回
    try:
        # Gemini 返回的内容通常为 markdown/code block，需提取 JSON
        import re
        match = re.search(r'```json\\s*(.*?)\\s*```', response.text, re.DOTALL)
        if match:
            result_json = json.loads(match.group(1))
        else:
            # 兼容无 code block 的情况
            result_json = json.loads(response.text)
    except Exception as e:
        result_json = {"error": f"Gemini返回解析失败: {e}", "raw": response.text}
    return result_json

def classify_and_output_advice(result_json):
    """
    按类别整理 Gemini 返回的建议，便于 GUI 展示
    """
    categories = [
        "short_term_reason", "mid_term_reason", "long_term_reason",
        "vp_analysis", "volume_analysis", "price_action", "summary",
        "entry_condition", "stop_loss", "take_profit", "risk_management",
        "position_action", "MARKET", "operation"
    ]
    output = {}
    for cat in categories:
        if cat in result_json:
            output[cat] = result_json[cat]
    # 其它未分类信息
    for k, v in result_json.items():
        if k not in output:
            output[k] = v
    return output

# 示例用法：
if __name__ == "__main__":
    # 假设 GUI 已整合好 info_json，图片路径 image_path
    api_key = "AIzaSyAQmyHLrT__85RHFxvuwDWETk-adOmLv-k"  # 直接写入你的API Key
    image_path = "./test_kline.png"
    with open("./test_info.json", "r", encoding="utf-8") as f:
        info_json = json.load(f)
    result = call_gemini_advisor(image_path, info_json, api_key)
    output = classify_and_output_advice(result)
    print(json.dumps(output, ensure_ascii=False, indent=2))
