# 本文件用于作为主控脚本，依次调用技术指标采集和宏观因子采集脚本，合并输出为标准化JSON，供GUI等模块调用。

import pandas as pd
import datetime
import json
import logging
import os
from okx.api import Market  # type: ignore
import numpy as np # 用于处理NaN值和数值运算
import concurrent.futures # Import concurrent.futures

config = json.load(open("config/config.json", "r"))

http_proxy = config["proxy"]["http_proxy"]
https_proxy = config["proxy"]["https_proxy"]
os.environ["http_proxy"] = http_proxy
os.environ["https_proxy"] = https_proxy
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = config["main_log_path"]
MODULE_TAG = "[technical_indicator_collector] "

# 防止重复添加handler
if not logging.getLogger("GeminiQuant").handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='[技术指标模块][%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'), logging.StreamHandler()]
    )

logger = logging.getLogger("GeminiQuant")



# --- API 配置 (请务必通过环境变量安全管理您的API密钥) ---
OKX_API_KEY = config["okx"]["api_key"]
OKX_SECRET_KEY = config["okx"]["secret_key"]
OKX_PASS_PHRASE = config["okx"]["passphrase"]
flag = config["okx"]["flag"]
if not all([OKX_API_KEY, OKX_SECRET_KEY, OKX_PASS_PHRASE]):
    logger.error("OKX API Key, Secret, 或 Passphrase 环境变量未设置，请检查配置。")
    # raise RuntimeError("API Key/Secret/Passphrase is not set.")

# --- 代理配置 ---
HTTP_PROXY = config["proxy"]["http_proxy"]
HTTPS_PROXY = config["proxy"]["https_proxy"]
os.environ['HTTP_PROXY'] = HTTP_PROXY
os.environ['HTTPS_PROXY'] = HTTPS_PROXY

# --- 技术指标计算辅助函数 ---
# 这些函数保持不变，因为它们是独立于数据来源的计算逻辑
def _calculate_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def _calculate_sma(series, length):
    return series.rolling(window=length).mean()

def _calculate_rsi(df, length=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0) 
    
    avg_gain = gain.ewm(span=length, adjust=False).mean()
    avg_loss = loss.ewm(span=length, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    rsi[avg_loss == 0] = 100
    rsi[avg_gain == 0] = 0
    return rsi

def _calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    ema_fast = _calculate_ema(df['close'], fast_period)
    ema_slow = _calculate_ema(df['close'], slow_period)
    macd = ema_fast - ema_slow
    signal = _calculate_ema(macd, signal_period)
    return macd, signal

def _calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_prev_close = abs(df['high'] - df['close'].shift(1))
    low_prev_close = abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return _calculate_ema(tr, length) 

def _calculate_adx(df, length=14):
    plus_dm = (df['high'] - df['high'].shift(1)).clip(lower=0)
    minus_dm = (df['low'].shift(1) - df['low']).clip(lower=0)

    plus_dm[(plus_dm > minus_dm) & (plus_dm > 0)] = plus_dm
    minus_dm[(minus_dm > plus_dm) & (minus_dm > 0)] = minus_dm
    # 修正：当其中一个为0时，另一个不应被清零
    # 原始逻辑可能导致错误，这里简化为直接计算
    # plus_dm = (df['high'] - df['high'].shift(1)).apply(lambda x: x if x > 0 else 0)
    # minus_dm = (df['low'].shift(1) - df['low']).apply(lambda x: x if x > 0 else 0)
    # true_plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    # true_minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    tr = df['high'] - df['low']
    tr = pd.concat([tr, abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))], axis=1).max(axis=1)
    
    atr_val = _calculate_ema(tr, length)

    plus_di = (_calculate_ema(plus_dm, length) / atr_val) * 100
    minus_di = (_calculate_ema(minus_dm, length) / atr_val) * 100

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = _calculate_ema(dx, length)
    return adx

def _calculate_stoch(df, k_period=14, d_period=3):
    lowest_low = df['low'].rolling(window=k_period).min()
    highest_high = df['high'].rolling(window=k_period).max()
    
    # 避免除以零
    denominator = (highest_high - lowest_low)
    k = ((df['close'] - lowest_low) / denominator) * 100
    k = k.replace([np.inf, -np.inf], np.nan).fillna(0) # 处理可能出现的inf或nan
    
    d = _calculate_sma(k, d_period)
    return k, d

def _calculate_stoch_rsi(df, rsi_period=14, k_period=14, d_period=3):
    rsi_val = _calculate_rsi(df, rsi_period) 
    
    lowest_rsi = rsi_val.rolling(window=k_period).min()
    highest_rsi = rsi_val.rolling(window=k_period).max()
    
    # 避免除以零
    denominator = (highest_rsi - lowest_rsi)
    k = ((rsi_val - lowest_rsi) / denominator) * 100
    k = k.replace([np.inf, -np.inf], np.nan).fillna(0) # 处理可能出现的inf或nan
    
    d = _calculate_sma(k, d_period)
    return k, d

