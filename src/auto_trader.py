import json
import logging
import os
import sys
import time
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

# 添加项目根目录到 Python 跻
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from function.trade.place_order import (
    place_order,
    get_order_info,
    close_position,
    place_order_with_tp_sl
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
            
        # 骮证每个交易指令
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
            # 将size字段由字符串转化为数字
            if isinstance(size, str):
                try:
                    if size not in ["N/A", "dynamic_calculation_needed"]:
                        size = float(size)
                except ValueError:
                    logger.error(f"第{idx+1}条交易指令的size字段无法转换为数字: {size}")
                    return None
                    
            if not (isinstance(size, (int, float)) or size in ["N/A", "dynamic_calculation_needed"]):
                logger.error(f"第{idx+1}条交易指令的size字段格式错误: {size}")
                return None
                
            # 更新size字段
            detail["size"] = size

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
            take_profits = []  # 初始化止盈列表
            
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
                trade_history.add_trade(
                    instrument_id=instrument_id,
                    side="close",
                    size=float(detail["size"]),
                    price=price if price is not None else -9999.0,  # 保证为float类型
                    order_type="market" if detail.get("market", False) else "limit",
                    order_id=result.get("order_id", "N/A"),
                    stop_loss=None,  # 平仓操作通常不需要止损
                    take_profits=[],
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

            
            elif position_action == "add_position":
                # 执行加仓操作
                logger.info(f"执行加仓操作")
                side = "long" if trade_type == "buy" else "short"
                leverage = int(float(detail.get("lever", "100")))
                
                # 准备止盈止损信息
                if isinstance(detail.get("take_profit"), list):
                    take_profits = detail["take_profit"]
                elif isinstance(detail.get("take_profit"), (int, float)):
                    # 如果是单个数值，转换为列表格式
                    take_profits = [{"price": float(detail["take_profit"]), "size": float(detail["size"])}]
                
                # 使用新的整合函数下单
                result = place_order_with_tp_sl(
                    instrument_id=instrument_id,
                    side=side,
                    size=float(detail["size"]),
                    price=None if detail.get("market", False) else float(detail["price"]),
                    leverage=leverage,
                    order_type="market" if detail.get("market", False) else "limit",
                    tdMode=detail.get("tdMode", "cross"),
                    stop_loss=detail.get("stop_loss"),
                    take_profits=take_profits
                )
            
            elif position_action == "reduce_position":
                # 执行减仓操作
                logger.info(f"执行减仓操作")
                if not isinstance(detail["size"], (int, float)):
                    logger.error("减仓操作必须指定具体的size")
                    continue
                
                side = "long" if trade_type == "buy" else "short"
                leverage = int(float(detail.get("lever", "100")))
                # 减仓使用常规下单函数，不需要设置止盈止损
                result = place_order(
                    instrument_id=instrument_id,
                    side=side,
                    size=float(detail["size"]),
                    price=None if detail.get("market", False) else float(detail["price"]),
                    leverage=leverage,
                    order_type="market" if detail.get("market", False) else "limit",
                    tdMode=detail.get("tdMode", "cross")
                )
            
            # 处理下单结果
            if isinstance(result, dict):
                # 获取主订单结果
                main_order_success = False
                main_order = None
                if result.get("main_order"):
                    main_order = result["main_order"]
                    main_order_success = main_order.get("success", False)
                else:
                    main_order_success = result.get("success", False)
                    main_order = result
                
                # 获取订单ID
                order_id = None
                if main_order and main_order.get("order_id"):
                    order_id = str(main_order["order_id"])
                
                if main_order_success and order_id:
                    # 记录交易历史
                    if position_action == "add_position":
                        try:
                            # 计算实际价格：市价单使用当前价，限价单使用指定价
                            trade_price = float(detail["price"])
                            if detail.get("market", False) and main_order.get("response", {}).get("data"):
                                fill_px = main_order["response"]["data"][0].get("fillPx")
                                if fill_px:
                                    trade_price = float(fill_px)
                            
                            # 检查止盈止损的设置结果
                            tp_sl_success = (result.get("tp_sl_orders", {}) or {}).get("success", False)
                            
                            # 根据止盈止损设置结果决定记录内容
                            final_stop_loss = (
                                float(detail["stop_loss"]) if tp_sl_success and detail.get("stop_loss") 
                                else None
                            )
                            final_take_profits = take_profits if tp_sl_success else []
                            
                            trade_history.add_trade(
                                instrument_id=instrument_id,
                                side="long" if trade_type == "buy" else "short",
                                size=float(detail["size"]),
                                price=trade_price,
                                order_type="market" if detail.get("market", False) else "limit",
                                order_id=order_id,
                                stop_loss=final_stop_loss,
                                take_profits=final_take_profits,
                                extra_info={
                                    "operation_comment": detail.get("operation_comment"),
                                    "expected_winrate": detail.get("expected_winrate"),
                                    "expected_return": detail.get("expected_return"),
                                    "trade_RR_ratio": detail.get("trade_RR_ratio"),
                                    "signal_strength": detail.get("signal_strength"),
                                    "risk_assessment": detail.get("risk_assessment"),
                                    "position_action": position_action,
                                    "tp_sl_status": "已设置" if tp_sl_success else "未设置",
                                    "tp_sl_error": result.get("tp_sl_orders", {}).get("error") if not tp_sl_success else None
                                }
                            )
                            logger.info(f"交易记录已保存，止盈止损状态: {'已设置' if tp_sl_success else '未设置'}")
                        except Exception as e:
                            logger.error(f"保存交易记录失败: {e}")
                    else:
                        logger.info("非加仓操作，跳过交易记录")
                else:
                    error_msg = result.get("error", "未知错误")
                    logger.error(f"交易失败: {error_msg}")
            
                logger.error(f"交易执行失败或返回结果格式不正确: {result}")
                
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
