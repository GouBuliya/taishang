import json
import logging
import os
import sys
import time
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from function.trade.place_order import (
    place_order,
    get_order_info,
    close_position
)
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
        required_fields = [
            "operation_comment", "type", "price", "stop_loss", "take_profit", 
            "size", "expected_winrate", "expected_return", "trade_RR_ratio", 
            "signal_strength", "position_action", "risk_assessment"
        ]
        valid_types = ["buy", "sell", "wait", "close"]
        valid_position_actions = ["add_position", "reduce_position", "close_position", "maintain_position", "modify_order", "N/A"]
        
        for idx, detail in enumerate(execution_details):
            if not isinstance(detail, dict):
                logger.error(f"第{idx+1}条交易指令格式错误: 必须是字典类型")
                return None
                
            # 检查必要字段
            missing_fields = [field for field in required_fields if field not in detail]
            if missing_fields:
                logger.error(f"第{idx+1}条交易指令缺少必要字段: {', '.join(missing_fields)}")
                return None
                
            # 验证字段类型和值
            trade_type = detail.get("type")
            if trade_type not in valid_types:
                logger.error(f"第{idx+1}条交易指令的type字段无效: {trade_type}, 必须是 {valid_types} 之一")
                return None
                
            # 验证position_action
            position_action = detail.get("position_action")
            if position_action not in valid_position_actions:
                logger.error(f"第{idx+1}条交易指令的position_action字段无效: {position_action}, 必须是 {valid_position_actions} 之一")
                return None
                
            # 根据type和position_action验证其他字段
            if trade_type == "wait":
                if detail.get("price") != "N/A":
                    logger.error(f"第{idx+1}条交易指令type为wait时，price必须为N/A")
                    return None
            elif position_action == "modify_order":
                if not isinstance(detail.get("price"), (int, float)):
                    logger.error(f"第{idx+1}条交易指令position_action为modify_order时，必须指定具体的price")
                    return None
            
            # 验证其他字段
            # 验证数值字段
            price = detail.get("price")
            if trade_type != "wait" and not (isinstance(price, (int, float)) or price == "N/A"):
                logger.error(f"第{idx+1}条交易指令的price字段格式错误: {price}")
                return None
                
            # 验证size字段
            size = detail.get("size")
            if not (isinstance(size, (int, float)) or size in ["N/A", "dynamic_calculation_needed"]):
                logger.error(f"第{idx+1}条交易指令的size字段格式错误: {size}")
                return None
                
            # 验证take_profit字段
            take_profit = detail.get("take_profit")
            if not (take_profit == "N/A" or isinstance(take_profit, list)):
                logger.error(f"第{idx+1}条交易指令的take_profit字段格式错误: {take_profit}")
                return None
                
            if isinstance(take_profit, list):
                for tp in take_profit:
                    if not isinstance(tp, dict) or "price" not in tp or "size" not in tp:
                        logger.error(f"第{idx+1}条交易指令的take_profit数组格式错误: {tp}")
                        return None
                        
            # 验证stop_loss字段
            stop_loss = detail.get("stop_loss")
            if not (isinstance(stop_loss, (int, float)) or stop_loss == "N/A"):
                logger.error(f"第{idx+1}条交易指令的stop_loss字段格式错误: {stop_loss}")
                return None
                
            # 验证其他数值字段
            numeric_fields = ["expected_winrate", "expected_return", "trade_RR_ratio", "signal_strength"]
            for field in numeric_fields:
                value = detail.get(field)
                if not (isinstance(value, (int, float)) or value == "N/A"):
                    logger.error(f"第{idx+1}条交易指令的{field}字段格式错误: {value}")
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
        
        # 获取交易对名称，默认使用ETH-USDT-SWAP
        instrument_id = detail.get("symbol", "ETH-USDT-SWAP")
        position_action = detail.get("position_action")
        trade_type = detail["type"]
        
        # 如果是wait或position_action为maintain_position，跳过交易
        if trade_type == "wait" or position_action == "maintain_position":
            logger.info(f"当前指令为观望或保持仓位，跳过交易执行")
            continue
        
        try:
            result = None
            side = None
            
            if position_action == "close_position" or trade_type == "close":
                # 执行平仓操作
                logger.info(f"执行平仓操作")
                # 处理价格参数
                price = None if detail.get("market", False) else float(detail["price"])
                result = close_position(
                    instrument_id=instrument_id,
                    size=float(detail["size"]),
                    price=price
                )
            
            elif position_action in ["add_position", "reduce_position"]:
                # 开仓或减仓操作
                side = "long" if trade_type == "buy" else "short"
                leverage = int(float(detail.get("lever", "100")))
                
                # 如果是减仓，检查size是否合理
                if position_action == "reduce_position":
                    logger.info(f"执行减仓操作")
                    if not isinstance(detail["size"], (int, float)):
                        logger.error("减仓操作必须指定具体的size")
                        continue
                else:
                    logger.info(f"执行加仓操作")
                
                # 处理价格参数
                price = None if detail.get("market", False) else float(detail["price"])
                order_args = {
                    "instrument_id": instrument_id,
                    "side": side,
                    "size": detail["size"],
                    "price": price,
                    "order_type": "market" if detail.get("market", False) else "limit",
                    "tdMode": detail.get("tdMode", "cross"),
                    "leverage": leverage
                }
                result = place_order(**order_args)
            
            else:
                logger.warning(f"未知的position_action: {position_action}，跳过交易")
                continue

            if not result:
                logger.error("交易结果为空")
                continue

            logger.info(f"交易结果: {result}")

            # 处理交易成功的情况
            if result["success"]:
                order_id = result["order_id"]
                logger.info(f"订单{order_id}已提交成功")
                
                # 只有开仓操作才需要记录交易和设置止盈止损
                if trade_type != "close" and position_action == "add_position" and side:
                    # 记录交易
                    trade_history.add_trade(
                        instrument_id=instrument_id,
                        side=side,  # 这里使用已确定的side
                        size=float(detail["size"]),
                        price=float(detail["price"]),
                        order_type=detail.get("market", "limit"),
                        order_id=order_id,
                        stop_loss=detail.get("stop_loss"),
                        take_profits=detail.get("take_profit"),
                        extra_info={
                            "operation_comment": detail.get("operation_comment"),
                            "expected_winrate": detail.get("expected_winrate"),
                            "expected_return": detail.get("expected_return"),
                            "trade_RR_ratio": detail.get("trade_RR_ratio"),
                            "signal_strength": detail.get("signal_strength"),
                            "risk_assessment": detail.get("risk_assessment"),
                            "position_action": position_action
                        }
                    )
                    
                    # 设置止盈止损（只对新增仓位设置）
                    if detail.get("stop_loss") or detail.get("take_profit"):
                        tp_sl_result = set_take_profit_stop_loss(
                            instrument_id=instrument_id,
                            pos_side=side,  # 这里使用已确定的side
                            size=float(detail["size"]),
                            stop_loss=detail.get("stop_loss"),
                            take_profits=detail.get("take_profit")
                        )
                        logger.info(f"止盈止损设置结果: {tp_sl_result}")
            else:
                logger.error(f"交易失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"执行交易指令失败: {e}")
            continue

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
