import logging
import numpy as np

logger = logging.getLogger("GeminiQuant")

def _get_last_n_klines(kline_data_list, n):
    """获取最新的N条K线数据，如果不足N条则返回所有可用K线。"""
    if not kline_data_list:
        return []
    return kline_data_list[-n:]

def _analyze_kline_shapes(kline_data_list):
    """
    分析最近K线形态。
    Args:
        kline_data_list (list): 包含K线数据的列表，每项是一个字典。
    Returns:
        dict: K线形态分析结果。
    """
    if not kline_data_list:
        return {"description": "无K线数据。", "strength": "N/A"}

    last_kline = kline_data_list[-1]
    prev_kline = kline_data_list[-2] if len(kline_data_list) >= 2 else None
    
    open_price = last_kline['open']
    close_price = last_kline['close']
    high_price = last_kline['high']
    low_price = last_kline['low']
    
    body_size = abs(close_price - open_price)
    total_range = high_price - low_price
    
    # 判断阳线/阴线
    is_bullish = close_price > open_price
    is_bearish = close_price < open_price

    description = []
    strength = "中"

    # 1. K线实体大小
    if total_range > 0:
        body_ratio = body_size / total_range
        if body_ratio > 0.7:
            description.append("实体饱满")
            strength = "高"
        elif body_ratio < 0.3:
            description.append("实体较小")
            strength = "低"
        else:
            description.append("实体中等")

    # 2. 影线长度
    upper_wick = high_price - max(open_price, close_price)
    lower_wick = min(open_price, close_price) - low_price

    if total_range > 0:
        upper_wick_ratio = upper_wick / total_range
        lower_wick_ratio = lower_wick / total_range

        if upper_wick_ratio > 0.4:
            description.append("长上影线")
            strength = "中" if strength == "中" else "高" # 如果是长上影线，可能削弱趋势
        if lower_wick_ratio > 0.4:
            description.append("长下影线")
            strength = "中" if strength == "中" else "高" # 如果是长下影线，可能强化趋势

    # 3. 吞没形态 (需要至少2根K线)
    if prev_kline:
        prev_open = prev_kline['open']
        prev_close = prev_kline['close']
        
        # 看涨吞没
        if is_bullish and prev_close < prev_open and close_price > prev_open and open_price < prev_close:
            description.append("看涨吞没形态")
            strength = "高"
        # 看跌吞没
        elif is_bearish and prev_close > prev_open and close_price < prev_open and open_price > prev_close:
            description.append("看跌吞没形态")
            strength = "高"

    # 4. 连续K线方向
    recent_3_klines = _get_last_n_klines(kline_data_list, 3)
    if len(recent_3_klines) == 3:
        bullish_count = sum(1 for k in recent_3_klines if k['close'] > k['open'])
        bearish_count = sum(1 for k in recent_3_klines if k['close'] < k['open'])
        
        if bullish_count == 3:
            description.append("三连阳")
            strength = "高"
        elif bearish_count == 3:
            description.append("三连阴")
            strength = "高"
        elif bullish_count >= 2 and is_bullish:
            description.append("近期多为阳线")
        elif bearish_count >= 2 and is_bearish:
            description.append("近期多为阴线")

    if is_bullish:
        description.insert(0, "阳线")
    elif is_bearish:
        description.insert(0, "阴线")
    else:
        description.insert(0, "十字星/小实体") # open == close 或非常接近

    return {"description": "，".join(description), "strength": strength}

def _analyze_bollinger_bands(kline_data_list):
    """
    分析布林带状态。
    Args:
        kline_data_list (list): 包含K线数据的列表，每项是一个字典。
    Returns:
        dict: 布林带分析结果。
    """
    if not kline_data_list or len(kline_data_list) < 2:
        return {"description": "K线数据不足以分析布林带。", "strength": "N/A"}

    last_kline = kline_data_list[-1]
    prev_kline = kline_data_list[-2]

    bb_upper = last_kline.get('BB_upper')
    bb_middle = last_kline.get('BB_middle')
    bb_lower = last_kline.get('BB_lower')
    close_price = last_kline['close']

    if any(v is None for v in [bb_upper, bb_middle, bb_lower]):
        return {"description": "布林带数据缺失。", "strength": "N/A"}

    description = []
    strength = "中"

    # 1. 价格相对于布林带的位置
    if close_price > bb_upper:
        description.append("价格突破上轨")
        strength = "高"
    elif close_price < bb_lower:
        description.append("价格跌破下轨")
        strength = "高"
    elif close_price > bb_middle and close_price <= bb_upper:
        description.append("价格位于中轨与上轨之间")
    elif close_price < bb_middle and close_price >= bb_lower:
        description.append("价格位于中轨与下轨之间")
    else:
        description.append("价格在中轨附近")

    # 2. 布林带的扩张/收缩
    current_bandwidth = bb_upper - bb_lower
    prev_bb_upper = prev_kline.get('BB_upper')
    prev_bb_lower = prev_kline.get('BB_lower')

    if prev_bb_upper is not None and prev_bb_lower is not None:
        prev_bandwidth = prev_bb_upper - prev_bb_lower
        if current_bandwidth > prev_bandwidth * 1.05: # 5% 扩张视为扩张
            description.append("布林带扩张")
            strength = "高"
        elif current_bandwidth < prev_bandwidth * 0.95: # 5% 收缩视为收缩
            description.append("布林带收缩")
            strength = "高"
        else:
            description.append("布林带平稳")

    # 3. 布林带的开口角度 (通过中轨斜率简要判断)
    current_middle = last_kline.get('BB_middle')
    prev_middle = prev_kline.get('BB_middle')
    if current_middle is not None and prev_middle is not None:
        if current_middle > prev_middle:
            description.append("中轨向上")
        elif current_middle < prev_middle:
            description.append("中轨向下")
        else:
            description.append("中轨走平")

    return {"description": "，".join(description), "strength": strength}

def _analyze_ema_alignment(kline_data_list):
    """
    分析EMA排列和斜率。
    Args:
        kline_data_list (list): 包含K线数据的列表，每项是一个字典。
    Returns:
        dict: EMA分析结果。
    """
    if not kline_data_list or len(kline_data_list) < 2:
        return {"description": "K线数据不足以分析EMA。", "strength": "N/A"}

    last_kline = kline_data_list[-1]
    prev_kline = kline_data_list[-2]

    emas = {
        'EMA5': last_kline.get('EMA5'),
        'EMA21': last_kline.get('EMA21'),
        'EMA55': last_kline.get('EMA55'),
        'EMA144': last_kline.get('EMA144'),
        'EMA200': last_kline.get('EMA200')
    }
    
    if any(v is None for v in emas.values()):
        return {"description": "EMA数据缺失。", "strength": "N/A"}

    description = []
    strength = "中"

    # 1. EMA排列
    if (emas['EMA5'] > emas['EMA21'] > emas['EMA55'] > emas['EMA144'] > emas['EMA200']):
        description.append("完美看涨排列")
        strength = "高"
    elif (emas['EMA5'] < emas['EMA21'] < emas['EMA55'] < emas['EMA144'] < emas['EMA200']):
        description.append("完美看跌排列")
        strength = "高"
    else:
        description.append("EMA排列混乱/盘整")
        strength = "低"

    # 2. EMA斜率 (判断短期EMA相对于长期EMA的趋势)
    ema5_current = emas['EMA5']
    ema21_current = emas['EMA21']
    ema55_current = emas['EMA55']

    ema5_prev = prev_kline.get('EMA5')
    ema21_prev = prev_kline.get('EMA21')
    ema55_prev = prev_kline.get('EMA55')

    if all(v is not None for v in [ema5_prev, ema21_prev, ema55_prev]):
        if ema5_current > ema5_prev and ema21_current > ema21_prev and ema55_current > ema55_prev:
            description.append("短期EMA向上倾斜")
        elif ema5_current < ema5_prev and ema21_current < ema21_prev and ema55_current < ema55_prev:
            description.append("短期EMA向下倾斜")
        else:
            description.append("短期EMA斜率混合")

    return {"description": "，".join(description), "strength": strength}

def _analyze_rsi(kline_data_list):
    """
    分析RSI状态。
    Args:
        kline_data_list (list): 包含K线数据的列表，每项是一个字典。
    Returns:
        dict: RSI分析结果。
    """
    if not kline_data_list or len(kline_data_list) < 2:
        return {"description": "K线数据不足以分析RSI。", "strength": "N/A"}

    last_kline = kline_data_list[-1]
    prev_kline = kline_data_list[-2]

    rsi_val = last_kline.get('RSI')
    prev_rsi_val = prev_kline.get('RSI')

    if rsi_val is None or prev_rsi_val is None:
        return {"description": "RSI数据缺失。", "strength": "N/A"}

    description = []
    strength = "中"

    # 1. 超买/超卖区域
    if rsi_val > 70:
        description.append("RSI超买")
        strength = "高"
    elif rsi_val < 30:
        description.append("RSI超卖")
        strength = "高"
    else:
        description.append("RSI中性区域")

    # 2. RSI趋势
    if rsi_val > prev_rsi_val:
        description.append("RSI向上")
    elif rsi_val < prev_rsi_val:
        description.append("RSI向下")
    else:
        description.append("RSI走平")

    # 3. 穿越50线
    if (prev_rsi_val < 50 and rsi_val >= 50):
        description.append("RSI上穿50线")
        strength = "高"
    elif (prev_rsi_val > 50 and rsi_val <= 50):
        description.append("RSI下穿50线")
        strength = "高"

    return {"description": f"RSI {rsi_val:.2f}，" + "，".join(description), "strength": strength}

