import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional, Union, cast
from datetime import datetime
# 确保项目根目录在 Python 路径中（避免重复添加）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.append(project_root)

# 从项目根目录加载配置
config_path = os.path.join(project_root, "config/config.json")
with open(config_path, "r") as f:
    Config = json.load(f)

from src.trading.api.place_order import (
    place_order,
    close_position,
    cancel_all_pending_orders,
    get_current_position,
    get_order_all
)
from src.trading.api.trade_history import TradeHistory

# ===================== 日志配置 =====================
# TODO: 将日志配置移至一个中央模块，以避免在多个文件中重复。
# 这样可以确保整个应用程序的日志记录风格一致。
def setup_logger():
    log_path = os.path.join(project_root, Config["main_log_path"])
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
# TODO: 考虑使用依赖注入的方式来提供 TradeHistory 实例，而不是在这里全局创建。
# 这将使 AutoTrader 类更易于测试。
trade_history = TradeHistory(os.path.join(project_root, Config["logs"]["trade_log_path"]))

# TODO: 这个类目前是无状态的，可以考虑将其方法重构为独立的函数。
# 如果未来需要维护状态（如跟踪已执行的订单），则保留类结构是合适的。
class AutoTrader:
    def execute_trades(self, execution_details: List[Dict[str, Any]]) -> bool:
        """执行交易指令"""
        for idx, detail in enumerate(execution_details):
            logger.info(f"执行第{idx+1}条交易指令: {detail}")
            
            try:
                # TODO: instId 应该是一个更明确的参数，或者从更高层传入，而不是在这里硬编码默认值。
                instrument_id = detail.get('instId', 'ETH-USDT-SWAP')
                
                # 检查是否为"等待"指令
                if detail.get('side') == 'wait' or detail.get('position_action') == 'wait':
                    logger.info(f"接收到等待指令，本轮交易执行暂停。")
                    break # 遇到等待指令，直接跳出循环，不执行后续指令

                # 根据 position_action 路由到不同的处理函数
                if detail.get('position_action') == 'close_position' or detail.get('side') == 'close':
                    self._handle_close_position(instrument_id, detail)
                else:
                    self._handle_open_position(instrument_id, detail)

            except Exception as e:
                logger.error(f"执行交易指令 #{idx+1} 时发生未知错误: {e}", exc_info=True)
                continue
        return True

    def _handle_close_position(self, instrument_id: str, detail: Dict[str, Any]):
        """处理平仓操作"""
        logger.info(f"开始处理平仓操作 for {instrument_id}")
        
        # 1. 首先尝试撤销所有相关挂单
        try:
            cancel_result = cancel_all_pending_orders(instrument_id)
            logger.info(f"撤销所有挂单结果: {cancel_result}")
        except Exception as e:
            # 即便撤单失败，也应继续尝试市价平仓，因为这通常是风险控制的关键步骤。
            logger.warning(f"撤销挂单时发生错误，将继续尝试市价平仓: {e}")
        
        # 2. 获取当前持仓信息以确定平仓细节
        position_info = get_current_position(instrument_id)
        if not position_info.get('success'):
            logger.error("获取持仓信息失败，无法执行平仓操作。")
            return False
            
        if position_info.get('position') == 0:
            logger.info("当前没有持仓，无需执行平仓操作。")
            return True
            
        # 3. 执行市价平仓
        # TODO: 从 position_info 中提取平仓方向和数量的逻辑可以封装成一个辅助函数。
        posSide_to_close = 'long' if position_info['position'] > 0 else 'short'
        
        result = close_position(instrument_id=instrument_id, posSide=posSide_to_close)
        logger.info(f"市价平仓结果: {result}")

        # 4. 记录平仓交易
        if result.get('success'):
            trade_history.add_trade(
                instrument_id=instrument_id,
                side='sell' if posSide_to_close == 'long' else 'buy',
                size=abs(position_info['position']),
                price=-1,  # -1 表示市价
                order_type='market_close',
                order_id=result.get('response', {}).get('ordId', 'N/A'),
                extra_info={
                    'position_action': 'close_position',
                    'operation_comment': detail.get('operation_comment', 'N/A'),
                    'raw_api_response': result
                }
            )
            logger.info(f"平仓交易已成功记录。")
        else:
            logger.error(f"平仓失败，API响应: {result}")
            return False
        return True


    def _handle_open_position(self, instrument_id: str, detail: Dict[str, Any]):
        """处理开仓操作"""
        logger.info(f"开始处理开仓操作 for {instrument_id}")

        # 1. 解析和验证参数
        # TODO: 这个参数解析和转换逻辑非常复杂，应该被重构为一个独立的、
        # 易于测试的函数或数据类（Pydantic模型），来负责验证和转换来自AI的数据。
        try:
            size_str = str(detail.get('size', 0))
            if size_str in ["N/A", "dynamic_calculation_needed", "None"]:
                logger.warning(f"订单大小为 '{size_str}'，无法执行开仓。跳过此订单。")
                return True
            size = float(size_str)
            if size <= 0:
                logger.warning(f"订单大小必须为正数，但收到了 {size}。跳过此订单。")
                return True

            price_str = str(detail.get('price'))
            price = float(price_str) if price_str not in ["N/A", "None"] and not detail.get('market') else None

        except (ValueError, TypeError) as e:
            logger.error(f"解析开仓参数失败: {e}. 原始指令: {detail}")
            return True

        # 2. 构建订单参数
        order_params = {
            'instrument_id': instrument_id,
            'tdMode': 'isolated',
            'side': detail.get('side'),
            'posSide': detail.get('posSide'),
            'order_type': 'market' if detail.get('market', False) else 'limit',
            'size': size,
            'price': price,
            'take_profit': detail.get('take_profit'),
            'stop_loss': detail.get('stop_loss'),
            'market': detail.get('market', False)
        }
        
        # 3. 下单
        result = place_order(**order_params)
        logger.info(f"下单结果: {result}")
        
        # 4. 记录开仓交易
        if result.get('success'):
            # TODO: 止盈止损的解析逻辑也应该被封装和简化。
            take_profits_parsed = []
            tp_list = detail.get('take_profit', [])
            if isinstance(tp_list, list):
                 for tp in tp_list:
                    if isinstance(tp, dict) and tp.get('price') not in ["N/A", None] and tp.get('size') not in ["N/A", None]:
                        try:
                            tp_price = float(tp['price'])
                            tp_size_str = str(tp['size'])
                            # 处理百分比或固定大小
                            tp_size = float(tp_size_str.rstrip('%')) / 100 if '%' in tp_size_str else float(tp_size_str)
                            take_profits_parsed.append({'price': tp_price, 'size_ratio': tp_size})
                        except (ValueError, TypeError):
                            logger.warning(f"无法解析止盈设置: {tp}，已忽略。")

            trade_history.add_trade(
                instrument_id=instrument_id,
                side=order_params['side'],
                size=size,
                price=price or -1, # 市价单价格记为-1
                order_type=order_params['order_type'],
                order_id=result.get('response', {}).get('ordId', 'N/A'),
                stop_loss=float(detail['stop_loss']) if detail.get('stop_loss') not in ["N/A", None] else None,
                take_profits=take_profits_parsed,
                extra_info={
                    'position_action': detail.get('position_action', 'open'),
                    'operation_comment': detail.get('operation_comment', 'N/A'),
                    'raw_api_response': result
                }
            )
            logger.info("开仓交易已成功记录。")
        else:
            logger.error(f"开仓失败，API响应: {result}")
            return False
        return True


