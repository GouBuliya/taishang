import okx.Trade as Trade
import okx.Account as Account
import json
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

config = json.load(open(os.path.join(BASE_DIR, "config/config.json"), "r"))


# API 初始化
apikey = config["okx"]["api_key"]
secretkey = config["okx"]["secret_key"]
passphrase = config["okx"]["passphrase"]

flag = config["okx"]["flag"]  # 实盘: 0, 模拟盘: 1

tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)
accountAPI = Account.AccountAPI(apikey, secretkey, passphrase, False, flag)

def place_order(instrument_id, side, size, price, leverage=100, order_type="limit"):
    """
    下单函数
    """
    try:
        # 检查杠杆是否在允许范围内
        if leverage < 100 or leverage > 1000:
            logger.warning(f"杠杆设置超出范围，默认使用100倍杠杆")
            leverage = 100


        res=accountAPI.set_leverage(
            instId=instrument_id,
            lever=str(leverage),
            mgnMode="cross"
        )
        if(res['code']!=0):
            logger.error(f"设置杠杆失败，错误信息：{res['msg']}")
            return False
        
        # 检查订单类型
        if order_type not in ["limit", "market"]:
            logger.warning(f"无效的订单类型，默认使用限价单")
            order_type="limit"

        result = tradeAPI.place_order(
            instId=instrument_id,#合约id
            tdMode="cross",#全倉
            posSide=side,#持仓方向
            ordType=order_type,#订单类型
            px=price,#价格
            sz=size#数量
        )
        if(result['code']!=0):
            logger.error(f"下单失败，错误信息：{result['msg']}")
            return False
        return True
    except Exception as e:
        logger.error(f"下单失败，错误信息：{e}")
        return False
