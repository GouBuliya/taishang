import okx.Trade as Trade
import okx.Account as Account
import json
import os
import time
import logging
from typing import Optional, Dict, Any
from ..utils import retry_on_error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_FILE = os.path.join(BASE_DIR, "logs/trade.log")
CONFIG_FILE = os.path.join(BASE_DIR, "config/config.json")

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
def _set_leverage(instrument_id: str, leverage: int) -> dict:
    """设置杠杆倍数（带重试）"""
    res = accountAPI.set_leverage(
        instId=instrument_id,
        lever=str(leverage),
        mgnMode="isolated",  # 假设使用隔离保证金模式
        posSide="long"  # 假设默认是多头持仓
    )
    logger.info(f"设置杠杆结果: {res}")
    res = accountAPI.set_leverage(
        instId=instrument_id,
        lever=str(leverage),
        mgnMode="isolated",  # 假设使用隔离保证金模式
        posSide="short"  # 假设默认是空头持仓
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
    tdMode: str = "isolated",
    posSide: Optional[str] = None, # 确保这个参数被正确处理
    stop_loss: Optional[float] = None, # 假设这里直接接收stop_loss和take_profit
    take_profit: Optional[list[Dict[str, float]]] = None, # 假设这里直接接收take_profit列表
    **kwargs) -> Dict[str, Any]:
    result = accountAPI.set_position_mode(
    posMode="long_short_mode"
    )

    try:
        set_leverage_result = _set_leverage(
            instrument_id=instrument_id,
            leverage=leverage,
        )
        if set_leverage_result.get("code") != "0":
            logger.error(f"设置杠杆失败: {set_leverage_result}")
            return {
                "success": False,
                "error": "设置杠杆失败",
                "response": set_leverage_result
            }

      
        order_params = {
            "instId": str(instrument_id),
            "tdMode": str(tdMode),
            "side": str(side),
            "posSide": str(posSide), 
            "ordType": str(order_type),
            "sz": str(size),
            "px": str(price) if order_type == "limit" and price is not None else None
        }

        attached_algo_orders_list = []

        if stop_loss is not None:
            attached_algo_orders_list.append({
                "algoOrdType": "SL",
                "slTriggerPx": str(stop_loss),
                "slOrdPx": "-1", 
                "sz": str(size) 
            })

        # 添加止盈订单
        if take_profit: 
            for tp_target in take_profit:
                tp_Ordpx = "-1"  # 默认市价止盈
                tp_price = tp_target.get('price')
                tp_size = tp_target.get('size')
                
                if tp_price is not None and tp_size is not None:
                    # 处理价格百分比
                    if isinstance(tp_price, str) and "%" in tp_price:
                        percentage = float(tp_price.strip('%+-')) / 100  # 移除%和正负号
                        if tp_price.startswith('-'):
                            tp_price = price * (1 - percentage)  # 下跌百分比
                        else:
                            tp_price = price * (1 + percentage)  # 上涨百分比
                    else:
                        tp_price = float(tp_price)  # 转换为浮点数
                        
                    # 处理数量百分比
                    if isinstance(tp_size, str) and "%" in tp_size:
                        # 如果数量是百分比形式（例如：'30%'），计算实际数量
                        percentage = float(tp_size.strip('%')) / 100
                        tp_size = size * percentage  # 基于总持仓量计算

                    attached_algo_orders_list.append({
                        "algoOrdType": "TP",
                        "tpTriggerPx": str(tp_price),
                        "tpOrdPx": tp_Ordpx, # 限价止盈，触发价和委托价通常相同
                        "sz": str(tp_size)
                    })

        # 如果有任何止盈止损订单，则添加到主订单参数中
        if attached_algo_orders_list:
            order_params["attachAlgoOrds"] = attached_algo_orders_list

        logger.info(f"准备下单参数: {order_params}")

        response = tradeAPI.place_order(**order_params)

        # 4. 处理下单结果 (这部分保持不变)
        success = response.get("code") == "0"
        if success:
            order_data = response.get("data", [{}])[0]
            order_id = order_data.get("ordId")
            logger.info(f"下单成功 - ordId: {order_id}")
            return {
                "success": True,
                "order_id": order_id,
                "response": response
            }
        else:
            logger.error(f"下单失败: {response}")
            return {
                "success": False,
                "error": response.get("msg", "Unknown error"),
                "response": response
            }

    except Exception as e:
        logger.error(f"下单过程发生异常: {str(e)}", exc_info=True) # 保持详细日志
        return {
            "success": False,
            "error": str(e),
            "response": None
        }
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
    posSide: Optional[str] = None,  # 确保这个参数被正确处理
    price: Optional[float] = None,
    auto_cancel: bool = True,
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
      
        posSide = posSide or "long"  # 如果未提供posSide，默认使用"long"
        result = tradeAPI.close_positions(
        instId=instrument_id,
        mgnMode="isolated",  # 假设使用隔离保证金模式
        posSide=posSide,  # 使用明确或推断出的posSide
        autoCxl="true"  # 是否自动撤销未完成的平仓单
    )
        logger.info(f"input:{instrument_id, posSide, size, price}")
        return {
            "success": result.get("code") == "0",
            "response": result
        }
    except Exception as e:
        logger.error(f"平仓过程发生异常: {str(e)}", exc_info=True)
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
def cancel_all_orders(instrument_id: str) -> Dict[str, Any]:
    """撤销指定交易对的所有挂单（带重试）
    
    Args:
        instrument_id: 交易对ID，例如：'ETH-USDT-SWAP'
        
    Returns:
        Dict[str, Any]: 撤单结果
        {
            'success': bool,  # 是否成功
            'response': dict  # API 响应数据
        }
    """
    try:
        logger.info(f"正在撤销所有挂单 - {instrument_id}")
        # 使用 cancel_multiple_orders 方法，instType='SWAP' 表示永续合约
        response = tradeAPI.cancel_multiple_orders([
            {
                'instId': instrument_id,
            }
        ])
        success = response.get('code') == '0'
        
        if success:
            logger.info(f"成功撤销所有挂单 - {instrument_id}")
        else:
            logger.warning(f"撤销所有挂单失败 - {instrument_id}, 响应: {response}")
            
        return {
            'success': success,
            'response': response
        }
    except Exception as e:
        logger.error(f"撤销所有挂单时发生错误 - {instrument_id}: {str(e)}")
        return {
            'success': False,
            'response': {'error': str(e)}
        }

