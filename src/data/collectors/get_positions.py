import okx.Account as Account
import okx.Trade as Trade
import json
import sys
import os
import logging
import time
import concurrent.futures # Import concurrent.futures

config = json.load(open("config/config.json", "r"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]

# 防止重复添加handler
if not logging.getLogger("GeminiQuant").handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

logger = logging.getLogger("GeminiQuant")



# API 初始化    
apikey = config["okx"]["api_key"]
secretkey = config["okx"]["secret_key"]
passphrase = config["okx"]["passphrase"]
flag = config["okx"]["flag"]  # 实盘:0 , 模拟盘:1
accountAPI= Account.AccountAPI(apikey, secretkey, passphrase, False, flag);#账户余额



def get_balance():
    res = accountAPI.get_account_balance()
    # logger.info(f"res: {json.dumps(res,indent=4,ensure_ascii=False)}")
    
    # 获取账户详细信息
    account_data = res['data'][0]
    details = account_data['details'][0]
    
    # 基础数据
    total_eq = float(account_data.get('totalEq', 0))  # 账户总权益
    avail_eq = float(details.get('availEq', 0))      # 可用保证金
    frozen_bal = float(details.get('frozenBal', 0))  # 冻结余额
    ord_frozen = float(details.get('ordFrozen', 0))  # 挂单冻结
    
    # 计算衍生指标
    used_margin = total_eq - avail_eq  # 已用保证金
    margin_ratio = (used_margin / total_eq * 100) if total_eq > 0 else 0  # 保证金使用率
    available_ratio = (avail_eq / total_eq * 100) if total_eq > 0 else 0  # 可用资金比例
    
    ans = {
        "total_equity": round(total_eq, 2),           # 账户总权益
        "available_margin": round(avail_eq, 2),       # 可用保证金
        "used_margin": round(used_margin, 2),         # 已用保证金
        "frozen_balance": round(frozen_bal, 2),       # 冻结余额
        "order_frozen": round(ord_frozen, 2),         # 挂单冻结
        "margin_usage_ratio": round(margin_ratio, 2), # 保证金使用率(%)
        "available_ratio": round(available_ratio, 2), # 可用资金比例(%)
        
        # 风险评估指标
        "risk_level": "低风险" if margin_ratio < 30 else "中风险" if margin_ratio < 60 else "高风险",
        "can_open_position": avail_eq > total_eq * 0.1,  # 是否还能开仓(保留10%缓冲)
        
        # 格式化显示
        "display": {
            "total_equity_display": f"{round(total_eq, 2)} USDT",
            "available_margin_display": f"{round(avail_eq, 2)} USDT",
            "used_margin_display": f"{round(used_margin, 2)} USDT",
            "margin_usage_display": f"{round(margin_ratio, 2)}%"
        }
    }
    return ans



def get_positions(instrument_id:str=""):#持仓
    res = accountAPI.get_positions(instId=instrument_id) # 显式传递 instId 参数给 API 调用

    ans=[]
    total_position_value = 0  # 总持仓价值
    
    for position in res['data']:
        _ans={}
        if position['availPos']:  # 确保只处理指定的 instrument_id
            position_data = position
            
            # 基础数据
            avail_pos = float(position_data.get('availPos', 0))
            avg_price = float(position_data.get('avgPx', 0))
            unrealized_pnl = float(position_data.get('upl', 0))  # 未实现盈亏
            realized_pnl = float(position_data.get('realizedPnl', 0))  # 已实现盈亏
            liq_price = float(position_data.get('liqPx', 0)) if position_data.get('liqPx') else 0
            leverage = float(position_data.get('lever', 1))
            margin = float(position_data.get('margin', 0))  # 保证金
            notional_usd = float(position_data.get('notionalUsd', 0))  # 名义价值USD
            
            # 计算衍生指标
            position_value = avail_pos * avg_price if avg_price > 0 else 0
            total_position_value += abs(position_value)
            
            # 盈亏比例
            pnl_ratio = (unrealized_pnl / margin * 100) if margin > 0 else 0
            
            # 距离强平价格的安全边距
            current_price = float(position_data.get('markPx', avg_price))  # 标记价格
            if liq_price > 0 and current_price > 0:
                if position_data.get('posSide') == 'long':
                    liquidation_distance = ((current_price - liq_price) / current_price * 100)
                else:  # short
                    liquidation_distance = ((liq_price - current_price) / current_price * 100)
            else:
                liquidation_distance = 0
            
            # 风险评估
            risk_level = "低风险"
            if liquidation_distance < 10:
                risk_level = "高风险"
            elif liquidation_distance < 30:
                risk_level = "中风险"
            
            _ans = {
                'instrument_id': instrument_id,
                'position_side': position_data.get('posSide', "N/A"),  # 持仓方向
                'position_size': avail_pos,  # 持仓数量
                'avg_price': avg_price,  # 平均开仓价格
                'current_price': current_price,  # 当前标记价格
                'unrealized_pnl': unrealized_pnl,  # 未实现盈亏
                'realized_pnl': realized_pnl,  # 已实现盈亏
                'liquidation_price': liq_price,  # 强平价格
                'leverage': leverage,  # 杠杆倍数
                'margin': margin,  # 保证金
                'notional_value': notional_usd,  # 名义价值
                'position_value': position_value,  # 持仓价值
                
                # 风险指标
                'pnl_ratio': round(pnl_ratio, 2),  # 盈亏比例(%)
                'liquidation_distance': round(liquidation_distance, 2),  # 距离强平距离(%)
                'risk_level': risk_level,  # 风险等级
                
                # 格式化显示
                'display': {
                    'position_display': f"{avail_pos} 张",
                    'avg_price_display': f"{avg_price} USDT",
                    'unrealized_pnl_display': f"{unrealized_pnl:+.2f} USDT",
                    'liquidation_price_display': f"{liq_price} USDT",
                    'leverage_display': f"{leverage}x",
                    'pnl_ratio_display': f"{pnl_ratio:+.2f}%",
                    'liquidation_distance_display': f"{liquidation_distance:.1f}%"
                }
            }
            
            logger.info(f"成功获取到 {instrument_id} 的持仓信息。")
            ans.append(_ans)
    
    if not ans:
        logger.warning(f"未获取到 {instrument_id} 的持仓信息或持仓列表为空。")
    
    return ans
   
#获取未成交订单
def get_orders(instrument_id:str=""):
    tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)
    orders = []

    # 1. 获取并处理普通订单
    res = tradeAPI.get_order_list(instId=instrument_id)
    logger.info(f"order:res: {json.dumps(res,indent=4,ensure_ascii=False)}")
    
    if res and res.get('code') == '0' and res.get('data'):
        for order_data in res['data']:
            order_info = {
                'instrument_id': instrument_id,
                'order_type': 'normal',  # 标记为普通订单
                'ordId': order_data.get('ordId', "N/A"),  # 订单ID
                'size': order_data.get('sz', "N/A"),  # 订单数量
                'price': order_data.get('px', "N/A"),  # 订单价格
                'lever': order_data.get('lever', "N/A"),  # 杠杆倍数
                'direction': order_data.get('side', "N/A"),  # 订单方向
                'posSide': order_data.get('posSide', "N/A"),  # 持仓方向
                'status': order_data.get('state', "N/A"),  # 订单状态
                'fillSz': order_data.get('fillSz', "0"),  # 已成交数量
                'avgPx': order_data.get('avgPx', "N/A"),  # 平均成交价格
                'createTime': order_data.get('cTime', "N/A")  # 创建时间
            }
            orders.append(order_info)
        logger.info(f"成功获取到 {instrument_id} 的 {len(orders)} 个普通挂单信息。")
    else:
        logger.info(f"未获取到 {instrument_id} 的普通挂单信息或挂单列表为空。")

    # 2. 获取并处理策略订单（条件单）
    res_algo = tradeAPI.order_algos_list(instId=instrument_id, ordType="conditional")
    logger.info(f"algo_orders:res_algo: {json.dumps(res_algo,indent=4,ensure_ascii=False)}")
    
    if res_algo and res_algo.get('code') == '0' and res_algo.get('data'):
        for algo_data in res_algo['data']:
            algo_order_info = {
                'instrument_id': instrument_id,
                'order_type': 'algo',  # 标记为策略订单
                'algoId': algo_data.get('algoId', "N/A"),  # 策略订单ID
                'ordId': algo_data.get('ordId', "N/A"),  # 订单ID
                'size': algo_data.get('sz', "N/A"),  # 数量
                'posSide': algo_data.get('posSide', "N/A"),  # 持仓方向
                'triggerPrice': algo_data.get('triggerPx', "N/A"),  # 触发价格
                'orderPrice': algo_data.get('orderPx', "N/A"),  # 委托价格
                'status': algo_data.get('state', "N/A"),  # 状态
                # 'type': algo_data.get('type', "N/A"),  # 策略类型
                'direction': algo_data.get('side', "N/A"),  # 方向
                'createTime': algo_data.get('cTime', "N/A")  # 创建时间
            }
            orders.append(algo_order_info)
        logger.info(f"成功获取到 {instrument_id} 的 {len(res_algo['data'])} 个策略订单信息。")
    else:
        logger.info(f"未获取到 {instrument_id} 的策略订单信息或策略订单列表为空。")
    
    return orders
    


# def #获取算法（止盈止损订单）
def collect_positions_data(instrument_id="ETH-USDT-SWAP"):
    logger.info(f"instrument_id: {instrument_id}")
    res = {
        "instrument_id": instrument_id,
        "balance": None,
        "positions": [],
        "orders": [],
        "account_analysis": {}  # 新增账户分析部分
    }

    # 使用 ThreadPoolExecutor 并行收集数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Store futures and their corresponding task names and start times
        futures = {}
        start_times = {}

        # 获取账户余额
        start_times["balance"] = time.time()
        futures[executor.submit(get_balance)] = "balance"

        # 获取持仓信息
        start_times["positions"] = time.time()
        futures[executor.submit(get_positions, instrument_id)] = "positions"

        # 获取订单信息
        start_times["orders"] = time.time()
        futures[executor.submit(get_orders, instrument_id)] = "orders"

        collected_data = {}
        for future in concurrent.futures.as_completed(futures):
            task_name = futures[future]
            try:
                data = future.result()
                collected_data[task_name] = data
                end_time = time.time()
                duration = end_time - start_times[task_name]
                logger.warning(f"{task_name} collection took {duration:.4f} seconds.")
            except Exception as exc:
                logger.error(f'{task_name} generated an exception: {exc}')
                collected_data[task_name] = None # 或者根据需要设置默认值

    res["balance"] = collected_data.get("balance")
    res["positions"] = collected_data.get("positions")
    res["orders"] = collected_data.get("orders")
    
    # 计算账户综合分析
    res["account_analysis"] = calculate_account_analysis(
        collected_data.get("balance"), 
        collected_data.get("positions"), 
        collected_data.get("orders")
    )

    return res

