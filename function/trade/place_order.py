import okx.Trade as Trade
import okx.Account as Account
import json
import os
import logging
from typing import Optional, Dict, Any
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

def place_order(
    instrument_id: str,
    side: str,
    size: float,
    price: Optional[float] = None,
    leverage: int = 100,
    order_type: str = "limit",
    tdMode: str = "cross",  # 新增参数: 交易模式
    **kwargs  # 支持其他可能的参数
) -> Dict[str, Any]:
    """
    下单函数，返回详细下单结果
    
    参数:
        instrument_id: str - 交易对ID
        side: str - 交易方向 ("long"/"short")
        size: float - 下单数量
        price: Optional[float] - 下单价格（市价单可不传）
        leverage: int - 杠杆倍数，默认100
        order_type: str - 订单类型 ("limit"/"market")
        tdMode: str - 交易模式 ("cross"/"isolated")
        **kwargs - 其他可能的参数
        
    返回:
        Dict[str, Any] - 下单结果
    """
    try:
    
        try:
            size = float(size)
            if size <= 0:
                logger.error("订单数量必须大于0")
                return {"success": False, "error": "订单数量必须大于0", "response": None}
        except (TypeError, ValueError):
            logger.error("无效的订单数量")
            return {"success": False, "error": "无效的订单数量", "response": None}

        # 对限价单验证价格
        str_price = None
        if order_type == "limit" and price is not None:
            try:
                float_price = float(price)
                if float_price <= 0:
                    logger.error("限价单价格必须大于0")
                    return {"success": False, "error": "限价单价格必须大于0", "response": None}
                # 转换为字符串，因为API要求
                str_price = str(float_price)
            except (TypeError, ValueError):
                logger.error("无效的价格")
                return {"success": False, "error": "无效的价格", "response": None}

        # 验证交易模式
        if tdMode not in ["cross", "isolated"]:
            logger.warning(f"无效的交易模式 {tdMode}，使用默认值 cross")
            tdMode = "cross"

        # 检查杠杆是否在允许范围内
        try:
            leverage = int(float(leverage))
            if leverage < 1 or leverage > 1000:
                logger.warning(f"杠杆设置超出范围({leverage})，默认使用100倍杠杆")
                leverage = 100
        except (TypeError, ValueError):
            logger.warning(f"无效的杠杆值({leverage})，使用默认值100")
            leverage = 100
            
        # 设置杠杆
        res = _set_leverage(instrument_id, leverage)
        
        # 检查杠杆设置结果
        if res.get('code') != '0':  # 注意：API返回的code是字符串类型
            logger.error(f"设置杠杆失败，错误信息：{res.get('msg', '')}")
            return {"success": False, "error": res.get('msg', ''), "response": res}
        logger.info(f"设置杠杆成功：{leverage}倍")
        
        # 转换side为buy/sell
        order_side = "buy" if side == "long" else "sell"
        
        # 执行下单
        params = {
            "instId": instrument_id,  # 合约ID
            "tdMode": tdMode,        # 交易模式
            "side": order_side,      # 订单方向
            "ordType": "market" if order_type == "market" else "limit",  # 订单类型
            "sz": str(size),         # 数量（API要求字符串类型）
        }
        
        # 限价单需要价格参数
        if order_type == "limit" and str_price is not None:
            params["px"] = str_price

        # 移除None值的参数
        params = {k: v for k, v in params.items() if v is not None}
        
        # 添加其他有效的参数
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value

        logger.debug(f"下单参数: {params}")
        result = _place_order(params)
        
        # 检查下单结果
        if result.get('code') != '0':  # API返回的code是字符串类型
            logger.error(f"下单失败，错误信息：{result.get('msg', '')}")
            return {"success": False, "error": result.get('msg', ''), "response": result}
            
        logger.info(f"下单成功：方向={order_side}, 价格={str_price if str_price else 'market'}, 数量={size}, 交易模式={tdMode}, 杠杆={leverage}倍")
        return {
            "success": True,
            "order_id": result.get('data', [{}])[0].get('ordId', None),
            "response": result
        }
    except Exception as e:
        logger.error(f"下单失败，错误信息：{e}")
        return {"success": False, "error": str(e), "response": None}

