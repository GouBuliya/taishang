import okx.Trade as Trade
import okx.Account as Account
import json
import os
import time
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
        auto_cancel: bool - 是否自动撤销未完成的平仓单，默认为True
        
    返回:
        Dict[str, Any] - 平仓结果
    """
    try:
        # 获取持仓信息

        try:
            res = tradeAPI.get_order_list(instId=instrument_id)

            if res.get("code") == "0":
                ordId = res.get("data", [{}])[0].get("ordId", None)
                if ordId:
                    result = tradeAPI.cancel_order(instId=instrument_id, ordId=ordId)
                    if result.get("code") == "0":
                        logger.info(f"成功撤销限价订单 {ordId}")
                    else:
                        logger.error(f"not able to cancel order {ordId}, error: {result.get('msg', '未知错误')}")
            else:
                logger.error(f"获取订单列表失败: {res.get('msg', '未知错误')}")
                

        except Exception as e:
            logger.error(f"获取订单列表过程中发生异常: {str(e)}")
           
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
        # 查找有效持仓（检查cross和isolated模式）
        valid_position = None
        for pos in positions:
            if pos.get("mgnMode") in ["cross", "isolated"]:  # 检查保证金模式
                pos_size = float(pos.get("pos", "0"))
                if pos_size != 0:  # 有效持仓数量不为0
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
        if pos_size == 0:
            logger.error("持仓数量为0")
            return {
                "success": False,
                "error": "持仓数量为0",
                "response": position_result
            }
            
        # 确定平仓方向和数量
        closing_side = "buy" if pos_size < 0 else "sell"
        size_to_close = abs(pos_size if size is None else size)
        
        logger.info(f"当前持仓:{pos_size}, 平仓方向:{closing_side}, 平仓数量:{size_to_close}")

        if auto_cancel:
            try:
                # 撤销所有未完成的普通限价单
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
            except Exception as e:
                logger.error(f"撤销订单过程中发生错误: {str(e)}")
                # 继续执行，不因撤单失败而中断平仓操作

        # 准备平仓参数
        order_params = {
            "instId": instrument_id,
            "tdMode": valid_position.get("mgnMode", "cross"),  # 使用持仓的保证金模式
            "side": closing_side,
            "ordType": "market",  # 使用市价单
            "sz": str(size_to_close)
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

@retry_on_error(max_retries=3, delay=1.0)
def set_tp_sl(
    instrument_id: str,
    order_detail: Dict[str, Any]
) -> Dict[str, Any]:
    """
    根据订单详情设置止盈止损
    
    参数:
        instrument_id: str - 交易对ID
        order_detail: Dict[str, Any] - 订单详情，包含止盈止损信息
        
    返回:
        Dict[str, Any] - 设置结果
    """
    try:
        # 1. 获取当前持仓信息以确定方向
        position_result = accountAPI.get_positions(
            instType="SWAP",
            instId=instrument_id
        )
        
        if position_result.get("code") != "0":
            return {
                "success": False,
                "error": f"获取持仓信息失败: {position_result.get('msg', '未知错误')}",
                "response": position_result
            }
            
        positions = position_result.get("data", [])
        valid_position = None
        for pos in positions:
            if pos.get("mgnMode") in ["cross", "isolated"]:
                pos_size = float(pos.get("pos", "0"))
                if pos_size != 0:
                    valid_position = pos
                    break
                    
        if not valid_position:
            return {
                "success": False,
                "error": "未找到有效持仓",
                "response": None
            }
        
        # 2. 确定持仓方向
        pos_size = float(valid_position.get("pos", "0"))
        position_side = "long" if pos_size > 0 else "short"
        
        # 3. 提取止盈止损信息
        stop_loss = order_detail.get("stop_loss")
        take_profits = order_detail.get("take_profit", [])
        
        if not stop_loss or not take_profits:
            return {
                "success": False,
                "error": "缺少止盈止损信息",
                "response": None
            }
            
        # 4. 准备触发价格和数量列表
        trigger_prices = [tp["price"] for tp in take_profits]
        sizes = [float(tp["size"]) for tp in take_profits]
        
        # 验证数量总和
        total_size = sum(sizes)
        if abs(total_size - float(order_detail.get("size", 0))) > 0.01:  # 允许0.01的误差
            logger.warning(f"止盈订单总量 {total_size} 与原始订单量 {order_detail.get('size')} 不匹配")
        
        # 5. 设置分批止盈和止损订单
        results = []
        success_count = 0
        
        # 确定订单方向
        tp_side = "sell" if position_side == "long" else "buy"
        sl_side = "sell" if position_side == "short" else "buy"
        
        # 设置分批止盈
        for price, size in zip(trigger_prices, sizes):
            tp_params = {
                "instId": instrument_id,
                "tdMode": valid_position.get("mgnMode", "cross"),
                "ordType": "conditional",
                "side": tp_side,
                "posSide": position_side,
                "triggerPx": str(price),
                "sz": str(size),
                "tpTriggerPxType": "last",
                "tpOrdPx": "-1"  # 市价止盈
            }
            
            result = tradeAPI.place_order(**tp_params)
            results.append(result)
            
            if result.get("code") == "0":
                success_count += 1
                logger.info(f"设置止盈成功 - 价格: {price}, 数量: {size}")
            else:
                logger.error(f"设置止盈失败 - 价格: {price}, 错误: {result.get('msg', '未知错误')}")
        
        # 设置止损
        sl_params = {
            "instId": instrument_id,
            "tdMode": valid_position.get("mgnMode", "cross"),
            "ordType": "conditional",
            "side": sl_side,
            "posSide": position_side,
            "triggerPx": str(stop_loss),
            "sz": str(total_size),
            "tpTriggerPxType": "last",
            "tpOrdPx": "-1"  # 市价止损
        }
        
        sl_result = tradeAPI.place_order(**sl_params)
        results.append(sl_result)
        
        if sl_result.get("code") == "0":
            success_count += 1
            logger.info(f"设置止损成功 - 价格: {stop_loss}, 数量: {total_size}")
        else:
            logger.error(f"设置止损失败 - 价格: {stop_loss}, 错误: {sl_result.get('msg', '未知错误')}")
        
        # 返回设置结果
        all_success = success_count == len(trigger_prices) + 1
        return {
            "success": all_success,
            "message": f"设置{'成功' if all_success else '部分成功'}，成功 {success_count}/{len(trigger_prices) + 1} 个订单",
            "response": results
        }
        
    except Exception as e:
        logger.error(f"设置止盈止损时发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }

@retry_on_error(max_retries=3, delay=1.0)
def place_order_with_tp_sl(
    instrument_id: str,
    side: str,
    size: float,
    price: Optional[float] = None,
    leverage: int = 100,
    order_type: str = "limit",
    tdMode: str = "cross",
    stop_loss: Optional[float] = None,
    take_profits: Optional[list] = None,
) -> Dict[str, Any]:
    """
    一次性完成开仓和设置止盈止损的函数
    
    参数:
        instrument_id: str - 交易对ID
        side: str - 交易方向 ("long"/"short")
        size: float - 下单数量
        price: Optional[float] - 下单价格（市价单可不传）
        leverage: int - 杠杆倍数，默认100
        order_type: str - 订单类型 ("limit"/"market")
        tdMode: str - 交易模式 ("cross"/"isolated")
        stop_loss: Optional[float] - 止损价格
        take_profits: Optional[list] - 止盈列表，格式如：[{"price": float, "size": float}, ...]
        
    返回:
        Dict[str, Any] - 下单结果
    """
    try:
        # 1. 执行主要订单
        main_order_result = place_order(
            instrument_id=instrument_id,
            side=side,
            size=size,
            price=price,
            leverage=leverage,
            order_type=order_type,
            tdMode=tdMode
        )
        
        if not main_order_result.get("success"):
            return main_order_result
            
        # 2. 如果没有止盈止损设置，直接返回主订单结果
        if not stop_loss and not take_profits:
            return main_order_result

        # 3. 获取订单ID
        order_id = main_order_result.get("order_id")
        if not order_id:
            return {
                "success": False,
                "main_order": main_order_result,
                "error": "未能获取订单ID",
                "message": "主订单成功但未返回订单ID"
            }

        # 4. 等待订单成交（市价单跳过此步）
        if order_type == "limit":
            max_retries = 5
            retry_delay = 2.0
            for i in range(max_retries):
                order_info = tradeAPI.get_order(instId=instrument_id, ordId=order_id)
                if order_info.get("code") == "0" and order_info.get("data"):
                    order_data = order_info["data"][0]
                    state = order_data.get("state")
                    if state == "filled":
                        logger.info("限价单已完全成交")
                        break
                    elif state == "canceled":
                        return {
                            "success": False,
                            "main_order": main_order_result,
                            "error": "订单已被取消",
                            "message": "主订单被取消，不设置止盈止损"
                        }
                        
                if i < max_retries - 1:
                    logger.info(f"等待订单成交，{retry_delay}秒后重试...")
                    time.sleep(retry_delay)
            else:
                logger.warning("订单未完全成交，继续设置止盈止损")

        # 5. 等待持仓确认
        max_retries = 5
        retry_delay = 2.0
        for i in range(max_retries):
            # 获取持仓信息
            position_result = accountAPI.get_positions(
                instType="SWAP",
                instId=instrument_id
            )
            
            if position_result.get("code") == "0":
                positions = position_result.get("data", [])
                valid_position = None
                for pos in positions:
                    if pos.get("mgnMode") in ["cross", "isolated"]:
                        pos_size = float(pos.get("pos", "0"))
                        if pos_size != 0:
                            valid_position = pos
                            break
                            
                if valid_position:
                    logger.info(f"已确认持仓建立，开始设置止盈止损")
                    break
            
            if i < max_retries - 1:
                logger.info(f"等待持仓确认，{retry_delay}秒后重试...")
                time.sleep(retry_delay)
        else:
            return {
                "success": False,
                "main_order": main_order_result,
                "tp_sl_orders": {
                    "success": False,
                    "error": "等待持仓确认超时",
                    "response": None
                },
                "message": "主订单：成功, 止盈止损：失败（等待持仓确认超时）"
            }
            
        # 6. 构造止盈止损订单详情
        tp_sl_detail = {
            "type": "close",
            "price": price,
            "size": size,
            "stop_loss": stop_loss,
            "take_profit": take_profits
        }
        
        # 7. 设置止盈止损
        tp_sl_result = set_tp_sl(instrument_id, tp_sl_detail)
        
        # 8. 合并结果
        return {
            "success": main_order_result.get("success") and tp_sl_result.get("success"),
            "main_order": main_order_result,
            "tp_sl_orders": tp_sl_result,
            "message": f"主订单：{'成功' if main_order_result.get('success') else '失败'}, " + \
                      f"止盈止损：{'成功' if tp_sl_result.get('success') else '失败'}"
        }
        
    except Exception as e:
        logger.error(f"下单及设置止盈止损时发生异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }
