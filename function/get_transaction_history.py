import json
import os
import pandas as pd
import logging

config=json.load(open("/root/codespace/Qwen_quant_v1/config/config.json","r"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = "/root/codespace/Qwen_quant_v1/nohup.out"
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

#获取/root/codespace/Qwen_quant_v1/trade_bot/trade_log.json最后3条交易纪录

trade_log_path =config['path']['trade_log_path']

with open(trade_log_path, "r") as f:
    trade_log = json.load(f)
#获取最后3条交易纪录
trade_log = trade_log[-3:]

#转化为json
trade_log_json = json.dumps(trade_log,indent=4,ensure_ascii=False)
print(trade_log_json)



