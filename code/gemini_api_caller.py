# gemini_api_caller.py
"""
调用 Gemini API，传入 GUI 打包的 JSON（持仓+main输出）和系统提示词，返回 Gemini 推理结果。
新版：严格对齐官方 cookbook，支持多模态图片、API Key传参。
"""
import os
import json
import google.generativeai as genai
import logging
import time
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "../gemini_quant.log")

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO, # 设置日志级别为INFO，将记录INFO及以上级别的信息
    format='[%(asctime)s] %(levelname)s %(message)s', # 定义日志输出格式
    datefmt='%Y-%m-%d %H:%M:%S', # 定义时间格式
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("GeminiQuant") # 获取名为"GeminiQuant"的日志记录器实例
MODULE_TAG = "[gemini_api_caller] "

# -------------------- 配置常量 --------------------
API_KEY = os.environ.get("GEMINI_API_KEY") # 从环境变量获取 GEMINI_API_KEY
DEFAULT_MODEL_NAME = "models/gemini-2.5-flash-preview-05-20" # 定义默认的模型名称
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'system_prompt_config.txt') # 构建系统提示词文件的绝对路径
with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
    SYSTEM_PROMPT = f.read() # 读取系统提示词内容到 SYSTEM_PROMPT 变量中

# -------------------- Gemini API参数全局配置 --------------------
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TOP_P = 0.95
# DEFAULT_MAX_OUTPUT_TOKENS = 256
DEFAULT_FREQUENCY_PENALTY = 1.0
DEFAULT_PRESENCE_PENALTY = 0.2

# -------------------- 辅助函数：判断输入内容是否有效 --------------------
def is_effective_content(d):
    """
    检查输入的字典 d 是否包含有效内容，用于判断是否需要调用API。
    如果字典为空、或只包含时间戳、或只包含 is_empty=True 的字段，则认为无效。
    """
    if not isinstance(d, dict): # 如果输入不是字典类型，则认为无效
        return False
    # 遍历字典中的所有键值对
    for k, v in d.items():
        if k in ("timestamp",): # 如果键是 "timestamp"，则跳过（不计入有效内容）
            continue
        # 只跳过 is_empty 且为 True 的情况，这是专门为 position_info.is_empty 设计的逻辑
        if k == "is_empty" and v is True:
            continue
        if v is None: # 如果值是 None，则跳过
            continue
        if isinstance(v, str) and v.strip() == "": # 如果值是空字符串或只包含空白字符，则跳过
            continue
        # 只要找到一个非 timestamp、非 is_empty=True、非 None、非空白字符串的有效字段，就认为内容有效
        return True
    return False # 如果遍历完所有字段都没有找到有效内容，则认为无效

# -------------------- 全局配置 API Key --------------------
# 建议在应用程序启动时只执行一次，避免重复配置。
# 如果 API_KEY 环境变量存在，则进行全局配置。
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logger.warning("GEMINI_API_KEY 环境变量未设置，后续API调用可能需要手动传入api_key参数。")

