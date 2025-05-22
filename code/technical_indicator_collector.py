import pandas as pd
import datetime
import json
from tradingview_screener import Query

# 设置 pandas 显示全部列
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)

def calc_ATR_OBV(df, atr_period=14):
    high_low = df['high'] - df['low']
    high_close_prev = (df['high'] - df['close'].shift(1)).abs()
    low_close_prev = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=atr_period, min_periods=1).mean()
    
    direction = df['close'].diff().fillna(0)
    volume = df['volume']
    df['OBV'] = (volume * direction.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))).cumsum()
    
    return df

# 查询 TradingView 指标数据
query = Query()
query.set_markets('crypto')
query.select(
    'name', 'close', 'volume', 'market_cap_basic', 'RSI',
    'MACD.macd', 'MACD.signal', 'ATR', 'ADX', 'Stoch.K', 'Stoch.D',
    'Stoch.RSI.K', 'Stoch.RSI.D', 'BB.upper', 'BB.lower',
    'EMA5', 'EMA8', 'EMA10', 'EMA20', 'EMA50', 'EMA100', 'EMA200',
    'SMA5', 'SMA8', 'SMA10', 'SMA20', 'SMA50', 'SMA100', 'SMA200',
    'VWAP',
)

# 新增：多周期技术指标整合
period_map = {
    'M15': ',15',
    'H1': ',60',
    'H4': ',240',
}
all_periods_data = {}
for label, tf_suffix in period_map.items():
    query = Query()
    query.set_markets('crypto')
    query.select(
        'name', 'close', 'volume', 'market_cap_basic', 'RSI',
        'MACD.macd', 'MACD.signal', 'ATR', 'ADX', 'Stoch.K', 'Stoch.D',
        'Stoch.RSI.K', 'Stoch.RSI.D', 'BB.upper', 'BB.lower',
        'EMA5', 'EMA8', 'EMA10', 'EMA20', 'EMA50', 'EMA100', 'EMA200',
        'SMA5', 'SMA8', 'SMA10', 'SMA20', 'SMA50', 'SMA100', 'SMA200',
        'VWAP',
    )
    total_count, df = query.get_scanner_data()
    # 筛选 symbol 名称带周期的 ETHUSDT，如 BINANCE:ETHUSDT,15
    df_ethusdt = df[df['name'].str.contains(f'ETHUSDT{tf_suffix}', case=False)]
    df_ethusdt_no_mexc = df_ethusdt[~df_ethusdt['ticker'].str.contains('MEXC:', case=False)]
    if not df_ethusdt_no_mexc.empty:
        row = df_ethusdt_no_mexc.iloc[-1]
        all_periods_data[label] = {
            "timestamp": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "indicators": {
                "ticker": row["ticker"],
                "name": row["name"],
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "RSI": float(row["RSI"]),
                "MACD_macd": float(row["MACD.macd"]),
                "MACD_signal": float(row["MACD.signal"]),
                "ATR": float(row["ATR"]),
                "ADX": float(row["ADX"]),
                "Stoch_K": float(row["Stoch.K"]),
                "Stoch_D": float(row["Stoch.D"]),
                "StochRSI_K": float(row["Stoch.RSI.K"]),
                "StochRSI_D": float(row["Stoch.RSI.D"]),
                "BB_upper": float(row["BB.upper"]),
                "BB_lower": float(row["BB.lower"]),
                "EMA5": float(row["EMA5"]),
                "EMA8": float(row["EMA8"]),
                "EMA10": float(row["EMA10"]),
                "EMA20": float(row["EMA20"]),
                "EMA50": float(row["EMA50"]),
                "EMA100": float(row["EMA100"]),
                "EMA200": float(row["EMA200"]),
                "SMA5": float(row["SMA5"]),
                "SMA8": float(row["SMA8"]),
                "SMA10": float(row["SMA10"]),
                "SMA20": float(row["SMA20"]),
                "SMA50": float(row["SMA50"]),
                "SMA100": float(row["SMA100"]),
                "SMA200": float(row["SMA200"]),
                "VWAP": float(row["VWAP"]),
            }
        }
    else:
        all_periods_data[label] = None

all_ethusdt = {}
for label, tf_suffix in period_map.items():
    query = Query()
    query.set_markets('crypto')
    query.select(
        'name', 'close', 'volume', 'market_cap_basic', 'RSI',
        'MACD.macd', 'MACD.signal', 'ATR', 'ADX', 'Stoch.K', 'Stoch.D',
        'Stoch.RSI.K', 'Stoch.RSI.D', 'BB.upper', 'BB.lower',
        'EMA5', 'EMA8', 'EMA10', 'EMA20', 'EMA50', 'EMA100', 'EMA200',
        'SMA5', 'SMA8', 'SMA10', 'SMA20', 'SMA50', 'SMA100', 'SMA200',
        'VWAP',
    )
    total_count, df = query.get_scanner_data()
    # 输出所有ETHUSDT相关symbol及其数据
    df_ethusdt = df[df['name'].str.contains('ETHUSDT', case=False)]
    ethusdt_list = []
    for _, row in df_ethusdt.iterrows():
        ethusdt_list.append({col: (float(row[col]) if isinstance(row[col], (int, float)) else str(row[col])) for col in df_ethusdt.columns})
    all_ethusdt[label] = ethusdt_list

# --- 只输出OKX:ETHUSDT.P的多周期json，并终止脚本 ---
try:
    # 只输出ETHUSDT.P的OKX数据，按M15/H1/H4归类
    okx_periods_data = {}
    for label in period_map.keys():
        okx_data = None
        for entry in all_ethusdt[label]:
            if entry.get('ticker', '').startswith('OKX:ETHUSDT.P'):
                okx_data = entry
                break
        okx_periods_data[label] = okx_data
    print(json.dumps(okx_periods_data, indent=2, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"error": f"技术指标采集异常: {str(e)}"}, ensure_ascii=False))
import sys
sys.exit(0)
