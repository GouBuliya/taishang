#------日志模块------
import os
import logging


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = "/root/codespace/Qwen_quant_v1/nohup.out"
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")



#-----------