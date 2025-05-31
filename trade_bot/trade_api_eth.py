import okx.Account as Account
import json
import os
import logging
from openai import OpenAI
import time
#eth交易api

API_KEY = "AIzaSyCkBZzYyaSvLzHRWGEsoabZbyNzlvAxa98"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = "/root/codespace/Qwen_quant_v1/log/nohup.out"
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

#gemini
system_prompt_path="/root/codespace/Qwen_quant_v1/config/bot_system_prompt.txt"

def get_balance_positions():
    path="/root/codespace/Qwen_quant_v1/code/get_positions.py"
    data=os.popen(f"python {path}").read()

    #data转化为json
    data=json.loads(data)
    #data转化为str
    data=json.dumps(data,indent=4,ensure_ascii=False)
    return data

def build_messages(prompt_text, system_prompt=None):#变量prompt_text为json格式
    #建立一个json格式变量messages
    messages = []
    sys_prompt = system_prompt 

    # Gemini's OpenAI compatibility supports a dedicated 'system' role
    if sys_prompt:#将sys_prompt作为元素加入json格式messages
        messages.append({"role": "system", "content": sys_prompt.strip()})
    #确保user_content_parts为json格式
    user_content_parts = [{"type": "text", "text": prompt_text},{"type": "text", "text": get_balance_positions()}]



    messages.append({"role": "user", "content": user_content_parts})

    return messages


def call_gemini_api_stream(
    prompt_text, # Directly accept prompt_text
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
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()
    try:
        _api_key = api_key or API_KEY
        if not _api_key:
            raise RuntimeError("未配置 GEMINI_API_KEY")
        
        
        client = OpenAI(
            api_key=_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        messages = build_messages(prompt_text, system_prompt=system_prompt)
        #将messages缓存到同目录下的messages.json
        # 为了提高 messages.json 的可读性，对其中的嵌套 JSON 字符串进行格式化
        messages_for_file = json.loads(json.dumps(messages)) # Deep copy
        for message in messages_for_file:
            if message.get("role") == "user" and isinstance(message.get("content"), list):
                formatted_content = []
                for item in message["content"]:
                    if item.get("type") == "text" and isinstance(item.get("text"), str):
                        try:
                            # 尝试解析嵌套的 JSON 字符串
                            nested_json_obj = json.loads(item["text"])
                            # 重新格式化为带有缩进的字符串
                            formatted_text = json.dumps(nested_json_obj, indent=2, ensure_ascii=False)
                            formatted_content.append({"type": "text", "text": formatted_text})
                        except json.JSONDecodeError:
                            # 如果不是有效的 JSON 字符串，则保留原始文本
                            formatted_content.append(item)
                    else:
                        formatted_content.append(item)
                message["content"] = formatted_content
                
        with open("/root/codespace/Qwen_quant_v1/trade_bot/messages.json", "w", encoding="utf-8") as f:
            json.dump(messages_for_file, f, indent=2, ensure_ascii=False)
        
        chat_params = {
            "model": "gemini-2.5-flash-preview-05-20",
            "messages": messages,
            "stream": True,
            "temperature": 0.0,
            "max_tokens": 24576,
        }

        # 根据文档，reasoning_effort 是直接的参数
        if enable_reasoning:
            chat_params["reasoning_effort"] = reasoning_effort or "low"
        
        stream = client.chat.completions.create(**chat_params)

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"[Gemini API调用异常] {e}"
__all__ = ["call_gemini_api_stream"]


# API 初始化
apikey = "e4690480-5f46-4f5c-9046-bced6c333bf9"
secretkey = "7C676520EDE0CF56479E0A13CB110BF8"
passphrase = "1528895030qQ@"

flag = "1"  # 实盘:0 , 模拟盘:1


if __name__ == "__main__":

    #读取/root/codespace/Qwen_quant_v1/code/reply_cache/gemini.json
    with open("/root/codespace/Qwen_quant_v1/code/reply_cache/gemini.json", "r", encoding="utf-8") as f:
        prompt = json.load(f)

    #确保prompt为json格式
    prompt = json.dumps(prompt,indent=4,ensure_ascii=False)

    # 读取系统提示词
    with open(system_prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
    logger.info(f"系统提示词以导入")
    #写一个进度条(使用logger)，进度条的进度为0.1，每秒更新一次
    
    output_buffer = []
    for text in call_gemini_api_stream(
        prompt,
        system_prompt=system_prompt,
        enable_reasoning=True,
        reasoning_effort="low"
    ):
        output_buffer.append(text)
    logger.info(f"Gemini API 流式调用结束。{output_buffer}")
    #将output_buffer开头的"```json"和结尾的"```"去掉
    output_buffer = [line.strip("```json").strip() for line in output_buffer]
    output_buffer = [line.strip("```").strip() for line in output_buffer]
    #将output_buffer转化为json,the JSON object must be str, bytes or bytearray, not list
    output_buffer = "".join(output_buffer)
    output_buffer = json.loads(output_buffer)
    output_buffer = json.dumps(output_buffer,indent=4,ensure_ascii=False)#支持中文编码


    """
    {
        "symbol": "string",
        "action": "string", // "buy" (开多/平空), "sell" (开空/平多), or "wait" (不交易)
        "order_type": "string", // "market", "limit", or "N/A" if action is "wait"
        "price": "string", // Required if order_type is "limit" or for market close. "N/A" if action is "wait" or cannot be determined.
        "stop_loss": "string", // "N/A" if action is "wait" or not provided/determined.
        "take_profit_targets": ["string", "string", "string"], // "N/A" if action is "wait" or not provided/determined. If fewer than 3, fill with "N/A".
        "size": "string", // Calculated size based on "full position mode" (either entire existing position or 1% risk for new position), or "dynamic_calculation_needed".
        "comment": "string" // Brief explanation of the decision and key factors, including any data limitations.
    }
    """
    Operations=output_buffer
    


    #将output_buffer写入/root/codespace/Qwen_quant_v1/trade_bot/trade_log.json（末尾追加）（加上时间戳）
    with open("/root/codespace/Qwen_quant_v1/trade_bot/trade_log.json", "a", encoding="utf-8") as f:
        #格式化时间戳并加入到json中符合json格式
        """
        {
            "time": "2025-05-30 06:46:24",
            "response": "response"
        }
        """
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        time_str = json.dumps(time_str,indent=4,ensure_ascii=False)
        f.write('{\n')  
        f.write(f'"time": {time_str},\n')
        f.write(f'"response": {output_buffer}\n')
        f.write('}\n')
        
    print(output_buffer)


    