@retry_on_error(max_retries=3, delay=1.0)
def cancel_all_pending_orders(instrument_id: str) -> Dict[str, Any]:
    """撤销指定交易对的所有挂单（带重试）
    
    Args:
        instrument_id: str - 交易对ID，例如：'ETH-USDT-SWAP'
        
    Returns:
        Dict[str, Any] - 撤单结果
        {
            'success': bool,  # 是否成功
            'response': dict  # API 响应数据
        }
    """
    try:
        logger.info(f"正在撤销所有挂单 - {instrument_id}")
        
        # 1. 获取所有未完成的订单
        pending_orders = tradeAPI.get_order_list(instId=instrument_id)
        if pending_orders.get('code') != '0':
            logger.warning(f"获取未完成订单失败 - {instrument_id}, 响应: {pending_orders}")
            return {'success': False, 'response': pending_orders}
            
        # 如果没有未完成的订单，直接返回成功
        if not pending_orders.get('data'):
            logger.info(f"没有未完成的订单需要撤销 - {instrument_id}")
            return {'success': True, 'response': {'code': '0', 'msg': 'no pending orders'}}
            
        # 2. 逐个撤销订单
        success_count = 0
        total_orders = len(pending_orders['data'])
        
        for order in pending_orders['data']:
            try:
                cancel_result = tradeAPI.cancel_order(
                    instId=instrument_id,
                    ordId=order['ordId']
                )
                if cancel_result.get('code') == '0':
                    success_count += 1
                    logger.info(f"成功撤销限价订单 {order['ordId']}")
                else:
                    logger.warning(f"撤销订单失败 - ordId: {order['ordId']}, 响应: {cancel_result}")
            except Exception as e:
                logger.error(f"撤销订单时发生错误 - ordId: {order['ordId']}: {str(e)}")
                
        all_cancelled = success_count == total_orders
        if all_cancelled:
            logger.info(f"成功撤销所有挂单 - {instrument_id}")
        else:
            logger.warning(f"部分订单撤销失败 - {instrument_id}, 成功: {success_count}/{total_orders}")
            
        return {
            'success': all_cancelled,
            'response': {
                'code': '0' if all_cancelled else '1',
                'msg': f'cancelled {success_count}/{total_orders} orders',
                'success_count': success_count,
                'total_orders': total_orders
            }
        }
    except Exception as e:
        logger.error(f"撤销所有挂单时发生错误 - {instrument_id}: {str(e)}")
        return {
            'success': False,
            'response': {'error': str(e)}
        }

