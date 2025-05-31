import logging
import os
import sys
import json
import traceback
import base64
# ===================== 全局配置与初始化 =====================
# 从config.json中读取配置
with open("/root/codespace/Qwen_quant_v1/config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["BTC_log_path"]
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")



MODULE_TAG = "[gemini_api_caller] "

# 推荐用 GEMINI_API_KEY 作为环境变量名
API_KEY = config["GEMINI_API_KEY"]
# 推荐Gemini模型名
DEFAULT_MODEL_NAME = config["MODEL_NAME"]
SYSTEM_PROMPT_PATH = config["SYSTEM_PROMPT_PATH"]
SYSTEM_PROMPT = ""

SYSTEM_JSON_PATH = config["BTC_data_path"]

if os.path.exists(SYSTEM_PROMPT_PATH):
    with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
    if not SYSTEM_PROMPT:
        logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {SYSTEM_PROMPT_PATH}.")
else:
    logger.warning(f"{MODULE_TAG}系统提示词文件未找到: {SYSTEM_PROMPT_PATH}. SYSTEM_PROMPT 将为空。")


# ===================== 全局配置与初始化 END =====================

# 从config.json中读取配置   
with open("/root/codespace/Qwen_quant_v1/config/config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

DEFAULT_TEMPERATURE = config["MODEL_CONFIG"]["default_temperature"]
DEFAULT_TOP_P = config["MODEL_CONFIG"]["default_top_p"]
DEFAULT_MAX_OUTPUT_TOKENS = config["MODEL_CONFIG"]["default_max_output_tokens"]
DEFAULT_THINKING_BUDGET = config["MODEL_CONFIG"]["default_thinking_budget"]
DEFAULT_INCLUDE_THOUGHTS = config["MODEL_CONFIG"]["default_include_thoughts"]

# ===================== Gemini API 调用主模块 =====================

# try:
#     from openai import OpenAI
# except ImportError as e:
#     raise ImportError("未找到 openai 库，请先运行 'pip install openai' 安装依赖。") from e

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
from google import genai
from google.genai import types
from pydantic import BaseModel

json_schema = open(config["schema_path"], "r", encoding="utf-8").read()
json_schema = json.loads(json_schema)
def call_gemini_api_stream(
    prompt_text, # Directly accept prompt_text
    screenshot_path=None,
    system_prompt=None,
):
    """
    流式调用 Gemini API，支持文本+图片输入。
    每次调用都是新的对话（无历史上下文）。
    新增参数：
        enable_reasoning: 是否开启深度思考链路 (通过 reasoning_effort 控制)
        reasoning_effort: Gemini 的思考强度 ("low", "medium", "high", "none")
        api_key: 可选，优先使用传入的API KEY
    """

    #结构化输出




    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()
    try:
        _api_key =  API_KEY
        if not _api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY")
        
        
        gemini_config = types.GenerateContentConfig(
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            thinking_config={
                "include_thoughts":DEFAULT_INCLUDE_THOUGHTS,
                "thinking_budget":DEFAULT_THINKING_BUDGET,
            },
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=json_schema
        )


        from PIL import Image
        if screenshot_path and os.path.exists(screenshot_path):
            image=Image.open(screenshot_path)

        client = genai.Client(api_key=_api_key)
        

        contents = [
           image,
           prompt_text
        ]
        response = client.models.generate_content_stream(
            model=DEFAULT_MODEL_NAME ,
            contents=contents,
            config=gemini_config
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"{MODULE_TAG}Gemini API调用异常: {e}\n{tb}")
        yield f"[Gemini API调用异常] {e}\nTraceback:\n{tb}"
__all__ = ["call_gemini_api_stream"]

if __name__ == "__main__":

    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'


    data_json_path = SYSTEM_JSON_PATH

    with open(data_json_path, "r", encoding="utf-8") as f:
        data_json = json.load(f)

    prompt_text = json.dumps(data_json, indent=2, ensure_ascii=False)

    #确保prompt_text为[]

    logging.info(f"prompt_text导入完成")
    screenshot_path = data_json.get("clipboard_image_path")
    logging.info(f"screenshot_path导入完成,path:{screenshot_path}")
    system_prompt_path = SYSTEM_PROMPT_PATH
    logging.info(f"system_prompt_path导入完成,path:{system_prompt_path}")
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    logging.info("开始测试 Gemini API 流式调用...")
    output_buffer = []  # 新增：用于收集输出内容

    thinking_config=config["MODEL_CONFIG"]["default_thinking_budget"]
    for text in call_gemini_api_stream(
        prompt_text=prompt_text,
        screenshot_path=screenshot_path,
        system_prompt=system_prompt,
    ):
        print(text, end="", flush=True)
        output_buffer.append(text)  # 新增：收集内容
    print("\nGemini API 流式调用结束。")

    #将test开头的"```json"和结尾的"```"去掉
    output_buffer = [line.strip("```json").strip() for line in output_buffer]
    output_buffer = [line.strip("```").strip() for line in output_buffer]
    output_buffer = "".join(output_buffer)
    #将output_buffer直接写入/root/codespace/Qwen_quant_v1/BTC_code/reply_cache/gemini.json
    with open(config["BTC_gemini_answer_path"], "w", encoding="utf-8") as f:
        f.write(output_buffer)

    print(f"已将输出内容保存到 {config['BTC_gemini_answer_path']}")

    # Clean up dummy files if they were created