@retry_on_error(max_retries=3, delay=1.0)
def cancel_order(instrument_id: str, order_id: str) -> Dict[str, Any]:
    """
    撤销订单函数
    
    参数:
        instrument_id: str - 交易对ID
        order_id: str - 订单ID
        
    返回:
        Dict[str, Any] - 撤单结果
    """
    try:
        result = tradeAPI.cancel_order(instId=instrument_id, ordId=order_id)
        
        if result.get("code") == "0":
            logger.info(f"撤单成功，订单ID: {order_id}")
            return {
                "success": True,
                "response": result
            }
        else:
            error_msg = result.get("msg", "未知错误")
            logger.error(f"撤单失败，错误信息: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "response": result
            }
    except Exception as e:
        logger.error(f"撤单过程发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }

@retry_on_error(max_retries=3, delay=1.0)
def cancel_algo_orders(instrument_id: str, pos_side: Optional[str] = None) -> Dict[str, Any]:
    """
    取消指定交易对的所有止盈止损订单
    
    参数:
        instrument_id: str - 交易对ID
        pos_side: Optional[str] - 可选的持仓方向，如果指定，则只取消该方向的订单
        
    返回:
        Dict[str, Any] - 撤销结果
    """
    try:
        # 查询未完成的止盈止损订单列表
        logger.info(f"开始查询{instrument_id}的未完成止盈止损订单")
        params = {
            "instId": instrument_id
        }
        if pos_side:
            params["posSide"] = pos_side
            
        result = tradeAPI.get_order_list(**params)
        
        if result.get("code") != "0":
            logger.error(f"获取订单列表失败: {result.get('msg', '未知错误')}")
            return {
                "success": False,
                "error": result.get("msg", "获取订单列表失败"),
                "response": result
            }
            
        # 筛选止盈止损订单
        algo_orders = [order for order in result.get("data", [])
                      if order.get("ordType") in ["conditional", "oco"]]
        
        if not algo_orders:
            return {
                "success": True,
                "message": "没有需要撤销的止盈止损订单",
                "response": result
            }
            
        # 批量撤销订单
        success_count = 0
        fail_count = 0
        
        for order in algo_orders:
            cancel_result = tradeAPI.cancel_order(
                instId=instrument_id,
                ordId=order["ordId"]
            )
            
            if cancel_result.get("code") == "0":
                success_count += 1
            else:
                fail_count += 1
                logger.warning(f"撤销订单{order['ordId']}失败: {cancel_result.get('msg')}")
        
        # 返回撤单结果
        total = success_count + fail_count
        if success_count > 0:
            message = f"成功撤销{success_count}/{total}个止盈止损订单"
            if fail_count > 0:
                message += f"，{fail_count}个撤销失败"
            logger.info(message)
            
            return {
                "success": True,
                "message": message,
                "stats": {
                    "total": total,
                    "success": success_count,
                    "failed": fail_count
                }
            }
        else:
            error_msg = f"所有止盈止损订单({total}个)撤销失败"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "stats": {
                    "total": total,
                    "success": 0,
                    "failed": fail_count
                }
            }
            
    except Exception as e:
        logger.error(f"撤销止盈止损订单时发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }

@retry_on_error(max_retries=3, delay=1.0)
def close_position(
    instrument_id: str,
    size: Optional[float] = None,
    price: Optional[float] = None,
    auto_cancel: bool = True
) -> Dict[str, Any]:
    """
    平仓函数，使用市价单或限价单进行平仓
    
    参数:
        instrument_id: str - 交易对ID
        size: Optional[float] - 平仓数量
        price: Optional[float] - 平仓价格，如果不提供则使用市价单
        auto_cancel: bool - 是否自动撤销未完成的平仓单和止盈止损单，默认为True
        
    返回:
        Dict[str, Any] - 平仓结果
    """
    try:
        if size is None or not isinstance(size, (int, float)) or size <= 0:
            logger.error("平仓数量无效")
            return {
                "success": False,
                "error": "平仓数量无效",
                "response": None
            }

        # 首先撤销所有未成交的限价单和止盈止损订单
        logger.info("检查并撤销未成交订单...")
        try:
            # 1. 获取并撤销所有普通限价单
            active_orders = tradeAPI.get_order_list(
                instId=instrument_id,
                state="live"
            )
            
            if active_orders.get("code") == "0" and active_orders.get("data"):
                for order in active_orders["data"]:
                    order_id = order.get("ordId")
                    if order_id:
                        cancel_result = tradeAPI.cancel_order(
                            instId=instrument_id,
                            ordId=order_id
                        )
                        if cancel_result.get("code") == "0":
                            logger.info(f"成功撤销限价订单 {order_id}")
                        else:
                            logger.warning(f"撤销限价订单 {order_id} 失败: {cancel_result.get('msg', '未知错误')}")

            # 2. 获取并撤销所有止盈止损订单
            algo_orders = tradeAPI.order_algos_list(
                instId=instrument_id,
                ordType="conditional,oco"  # 获取条件单和OCO订单
            )
            
            if algo_orders.get("code") == "0" and algo_orders.get("data"):
                for order in algo_orders["data"]:
                    algo_id = order.get("algoId")
                    if algo_id:
                        algo_cancel_params = {
                            "algoId": [algo_id]
                        }
                        cancel_result = tradeAPI.cancel_algo_order(algo_cancel_params)
                        if cancel_result.get("code") == "0":
                            logger.info(f"成功撤销止盈止损订单 {algo_id}")
                        else:
                            logger.warning(f"撤销止盈止损订单 {algo_id} 失败: {cancel_result.get('msg', '未知错误')}")
        except Exception as e:
            logger.error(f"撤销订单过程中发生错误: {str(e)}")
            # 继续执行，不因撤单失败而中断平仓操作
        
        # 获取持仓信息
        position_result = accountAPI.get_positions(
            instType="SWAP",
            instId=instrument_id
        )
        
        if position_result.get("code") != "0":
            logger.error(f"获取持仓信息失败: {position_result.get('msg', '未知错误')}")
            return {
                "success": False,
                "error": position_result.get("msg", "获取持仓信息失败"),
                "response": position_result
            }
            
        # 检查持仓
        positions = position_result.get("data", [])
        if not positions:
            logger.error("没有找到需要平仓的持仓")
            return {
                "success": False,
                "error": "没有找到需要平仓的持仓",
                "response": position_result
            }
        
        # 查找有效持仓
        valid_position = None
        for pos in positions:
            pos_size = float(pos.get("pos", "0"))
            if pos_size != 0:
                valid_position = pos
                break

        if not valid_position:
            logger.error("当前没有持仓")
            return {
                "success": False,
                "error": "当前没有持仓",
                "response": position_result
            }
            
        # 获取当前持仓方向和数量
        pos_size = float(valid_position.get("pos", "0"))
        # 确定平仓方向
        closing_side = "buy" if pos_size < 0 else "sell"
        logger.info(f"当前持仓:{pos_size}, 平仓方向:{closing_side}")
        
        # 准备平仓参数
        order_params = {
            "instId": instrument_id,
            "tdMode": "cross",
            "side": closing_side,
            "ordType": "market",  # 使用市价单
            "sz": str(abs(size))
        }
            
        logger.info(f"执行平仓: {order_params}")
        # 下单平仓
        result = tradeAPI.place_order(**order_params)
        
        if result.get("code") == "0":
            logger.info(f"平仓成功: {result}")
            order_data = result.get("data", [{}])[0]
            return {
                "success": True,
                "order_id": order_data.get("ordId"),
                "message": "平仓订单已提交",
                "response": result
            }
        else:
            error_msg = result.get("msg", "未知错误")
            logger.error(f"平仓失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "response": result
            }
            
    except Exception as e:
        logger.error(f"平仓过程发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }

@retry_on_error(max_retries=3, delay=1.0)
def get_order_info(instrument_id: str, order_id: str) -> Dict[str, Any]:
    """
    获取订单详情
    
    参数:
        instrument_id: str - 交易对ID
        order_id: str - 订单ID
        
    返回:
        Dict[str, Any] - 订单详情
    """
    try:
        result = tradeAPI.get_order(instId=instrument_id, ordId=order_id)
        
        if result.get("code") == "0":
            order_info = result.get("data", [{}])[0]
            return {
                "success": True,
                "order_info": order_info,
                "response": result
            }
        else:
            error_msg = result.get("msg", "未知错误")
            logger.error(f"获取订单详情失败，错误信息: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "response": result
            }
    except Exception as e:
        logger.error(f"获取订单详情过程发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }
