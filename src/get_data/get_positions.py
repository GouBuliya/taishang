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
    avail_eq_value = res['data'][0]['details'][0]['availEq']
    #保留两位小数,防止TypeError: type str doesn't define __round__ method
    avail_eq_value = round(float(avail_eq_value), 2)
    ans = {}
    ans["Available_Margin"]=str(avail_eq_value)+" USDT"#可用保证金
    return ans



def get_positions(instrument_id:str=""):#持仓
    res = accountAPI.get_positions(instId=instrument_id) # 显式传递 instId 参数给 API 调用

    ans=[]
    for position in res['data']:
        _ans={}
        if position['availPos']:  # 确保只处理指定的 instrument_id
            _ans['instrument_id']=instrument_id  #标的
            position_data = position
            _ans['Position direction'] = position_data.get('posSide', "N/A")  #持仓方向   #多头:long,空头:short
            _ans['pos']=str(position_data.get('availPos', "0"))+ " piece" #持仓数量（单位：张（英文））
            _ans['avgPrice']=str(position_data.get('avgPx', "N/A"))+ " USDT" #平均开仓价格
            _ans['Unrealized Gains']=str(position_data.get('realizedPnl', "N/A"))+ " USDT" #未实现盈亏
            _ans['liqPrice']=str(position_data.get('liqPx', "N/A"))+ " USDT" #强平价格
            _ans['lever']=str(position_data.get('lever', "N/A"))+ " x" #杠杆倍数
            logger.info(f"成功获取到 {instrument_id} 的持仓信息。")
            logger.warning(f"未获取到 {instrument_id} 的持仓信息或持仓列表为空。")
            ans.append(_ans)
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
        "orders": []
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

    return res

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