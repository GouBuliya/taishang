import json
import os
import pandas as pd
import logging

def get_latest_transactions(config):
    # 根据 config 动态设置日志文件路径
    log_file_path = config["main_log_path"] # 从传入的 config 中获取日志路径
    
    # 获取当前文件所在的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
 
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.INFO,
        format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(log_file_path, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

    logger = logging.getLogger("GeminiQuant")

    trade_log_path = config['logs']['trade_log_path']
    
    if not os.path.exists(trade_log_path):
        logger.error(f"交易日志文件不存在: {trade_log_path}")
        return json.dumps({"error": f"交易日志文件不存在: {trade_log_path}"})
    
    try:
        with open(trade_log_path, "r", encoding="utf-8") as f:
            trade_log = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"解析交易日志文件失败: {trade_log_path}, 错误: {e}")
        return json.dumps({"error": f"解析交易日志文件失败: {trade_log_path}, 错误: {e}"})
    except Exception as e:
        logger.error(f"读取交易日志文件异常: {trade_log_path}, 错误: {e}")
        return json.dumps({"error": f"读取交易日志文件异常: {trade_log_path}, 错误: {e}"})
    timeframes = ['15m', '1h', '4h']
    result = {}
    
    for timeframe in timeframes:
        # 过滤出对应时间周期的交易记录
        filtered_logs = [log for log in trade_log if log.get('timeframe') == timeframe]
        # 获取最后3条记录
        result[timeframe] = filtered_logs[-3:] if filtered_logs else []
    
    trade_log_json = json.dumps(result, indent=4, ensure_ascii=False)
    logger.info(f"成功获取多个时间周期的交易记录: {trade_log_json}")
    return trade_log_json