def load_gemini_answer() -> Optional[Dict[str, Any]]:
    """
    加载并验证来自Gemini的交易指令文件。
    
    Returns:
        Optional[Dict[str, Any]]: 如果文件有效，则返回包含指令的字典，否则返回None。
    """
    # TODO: 应该使用 PathManager 来获取这个路径。
    path = os.path.join(project_root, Config["Controller_answer_path"])
    if not os.path.exists(path):
        logger.error(f"交易指令文件不存在: {path}")
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # TODO: 使用更严格的模式验证（如JSON Schema或Pydantic）来确保数据结构的正确性。
        if not isinstance(data, dict) or 'execution_details' not in data:
            logger.error(f"交易指令文件格式错误，缺少 'execution_details' 键。文件内容: {data}")
            return None
        
        if not isinstance(data['execution_details'], list):
            logger.error(f"'execution_details' 应该是一个列表，但收到了 {type(data['execution_details'])}。")
            return None

        return data
    except json.JSONDecodeError:
        logger.error(f"解析交易指令文件失败，不是有效的JSON格式。文件路径: {path}")
        return None
    except Exception as e:
        logger.error(f"读取或解析交易指令文件时发生未知错误: {e}", exc_info=True)
        return None

def main():
    """主函数"""
    data = load_gemini_answer()
    if data is None:
        logger.error("加载交易指令失败，自动化交易终止。")
        return False

    execution_details = data.get('execution_details', [])
    if not execution_details:
        logger.warning("交易指令为空，本轮无任何操作。")
        return True

    try:
        trader = AutoTrader()
        if not trader.execute_trades(execution_details):
            logger.error("执行交易时发生顶层异常，自动化交易终止。")
            return False
    except Exception as e:
        logger.error(f"执行交易时发生顶层异常: {e}", exc_info=True)
        # 在生产环境中，这里可能需要更复杂的错误处理或通知机制
        return False

if __name__ == "__main__":
    main()
