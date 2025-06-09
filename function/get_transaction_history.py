import json
import os
import pandas as pd
import logging

# config=json.load(open("/root/codespace/Qwen_quant_v1/config/config.json","r")) # 移除硬编码的 config 加载

# BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # 稍后调整 BASE_DIR 的使用
# LOG_FILE = "/root/codespace/Qwen_quant_v1/nohup.out" # 移除硬编码的 LOG_FILE

# 修改为函数，接收 config 参数
def get_latest_transactions(config):
    # 根据 config 动态设置日志文件路径
    log_file_path = config["main_log_path"] # 从传入的 config 中获取日志路径
    
    # 获取当前文件所在的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 计算相对于当前文件目录的 LOG_FILE 路径，或者直接使用 config 中提供的绝对路径
    # 这里我们假设 config["main_log_path"] 是一个绝对路径或者可以被直接使用的路径
    # 如果 config["main_log_path"] 是相对路径，需要额外处理，但目前看起来是绝对路径
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 重新配置日志
    # 移除之前的 logging.basicConfig，因为它可能在其他地方被配置
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=logging.INFO,
        format='[%(filename)s][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(log_file_path, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

    logger = logging.getLogger("GeminiQuant")

    # 获取 trade_log_path
    trade_log_path = config['logs']['trade_log_path']
    
    # 确保 trade_log_path 存在且可读
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

    # 按时间周期分组并获取最后3条交易纪录
    timeframes = ['15m', '1h', '4h']
    result = {}
    
    for timeframe in timeframes:
        # 过滤出对应时间周期的交易记录
        filtered_logs = [log for log in trade_log if log.get('timeframe') == timeframe]
        # 获取最后3条记录
        result[timeframe] = filtered_logs[-3:] if filtered_logs else []
    
    # 转化为json
    trade_log_json = json.dumps(result, indent=4, ensure_ascii=False)
    logger.info(f"成功获取多个时间周期的交易记录: {trade_log_json}")
    return trade_log_json



