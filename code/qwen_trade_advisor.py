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
    适配新版data.json结构，自动提取关键信息生成Gemini所需prompt。
    """
    text_lines = []
    # 1. 提取主周期（优先15m，其次1h、4h）
    main_tf = None
    for tf in ["15m", "1h", "4h"]:
        if "indicators" in info_json and tf in info_json["indicators"]:
            main_tf = tf
            break
    # 2. 提取symbol、时间戳、主周期指标
    symbol = None
    timestamp = info_json.get("timestamp")
    if main_tf:
        tf_data = info_json["indicators"][main_tf]
        ind = tf_data.get("indicators", {})
        symbol = ind.get("name") or ind.get("ticker")
        text_lines.append(f"主周期: {main_tf}")
        text_lines.append(f"主周期时间: {tf_data.get('timestamp', 'N/A')}")
        text_lines.append(f"主周期收盘价: {ind.get('close', 'N/A')}")
        text_lines.append(f"主周期成交量: {ind.get('volume', 'N/A')}")
        text_lines.append(f"RSI: {ind.get('RSI', 'N/A')}")
        text_lines.append(f"MACD: {ind.get('MACD_macd', 'N/A')}, Signal: {ind.get('MACD_signal', 'N/A')}")
        text_lines.append(f"ATR: {ind.get('ATR', 'N/A')}")
        text_lines.append(f"ADX: {ind.get('ADX', 'N/A')}")
        text_lines.append(f"布林带: 上轨 {ind.get('BB_upper', 'N/A')}, 下轨 {ind.get('BB_lower', 'N/A')}, 中轨 {ind.get('BB_middle', 'N/A')}")
        text_lines.append(f"EMA5: {ind.get('EMA5', 'N/A')}, EMA21: {ind.get('EMA21', 'N/A')}, EMA55: {ind.get('EMA55', 'N/A')}, EMA144: {ind.get('EMA144', 'N/A')}, EMA200: {ind.get('EMA200', 'N/A')}")
        text_lines.append(f"VWAP: {ind.get('VWAP', 'N/A')}")
    if symbol:
        text_lines.insert(0, f"标的: {symbol}")
    if timestamp:
        text_lines.append(f"数据更新时间: {timestamp}")
    # 3. 宏观因子
    if "factors" in info_json and "factors" in info_json["factors"]:
        macro = info_json["factors"]["factors"]
        text_lines.append(f"资金费率: {macro.get('funding_rate', 'N/A')}")
        text_lines.append(f"恐慌贪婪指数: {macro.get('fear_greed_index', 'N/A')}")
        text_lines.append(f"持仓量: {macro.get('open_interest', 'N/A')}")
    # 4. 盘口/最新价
    if "data" in info_json and "data" in info_json["data"] and len(info_json["data"]["data"]) > 0:
        d = info_json["data"]["data"][0]
        text_lines.append(f"最新价: {d.get('last', 'N/A')}，24h高: {d.get('high24h', 'N/A')}，24h低: {d.get('low24h', 'N/A')}")
        text_lines.append(f"买一: {d.get('bidPx', 'N/A')}({d.get('bidSz', 'N/A')})，卖一: {d.get('askPx', 'N/A')}({d.get('askSz', 'N/A')})")
    # 5. 图片路径（如有）
    if "clipboard_image_path" in info_json:
        text_lines.append(f"截图路径: {info_json['clipboard_image_path']}")
    # 6. 其它补充
    for k in ["macro_factors", "script_output"]:
        if k in info_json:
            text_lines.append(f"{k}: {info_json[k]}")
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
