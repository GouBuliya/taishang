import okx.Account as Account
import json
import os
import logging
from openai import OpenAI
import time
#eth交易api

config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r", encoding="utf-8"))

API_KEY = config["api_key"]["gemini_api_key"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["path"]["log_file"]
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")





# API 初始化
apikey = config["api_key"]["okx_api_key"]
secretkey = config["api_key"]["okx_secret_key"]
passphrase = config["api_key"]["okx_passphrase"]

flag = "1"  # 实盘:0 , 模拟盘:1


if __name__ == "__main__":