def _analyze_macd(kline_data_list):
    """
    分析MACD状态。
    Args:
        kline_data_list (list): 包含K线数据的列表，每项是一个字典。
    Returns:
        dict: MACD分析结果。
    """
    if not kline_data_list or len(kline_data_list) < 2:
        return {"description": "K线数据不足以分析MACD。", "strength": "N/A"}

    last_kline = kline_data_list[-1]
    prev_kline = kline_data_list[-2]

    macd_val = last_kline.get('MACD_macd')
    signal_val = last_kline.get('MACD_signal')
    
    prev_macd_val = prev_kline.get('MACD_macd')
    prev_signal_val = prev_kline.get('MACD_signal')

    if any(v is None for v in [macd_val, signal_val, prev_macd_val, prev_signal_val]):
        return {"description": "MACD数据缺失。", "strength": "N/A"}

    description = []
    strength = "中"

    # 1. 金叉/死叉
    if macd_val > signal_val and prev_macd_val <= prev_signal_val:
        description.append("MACD金叉")
        strength = "高"
    elif macd_val < signal_val and prev_macd_val >= prev_signal_val:
        description.append("MACD死叉")
        strength = "高"
    elif macd_val > signal_val:
        description.append("MACD金叉持续")
    elif macd_val < signal_val:
        description.append("MACD死叉持续")

    # 2. 能量柱 (histogram) 变化
    histogram_current = macd_val - signal_val
    histogram_prev = prev_macd_val - prev_signal_val

    if histogram_current > histogram_prev and histogram_current > 0:
        description.append("能量柱增长(多头)")
    elif histogram_current < histogram_prev and histogram_current < 0:
        description.append("能量柱增长(空头)")
    elif histogram_current < histogram_prev and histogram_current > 0:
        description.append("能量柱收缩(多头)")
    elif histogram_current > histogram_prev and histogram_current < 0:
        description.append("能量柱收缩(空头)")
    else:
        description.append("能量柱平稳")

    return {"description": "，".join(description), "strength": strength}


def analyze_kline_patterns(kline_data_list: list) -> dict:
    """
    对给定时间周期的K线数据进行数值化模式识别和技术指标分析。
    此工具将替代对K线图的视觉判断，直接从数值数据中提取K线形态、布林带、EMA排列、RSI和MACD的特征。

    Args:
        kline_data_list (list): 包含K线数据的列表，每项是一个字典。
                                列表应包含至少15条K线，以确保指标计算的完整性。
                                每条K线字典应包含 'open', 'high', 'low', 'close', 'volume'
                                以及 'RSI', 'MACD_macd', 'MACD_signal', 'BB_upper', 'BB_middle', 'BB_lower',
                                'EMA5', 'EMA21', 'EMA55', 'EMA144', 'EMA200' 等指标。

    Returns:
        dict: 包含以下键的分析结果：
        - 'kline_shapes': K线形态分析 (dict)
        - 'bollinger_bands': 布林带分析 (dict)
        - 'ema_alignment': EMA排列分析 (dict)
        - 'rsi_analysis': RSI分析 (dict)
        - 'macd_analysis': MACD分析 (dict)
    """
    if not kline_data_list or len(kline_data_list) < 10:
        logger.warning("K线数据不足10条，可能无法进行完整的模式识别。")
        return {
            "kline_shapes": {"description": "K线数据不足。", "strength": "N/A"},
            "bollinger_bands": {"description": "K线数据不足。", "strength": "N/A"},
            "ema_alignment": {"description": "K线数据不足。", "strength": "N/A"},
            "rsi_analysis": {"description": "K线数据不足。", "strength": "N/A"},
            "macd_analysis": {"description": "K线数据不足。", "strength": "N/A"}
        }

    # 提取最近的15条K线用于分析，确保所有指标都有足够的数据点
    # 实际的指标计算已经在 technical_indicator_collector 中完成，这里直接使用
    # 确保传入的 kline_data_list 已经是处理好的最新15条K线
    
    analysis_results = {
        "kline_shapes": _analyze_kline_shapes(kline_data_list),
        "bollinger_bands": _analyze_bollinger_bands(kline_data_list),
        "ema_alignment": _analyze_ema_alignment(kline_data_list),
        "rsi_analysis": _analyze_rsi(kline_data_list),
        "macd_analysis": _analyze_macd(kline_data_list)
    }
    
    return analysis_results