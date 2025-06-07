import okx.Trade as Trade
import okx.Account as Account
import json
import os
import logging
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

@retry_on_error(max_retries=3, delay=1.0)
def _get_pending_orders(instrument_id: str) -> dict:
    """获取未完成订单（带重试）"""
    result = tradeAPI.get_order_list(
        instId=instrument_id,
        ordType="limit",  # 只获取限价挂单
        state="live"      # 获取未成交订单
    )
    return result

@retry_on_error(max_retries=3, delay=1.0)
def _cancel_order(instrument_id: str, order_id: str) -> dict:
    """取消订单（带重试）"""
    result = tradeAPI.cancel_order(
        instId=instrument_id,
        ordId=order_id
    )
    return result

def place_order(instrument_id, side, size, price, leverage=100, order_type="limit"):
    """
    下单函数，返回详细下单结果
    :param instrument_id: 交易对ID
    :param side: 方向 (long/short/close/wait)
    :param size: 数量
    :param price: 价格 (限价单必需，市价单可为"N/A")
    :param leverage: 杠杆倍数
    :param order_type: 订单类型 (limit/market)
    """
    try:
        # 对wait类型指令特殊处理
        if side == "wait":
            logger.info("收到wait指令，跳过下单")
            return {
                "success": True,
                "order_id": None,
                "response": "wait_instruction"
            }

        # 验证订单数量
        try:
            size = float(size)
            if size <= 0:
                logger.error("订单数量必须大于0")
                return {"success": False, "error": "订单数量必须大于0", "response": None}
        except (TypeError, ValueError):
            if size != "N/A":  # 允许N/A作为wait指令的size值
                logger.error("无效的订单数量")
                return {"success": False, "error": "无效的订单数量", "response": None}
            return {
                "success": True,
                "order_id": None,
                "response": "wait_instruction"
            }

        # 对close类型指令特殊处理（撤销挂单）
        if side == "close":
            logger.info("收到close指令，执行撤单操作")
            cancel_result = cancel_all_pending_orders(instrument_id)
            return {
                "success": cancel_result["success"],
                "order_id": None,
                "response": cancel_result
            }
        # 对限价单验证价格
        elif order_type == "limit":
            if str(price).upper() == "N/A":  # 如果价格为N/A，转换为市价单
                logger.info("价格为N/A，转换为市价单")
                order_type = "market"
                price = ""
            else:
                try:
                    price = float(price)
                    if price <= 0:
                        logger.error("限价单价格必须大于0")
                        return {"success": False, "error": "限价单价格必须大于0", "response": None}
                    price = str(price)  # 转换为字符串，因为API要求
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

        # 转换side为buy/sell
        if side == "close":
            # 平仓时需要反向操作：多仓平仓=卖出，空仓平仓=买入
            order_side = "sell" if side == "long" else "buy"
        else:
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
            
        logger.info(f"下单成功：方向={order_side}, 价格={price or 'market'}, 数量={size}")
        return {
            "success": True,
            "order_id": result.get('data', [{}])[0].get('ordId', None),
            "response": result
        }
    except Exception as e:
        logger.error(f"下单失败，错误信息：{e}")
        return {"success": False, "error": str(e), "response": None}

def cancel_all_pending_orders(instrument_id: str) -> dict:
    """
    取消指定交易对的所有未完成订单
    :param instrument_id: 交易对ID
    :return: 取消结果
    """
    try:
        # 获取未完成订单
        pending_orders = _get_pending_orders(instrument_id)
        if pending_orders.get('code') != '0':
            logger.error(f"获取未完成订单失败：{pending_orders.get('msg', '')}")
            return {
                "success": False,
                "error": pending_orders.get('msg', ''),
                "response": pending_orders
            }

        orders = pending_orders.get('data', [])
        if not orders:
            logger.info("没有未完成的订单需要取消")
            return {
                "success": True,
                "canceled_orders": [],
                "message": "No pending orders"
            }

        # 取消所有未完成订单
        canceled_orders = []
        for order in orders:
            order_id = order.get('ordId')
            if not order_id:
                continue

            result = _cancel_order(instrument_id, order_id)
            if result.get('code') == '0':
                canceled_orders.append(order_id)
                logger.info(f"成功取消订单 {order_id}")
            else:
                logger.error(f"取消订单 {order_id} 失败：{result.get('msg', '')}")

        return {
            "success": True,
            "canceled_orders": canceled_orders,
            "message": f"Successfully canceled {len(canceled_orders)} orders"
        }

    except Exception as e:
        logger.error(f"取消订单失败：{e}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }
