import okx.Trade as Trade
import okx.Account as Account
import json
import os
import logging
from typing import List, Dict, Union, Optional
from ..utils import retry_on_error

# 路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(BASE_DIR, "logs/trade.log")
CONFIG_FILE = os.path.join(BASE_DIR, "config/config.json")

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

@retry_on_error(max_retries=3, delay=1.0)
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
    :param take_profits: 止盈列表，每个元素包含 price (价格) 和 size (数量) （可为None）
                        示例: [{"price": 2450.0, "size": 38.83}, {"price": 2420.0, "size": 38.83}]
    :return: 下单结果dict
    """
    try:
        results = []
        min_lot_size = 0.1  # ETH合约的最小交易单位
        
        # 设置分级止盈止损
        if take_profits and stop_loss is not None:
            # 验证总止盈数量不超过持仓数量
            total_tp_size = sum(float(tp["size"]) for tp in take_profits)
            if total_tp_size > size + 0.1:  # 允许0.1的误差
                logger.error(f"止盈总数量({total_tp_size})超过持仓数量({size})")
                return {"success": False, "error": "止盈总数量超过持仓数量", "response": None}

            for i, tp in enumerate(take_profits):
                try:
                    price = float(tp["price"])
                    tp_size = float(tp["size"])
                    
                    if price <= 0 or tp_size <= 0:
                        logger.error(f"无效的止盈配置: 价格={price}, 数量={tp_size}")
                        continue
                    
                    # 将数量转换为最小交易单位的整数倍
                    lots = round(tp_size / min_lot_size)  # 四舍五入到最接近的完整单位
                    actual_size = lots * min_lot_size
                    
                except (TypeError, ValueError, KeyError) as e:
                    logger.error(f"处理止盈配置时出错: {str(e)}")
                    continue

                # 跳过数量为0的订单
                if lots <= 0:
                    logger.warning(f"跳过数量为0的止盈订单: 价格={price}")
                    continue

                # 记录详细的数量信息用于调试
                logger.debug(f"数量计算: 目标数量={tp_size}, lots={lots}, 实际数量={actual_size}")

                # 根据持仓方向设置订单方向
                side = "sell" if pos_side == "long" else "buy"  # 止盈/止损时平仓

                params = {
                    "instId": instrument_id,
                    "tdMode": "cross",
                    "side": side,           # 订单方向
                    "ordType": "conditional",  # 使用条件单，不使用OCO
                    "sz": str(lots),        # 使用lots作为数量单位
                    "tpTriggerPx": str(price),  # 止盈触发价
                    "tpOrdPx": "-1"         # 市价止盈
                }
                
                # 对于第一个订单添加止损
                if i == 0:
                    params.update({
                        "ordType": "oco",   # 第一个订单使用OCO类型
                        "slTriggerPx": str(stop_loss),  # 止损触发价
                        "slOrdPx": "-1"     # 市价止损
                    })
                
                result = tradeAPI.place_algo_order(**params)
                if result.get('code') != '0':
                    error_msg = result.get('msg', '未知错误')
                    logger.error(f"{'OCO' if i == 0 else '条件'}订单下单失败，错误信息：{error_msg}")
                    return {"success": False, "error": error_msg, "response": result}
                
                logger.info(f"{'OCO' if i == 0 else '条件'}订单设置成功: 止盈价格={price}" + 
                          (f", 止损价格={stop_loss}" if i == 0 else "") + 
                          f", 数量={actual_size} ({lots} lots)")
                results.append({
                    "type": "oco" if i == 0 else "conditional",
                    "take_profit_price": price,
                    "stop_loss_price": stop_loss if i == 0 else None,
                    "size": actual_size,
                    "lots": lots,
                    "result": result
                })

        if not results:
            return {"success": False, "error": "未设置任何止盈止损", "response": None}

        return {"success": True, "results": results}
    except Exception as e:
        logger.error(f"设置止盈止损失败，错误信息：{str(e)}")
        return {"success": False, "error": str(e), "response": None}
