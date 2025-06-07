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
        level=logging.WARNING,
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

    ans={}
    ans['instrument_id']=instrument_id  #标的

    if not res or res.get('code') != '0' or not res.get('data'):
        # 如果返回数据为空，或者code不是0，或者data列表为空
        ans['Margin_Model']= "N/A" # 保证金模式
        ans['Position direction']= "N/A" # 持仓方向
        ans['pos']= "0" # 持仓数量
        ans['avgPrice']= "N/A" # 平均开仓价格
        ans['Unrealized Gains']= "N/A" # 未实现盈亏
        ans['liqPrice']= "N/A" # 强平价格
        ans['lever']= "N/A" # 杠杆倍数
        logger.info(f"未获取到 {instrument_id} 的持仓信息或持仓列表为空。")
    else:
        # 如果data列表不为空，则正常解析持仓信息
        # 注意：OKX API的持仓接口可能返回多个持仓（例如多仓和空仓），这里只取第一个作为示例
        # 实际应用中可能需要遍历data列表处理所有持仓
        position_data = res['data'][0]
        ans['Margin_Model']=position_data.get('mgnMode', "N/A") #保证金模式
        ans['Position direction']=position_data.get('posSide', "N/A") #持仓方向   #多头:long,空头:short

        ans['pos']=str(position_data.get('pos', "0"))+ " piece" #持仓数量（单位：张（英文））

        ans['avgPrice']=str(position_data.get('avgPx', "N/A"))+ " USDT" #平均开仓价格
        ans['Unrealized Gains']=str(position_data.get('upl', "N/A"))+ " USDT" #未实现盈亏
        ans['liqPrice']=str(position_data.get('liqPx', "N/A"))+ " USDT" #强平价格
        ans['lever']=str(position_data.get('lever', "N/A"))+ " x" #杠杆倍数
        logger.info(f"成功获取到 {instrument_id} 的持仓信息。")
    return ans
   
#获取未成交订单
def get_orders(instrument_id:str=""):

    tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)

    res = tradeAPI.get_order_list(instId=instrument_id)
    ans={}
    logger.info(f"res: {json.dumps(res,indent=4,ensure_ascii=False)}")

    # Check if the response is successful and contains data
    if res and res.get('code') == '0' and res.get('data') and len(res['data']) > 0:
        # Assuming only the first order is needed as per previous structure
        
        order_data = res['data'][0]
        ans['size'] = order_data.get('sz', "N/A")  # 订单数量
        ans['price'] = order_data.get('px', "N/A")  # 订单价格
        ans['lever'] = order_data.get('lever', "N/A")  # 杠杆倍数
        ans['direction'] = order_data.get('side', "N/A")  # 订单方向
        ans['status'] = order_data.get('state', "N/A")  # 订单状态
        # You might want to add order ID or other relevant fields here
        # ans['ordId'] = order_data.get('ordId', "N/A")
        logger.info(f"成功获取到 {instrument_id} 的挂单信息。")
    else:
        # If no pending orders or error in response
        ans['size'] = "N/A"
        ans['price'] = "N/A"
        ans['lever'] = "N/A"
        ans['direction'] = "N/A"
        ans['status'] = "N/A"
        # ans['ordId'] = "N/A"
        logger.info(f"未获取到 {instrument_id} 的挂单信息或挂单列表为空。")
    
    ans["algo_orders"] = {} # 新增一个键用于存储策略订单信息
    res_algo=tradeAPI.order_algos_list(instId=instrument_id) 
    if res_algo and res_algo.get('code') == '0' and res_algo.get('data') and len(res_algo['data']) > 0:
        algo_data=res_algo['data'][0]
        ans["algo_orders"]['instId']=algo_data.get('instId', "N/A")#策略id
        ans["algo_orders"]['algo_state']=algo_data.get('state', "N/A")#策略状态
        ans["algo_orders"]['algo_type']=algo_data.get('type', "N/A")#策略类型
        ans["algo_orders"]['algo_trigger_price']=algo_data.get('triggerPx', "N/A")#触发价格
        logger.info(f"成功获取到 {instrument_id} 的策略挂单信息。")
    else:
        logger.info(f"未获取到 {instrument_id} 的策略挂单信息或策略挂单列表为空。")
        
    return ans


def collect_positions_data(instrument_id="ETH-USDT-SWAP"):
    logger.info(f"instrument_id: {instrument_id}")
    res={}
    res["instrument_id"]=instrument_id

    # 使用 ThreadPoolExecutor 并行收集数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Store futures and their corresponding task names and start times
        futures = {}
        start_times = {}

        start_times["balance"] = time.time()
        futures[executor.submit(get_balance)] = "balance"

        start_times["positions"] = time.time()
        futures[executor.submit(get_positions, instrument_id)] = "positions"

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
    res=collect_positions_data()
    print(json.dumps(res,indent=4,ensure_ascii=False))
    end_time=time.time()
    logger.warning(f"数据收集完成，耗时: {end_time - start_time} 秒")