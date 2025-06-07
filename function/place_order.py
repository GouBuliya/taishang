import okx.Trade as Trade
import okx.Account as Account
import json
import os
import logging
from function.utils import retry_on_error  # 修改导入路径

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
LOG_FILE = os.path.join(PROJECT_ROOT, "logs/trade.log")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config/config.json")

# 确保日志目录存在
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

try:
    config = json.load(open(CONFIG_FILE, "r"))
except FileNotFoundError:
    logger.error(f"配置文件不存在: {CONFIG_FILE}")
    raise
except json.JSONDecodeError:
    logger.error(f"配置文件格式错误: {CONFIG_FILE}")
    raise

# API 初始化
apikey = config["okx"]["api_key"]
secretkey = config["okx"]["secret_key"]
passphrase = config["okx"]["passphrase"]

flag = config["okx"]["flag"]  # 实盘: 0, 模拟盘: 1

tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)
accountAPI = Account.AccountAPI(apikey, secretkey, passphrase, False, flag)

@retry_on_error(max_retries=3, delay=1.0)
def _set_leverage(instrument_id: str, leverage: int) -> dict:
    """设置杠杆倍数（带重试）"""
    res = accountAPI.set_leverage(
        instId=instrument_id,
        lever=str(leverage),
        mgnMode="cross"
    )
    return res

@retry_on_error(max_retries=3, delay=1.0)
def _place_order(params: dict) -> dict:
    """执行下单（带重试）"""
    result = tradeAPI.place_order(**params)
    return result

def place_order(instrument_id, side, size, price, leverage=100, order_type="limit"):
    """
    下单函数，返回详细下单结果
    """
    try:
        # 验证订单数量
        try:
            size = float(size)
            if size <= 0:
                logger.error("订单数量必须大于0")
                return {"success": False, "error": "订单数量必须大于0", "response": None}
        except (TypeError, ValueError):
            logger.error("无效的订单数量")
            return {"success": False, "error": "无效的订单数量", "response": None}

        # 对限价单验证价格
        if order_type == "limit":
            try:
                price = float(price)
                if price <= 0:
                    logger.error("限价单价格必须大于0")
                    return {"success": False, "error": "限价单价格必须大于0", "response": None}
                # 转换为字符串，因为API要求
                price = str(price)
            except (TypeError, ValueError):
                logger.error("无效的价格")
                return {"success": False, "error": "无效的价格", "response": None}
        else:
            # 市价单不需要价格
            price = ""

        # 检查杠杆是否在允许范围内
        if leverage < 100 or leverage > 1000:
            logger.warning(f"杠杆设置超出范围，默认使用100倍杠杆")
            leverage = 100
            
        # 设置杠杆
        res = _set_leverage(instrument_id, leverage)
        
        # 检查杠杆设置结果
        if res.get('code') != '0':  # 注意：API返回的code是字符串类型
            logger.error(f"设置杠杆失败，错误信息：{res.get('msg', '')}")
            return {"success": False, "error": res.get('msg', ''), "response": res}
        logger.info(f"设置杠杆成功：{leverage}倍")
        
        # 检查订单类型
        if order_type not in ["limit", "market"]:
            logger.warning(f"无效的订单类型，默认使用限价单")
            order_type = "limit"

        # 转换side为buy/sell
        order_side = "buy" if side == "long" else "sell"
        
        # 执行下单
        params = {
            "side": order_side,       # 交易方向: buy 或 sell
            "instId": instrument_id,  # 合约id
            "tdMode": "cross",       # 全仓模式
            "ordType": order_type,   # 订单类型
            "sz": str(size)          # 数量（API要求字符串类型）
        }
        
        # 限价单需要价格参数
        if order_type == "limit":
            params["px"] = price
            
        result = _place_order(params)
        
        # 检查下单结果
        if result.get('code') != '0':  # API返回的code是字符串类型
            logger.error(f"下单失败，错误信息：{result.get('msg', '')}")
            return {"success": False, "error": result.get('msg', ''), "response": result}
            
        logger.info(f"下单成功：方向={order_side}, 价格={price}, 数量={size}")
        return {
            "success": True,
            "order_id": result.get('data', [{}])[0].get('ordId', None),
            "response": result
        }
    except Exception as e:
        logger.error(f"下单失败，错误信息：{e}")
        return {"success": False, "error": str(e), "response": None}
