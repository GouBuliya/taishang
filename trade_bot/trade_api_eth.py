import okx.Account as Account
import okx.Trade as Trade
import json
import os
import logging
from openai import OpenAI
import time
from typing import List, Dict, Any, Optional
import datetime

#eth交易api

config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r", encoding="utf-8"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["path"]["log_file"]
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

gemini_answer_path = config["ETH_gemini_answer_path"]
gemini_answer = json.load(open(gemini_answer_path, "r", encoding="utf-8"))
execution = gemini_answer["execution_details"] #为array


# API 初始化
apikey = config["okx"]["api_key"]
secretkey = config["okx"]["secret_key"]
passphrase = config["okx"]["passphrase"]

flag = config["okx"]["flag"]  # 实盘:0 , 模拟盘:1


tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)

accountAPI = Account.AccountAPI(apikey, secretkey, passphrase, False, flag)

import function.place_order as place_order
if __name__ == "__main__":

    



    res=place_order.place_order()
    print(res)