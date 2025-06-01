import okx.Account as Account
import okx.Trade as Trade
import json
import os
import logging
from openai import OpenAI
import time
from typing import List, Dict, Any, Optional
import datetime

#eth交易api

config = json.load(open("/root/codespace/Qwen_quant_v1/config/config.json", "r", encoding="utf-8"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["path"]["log_file"]
logging.basicConfig(
    level=logging.INFO,
    format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
)

logger = logging.getLogger("GeminiQuant")

gemini_answer_path = config["ETH_gemini_answer_path"]
gemini_answer = json.load(open(gemini_answer_path, "r", encoding="utf-8"))
execution = gemini_answer["execution_details"] #为array


# API 初始化
apikey = config["okx"]["api_key"]
secretkey = config["okx"]["secret_key"]
passphrase = config["okx"]["passphrase"]

flag = config["okx"]["flag"]  # 实盘:0 , 模拟盘:1


tradeAPI = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)

accountAPI = Account.AccountAPI(apikey, secretkey, passphrase, False, flag)

# ==================== 带有三级止盈的下单函数 (调整以处理可选TP) ====================

def place_order_with_three_tp(
    instId: str,#合约名称
    tdMode: str,#交易模式
    side: str,#买卖方向
    ordType: str,#订单类型
    sz: str,#下单数量
    px: str,#下单价格
    stop_loss: str,#止损价格
    take_profit: str#止盈价格
):
    # 创建一个 TradeAPI 实例
    #止盈9:1
    trade_client = Trade.TradeAPI(apikey, secretkey, passphrase, False, flag)
    if ordType == "market":
        result = trade_client.place_order(
        instId=instId,
        tdMode=tdMode,
        side=side,
        ordType=ordType,
        sz=sz,
        px=px,
        attachAlgoOrds=[{
            "amendPxOnTriggerType":1,
            "slTriggerPx":stop_loss,
            "slOrdPx":stop_loss,
            "tpTriggerPx":take_profit,
            "tpOrdPx":take_profit+0.01,
            "sz":sz*0.9,
            }]
        )
    else:
        result = trade_client.place_order(
            instId=instId,
        tdMode=tdMode,
        side=side,
        ordType=ordType,
        sz=sz,
        px=px,
        attachAlgoOrds=[{
            "amendPxOnTriggerType":1,
            "slTriggerPx":stop_loss,
            "slOrdPx":stop_loss,
            "tpTriggerPx":take_profit,
            "tpOrdPx":take_profit+0.01,
            "sz":sz*0.9,
            }]
    )
    if result.get("code") == "0":
        logger.info(f"主订单下单成功,")

    else:
        logger.error(f"主订单下单失败: {result}")
        return "error"


def close_position(instId: str, tdMode: str,size: float):
    # 获取当前持仓
    try:
        position_info = accountAPI.get_positions(
            instId=instId,
        )
        # 检查 position_info 是否有效且 data 列表不为空
        if not (position_info and position_info.get('data') and position_info['data']):
            logger.info(f"当前 {instId} 无持仓。")
            return {"status": "info", "message": "当前无持仓"}

    except Exception as e:
        logger.error(f"获取当前持仓失败: {e}")
        return {"status": "error", "message": "获取当前持仓失败"}

    try:
        # 如果pos为正则方向多，如果pos为负则方向空
        # 确保 data[0] 存在 before accessing
        if float(position_info['data'][0]['pos']) > 0:
            position_type = "long"
        elif float(position_info['data'][0]['pos']) < 0:
             position_type = "short"
        else:
             logger.info("当前持仓数量为0，无需平仓。")
             return {"status": "info", "message": "当前持仓数量为0"}

        if position_type == "long":
            logger.info("当前持有多单，准备平仓...")
            # 平仓
            result_ = tradeAPI.place_order(
                instId=instId,
                tdMode=tdMode,
                side="sell",
                ordType="market",
                sz=size,
                px="-1" # 市价平仓价格设为-1
            )
            logger.info(f"多单平仓结果: {result_}")
        elif position_type == "short":
            logger.info("当前持有空单，准备平仓...")
            # 平仓
            result_ = tradeAPI.place_order(
                instId=instId,
                tdMode=tdMode,
                side="buy",
                ordType="market",
                sz=size,
                px="-1" # 市价平仓价格设为-1
            )
            logger.info(f"空单平仓结果: {result_}")

    except Exception as e:
        logger.error(f"执行平仓下单失败: {e}")
        return {"status": "error", "message": "执行平仓下单失败"}

    # 处理挂单（撤单或修改）
    order_info = tradeAPI.get_order_list(instId=instId)
    # 检查 order_info 是否有效且 data 列表不为空
    if not (order_info and order_info.get('data') and order_info['data']):
        logger.info("当前无未成交挂单，无需处理。")
        return {"status": "success", "message": "平仓成功，无挂单需处理"}


    try:
        # 确保 data[0] 存在 before accessing
        first_order = order_info['data'][0]
        order_size = float(first_order['sz'])
        order_id = first_order['ordId']

        if order_size == size:
            # 如果挂单数量等于平仓数量，则全部撤单
            tradeAPI.cancel_order(instId=instId, ordId=order_id)
            logger.info(f"已全部平仓，并撤销挂单 {order_id}")
            return {"status": "success", "message": "全部平仓，已撤销挂单"}
        elif order_size > size:
            # 如果挂单数量大于平仓数量，则修改挂单数量
            new_size = order_size - size
            tradeAPI.amend_order(instId=instId, ordId=order_id, newSz=str(new_size)) # newSz 需要是字符串
            logger.info(f"部分平仓，修改挂单 {order_id} 数量为 {new_size}")
            return {"status": "success", "message": "部分平仓，已修改挂单"}
        else:
             # 挂单数量小于平仓数量，这通常不应该发生，或者需要更复杂的逻辑（例如撤销所有挂单）
             # 为了简单起见，这里只记录警告
             logger.warning(f"挂单数量 ({order_size}) 小于或等于平仓数量 ({size})，请检查逻辑。")
             # 可以选择在这里添加撤销所有挂单的逻辑 if needed
             return {"status": "warning", "message": "部分平仓，挂单数量异常"}


    except Exception as e:
        logger.error(f"处理挂单失败: {e}")
        return {"status": "error", "message": "处理挂单失败"}


def trade_api(execution):
    # trade_api 函数现在负责根据 execution 的 type 调用相应的操作

    order_type = execution["type"]

    if order_type == "buy" or order_type == "sell":
        # 从 execution 中提取下单所需参数

        #如果之前有未成交的订单，自动撤单
        order_info = tradeAPI.get_order_list(instId="ETH-USDT-SWAP")
        logger.info(f"获取未成交订单信息: {order_info}")
        # 检查 order_info 是否有效且 data 列表不为空
        if order_info and order_info.get('data') and order_info['data']:
            cancel_orders_with_orderId=[]
            for order in order_info['data']:
                cancel_orders_with_orderId.append({"instId":"ETH-USDT-SWAP","ordId":order['ordId']})
            cancel_result = tradeAPI.cancel_multiple_orders(cancel_orders_with_orderId)
            logger.info(f"自动撤销未成交订单结果: {cancel_result}")
        else:
             logger.info("当前无未成交订单，无需自动撤单。")


        price = execution["price"]
        size = execution["size"]
        stop_loss = execution["stop_loss"]
        take_profit = execution["take_profit"]

        # 调用 place_order_with_three_tp 函数
        if execution.get("market"):
            logger.info(f"正在下市价 {order_type} 单...")
            place_order_with_three_tp(
                instId="ETH-USDT-SWAP",
                tdMode="cross",
                side=order_type,
                ordType="market",
                sz=size,
                px=price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        else:
            logger.info(f"正在下限价 {order_type} 单，价格 {price}，数量 {size}...")
            place_order_with_three_tp(
                instId="ETH-USDT-SWAP",
                tdMode="cross",
                side=order_type,
                ordType="limit",
                sz=size,
                px=price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        return {"status": "success", "message": "下单成功"}
    elif order_type == "wait":
        logger.info("类型为 wait，不执行交易操作。")
        return {"status": "wait"}

    elif order_type == "close":
        logger.info("类型为 close，执行平仓逻辑。")
        try:
            close_position(
                instId="ETH-USDT-SWAP",
                tdMode="cross",
                size=float(execution.get("size", 0)) # 确保 size 是 float 类型，提供默认值
            )
        except Exception as e:
            logger.error(f"平仓失败: {e}")
            return {"status": "error", "message": "平仓失败"}

        return {"status": "close", "message": "Close logic executed"}

    else:
        logger.warning(f"未知的订单类型: {order_type}，不执行交易操作。")
        return {"error": f"Unknown order type: {order_type}"}


if __name__ == "__main__":

    # 在调用 trade_api 之前，进行格式检查
    # check_format(execution) # check_format 内部会 exit，这里先注释掉方便调试
    # logger.info("格式检查完成")

    # 从 execution 中获取 instId 和 tdMode，用于设置杠杆
    # 注意：execution 中没有直接提供 instId 和 tdMode，这里假设它们是固定的

    accountAPI.set_position_mode(
    posMode="net_mode"
    )# 设置为买卖模式
    instrument_id_for_leverage = "ETH-USDT-SWAP"
    td_mode_for_leverage = "cross"

    # 默认杠杆设置
    leverage = config["okx"]["lever"]
    logger.info(f"正在设置 {instrument_id_for_leverage} 在 {td_mode_for_leverage} 模式下的杠杆为 {leverage} 倍...")

    try:
        set_leverage_result = accountAPI.set_leverage(
            instId=instrument_id_for_leverage,
            lever=leverage,
            mgnMode=td_mode_for_leverage
        )
        # 检查设置杠杆的结果
        if set_leverage_result and set_leverage_result.get('code') == '0':
            logger.info(f"杠杆设置为 {leverage} 倍成功。")
        else:
            logger.error(f"设置杠杆失败: {set_leverage_result}")

    except Exception as e:
        logger.error(f"设置杠杆异常: {e}")
        exit(1)


    # 调用 trade_api 函数执行交易逻辑
    for execution_item in execution:
        trade_result = trade_api(execution_item)
        logger.info(f"trade_result: {trade_result}")
        execution_json = json.dumps(execution_item, indent=4, ensure_ascii=False)
        logger.info(f"execution: {execution_json}")


    logger.info("交易API调用完成")
    # 您可能想在这里根据 trade_result 进行后续处理或输出
    # print(json.dumps(trade_result, indent=2, ensure_ascii=False))

    # --- 将本次操作结果记录到 trade_log.json ---
    trade_log_path = config["path"]["trade_log_path"]
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "execution_details": execution, # 记录用于本次交易的 execution 细节
        "trade_api_result": trade_result # 记录 trade_api 函数的返回结果
    }

    trade_logs = []
    if os.path.exists(trade_log_path) and os.path.getsize(trade_log_path) > 0:
        try:
            with open(trade_log_path, "r", encoding="utf-8") as f:
                trade_logs = json.load(f)
            # Ensure trade_logs is a list if file exists but is not a list of logs
            if not isinstance(trade_logs, list):
                 trade_logs = [trade_logs] # Wrap existing content in a list if not already
        except json.JSONDecodeError:
            logger.error(f"trade_log.json 文件内容无效，初始化为空列表: {trade_log_path}")
            trade_logs = [] # If file is invalid JSON, start with an empty list
        except Exception as e:
            logger.error(f"读取 trade_log.json 文件异常: {e}")
            trade_logs = [] # On other read errors, start with an empty list

    trade_logs.append(log_entry)

    try:
        with open(trade_log_path, "w", encoding="utf-8") as f:
            json.dump(trade_logs, f, indent=4, ensure_ascii=False)
        logger.info(f"交易日志已追加到 {trade_log_path}")
    except Exception as e:
        logger.error(f"写入 trade_log.json 文件异常: {e}")

    # --- 记录结束 ---

        