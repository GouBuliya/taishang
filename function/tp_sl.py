import okx.Trade as Trade
import okx.Account as Account
import json
import os
import logging
from typing import List, Dict, Union, Optional

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

apikey = config["okx"]["api_key"]
secretkey = config["okx"]["secret_key"]
passphrase = config["okx"]["passphrase"]
flag = config["okx"]["flag"]  # 实盘: 0, 模拟盘: 1

tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)
accountAPI = Account.AccountAPI(apikey, secretkey, passphrase, False, flag)

def set_take_profit_stop_loss(
    instrument_id: str, 
    pos_side: str,
    size: float,
    stop_loss: Optional[float] = None, 
    take_profits: Optional[List[Dict[str, Union[float, float]]]] = None
) -> Dict:
    """
    设置止盈止损单，支持分级止盈
    :param instrument_id: 合约ID
    :param pos_side: 持仓方向 long/short（用于确定止盈止损方向）
    :param size: 持仓数量
    :param stop_loss: 止损价格（可为None）
    :param take_profits: 止盈列表，每个元素包含 price (价格) 和 size (数量占比) （可为None）
                        示例: [{"price": 2450.0, "size": 0.9}, {"price": 2400.0, "size": 0.1}]
    :return: 下单结果dict
    """
    try:
        results = []
        
        # 设置止损
        if stop_loss is not None:
            try:
                stop_loss = float(stop_loss)
                if stop_loss <= 0:
                    logger.error("止损价格必须大于0")
                    return {"success": False, "error": "止损价格必须大于0", "response": None}
            except (TypeError, ValueError):
                logger.error("无效的止损价格")
                return {"success": False, "error": "无效的止损价格", "response": None}

            # 根据持仓方向设置止损类型
            side = "buy" if pos_side == "short" else "sell"  # 止损时反向操作

            params = {
                "instId": instrument_id,
                "tdMode": "cross",
                "side": side,             # 止损触发时的交易方向
                "ordType": "conditional",  # 条件单类型
                "slTriggerPx": str(stop_loss),  # 止损触发价
                "slOrdPx": "-1",          # 市价止损
                "sz": str(size),          # 止损数量
            }
            result = tradeAPI.place_algo_order(**params)
            if result.get('code', None) != '0':
                logger.error(f"止损下单失败，错误信息：{result.get('msg', '')}")
                return {"success": False, "error": result.get('msg', ''), "response": result}
            results.append({"type": "stop_loss", "result": result})

        # 设置分级止盈
        if take_profits:
            for tp in take_profits:
                try:
                    price = float(tp["price"])
                    size_ratio = float(tp["size"])
                    if price <= 0 or size_ratio <= 0 or size_ratio > 1:
                        logger.error("无效的止盈价格或比例")
                        continue
                    
                    # 计算该档位的止盈数量
                    tp_size = size * size_ratio
                    
                except (TypeError, ValueError, KeyError):
                    logger.error("无效的止盈配置")
                    continue

                # 根据持仓方向设置止盈类型
                side = "sell" if pos_side == "long" else "buy"  # 止盈时平仓

                params = {
                    "instId": instrument_id,
                    "tdMode": "cross",
                    "side": side,           # 止盈触发时的交易方向
                    "ordType": "conditional",  # 条件单类型
                    "tpTriggerPx": str(price),  # 止盈触发价
                    "tpOrdPx": "-1",         # 市价止盈
                    "sz": str(tp_size)       # 该档位的止盈数量
                }
                result = tradeAPI.place_algo_order(**params)
                if result.get('code', None) != '0':
                    logger.error(f"止盈下单失败，错误信息：{result.get('msg', '')}")
                else:
                    results.append({"type": "take_profit", "price": price, "size": tp_size, "result": result})

        if not results:
            return {"success": False, "error": "未设置任何止盈止损", "response": None}

        return {"success": True, "results": results}
    except Exception as e:
        logger.error(f"设置止盈止损失败，错误信息：{e}")
        return {"success": False, "error": str(e), "response": None}
