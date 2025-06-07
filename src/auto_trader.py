import json
import logging
import os
import sys
from typing import Dict, Any, List
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from function.trade.place_order import place_order
from function.trade.tp_sl import set_take_profit_stop_loss
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

def load_gemini_answer():
    """加载交易指令配置"""
    path = os.path.join(project_root, "data/gemini_answer.json")
    if not os.path.exists(path):
        logger.error(f"配置文件不存在: {path}")
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 验证配置文件结构
        if not isinstance(data, dict):
            logger.error("配置文件格式错误: 必须是JSON对象")
            return None
            
        # 验证必要字段
        if 'execution_details' not in data:
            logger.error("配置文件缺少必要字段: execution_details")
            return None
            
        # 验证execution_details结构
        execution_details = data['execution_details']
        if not isinstance(execution_details, list):
            logger.error("execution_details必须是数组")
            return None
            
        # 验证每个交易指令
        for idx, detail in enumerate(execution_details):
            if not isinstance(detail, dict):
                logger.error(f"第{idx+1}条交易指令格式错误")
                return None
                
            # 检查必要字段
            required_fields = ['type', 'size', 'price']
            missing_fields = [field for field in required_fields if field not in detail]
            if missing_fields:
                logger.error(f"第{idx+1}条交易指令缺少必要字段: {', '.join(missing_fields)}")
                return None
                
        return data
    except json.JSONDecodeError:
        logger.error("配置文件JSON格式错误")
        return None
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return None

def execute_trades(execution_details):
    """执行交易指令"""
    for idx, detail in enumerate(execution_details):
        logger.info(f"执行第{idx+1}条交易指令: {detail}")
        try:
            # 检查是否为等待指令
            if detail.get("type") == "wait":
                logger.info("收到等待指令，跳过交易执行")
                # 记录等待指令到交易历史
                trade_history.add_trade(
                    instrument_id=detail.get("symbol", "ETH-USDT-SWAP"),
                    side="wait",
                    size=0,
                    price=0,
                    order_type="wait",
                    order_id="wait",
                    stop_loss=None,
                    take_profits=None,
                    extra_info={
                        "operation_comment": detail.get("operation_comment"),
                        "expected_winrate": detail.get("expected_winrate"),
                        "expected_return": detail.get("expected_return"),
                        "trade_RR_ratio": detail.get("trade_RR_ratio"),
                        "signal_strength": detail.get("signal_strength"),
                        "risk_assessment": detail.get("risk_assessment"),
                        "position_action": detail.get("position_action")
                    }
                )
                continue

            # 获取交易对名称，默认使用ETH-USDT-SWAP
            instrument_id = detail.get("symbol", "ETH-USDT-SWAP")
            
            # 处理订单类型和方向
            order_type = "market" if detail.get("market") or detail.get("type") == "close" else "limit"
            if detail.get("type") == "close":
                pos_side = "close"
            else:
                pos_side = "long" if detail["type"] == "buy" else "short"
            
            # 兼容place_order参数
            order_args = {
                "instrument_id": instrument_id,
                "side": pos_side,
                "size": detail["size"],
                "price": detail["price"],
                "order_type": order_type
            }

            # 执行下单
            result = place_order(**order_args)
            logger.info(f"下单结果: {result}")
            
            if result["success"]:
                # 记录交易
                size = 0
                price = 0
                
                try:
                    if str(detail["size"]).upper() != "N/A":
                        size = float(detail["size"])
                except (TypeError, ValueError):
                    logger.warning(f"无效的订单数量: {detail['size']}")
                    
                try:
                    if str(detail["price"]).upper() != "N/A":
                        price = float(detail["price"])
                except (TypeError, ValueError):
                    logger.warning(f"无效的订单价格: {detail['price']}")
                
                trade_history.add_trade(
                    instrument_id=instrument_id,
                    side=pos_side,
                    size=size,
                    price=price,
                    order_type=order_type,
                    order_id=result["order_id"] or "no_order",
                    stop_loss=detail.get("stop_loss"),
                    take_profits=detail.get("take_profit"),
                    extra_info={
                        "operation_comment": detail.get("operation_comment"),
                        "expected_winrate": detail.get("expected_winrate"),
                        "expected_return": detail.get("expected_return"),
                        "trade_RR_ratio": detail.get("trade_RR_ratio"),
                        "signal_strength": detail.get("signal_strength"),
                        "risk_assessment": detail.get("risk_assessment"),
                        "position_action": detail.get("position_action")
                    }
                )
                
                # 设置止盈止损（仅对开仓订单）
                if pos_side != "close" and (detail.get("stop_loss") or detail.get("take_profit")):
                    tp_sl_result = set_take_profit_stop_loss(
                        instrument_id=instrument_id,
                        pos_side=pos_side,
                        size=size,  # 使用已经转换的size
                        stop_loss=detail.get("stop_loss"),
                        take_profits=detail.get("take_profit")
                    )
                    logger.info(f"止盈止损设置结果: {tp_sl_result}")
            else:
                logger.error(f"下单失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"执行交易指令失败: {e}")
            logger.exception(e)  # 打印详细的异常堆栈

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
        
    execute_trades(execution_details)

if __name__ == "__main__":
    main()