# -------------------- 主要函数：调用 Gemini API --------------------
def call_gemini_api(
        packaged_json: dict, 
        model_name: str = None,
        screenshot_path: str = None, 
        api_key: str = None,
        temperature: float = DEFAULT_TEMPERATURE, 
        top_p: float = DEFAULT_TOP_P, 
        # max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        frequency_penalty: float = DEFAULT_FREQUENCY_PENALTY, 
        presence_penalty: float = DEFAULT_PRESENCE_PENALTY):
    """
    调用 Gemini API 进行内容生成。
    Args:
        packaged_json (dict): 包含持仓信息、主信息等的用户输入 JSON 数据。
        model_name (str): 要使用的模型名称，默认为 DEFAULT_MODEL_NAME。
        screenshot_path (str): K线图截图文件路径。
        api_key (str): 可选的 API Key，如果传入则覆盖环境变量设置。
        temperature (float): 生成温度，控制随机性。
        top_p (float): top_p 参数，控制多样性。
        max_output_tokens (int): 最大输出词元数。
        frequency_penalty (float): 频率惩罚。
        presence_penalty (float): 存在惩罚。
    Returns:
        str: Gemini 模型生成的文本结果。
    Raises:
        RuntimeError: API Key 未配置，或输入内容无效，或API调用失败，或返回空内容。
    """
    if not model_name: # 如果没有指定模型名称，则使用默认模型
        model_name = DEFAULT_MODEL_NAME
    logger.info(MODULE_TAG + f"实际使用的 model_name: {model_name}") # 记录实际使用的模型名称

    key = api_key if api_key and str(api_key).strip() else API_KEY # 确定最终使用的 API Key：优先函数参数，其次环境变量
    logger.info(MODULE_TAG + f"实际使用的 api_key: {'已设置' if key else '未设置'}") # 记录 API Key 是否已设置
    system_instruction = SYSTEM_PROMPT # 获取系统提示词内容
    logger.info(MODULE_TAG + f"system_instruction 长度: {len(system_instruction) if system_instruction else 0}") # 记录系统提示词长度

    if not key: # 如果 API Key 未设置，则抛出运行时错误
        logger.error(MODULE_TAG + "Gemini API Key 未配置。请设置 GEMINI_API_KEY 环境变量或在代码中提供。")
        raise RuntimeError("Gemini API Key 未配置。请设置 GEMINI_API_KEY 环境变量或在代码中提供。")

    if not is_effective_content(packaged_json): # 检查打包后的 JSON 内容是否有效
        logger.error(MODULE_TAG + '未检测到有效内容用于生成建议，请检查输入数据。')
        raise RuntimeError('未检测到有效内容用于生成建议，请检查输入数据。')

    # 若传入了不同的key则临时覆盖全局配置
    # 注意：genai.configure 确实会重新配置，如果在一个长时间运行的应用中频繁传入不同key，
    # 可能会有轻微的性能开销，但对于大多数使用场景影响不大。
    if api_key and str(api_key).strip() != (API_KEY or ""):
        genai.configure(api_key=api_key)
        logger.info(MODULE_TAG + "API Key 已根据函数参数临时更新。")

    # -------------------- 准备用户输入内容 --------------------
    position_info = packaged_json.get('position_info', {}) # 获取持仓信息，默认为空字典
    main_info = packaged_json.get('main_info', {}) # 获取主信息，默认为空字典
    # 提取 packaged_json 中除了 'position_info' 和 'main_info' 之外的所有其他键值对
    other_keys = {k: v for k, v in packaged_json.items() if k not in ('position_info', 'main_info')}

    # 合并用户输入内容，如果 position_info 为空或 is_empty 为 True，则不包含 position_info
    if (not position_info or position_info.get('is_empty') is True):
        merged_content = {
            "main_info": main_info,
            **other_keys # 字典合并语法「方案选单」
        }
    else:
        merged_content = {
            "position_info": position_info,
            "main_info": main_info,
            **other_keys
        }
    # 将合并后的内容转换为 JSON 字符串作为用户提示的一部分
    user_content = "图片周期为：M15\n" + json.dumps(merged_content, ensure_ascii=False, indent=2)

    contents = [] # 初始化内容列表，用于多模态输入
    if screenshot_path and os.path.exists(screenshot_path): # 如果截图路径存在且文件存在
        try:
            from PIL import Image # 尝试导入 Pillow 库
            img = Image.open(screenshot_path) # 打开图片文件
            logger.info(MODULE_TAG + f"图片已加载: {screenshot_path}, size={img.size}, mode={img.mode}")
            contents.append(img) # 将图片添加到内容列表
        except Exception as e: # 捕获图片加载过程中可能发生的任何异常
            logger.error(MODULE_TAG + f"加载图片失败，跳过图片输入: {screenshot_path}, 错误: {e}")
            # 继续执行不带图片的API调用，这是一个很好的错误处理策略，保证程序不会因为图片问题中断
    else: # 如果截图路径不存在或文件不存在
        logger.warning(MODULE_TAG + f"未加载图片，screenshot_path={screenshot_path}") # 记录警告信息

    contents.append(user_content) # 将用户文本内容添加到内容列表
    logger.info(MODULE_TAG + f"contents 类型: {[type(c) for c in contents]}") # 记录 contents 中每个元素的类型

    # -------------------- 配置模型和生成参数 --------------------
    # 初始化 GenerativeModel 实例
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)

    # 构建 generation_config 字典，包含所有通用参数
    generation_config = {
        "temperature": temperature,
        "top_p": top_p,
    }

    # 仅对非 flash/preview 模型传递 penalty 参数
    # 判断模型是否为 "flash" 系列，不区分大小写
    if not (model_name and "flash" in model_name.lower()): # 增加了 .lower() 使判断更健壮
        generation_config["frequency_penalty"] = frequency_penalty # 添加频率惩罚参数
        generation_config["presence_penalty"] = presence_penalty # 添加存在惩罚参数
        logger.info(MODULE_TAG + f"模型 '{model_name}' 支持惩罚参数，已添加 frequency_penalty: {frequency_penalty}, presence_penalty: {presence_penalty}。")
    else:
        logger.warning(MODULE_TAG + f"模型 '{model_name}' (Flash 系列) 不支持惩罚参数，已跳过 frequency_penalty 和 presence_penalty。")


    # -------------------- 调用 API 并处理响应 --------------------
    try:
        start_time = time.time()
        logger.info(MODULE_TAG + f"即将调用 Gemini API ...\n参数: {generation_config}") # 记录 API 调用参数
        response = model.generate_content(contents, generation_config=generation_config) # 调用 Gemini API
        end_time = time.time()
        logger.info(MODULE_TAG + "Gemini API 已返回结果") # 记录 API 返回信息

        # 检查 candidates 是否有内容，避免 response.text 抛异常
        # 这是一个重要的健壮性改进，防止当API返回空内容时出现属性错误
        if not response.candidates or not response.candidates[0].content.parts:
            # 尝试获取 finish_reason 以便日志记录更详细的错误原因
            finish_reason = getattr(response.candidates[0], 'finish_reason', None) if response.candidates else None
            logger.error(MODULE_TAG + f"Gemini API 返回空内容，finish_reason: {finish_reason}")
            raise RuntimeError(f"Gemini API 返回空内容，finish_reason: {finish_reason}")
        text = response.text if hasattr(response, 'text') else str(response)
        # === AI思考判定机制 ===
        think_time = end_time - start_time
        key_phrases = ["reason", "推理", "分析", "流程", "summary", "entry_condition"]
        if (think_time < 1.5 and len(text) < 80) or not any(k in text for k in key_phrases):
            logger.warning(MODULE_TAG + f"AI回复疑似未认真推理，耗时{think_time:.2f}s，内容：{text[:60]}")
            return "[警告] AI回复疑似未认真推理，请重试或更换模型。\n\n原始内容：\n" + text
        return text # 返回模型生成的文本结果

    except Exception as e: # 捕获 API 调用过程中可能发生的任何异常
        logger.error(MODULE_TAG + f"Gemini API 调用异常: {e}") # 记录错误信息
        raise RuntimeError(f"Gemini API 调用失败: {e}") # 重新抛出运行时错误

