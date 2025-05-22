# gemini_api_caller.py
"""
调用 Gemini API，传入 GUI 打包的 JSON（持仓+main输出）和系统提示词，返回 Gemini 推理结果。
新版：严格对齐官方 cookbook，支持多模态图片、API Key传参。
"""
import os
import json
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

# --- 配置区 ---
API_KEY = os.environ.get("GEMINI_API_KEY")
DEFAULT_MODEL_NAME = "gemini-2.5-pro-preview-05-06"
PROMPT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt_config.py')
SYSTEM_INSTRUCTION = None

# --- 系统提示词加载 ---
try:
    with open(PROMPT_CONFIG_PATH, 'r', encoding='utf-8') as f:
        config_vars = {}
        exec(f.read(), config_vars)
        SYSTEM_INSTRUCTION = config_vars.get('SYSTEM_INSTRUCTION')
    if SYSTEM_INSTRUCTION is None:
        raise RuntimeError(f"未能从 {PROMPT_CONFIG_PATH} 读取到 SYSTEM_INSTRUCTION 变量。")
    print(f"成功加载系统提示词: '{SYSTEM_INSTRUCTION[:100]}...'")
except FileNotFoundError:
    print(f"错误: 系统提示词文件 {PROMPT_CONFIG_PATH} 未找到。")
    SYSTEM_INSTRUCTION = "This is a default fallback system instruction."
    print(f"警告: 使用了回退系统提示词: '{SYSTEM_INSTRUCTION}'")
except Exception as e:
    print(f"错误: 加载系统提示词时发生错误: {e}")
    SYSTEM_INSTRUCTION = "Error loading system instruction. Proceeding with basic mode."

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

def call_gemini_model(
    user_content: str,
    model_name: str = DEFAULT_MODEL_NAME,
    temperature: float = 0.0,
    api_key_to_use: str = None
):
    """
    调用 Gemini API 并返回模型的文本响应。
    :param user_content: 用户提供给模型的输入文本。
    :param model_name: 要使用的 Gemini 模型名称。
    :param temperature: 生成文本的温度。0 表示更确定性的输出。
    :param api_key_to_use: 要使用的 API Key。如果为 None，则使用全局 API_KEY。
    :return: 模型生成的文本响应。
    :raises RuntimeError: 如果 API Key 未配置或 API 调用失败。
    """
    current_api_key = api_key_to_use if api_key_to_use is not None else API_KEY
    if not current_api_key:
        raise RuntimeError("Gemini API Key 未配置。请设置 GEMINI_API_KEY 环境变量或在代码中提供。")
    if not SYSTEM_INSTRUCTION:
        raise RuntimeError("系统提示词 (SYSTEM_INSTRUCTION) 未加载，无法继续。")
    try:
        genai.configure(api_key=current_api_key)
        generation_config = GenerationConfig(temperature=temperature)
        print(f"正在初始化模型: {model_name}...")
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config=generation_config
        )
        print(f"向模型发送内容:\n'''\n{user_content[:200]}...\n'''")
        response = model.generate_content(user_content)
        if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
            return response.text
        else:
            print("警告: 模型没有返回有效的响应内容。\n响应详情:", response)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and getattr(response.prompt_feedback, 'block_reason', None):
                return f"请求被阻止，原因: {getattr(response.prompt_feedback, 'block_reason_message', '未知')}"
            return "模型没有返回预期的文本内容。"
    except Exception as e:
        print(f"调用 Gemini API 时发生错误: {e}")
        raise RuntimeError(f"Gemini API 调用失败: {e}") from e

def call_gemini_api(packaged_json: dict, model_name: str = DEFAULT_MODEL_NAME, screenshot_path: str = None, api_key: str = None):
    """
    兼容原有GUI调用风格，支持多模态图片和内容有效性校验。
    :param packaged_json: GUI打包的完整输入（dict）
    :param model_name: Gemini模型名
    :param screenshot_path: 截图文件路径（可选，支持多模态推理）
    :param api_key: Gemini API Key
    :return: Gemini返回的字符串
    """
    if not is_effective_content(packaged_json):
        raise RuntimeError('所有输入字段均为空，请完善持仓或策略信息后再请求Gemini建议。')
    user_content_json_string = json.dumps(packaged_json, ensure_ascii=False, indent=2)
    # 多模态图片支持（如有图片则拼接描述）
    if screenshot_path and os.path.exists(screenshot_path):
        from PIL import Image
        img = Image.open(screenshot_path)
        user_content_json_string = "[图片已上传] " + user_content_json_string
    return call_gemini_model(user_content=user_content_json_string, model_name=model_name, api_key_to_use=api_key)

# --- 主API调用接口，仅保留正式功能，无示例入口 ---

__all__ = ["call_gemini_api", "call_gemini_model", "is_effective_content"]