def calculate_account_analysis(balance_data, positions_data, orders_data):
    """计算账户综合分析数据"""
    analysis = {
        "total_positions": 0,
        "total_position_value": 0,
        "total_unrealized_pnl": 0,
        "position_concentration": {},
        "risk_summary": {},
        "trading_activity": {},
        "recommendations": []
    }
    
    if not balance_data or not positions_data:
        return analysis
    
    try:
        total_equity = balance_data.get("total_equity", 0)
        
        # 持仓分析
        total_position_value = 0
        total_unrealized_pnl = 0
        high_risk_positions = 0
        
        for position in positions_data:
            if isinstance(position, dict):
                analysis["total_positions"] += 1
                position_value = abs(position.get("position_value", 0))
                total_position_value += position_value
                total_unrealized_pnl += position.get("unrealized_pnl", 0)
                
                # 风险统计
                if position.get("risk_level") == "高风险":
                    high_risk_positions += 1
        
        analysis["total_position_value"] = round(total_position_value, 2)
        analysis["total_unrealized_pnl"] = round(total_unrealized_pnl, 2)
        
        # 仓位集中度分析
        if total_equity > 0:
            position_ratio = (total_position_value / total_equity * 100)
            analysis["position_concentration"] = {
                "position_to_equity_ratio": round(position_ratio, 2),
                "concentration_level": "高" if position_ratio > 80 else "中" if position_ratio > 50 else "低"
            }
        
        # 风险汇总
        analysis["risk_summary"] = {
            "high_risk_positions": high_risk_positions,
            "margin_usage_ratio": balance_data.get("margin_usage_ratio", 0),
            "overall_risk": balance_data.get("risk_level", "未知"),
            "can_open_new_position": balance_data.get("can_open_position", False)
        }
        
        # 交易活动分析
        pending_orders = len(orders_data) if orders_data else 0
        analysis["trading_activity"] = {
            "pending_orders_count": pending_orders,
            "has_pending_orders": pending_orders > 0
        }
        
        # 生成建议
        recommendations = []
        
        if balance_data.get("margin_usage_ratio", 0) > 70:
            recommendations.append("保证金使用率过高，建议减少仓位或增加资金")
        
        if high_risk_positions > 0:
            recommendations.append(f"有{high_risk_positions}个高风险持仓，建议关注强平风险")
        
        if analysis["position_concentration"].get("concentration_level") == "高":
            recommendations.append("仓位过于集中，建议分散投资降低风险")
        
        if total_unrealized_pnl < -total_equity * 0.1:
            recommendations.append("未实现亏损较大，建议评估止损策略")
        
        if not balance_data.get("can_open_position", False):
            recommendations.append("可用资金不足，暂时无法开新仓")
        
        if not recommendations:
            recommendations.append("账户状态良好，可以正常交易")
        
        analysis["recommendations"] = recommendations
        
    except Exception as e:
        logger.error(f"计算账户分析时发生错误: {e}")
        analysis["error"] = str(e)
    
    return analysis

if __name__ == "__main__":
    #传入instrument_id
    import time
    start_time=time.time()
    res = get_orders
    res = get_positions("ETH-USDT-SWAP")
    res=collect_positions_data()
    print(json.dumps(res,indent=4,ensure_ascii=False))
    end_time=time.time()
    logger.warning(f"数据收集完成，耗时: {end_time - start_time} 秒")