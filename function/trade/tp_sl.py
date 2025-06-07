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
    stop_loss: Optional[Union[float, str]] = None, 
    take_profits: Optional[List[Dict[str, Union[float, str, float]]]] = None
) -> Dict:
    """
    设置止盈止损单，支持分级止盈
    :param instrument_id: 合约ID
    :param pos_side: 持仓方向 long/short（用于确定止盈止损方向）
    :param size: 持仓数量
    :param stop_loss: 止损价格（可为None或"N/A"）
    :param take_profits: 止盈列表，每个元素包含 price (价格) 和 size (数量) （可为None）
                        示例: [{"price": 2450.0, "size": 38.83}, {"price": "N/A", "size": 38.83}]
    :return: 下单结果dict
    """
    try:
        results = []
        min_lot_size = 0.1  # ETH合约的最小交易单位
        
        # 验证和转换止损价格
        has_valid_stop_loss = False
        if stop_loss is not None:
            if str(stop_loss).upper() == "N/A":
                logger.info("止损价格为N/A，跳过止损设置")
                stop_loss = None
            else:
                try:
                    stop_loss = float(stop_loss)
                    has_valid_stop_loss = stop_loss > 0
                    if not has_valid_stop_loss:
                        logger.warning("止损价格必须大于0")
                        stop_loss = None
                except (TypeError, ValueError):
                    logger.warning(f"无效的止损价格: {stop_loss}")
                    stop_loss = None

        # 验证和处理止盈列表
        if take_profits:
            # 验证总止盈数量不超过持仓数量
            valid_tps = []
            total_tp_size = 0
            
            for tp in take_profits:
                try:
                    price = tp.get("price")
                    if price is None or str(price).upper() == "N/A":
                        logger.info(f"跳过无效止盈价格: {price}")
                        continue
                        
                    price = float(price)
                    tp_size = float(tp.get("size", 0))
                    
                    if price <= 0:
                        logger.warning(f"止盈价格必须大于0: {price}")
                        continue
                    
                    if tp_size <= 0:
                        logger.warning(f"止盈数量必须大于0: {tp_size}")
                        continue
                        
                    # 计算lots（向下取整到最小交易单位的倍数）
                    lots = int(tp_size / min_lot_size) * min_lot_size
                    if lots < min_lot_size:
                        logger.warning(f"止盈数量{tp_size}小于最小交易单位{min_lot_size}")
                        continue
                        
                    total_tp_size += lots
                    if total_tp_size > size:
                        logger.warning(f"总止盈数量{total_tp_size}超过持仓数量{size}")
                        # 调整最后一个止盈数量
                        lots = max(min_lot_size, size - (total_tp_size - lots))
                        total_tp_size = size
                        
                    valid_tps.append({
                        "price": price,
                        "size": lots,
                        "lots": lots
                    })
                    
                except (TypeError, ValueError) as e:
                    logger.warning(f"处理止盈订单时出错: {e}")
                    continue
            
            take_profits = valid_tps
            
            # 如果没有有效的止盈订单，返回空结果
            if not take_profits:
                logger.info("没有有效的止盈订单")
                return {"success": True, "results": [], "message": "No valid take profit orders"}
            
            # 执行止盈止损订单
            for i, tp in enumerate(take_profits):
                # 设置订单参数
                params = {
                    "instId": instrument_id,
                    "tdMode": "cross",
                    "sz": str(tp["size"])
                }
                
                # 第一个止盈可以带止损（OCO订单）
                if i == 0 and has_valid_stop_loss:
                    # OCO订单（组合止盈止损）
                    params.update({
                        "ordType": "conditional",
                        "tpTriggerPx": str(tp["price"]),
                        "tpOrdPx": str(tp["price"]),
                        "slTriggerPx": str(stop_loss),
                        "slOrdPx": str(stop_loss),
                        "tpTriggerPxType": "last",  # 最新价格触发
                        "slTriggerPxType": "last"   # 最新价格触发
                    })
                else:
                    # 普通条件单（止盈）
                    params.update({
                        "ordType": "conditional",
                        "tpTriggerPx": str(tp["price"]),
                        "tpOrdPx": str(tp["price"]),
                        "tpTriggerPxType": "last"  # 最新价格触发
                    })
                
                # 设置触发方向
                if pos_side == "long":
                    params["side"] = "sell"
                else:
                    params["side"] = "buy"
                params["posSide"] = "net"  # OKX API需要使用'net'作为持仓方向
                
                result = tradeAPI.place_algo_order(**params)
                if result.get('code') != '0':
                    error_msg = result.get('msg', '未知错误')
                    logger.error(f"{'OCO' if i == 0 and has_valid_stop_loss else '条件'}订单下单失败，错误信息：{error_msg}")
                    return {"success": False, "error": error_msg, "response": result}
                
                logger.info(
                    f"{'OCO' if i == 0 and has_valid_stop_loss else '条件'}订单设置成功: " +
                    f"止盈价格={tp['price']}" +
                    (f", 止损价格={stop_loss}" if i == 0 and has_valid_stop_loss else "") +
                    f", 数量={tp['size']} ({tp['lots']} lots)"
                )
                
                results.append({
                    "type": "oco" if i == 0 and has_valid_stop_loss else "conditional",
                    "take_profit_price": tp["price"],
                    "stop_loss_price": stop_loss if i == 0 and has_valid_stop_loss else None,
                    "size": tp["size"],
                    "lots": tp["lots"],
                    "result": result
                })

        if not results:
            return {"success": True, "results": [], "message": "No orders placed"}
            
        return {"success": True, "results": results}
        
    except Exception as e:
        logger.error(f"设置止盈止损失败: {e}")
        return {"success": False, "error": str(e), "response": None}