def _calculate_bbands(df, length=20, std_dev=2.0):
    middle_band = _calculate_sma(df['close'], length)
    std = df['close'].rolling(window=length).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    return upper_band, middle_band, lower_band

def _calculate_vwap(df):
    typical_price = (df['high'] + df['low'] + df['close']) / 3
    cumulative_tp_x_volume = (typical_price * df['volume']).cumsum()
    cumulative_volume = df['volume'].cumsum()
    vwap = cumulative_tp_x_volume / cumulative_volume
    return vwap.replace([np.inf, -np.inf], np.nan) 

# --- 常量定义 ---
TARGET_SYMBOL_INST = 'ETH-USDT-SWAP' # OKX API 产品 ID
TARGET_SYMBOL_JSON = 'OKX:ETHUSDT.P'  # 输出JSON中的ticker和name

period_map = {
    '15m': '15m',
    '1h': '1H',
    '4h': '4H',
}#！！！这里千万别动，老娘调了1h！！！！！

KLINES_LIMIT = 300  # 获取足够多的K线用于计算长期技术指标
flag="0" # 实盘: "0" , 模拟盘: "1"


marketDataAPI = Market(flag=flag)

def _collect_indicators_for_period(label, okx_bar_string):
    """
    为单个时间周期获取数据并计算技术指标。
    返回指定数量的最新K线数据，每条K线包含其OHLCV和所有计算出的技术指标。
    """
    logger.info(f"正在获取 {TARGET_SYMBOL_INST} 在 {label} ({okx_bar_string}) 周期的数据...")
    try:
        result = marketDataAPI.get_history_candles(
            instId=TARGET_SYMBOL_INST,
            bar=okx_bar_string,
            limit=str(KLINES_LIMIT),
        )
        ohlcv_raw = result['data'] if isinstance(result, dict) and 'data' in result else result

        if not ohlcv_raw or len(ohlcv_raw) == 0:
            logger.warning(f"{label} 周期未获取到任何K线数据，跳过。返回内容: {ohlcv_raw}")
            return label, []

        # 按官方文档顺序映射字段，并确保数值类型正确
        df = pd.DataFrame(ohlcv_raw, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'
        ])
        
        # 预处理：确保数值列为float类型
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 处理时间戳
        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        df['format_time'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%Y-%m-%dT%H:%M:%S+0000')
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.set_index('timestamp').copy()
        
        # 只保留需要的列并确保它们是float类型
        df = df[['open', 'high', 'low', 'close', 'volume', 'format_time']].astype({
            'open': float,
            'high': float,
            'low': float,
            'close': float,
            'volume': float
        }, errors='ignore')  # 忽略format_time列的类型转换

        # 先反转数据顺序，保证从旧到新计算
        df = df.iloc[::-1]
        
        # 计算所有技术指标
        # EMA指标 - 从短期到长期
        df['EMA5'] = _calculate_ema(df['close'], 5)
        df['EMA21'] = _calculate_ema(df['close'], 21)
        df['EMA55'] = _calculate_ema(df['close'], 55)
        df['EMA144'] = _calculate_ema(df['close'], 144)
        df['EMA200'] = _calculate_ema(df['close'], 200)
        
        # RSI和ATR
        df['RSI'] = _calculate_rsi(df, length=14)  # 标准14周期
        df['ATR'] = _calculate_atr(df, length=14)
        
        # ADX - 趋势强度指标
        df['ADX'] = _calculate_adx(df, length=14)
        
        # MACD
        df['MACD'], df['MACD_Signal'] = _calculate_macd(df, fast_period=12, slow_period=26, signal_period=9)
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # Stochastic KD
        df['Stoch_K'], df['Stoch_D'] = _calculate_stoch(df, k_period=14, d_period=3)
        
        # StochRSI
        df['StochRSI_K'], df['StochRSI_D'] = _calculate_stoch_rsi(df, rsi_period=14, k_period=14, d_period=3)
        
        # 布林带
        upper_band, middle_band, lower_band = _calculate_bbands(df, length=20, std_dev=2.0)
        df['BB_upper'] = upper_band
        df['BB_middle'] = middle_band
        df['BB_lower'] = lower_band
        
        # VWAP
        df['VWAP'] = _calculate_vwap(df)
        
        # 再次反转回来，让最新数据在前
        df = df.iloc[::-1]

        # 提取最新的K线数据
        num_klines_to_return = 200  # 只返回最新的200根K线
        if df.shape[0] < num_klines_to_return:
            logger.warning(f"{label} 周期可用K线不足 {num_klines_to_return} 条 ({df.shape[0]} 条)")
            last_n_klines_df = df
        else:
            last_n_klines_df = df.iloc[-num_klines_to_return:]

        # 组装输出数据
        period_data_list = []
        for _, row in last_n_klines_df.iterrows():
            kline_data = {
                "开盘时间": row["format_time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                # 技术指标
                "RSI": float(row["RSI"]),
                "BB_upper": float(row["BB_upper"]),
                "BB_middle": float(row["BB_middle"]),
                "BB_lower": float(row["BB_lower"]),
                "EMA5": float(row["EMA5"]),
                "EMA21": float(row["EMA21"]),
                "EMA55": float(row["EMA55"]),
                "EMA144": float(row["EMA144"]),
                "EMA200": float(row["EMA200"]),
                "ATR": float(row["ATR"]),
                "ADX": float(row["ADX"]),
                "MACD_macd": float(row["MACD"]),
                "MACD_signal": float(row["MACD_Signal"]),
                "MACD_hist": float(row["MACD_Hist"]),
                "Stoch_K": float(row["Stoch_K"]),
                "Stoch_D": float(row["Stoch_D"]),
                "StochRSI_K": float(row["StochRSI_K"]),
                "StochRSI_D": float(row["StochRSI_D"]),
                "VWAP": float(row["VWAP"]) if "VWAP" in row else None
            }            
            period_data_list.append(kline_data)
        
        # 反转 period_data_list，确保最新的数据在最后
        period_data_list = period_data_list[::-1]

        logger.info(f"成功获取并处理 {label} 周期的数据，共 {len(period_data_list)} 条K线。")
        return label, period_data_list

    except Exception as e:
        logger.error(f"获取或处理 {label} 周期数据失败: {e}")
        return label, []

def collect_technical_indicators():
    all_periods_data = {}  # 存放所有周期的结果数据
    # 使用 ThreadPoolExecutor 并行处理不同周期
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(period_map)) as executor:
        # 存储 Future 对象，并保持与 period_map 相同的顺序
        ordered_futures = []
        for label, okx_bar_string in period_map.items():
            future = executor.submit(_collect_indicators_for_period, label, okx_bar_string)
            ordered_futures.append((label, future))

        # 按照提交的顺序获取结果
        for label, future in ordered_futures:
            try:
                _, period_data = future.result()
                
                # 过滤并保留所有计算出的指标
                filtered_period_data = []
                for kline in period_data:
                    filtered_kline = {
                        "开盘时间": kline["开盘时间"],
                        "open": kline["open"],
                        "high": kline["high"],
                        "low": kline["low"],
                        "close": kline["close"],
                        "volume": kline["volume"],
                        "RSI": kline["RSI"],
                        "BB_upper": kline["BB_upper"],
                        "BB_lower": kline["BB_lower"],
                        "BB_middle": kline["BB_middle"],
                        "EMA5": kline["EMA5"],
                        "EMA21": kline["EMA21"],
                        "EMA55": kline["EMA55"],
                        "EMA144": kline["EMA144"],
                        "EMA200": kline["EMA200"],
                        "ATR": kline["ATR"],
                        "ADX": kline["ADX"],
                        "MACD": kline["MACD_macd"],
                        "MACD_Signal": kline["MACD_signal"],
                        "MACD_Hist": kline["MACD_hist"],
                        "Stoch_K": kline["Stoch_K"],
                        "Stoch_D": kline["Stoch_D"],
                        "StochRSI_K": kline["StochRSI_K"],
                        "StochRSI_D": kline["StochRSI_D"],
                        "VWAP": kline.get("VWAP", None)
                    }
                    # 只保留非 None 和非 NaN 的值
                    filtered_kline = {k: float(v) if isinstance(v, (int, float)) and not np.isnan(v) else v 
                                   for k, v in filtered_kline.items() 
                                   if v is not None and (not isinstance(v, float) or not np.isnan(v))}
                    filtered_period_data.append(filtered_kline)
                
                all_periods_data[label] = filtered_period_data
            except Exception as exc:
                logger.error(f'{label} 周期数据采集生成异常: {exc}')
                all_periods_data[label] = []

    return all_periods_data

if __name__ == "__main__":
    try:
        import time
        start_time = time.time()
        result = collect_technical_indicators()
        print(json.dumps(result, indent=2, ensure_ascii=False)) 
        end_time = time.time()
        logger.info(f"数据采集与处理耗时: {end_time - start_time:.2f}秒")
    except Exception as e:
        logger.error(f"最终JSON序列化异常: {str(e)}")
        print(json.dumps({"error": f"最终JSON输出异常: {str(e)}"}, ensure_ascii=False))

# 示例：如有子进程调用请用 venv_python 作为解释器
# subprocess.run([venv_python, 'other_script.py', ...])