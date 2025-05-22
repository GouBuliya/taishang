# gemini_api_caller.py
"""
调用 Gemini API，传入 GUI 打包的 JSON（持仓+main输出）和系统提示词，返回 Gemini 推理结果。
"""
import os
import json
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import ContentPart

# 读取系统提示词
PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt_config.py')
SYSTEM_INSTRUCTION = None
with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip().startswith('SYSTEM_INSTRUCTION ='):
            SYSTEM_INSTRUCTION = line.split('=',1)[1].strip().strip('"""').strip('"')
            break
if SYSTEM_INSTRUCTION is None:
    raise RuntimeError('未能读取到 SYSTEM_INSTRUCTION')

# Gemini API KEY
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise RuntimeError('请先设置环境变量 GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

# 调用 Gemini

def call_gemini_api(packaged_json: dict, system_instruction: str = None, model_name: str = 'gemini-2.5-pro-preview-05-06', screenshot_path: str = None, api_key: str = None):
    """
    Gemini Cookbook风格重构：
    - 支持文本+图片多模态
    - 兼容系统提示词
    - 兼容API Key传参
    """
    if system_instruction is None:
        system_instruction = SYSTEM_INSTRUCTION
    if api_key is None:
        api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('请先设置环境变量 GEMINI_API_KEY 或传入api_key参数')
    genai.configure(api_key=api_key)
    user_content = json.dumps(packaged_json, ensure_ascii=False, indent=2)
    # 构造parts
    parts = []
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, 'rb') as img_f:
            img_bytes = img_f.read()
        parts.append(ContentPart.image(data=img_bytes, mime_type="image/png"))
    parts.append(ContentPart.text(user_content))
    # 构造messages
    messages = [
        genai.types.Message(role="system", parts=[ContentPart.text(system_instruction)]),
        genai.types.Message(role="user", parts=parts)
    ]
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(messages, generation_config=genai.types.GenerationConfig(temperature=0))
    return response.text

if __name__ == '__main__':
    # 示例：从文件读取GUI打包的json
    input_json_path = os.path.join(os.path.dirname(__file__), 'sample_input.json')
    with open(input_json_path, 'r', encoding='utf-8') as f:
        packaged_json = json.load(f)
    result = call_gemini_api(packaged_json)
    print('Gemini回复：\n', result)
