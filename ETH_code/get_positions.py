import okx.Account as Account
import json
import sys
import os
import logging

config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["ETH_log_path"]
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
    avail_eq_value = res['data'][0]['details'][0]['availEq']
    #保留两位小数,防止TypeError: type str doesn't define __round__ method
    avail_eq_value = round(float(avail_eq_value), 2)
    ans = {}
    ans["Available_Margin"]=str(avail_eq_value)+" USDT"#可用保证金
    ans=json.dumps(ans,indent=4,ensure_ascii=False)
    return ans



def get_positions(instrument_id:str=None):#持仓
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


    ans=json.dumps(ans,indent=4,ensure_ascii=False)
    # logger.info(res)
    return ans
   
def main(instrument_id="ETH-USDT-SWAP"):
    logger.info(f"instrument_id: {instrument_id}")
    res={}
    res["instrument_id"]=instrument_id
    res["balance"]=json.loads(get_balance())
    res["positions"]=json.loads(get_positions(instrument_id))
    res=json.dumps(res,indent=4,ensure_ascii=False)
    return res
if __name__ == "__main__":
    #传入instrument_id
    res=main()
    print(res)