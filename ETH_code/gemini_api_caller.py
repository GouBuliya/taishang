    import logging
    import os
    import sys
    import json
    import traceback
    import base64
    import random # 导入 random 模块
    import re

    # ===================== 全局配置与初始化 =====================

    config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r"))

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOG_FILE = config["ETH_log_path"]
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
    DEFAULT_MODEL_NAME = "gemini-2.5-flash-preview-05-20"
    SYSTEM_PROMPT_PATH =  config["SYSTEM_PROMPT_PATH"]
    SYSTEM_PROMPT = ""

    SYSTEM_JSON_PATH=config["ETH_data_path"]
    if os.path.exists(SYSTEM_PROMPT_PATH):
        with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
            SYSTEM_PROMPT = f.read().strip()
        if not SYSTEM_PROMPT:
            logger.warning(f"{MODULE_TAG}系统提示词文件内容为空: {SYSTEM_PROMPT_PATH}.")
    else:
        logger.warning(f"{MODULE_TAG}系统提示词文件未找到: {SYSTEM_PROMPT_PATH}. SYSTEM_PROMPT 将为空。")
    # ===================== 全局配置与初始化 END =====================

    DEFAULT_TEMPERATURE = config["MODEL_CONFIG"]["default_temperature"]
    DEFAULT_TOP_P = config["MODEL_CONFIG"]["default_top_p"]
    DEFAULT_MAX_OUTPUT_TOKENS = config["MODEL_CONFIG"]["default_max_output_tokens"]
    DEFAULT_THINKING_BUDGET = config["MODEL_CONFIG"]["default_thinking_budget"]
    DEFAULT_INCLUDE_THOUGHTS = config["MODEL_CONFIG"]["default_include_thoughts"]

    # ===================== Gemini API 调用主模块 =====================

    from google import genai
    from google.genai import types
    from pydantic import BaseModel

    #=================tools=================    

    def get_transaction_history(target:str)->dict:
        """
        Args:
            target: the target
        Returns:
            The last 3 transaction history (JSON format)
        """
        import subprocess
        #运行get_transaction_history.py
        
        logger.info(f"{MODULE_TAG}运行get_transaction_history.py")
        trade_log=subprocess.run([config["python_path"]["global"], config["path"]["function_path"]["get_transaction_history"]], capture_output=True, text=True, timeout=360)
        #获取最后3条交易纪录
        trade_log=trade_log.stdout  
        logger.info(f"{MODULE_TAG}获取最后3条交易纪录完成")
        res={}
        res["transaction_history"]=trade_log
        return res



    get_transaction_history_declaration={
        "name":"get_transaction_history",
        "description":"get the last 3 transaction history",
        "parameters":{
            "type":"object",
            "properties":{
                "transaction_history":{
                    "type":"string",
                    "description":"the target"
                },
            },
            "required":["transaction_history"]

        }
    }

    def get_time(target:str)->dict:
        """
        Args:
            target: the target
        Returns:
            The current time (JSON format)
        """
        import subprocess
        #运行get_time.py
        logger.info(f"{MODULE_TAG}运行get_time.py")
        time=subprocess.run([config["python_path"]["global"], config["path"]["function_path"]["get_time"]], capture_output=True, text=True, timeout=360)
        logger.info(f"{MODULE_TAG}获取当前时间完成")
        res={}
        res["time"]=time.stdout
        return res


    get_time_declaration={
        "name":"get_time",
        "description":"get the current time",
        "parameters":{
            "type":"object",
            "properties":{
                "time":{
                    "type":"string",
                    "description":"the target"
                },
            },
            "required":["time"]
        }
    }

    #=======================================    
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
            
            tools=types.Tool(function_declarations=[get_transaction_history_declaration,get_time_declaration])
            gemini_config = types.GenerateContentConfig(
                temperature=DEFAULT_TEMPERATURE,
                top_p=DEFAULT_TOP_P,
                max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                thinking_config={
                    "include_thoughts":DEFAULT_INCLUDE_THOUGHTS,
                    "thinking_budget":DEFAULT_THINKING_BUDGET,
                },
                system_instruction=system_prompt,
                tools=[tools]
            )


        

            client = genai.Client(api_key=_api_key)
            try:
                logger.info(f"{MODULE_TAG}图片导入开始:{screenshot_path}")
                image=client.files.upload(file=screenshot_path)
                logger.info(f"{MODULE_TAG}图片导入完成")
            except Exception as e:
                logger.error(f"{MODULE_TAG}图片导入失败: {e}")
                image=None


            contents = [
            image,
            prompt_text
            ]
            response = client.models.generate_content_stream(
                model=DEFAULT_MODEL_NAME ,
                contents=contents,
                config=gemini_config
            )
            output_buffer = []
            for chunk in response:
                print(f"chunk.text:{chunk.text}\n", end="", flush=True)
                print(f"chunk.function_calls:{chunk.function_calls}\n", end="", flush=True)
                if chunk.text is not None:
                    output_buffer.append(chunk.text)
            output_buffer = "".join(output_buffer)#将output_buffer转换为字符串
            return output_buffer


        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"{MODULE_TAG}Gemini API调用异常: {e}\n{tb}")
            return f"[Gemini API调用异常] {e}\nTraceback:\n{tb}"
    __all__ = ["call_gemini_api_stream"]

    if __name__ == "__main__":

        os.environ['HTTP_PROXY'] = config["proxy"]["http_proxy"]
        os.environ['HTTPS_PROXY'] = config["proxy"]["https_proxy"]
        #tools自检
        logger.info(f"{MODULE_TAG}开始自检")
        try:
            get_transaction_history("ETH-USDT")
            logger.info(f"{MODULE_TAG}get_transaction_history自检完成")
            logger.info(get_transaction_history("ETH-USDT"))
            logger.info(f"{MODULE_TAG}get_transaction_history自检完成")
        except Exception as e:
            logger.error(f"{MODULE_TAG}get_transaction_history自检失败: {e}")
        try:
            logger.info(get_time("ETH-USDT"))
            logger.info(f"{MODULE_TAG}get_time自检完成")
        except Exception as e:
            logger.error(f"{MODULE_TAG}get_time自检失败: {e}")

        data_json_path = SYSTEM_JSON_PATH

        with open(data_json_path, "r", encoding="utf-8") as f:
            data_json = json.load(f)

        prompt_text = json.dumps(data_json, indent=2, ensure_ascii=False)

        logger.info(f"prompt_text导入完成")
        # logger.info(f"prompt_text:{prompt_text}")
        screenshot_path = data_json.get("clipboard_image_path")
        logger.info(f"screenshot_path导入完成,path:{screenshot_path}")
        system_prompt_path = SYSTEM_PROMPT_PATH
        logger.info(f"system_prompt_path导入完成,path:{system_prompt_path}")
        with open(system_prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read().strip()

        logger.info("开始 Gemini API 流式调用...")
        output_buffer = []  # 新增：用于收集输出内容

        thinking_config=config["MODEL_CONFIG"]["default_thinking_budget"]

        # 开始 Gemini API 调用，处理流式响应



        response = call_gemini_api_stream(
            prompt_text=prompt_text,
            screenshot_path=screenshot_path,
            system_prompt=system_prompt,
        )
        print(response)
            # 尝试解析 JSON
        #去除````json和````(只去除开头和结尾)
        response = response.replace("```json", "").replace("```", "")#去除开头和结尾的```json和```
        #将response写入/root/codespace/Qwen_quant_v1/BTC_code/reply_cache/gemini.json
    
        
        output_data = json.loads(response)
            # 将解析后的数据写入文件
        with open(config["ETH_gemini_answer_path"], "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"已将解析后的输出内容保存到 {config['ETH_gemini_answer_path']}")
    