def call_gemini_api_stream(
        packaged_json: dict, 
        model_name: str = None, 
        screenshot_path: str = None, 
        api_key: str = None,
        temperature: float = DEFAULT_TEMPERATURE, 
        top_p: float = DEFAULT_TOP_P, 
        # max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        frequency_penalty: float = DEFAULT_FREQUENCY_PENALTY, 
        presence_penalty: float = DEFAULT_PRESENCE_PENALTY, 
        include_thoughts: bool = True):
    """
    流式调用 Gemini API，逐步返回内容块。若不支持流式API则自动降级为同步API并分块输出。
    新增：支持思考摘要（thought summary）流式输出。
    """
    if not model_name:
        model_name = DEFAULT_MODEL_NAME
    key = api_key if api_key and str(api_key).strip() else API_KEY
    system_instruction = SYSTEM_PROMPT
    if not key:
        raise RuntimeError("Gemini API Key 未配置。请设置 GEMINI_API_KEY 环境变量或在代码中提供。")
    if not is_effective_content(packaged_json):
        raise RuntimeError('未检测到有效内容用于生成建议，请检查输入数据。')
    if api_key and str(api_key).strip() != (API_KEY or ""):
        genai.configure(api_key=api_key)
    position_info = packaged_json.get('position_info', {})
    main_info = packaged_json.get('main_info', {})
    other_keys = {k: v for k, v in packaged_json.items() if k not in ('position_info', 'main_info')}
    if (not position_info or position_info.get('is_empty') is True):
        merged_content = {"main_info": main_info, **other_keys}
    else:
        merged_content = {"position_info": position_info, "main_info": main_info, **other_keys}
    user_content = "图片周期为：M15\n" + json.dumps(merged_content, ensure_ascii=False, indent=2)
    contents = []
    if screenshot_path and os.path.exists(screenshot_path):
        try:
            from PIL import Image
            img = Image.open(screenshot_path)
            contents.append(img)
        except Exception:
            pass
    contents.append(user_content)
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction)
    generation_config = {"temperature": temperature, "top_p": top_p}
    if not (model_name and "flash" in model_name.lower()):
        generation_config["frequency_penalty"] = frequency_penalty
        generation_config["presence_penalty"] = presence_penalty
    try:
        try:
            from google.generativeai.types import GenerateContentConfig, ThinkingConfig
            types_ok = True
        except ImportError:
            types_ok = False
        if hasattr(model, "generate_content_stream") and types_ok:
            config = GenerateContentConfig(
                thinking_config=ThinkingConfig(
                    include_thoughts=include_thoughts
                )
            )
            response = model.generate_content_stream(contents, generation_config=generation_config, config=config)
            for chunk in response:
                for cand in getattr(chunk, 'candidates', []):
                    for part in getattr(getattr(cand, 'content', None), 'parts', []):
                        if not getattr(part, 'text', None):
                            continue
                        if getattr(part, 'thought', False):
                            yield f"[思考摘要]\n{part.text}\n"
                        else:
                            yield part.text
        elif hasattr(model, "generate_content_stream"):
            response = model.generate_content_stream(contents, generation_config=generation_config)
            buffer = ""
            for chunk in response:
                for cand in getattr(chunk, 'candidates', []):
                    for part in getattr(getattr(cand, 'content', None), 'parts', []):
                        if not getattr(part, 'text', None):
                            continue
                        buffer += part.text
                        yield buffer
        else:
            raise AttributeError
    except AttributeError:
        # fallback: 用同步API并分块yield
        try:
            try:
                from google.generativeai.types import GenerateContentConfig, ThinkingConfig
                types_ok = True
            except ImportError:
                types_ok = False
            if types_ok:
                config = GenerateContentConfig(
                    thinking_config=ThinkingConfig(
                        include_thoughts=include_thoughts
                    )
                )
                resp = model.generate_content(contents, generation_config=generation_config, config=config)
                for part in getattr(resp.candidates[0].content, 'parts', []):
                    if not getattr(part, 'text', None):
                        continue
                    if getattr(part, 'thought', False):
                        yield f"[思考摘要]\n{part.text}\n"
                    else:
                        yield part.text
            else:
                resp = model.generate_content(contents, generation_config=generation_config)
                text = getattr(resp, 'text', None) or ''
                block_size = 40
                for i in range(0, len(text), block_size):
                    yield text[i:i+block_size]
        except Exception as e:
            raise RuntimeError(f"Gemini API 同步调用失败: {e}")
    except Exception as e:
        raise RuntimeError(f"Gemini API 流式调用失败: {e}")

def get_configured_model(model_name_str, system_instruction_text=None):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY 环境变量未找到或未设置。")
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        raise RuntimeError(f"配置 Gemini API 失败: {e}")
    return genai.GenerativeModel(
        model_name_str,
        system_instruction=system_instruction_text
    )

# -------------------- 模块导出 --------------------
__all__ = ["call_gemini_api", "call_gemini_api_stream", "is_effective_content"] # 定义模块对外暴露的名称

venv_python = "/home/li-xufeng/codespace/gemini_quant_v1/.venv/bin/python"
# 所有子进程调用请用 venv_python 作为解释器
# 示例：如有子进程调用请用 venv_python 作为解释器
# subprocess.run([venv_python, 'other_script.py', ...])