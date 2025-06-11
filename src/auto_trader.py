import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional, Union, cast
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from function.trade.place_order import (
    place_order,
    close_position,
    cancel_all_pending_orders,
    get_current_position,
    get_order_all
)
from function.trade.trade_history import TradeHistory

# 日志配置
def setup_logger():
    log_path = os.path.join(project_root, "logs/trade_auto.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='[AutoTrade][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(log_path, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )
    return logging.getLogger("AutoTrade")

logger = setup_logger()

# 创建交易记录器
trade_history = TradeHistory(os.path.join(project_root, "logs/trade_history.json"))

class AutoTrader:
    def execute_trades(self, execution_details: List[Dict[str, Any]]) -> None:
        """执行交易指令"""
        for idx, detail in enumerate(execution_details):
            logger.info(f"执行第{idx+1}条交易指令: {detail}")
            
            try:
                instrument_id = detail.get('instId', 'ETH-USDT-SWAP')
                if detail.get('side') == 'wait':
                    logger.info(f"跳过等待指令: {detail}")
                    break
                # 处理平仓操作
                if detail['position_action'] == 'close_position' or detail['side'] == 'close':
                    # 1. 首先尝试撤销所有挂单
                    try:
                        cancel_result = cancel_all_pending_orders(instrument_id)
                        logger.info(f"撤销所有挂单结果: {cancel_result}")
                    except Exception as e:
                        logger.warning(f"撤销挂单失败，继续执行市价平仓: {e}")
                    
                    # 2. 获取当前持仓信息以确定平仓方向
                    position_info = get_current_position(instrument_id)
                    # logger.info(f"获取持仓信息: {json.dumps(position_info, indent=4, ensure_ascii=False)}")
                    if not position_info['success']:
                        logger.error("获取持仓信息失败，无法执行平仓操作")
                        continue
                        
                    if position_info['position'] == 0:
                        logger.info("当前没有持仓，跳过平仓操作")
                        continue
                        
                    position_side = 'buy' if position_info['position'] > 0 else 'sell'
                    position_size = abs(position_info['position'])
                    
                    # 3. 执行市价平仓
                    result = close_position(
                        instrument_id=instrument_id,
                        posSide='short' if position_side else "long",
                        size=None,  # size=None 表示全部平仓
                        price=None ,
                         # price=None 表示市价单
                    )
                    logger.info(f"平仓结果: {result}")
                    # 记录平仓交易
                    trade_history.add_trade(
                        instrument_id=instrument_id,
                        side=position_side,  # 使用从持仓信息中获取的方向
                        size=position_size,  # 使用从持仓信息中获取的数量
                        price=-1,  # 市价单价格为-1
                        order_type='market',
                        order_id=result.get('response', {}).get('ordId', ''),
                        extra_info={
                            'position_action': 'close_position',
                            'trade_type': 'close',
                            'operation_comment': detail.get('operation_comment', ''),
                            'force_market_close': True  # 标记这是一个强制市价平仓操作
                        }
                    )
                else:
                    # 处理开仓操作
                    size_str = str(detail.get('size', 0)) if detail.get('size') not in ["N/A", "dynamic_calculation_needed"] else "0"
                    size = float(size_str)
                    
                    order_params = {
                        'instrument_id': instrument_id,
                        'tdMode': 'isolated',
                        'side': detail['side'] ,# 修正交易方向
                        'posSide': detail['posSide'],
                        'order_type': 'market' if detail.get('market', False) else 'limit',
                        'size': size,
                        'take_profit': detail.get('take_profit', None),
                        'stop_loss': detail.get('stop_loss', None),
                        'market': detail.get('market', False)
                    }
                    
                    price = None
                    if not detail.get('market', False) and detail.get('price') not in ["N/A", None]:
                        price = float(detail['price'])
                        order_params['price'] = price
                        
                    result = place_order(**order_params)
                    logger.info(f"下单结果: {result}")
                    
                    if result.get('success'):
                        # 记录开仓交易
                        trade_history.add_trade(
                            instrument_id=instrument_id,
                            side=order_params['side'],
                            size=size,
                            price=price if price else 0.0,  # 市价单时价格为0
                            order_type=order_params['order_type'],
                            order_id=result.get('response', {}).get('ordId', ''),
                            stop_loss=float(detail['stop_loss']) if detail.get('stop_loss') not in ["N/A", None] else None,
                            take_profits=[{
                                'price': float(tp['price']),
                                'size': float(str(tp['size']).rstrip('%')) / 100 if '%' in str(tp['size']) else float(tp['size']),  # 向下取整
                            } for tp in detail.get('take_profit', []) if tp.get('price') != "N/A" and tp.get('size') != "N/A"],
                            extra_info={
                                'position_action': detail.get('position_action'),
                                'trade_type': 'open',
                                'operation_comment': detail.get('operation_comment', '')
                            }
                        )
                        # for tp in detail.get('take_profit', []):
                        #     if tp.get('price') != "N/A" and tp.get('size') != "N/A":
                        #         logger.info(f"tpsize{round(float(str(tp['size']).rstrip('%')) / 100 if '%' in str(tp['size']) else float(tp['size']), 2)  }")

                logger.info(f"交易执行成功: {result}")
                    
            except Exception as e:
                logger.error(f"执行交易失败: {e}")
                continue

def load_gemini_answer():
    """加载交易指令配置"""
    path = os.path.join(project_root, "data/gemini_answer.json")
    if not os.path.exists(path):
        logger.error(f"配置文件不存在: {path}")
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, dict) or 'execution_details' not in data:
            logger.error("配置文件格式错误")
            return None
            
        return data
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return None

def main():
    """主函数"""
    data = load_gemini_answer()
    if data is None:
        logger.error("加载配置文件失败，自动化交易终止。")
        return
        
    execution_details = data.get('execution_details', [])
    if not execution_details:
        logger.warning("未找到交易执行细节，自动化交易终止。")
        return
        
    try:
        trader = AutoTrader()
        trader.execute_trades(execution_details)
    except Exception as e:
        logger.error(f"执行交易失败: {e}")
        return

if __name__ == "__main__":
    main()
