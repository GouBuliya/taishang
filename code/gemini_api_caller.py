# gemini_api_caller.py
"""
调用 Gemini API，传入 GUI 打包的 JSON（持仓+main输出）和系统提示词，返回 Gemini 推理结果。
新版：严格对齐官方 cookbook，支持多模态图片、API Key传参。
"""
import os
import json
import google.generativeai as genai
from google.generativeai import types as genai_types

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

def call_gemini_api(packaged_json: dict, system_instruction: str = None, model_name: str = 'gemini-1.5-pro-preview-0513', screenshot_path: str = None, api_key: str = None):
    """
    :param packaged_json: GUI打包的完整输入（dict）
    :param system_instruction: 系统提示词（str）
    :param model_name: Gemini模型名
    :param screenshot_path: 截图文件路径（可选，支持多模态推理）
    :param api_key: Gemini API Key（可选，优先使用）
    :return: Gemini返回的字符串
    """
    if system_instruction is None:
        system_instruction = SYSTEM_INSTRUCTION
    if api_key is None:
        api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('请先设置环境变量 GEMINI_API_KEY 或传入api_key参数')
    genai.configure(api_key=api_key)

    # 构造多模态输入
    user_parts = []
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, 'rb') as img_f:
            img_bytes = img_f.read()
        user_parts.append(genai_types.Part(inline_data=genai_types.Blob(data=img_bytes, mime_type="image/png")))
    user_parts.append(genai_types.Part(text=json.dumps(packaged_json, ensure_ascii=False, indent=2)))

    # 构造消息
    messages = [
        genai_types.Content(role="system", parts=[genai_types.Part(text=system_instruction)]),
        genai_types.Content(role="user", parts=user_parts)
    ]

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(messages, generation_config=genai_types.GenerationConfig(temperature=0))
    return response.text

if __name__ == '__main__':
    # 示例：从文件读取GUI打包的json
    input_json_path = os.path.join(os.path.dirname(__file__), 'sample_input.json')
    with open(input_json_path, 'r', encoding='utf-8') as f:
        packaged_json = json.load(f)
    result = call_gemini_api(packaged_json)
    print('Gemini回复：\n', result)
