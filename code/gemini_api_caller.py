import logging
import os
import sys
import json
import traceback
import base64

# ===================== 全局配置与初始化 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "../gemini_quant.log")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuant")
MODULE_TAG = "[gemini_api_caller] "

# 推荐用 GEMINI_API_KEY 作为环境变量名
API_KEY = os.environ.get("GEMINI_API_KEY")
# 推荐Gemini模型名
DEFAULT_MODEL_NAME = "gemini-2.5-flash-preview-05-20"
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
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_THINKING_BUDGET = 24576
DEFAULT_INCLUDE_THOUGHTS = True

# ===================== Gemini API 调用主模块 =====================

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError("未找到 openai 库，请先运行 'pip install openai' 安装依赖。") from e


def build_messages(prompt_text, screenshot_path=None, system_prompt=None):
    """
    构造符合OpenAI兼容API的messages结构。
    - content字段：无图片时为字符串，有图片时为list（text+image_url）
    - role: 支持 system 和 user
    - 若prompt_text为空，自动填充默认内容，避免API 400错误
    - 支持自定义system_prompt
    """
    messages = []
    sys_prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT

    # Gemini's OpenAI compatibility supports a dedicated 'system' role
    if sys_prompt:
        messages.append({"role": "system", "content": sys_prompt.strip()})

    if not prompt_text or (isinstance(prompt_text, str) and not prompt_text.strip()):
        prompt_text = "请分析当前市场趋势"

    user_content_parts = []
    user_content_parts.append({"type": "text", "text": prompt_text})

    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        # Ensure correct image format for Gemini (jpeg, png, webp, heic, heif)
        user_content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})

    # If there's only text and no screenshot, send content as a string, otherwise as a list of parts
    messages.append({"role": "user", "content": user_content_parts if len(user_content_parts) > 1 or screenshot_path else prompt_text})
    return messages

def call_gemini_api_stream(
    prompt_text, # Directly accept prompt_text
    screenshot_path=None,
    model_name=None,
    system_prompt=None,
    enable_reasoning=True, # 此参数现在将通过 reasoning_effort 起作用
    reasoning_effort=None, # 此参数会直接传递
    api_key=None
):
    """
    流式调用 Gemini API，支持文本+图片输入。
    每次调用都是新的对话（无历史上下文）。
    新增参数：
        enable_reasoning: 是否开启深度思考链路 (通过 reasoning_effort 控制)
        reasoning_effort: Gemini 的思考强度 ("low", "medium", "high", "none")
        api_key: 可选，优先使用传入的API KEY
    """
    try:
        _api_key = api_key or API_KEY
        if not _api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY")
        
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
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        messages = build_messages(prompt_text, screenshot_path, system_prompt=system_prompt)
        
        chat_params = {
            "model": model_name or DEFAULT_MODEL_NAME,
            "messages": messages,
            "stream": True,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        }

        # 根据文档，reasoning_effort 是直接的参数
        if enable_reasoning:
            chat_params["reasoning_effort"] = reasoning_effort or DEFAULT_REASONING_EFFORT
        
        stream = client.chat.completions.create(**chat_params)

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Gemini API调用异常: {e}\n{tb}")
        yield f"[Gemini API调用异常] {e}\nTraceback:\n{tb}"
__all__ = ["call_gemini_api_stream"]

if __name__ == "__main__":
    # 示例main函数：只调用Gemini API流式接口并打印结果
    # 请将 "YOUR_GEMINI_API_KEY" 替换为您的实际Gemini API KEY
    os.environ["GEMINI_API_KEY"] = "AIzaSyCkBZzYyaSvLzHRWGEsoabZbyNzlvAxa98" # 替换成您真实的API Key
    API_KEY = os.environ.get("GEMINI_API_KEY")

    # ==========================================================
    # >>>>> 在这里添加代理设置 <<<<<
    # 请根据您的Clash配置修改端口号。
    # 如果Clash提供HTTP代理，推荐使用HTTP代理。
    # 如果是混合端口，则两者都设置为该端口。

    # 假设您的Clash HTTP代理端口是 7890
    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

    # 如果您的Clash只提供SOCKS5代理，或者您更倾向于使用SOCKS5，
    # 并且您的Python环境安装了 `socksio` 或 `PySocks` 库，
    # 则可以这样设置（需要先 pip install 'httpx[socks]' 或 pip install 'requests[socks]'）
    # os.environ['ALL_PROXY'] = 'socks5://127.0.0.1:7891' # 假设SOCKS5端口是7891
    # ==========================================================
    
    # 读取 data.json 内容
    data_json_path = os.path.join(BASE_DIR, "data.json")
    # Create a dummy data.json for testing if it doesn't exist
    if not os.path.exists(data_json_path):
        dummy_data = {
            "prompt": "请分析一下这张图片展示的市场趋势。",
            "clipboard_image_path": "dummy_image.png"
        }
        with open(data_json_path, "w", encoding="utf-8") as f:
            json.dump(dummy_data, f, ensure_ascii=False, indent=4)
        # Create a dummy image file for testing
        try:
            from PIL import Image # This import is for creating the dummy image, not for the API call itself
            img = Image.new('RGB', (60, 30), color = 'red')
            img.save("dummy_image.png")
            print("Created dummy data.json and dummy_image.png for testing.")
        except ImportError:
            print("Pillow (PIL) not found. Cannot create dummy image. Please install it with 'pip install Pillow' if you want to test image functionality.")
            print("Or manually create a 'dummy_image.png' file.")


    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)
    
    # 获取 prompt_text 和图片路径
    prompt_text = data_json.get("prompt", "请分析当前市场趋势。")
    screenshot_path = data_json.get("clipboard_image_path")
    
    # 读取 system_prompt_config.txt 内容
    system_prompt_path = os.path.join(BASE_DIR, "system_prompt_config.txt")
    # Create a dummy system_prompt_config.txt if it doesn't exist
    if not os.path.exists(system_prompt_path):
        with open(system_prompt_path, "w", encoding="utf-8") as f:
            f.write("你是一个专业的市场分析师。")
        print("Created dummy system_prompt_config.txt for testing.")

    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    print("开始测试 Gemini API 流式调用...")
    for text in call_gemini_api_stream(
        prompt_text,
        screenshot_path=screenshot_path,
        system_prompt=system_prompt,
        enable_reasoning=True,
        reasoning_effort="high"
    ):
        print(text, end="", flush=True)
    print("\nGemini API 流式调用结束。")

    # Clean up dummy files if they were created
    if os.path.exists("dummy_image.png"):
        os.remove("dummy_image.png")
    if os.path.exists(data_json_path) and data_json.get("clipboard_image_path") == "dummy_image.png":
        os.remove(data_json_path)
    if os.path.exists(system_prompt_path) and system_prompt == "你是一个专业的市场分析师。":
        os.remove(system_prompt_path)