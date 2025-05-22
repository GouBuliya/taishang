# gemini_api_caller.py
"""
调用 Gemini API，传入 GUI 打包的 JSON（持仓+main输出）和系统提示词，返回 Gemini 推理结果。
新版：严格对齐官方 cookbook，支持多模态图片、API Key传参。
"""
import os
import json
import google.generativeai as genai

API_KEY = os.environ.get("GEMINI_API_KEY")
DEFAULT_MODEL_NAME = "models/gemini-2.5-flash-preview-05-20"
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt_config.txt')
with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
    SYSTEM_PROMPT = f.read()

def is_effective_content(d):
    if not isinstance(d, dict):
        return False
    for k, v in d.items():
        if k in ("timestamp",):
            continue
        if isinstance(v, bool):
            continue
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return True
    return False

def call_gemini_api(packaged_json: dict, model_name: str = None, screenshot_path: str = None, api_key: str = None, temperature: float = 0.0):
    # 修正: 若 model_name 为空则用默认模型名
    if not model_name:
        model_name = DEFAULT_MODEL_NAME
    key = api_key if api_key and str(api_key).strip() else API_KEY
    system_instruction = SYSTEM_PROMPT
    if not key:
        raise RuntimeError("Gemini API Key 未配置。请设置 GEMINI_API_KEY 环境变量或在代码中提供。")
    if not is_effective_content(packaged_json):
        raise RuntimeError('所有输入字段均为空，请完善持仓或策略信息后再请求Gemini建议。')
    genai.configure(api_key=key)
    position_info = packaged_json.get('position_info', {})
    main_info = packaged_json.get('main_info', {})
    other_keys = {k: v for k, v in packaged_json.items() if k not in ('position_info', 'main_info')}
    if (not position_info or position_info.get('is_empty') is True):
        merged_content = {
            "main_info": main_info,
            **other_keys
        }
    else:
        merged_content = {
            "position_info": position_info,
            "main_info": main_info,
            **other_keys
        }
    user_content = "图片周期为：M15\n" + json.dumps(merged_content, ensure_ascii=False, indent=2)
    contents = []
    if screenshot_path and os.path.exists(screenshot_path):
        from PIL import Image
        img = Image.open(screenshot_path)
        contents.append(img)
    contents.append(user_content)
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
    try:
        response = model.generate_content(contents, generation_config={"temperature": 0})
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API 调用失败: {e}")

__all__ = ["call_gemini_api", "is_effective_content"]
