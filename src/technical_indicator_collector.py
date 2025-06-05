#ETH

import pandas as pd
import datetime
import json
import logging
import os
from okx.api import Market  # type: ignore
import numpy as np # 用于处理NaN值和数值运算


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
    plus_dm[(minus_dm > plus_dm) & (minus_dm > 0)] = 0

    minus_dm[(minus_dm > plus_dm) & (minus_dm > 0)] = minus_dm
    minus_dm[(plus_dm > minus_dm) & (plus_dm > 0)] = 0

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
    
    k = ((df['close'] - lowest_low) / (highest_high - lowest_low)) * 100
    d = _calculate_sma(k, d_period)
    return k, d

def _calculate_stoch_rsi(df, rsi_period=14, k_period=14, d_period=3):
    rsi_val = _calculate_rsi(df, rsi_period) 
    
    lowest_rsi = rsi_val.rolling(window=k_period).min()
    highest_rsi = rsi_val.rolling(window=k_period).max()
    
    k = ((rsi_val - lowest_rsi) / (highest_rsi - lowest_rsi)) * 100
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

KLINES_LIMIT = 300  # 拉取K线数量，需根据API实际限制和分页需求调整
flag="0" # 实盘: "0" , 模拟盘: "1"


marketDataAPI = Market(flag=flag)


def collect_technical_indicators():
    all_periods_data = {}  # 存放所有周期的结果数据
    for label, okx_bar_string in period_map.items():
        logger.info(f"正在获取 {TARGET_SYMBOL_INST} 在 {label} ({okx_bar_string}) 周期的数据...")
        try:
            # --- 核心修正：使用 get_history_candles 获取交易价格K线 ---
            # 这个接口通常有更长的历史数据
            # 注意：如果 limit=300 仍然不够，则需要在这里实现分页逻辑
            result = marketDataAPI.get_history_candles(
                instId=TARGET_SYMBOL_INST,
                bar=okx_bar_string,
                limit=KLINES_LIMIT,
            )
            ohlcv_raw = result['data'] if isinstance(result, dict) and 'data' in result else result

            # --- 新增：K线数据有效性检查 ---
            if not ohlcv_raw or len(ohlcv_raw) == 0:
                logger.warning(f"{label} 周期未获取到任何K线数据，跳过。返回内容: {ohlcv_raw}")
                all_periods_data[label] = None
                continue
            
            # 按官方文档顺序映射字段
            df = pd.DataFrame(ohlcv_raw, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcy', 'volCcyQuote', 'confirm'
            ])
            # --- FutureWarning优化：确保类型安全 ---
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce').astype(np.int64)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df = df.set_index('timestamp')
            df = df[['open', 'high', 'low', 'close', 'volume']].astype(float) # 确保所需列为浮点数

            # --- 手动计算技术指标 ---
            df['EMA5'] = _calculate_ema(df['close'], 5)
            df['EMA21'] = _calculate_ema(df['close'], 21)
            df['EMA55'] = _calculate_ema(df['close'], 55)
            df['EMA144'] = _calculate_ema(df['close'], 144)
            df['EMA200'] = _calculate_ema(df['close'], 200)

            df['RSI'] = _calculate_rsi(df, 14)
            df['MACD_macd'], df['MACD_signal'] = _calculate_macd(df)
            df['ATR'] = _calculate_atr(df, 14)
            df['ADX'] = _calculate_adx(df, 14)
            df['Stoch_K'], df['Stoch_D'] = _calculate_stoch(df)
            df['StochRSI_K'], df['StochRSI_D'] = _calculate_stoch_rsi(df)
            df['BB_upper'], df['BB_middle'], df['BB_lower'] = _calculate_bbands(df)
            df['VWAP'] = _calculate_vwap(df)
            
            # 处理NaN
            # 在计算指标后，DataFrame的开头可能会有NaN值。确保提取最新K线时，这些值是有效的。
            # fillna(method='ffill') 填充前向NaN
            # fillna(0) 填充开头的NaN
            df = df.ffill().fillna(0)  # FutureWarning优化
            
            # --- 新增：异常保护，防止df为空时报错 ---
            if df.shape[0] == 0:
                logger.error(f"{label} 周期DataFrame为空，无法提取最新K线。原始K线长度: {len(ohlcv_raw)}，内容片段: {ohlcv_raw[:3]}")
                all_periods_data[label] = None
                continue

            latest_kline = df.iloc[-1]  # 获取最新一根K线

            # 组装输出JSON结构
            all_periods_data[label] = {
                "indicators": {
                    "ticker": TARGET_SYMBOL_INST,
                    "name": TARGET_SYMBOL_JSON.split(':')[-1],
                    "close": float(latest_kline["close"]),
                    "volume": float(latest_kline["volume"]),
                    "RSI": float(latest_kline.get("RSI", 0)),
                    "MACD_macd": float(latest_kline.get("MACD_macd", 0)),
                    "MACD_signal": float(latest_kline.get("MACD_signal", 0)),
                    "ATR": float(latest_kline.get("ATR", 0)),
                    "ADX": float(latest_kline.get("ADX", 0)),
                    "Stoch_K": float(latest_kline.get("Stoch_K", 0)),
                    "Stoch_D": float(latest_kline.get("Stoch_D", 0)),
                    "StochRSI_K": float(latest_kline.get("StochRSI_K", 0)),
                    "StochRSI_D": float(latest_kline.get("StochRSI_D", 0)),
                    "BB_upper": float(latest_kline.get("BB_upper", 0)),
                    "BB_lower": float(latest_kline.get("BB_lower", 0)),
                    "BB_middle": float(latest_kline.get("BB_middle", 0)),
                    "EMA5": float(latest_kline.get("EMA5", 0)),
                    "EMA21": float(latest_kline.get("EMA21", 0)),
                    "EMA55": float(latest_kline.get("EMA55", 0)),
                    "EMA144": float(latest_kline.get("EMA144", 0)),
                    "EMA200": float(latest_kline.get("EMA200", 0)),
                    "VWAP": float(latest_kline.get("VWAP", 0)),
                }
            }
            logger.info(f"成功获取并处理 {label} 周期的数据。")
        except Exception as e:
            logger.error(f"获取或处理 {label} 周期数据失败: {e}")
            all_periods_data[label] = None
    return all_periods_data

if __name__ == "__main__":
    try:
        result = collect_technical_indicators()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error(f"最终JSON序列化异常: {str(e)}")
        print(json.dumps({"error": f"最终JSON输出异常: {str(e)}"}, ensure_ascii=False))

# 示例：如有子进程调用请用 venv_python 作为解释器
# subprocess.run([venv_python, 'other_script.py', ...])