@retry_on_error(max_retries=3, delay=1.0)
def get_current_position(instrument_id: str) -> Dict[str, Any]:
    """获取指定交易对的当前持仓数量和详细信息
    
    Args:
        instrument_id: str - 交易对ID，例如：'ETH-USDT-SWAP'
        
    Returns:
        Dict[str, Any] - 持仓信息
        {
            'success': bool,  # 是否成功获取持仓信息
            'position': float,  # 持仓数量，正数表示多头，负数表示空头，0表示无持仓
            'response': dict  # API 完整响应数据
        }
    """
    try:
        # 获取持仓信息
        response = accountAPI.get_positions(instType='SWAP', instId=instrument_id)
        if response.get('code') == '0':
            if not response.get('data'):
                logger.info("当前没有持仓")
                return {
                    'success': True,
                    'position': 0.0,
                    'response': response
                }
            
            # 筛选有效持仓
            valid_positions = [
                pos for pos in response['data']
                if (pos.get('instId') == instrument_id and  # 匹配交易对
                    pos.get('pos') not in [None, '', '0'] and  # 持仓量不为空或0
                    pos.get('posSide') != 'net')  # 不是净持仓模式
            ]
            
            if not valid_positions:
                logger.info(f"{instrument_id} 当前没有有效持仓")
                return {
                    'success': True,
                    'position': 0.0,
                    'response': response
                }
            
            # 取最新的有效持仓（按uTime排序）
            position_data = max(valid_positions, key=lambda x: int(x.get('uTime', '0')))
            logger.info(f"获取到持仓信息: {position_data}")
            
            pos = float(position_data.get('pos', '0'))
            if pos == 0:
                return {
                    'success': True,
                    'position': 0.0,
                    'response': response
                }
                
            pos_side = position_data.get('posSide')
            # 根据持仓方向调整数值的正负
            actual_position = pos if pos_side == 'long' else -pos
            
            logger.info(f"当前持仓: {actual_position} ({pos_side})")
            return {
                'success': True,
                'position': actual_position,
                'response': response
            }
            
        logger.error(f"获取持仓信息API调用失败: {response}")
        return {
            'success': False,
            'position': 0.0,
            'response': response
        }
    except Exception as e:
        logger.error(f"获取持仓信息失败 - {instrument_id}: {str(e)}")
        return {
            'success': False,
            'position': 0.0,
            'response': {'error': str(e)}
        }
@retry_on_error(max_retries=3, delay=1.0)
def get_order_all(instrument_id: str) -> Dict[str, Any]:
    """获取指定交易对的所有订单信息
    
    Args:
        instrument_id: str - 交易对ID，例如：'ETH-USDT-SWAP'
        
    Returns:
        Dict[str, Any] - 订单信息
        {
            'success': bool,  # 是否成功获取订单信息
            'orders': list,   # 订单列表
            'response': dict  # API 完整响应数据
        }
    """
    try:
        response = tradeAPI.get_order_list(instId=instrument_id)
        
        if response.get('code') == '0':
            orders = response.get('data', [])
            logger.info(f"成功获取 {len(orders)} 个订单")
            return {
                'success': True,
                'orders': orders,
                'response': response
            }
        else:
            logger.error(f"获取订单信息API调用失败: {response}")
            return {
                'success': False,
                'orders': [],
                'response': response
            }
    except Exception as e:
        logger.error(f"获取订单信息失败 - {instrument_id}: {str(e)}")
        return {
            'success': False,
            'orders': [],
            'response': {'error': str(e)}
        }