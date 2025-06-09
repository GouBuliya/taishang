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
    分析布林带状态，提供更详细的分析。
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

    # 1. 价格相对于布林带的位置（增加更详细的百分比分析）
    bb_range = bb_upper - bb_lower
    price_position = ((close_price - bb_lower) / bb_range) * 100 if bb_range > 0 else 50
    bb_width_percent = (bb_upper - bb_lower) / bb_middle * 100  # 布林带宽度占中轨的百分比
    
    if close_price > bb_upper:
        over_upper = (close_price - bb_upper) / bb_upper * 100
        description.append(f"价格突破上轨{over_upper:.1f}%，极度超买")
        strength = "高"
    elif close_price < bb_lower:
        below_lower = (bb_lower - close_price) / bb_lower * 100
        description.append(f"价格跌破下轨{below_lower:.1f}%，极度超卖")
        strength = "高"
    else:
        description.append(f"价格在布林带内，位于{price_position:.1f}%处（0%为下轨，100%为上轨）")

    # 2. 布林带的扩张/收缩（增加更多细节）
    current_bandwidth = bb_upper - bb_lower
    prev_bb_upper = prev_kline.get('BB_upper')
    prev_bb_lower = prev_kline.get('BB_lower')

    if prev_bb_upper is not None and prev_bb_lower is not None:
        prev_bandwidth = prev_bb_upper - prev_bb_lower
        bandwidth_change = ((current_bandwidth - prev_bandwidth) / prev_bandwidth) * 100
        avg_daily_volatility = bb_width_percent / 20  # 估算日均波动率
        
        if bandwidth_change > 5:
            description.append(f"布林带扩张{bandwidth_change:.1f}%，日均波动{avg_daily_volatility:.1f}%")
            strength = "高" if bandwidth_change > 10 else "中"
        elif bandwidth_change < -5:
            description.append(f"布林带收缩{-bandwidth_change:.1f}%，日均波动{avg_daily_volatility:.1f}%")
            strength = "高" if bandwidth_change < -10 else "中"
        else:
            description.append(f"布林带宽度稳定，日均波动{avg_daily_volatility:.1f}%")

    # 3. 布林带趋势（增加更多趋势细节）
    current_middle = bb_middle
    prev_middle = prev_kline.get('BB_middle')
    if current_middle is not None and prev_middle is not None:
        middle_change = ((current_middle - prev_middle) / prev_middle) * 100
        momentum = abs(middle_change) * (1 + bb_width_percent/100)  # 考虑带宽的趋势动量
        
        if middle_change > 0.1:
            description.append(f"中轨向上{middle_change:.1f}%，趋势动量{momentum:.1f}")
        elif middle_change < -0.1:
            description.append(f"中轨向下{middle_change:.1f}%，趋势动量{momentum:.1f}")
        else:
            description.append("中轨走平，横盘整理")

    # 4. 波动率评估和预警
    volatility_warning = ""
    if bb_width_percent < 0.5:
        volatility_warning = "，即将爆发"
        strength = "高"
    elif bb_width_percent > 5:
        volatility_warning = "，建议注意风险"
        strength = "高"
    
    description.append(f"布林带宽度占中轨{bb_width_percent:.1f}%{volatility_warning}")

    return {"description": "，".join(description), "strength": strength}

def _analyze_ema_alignment(kline_data_list):
    """
    分析EMA排列、趋势变化和支撑阻力。
    """
    if not kline_data_list or len(kline_data_list) < 2:
        return {"description": "K线数据不足以分析EMA。", "strength": "N/A"}

    last_kline = kline_data_list[-1]
    prev_kline = kline_data_list[-2]
    current_price = last_kline['close']

    # 只检查我们需要的EMA指标
    emas = {
        'EMA5': last_kline.get('EMA5'),
        'EMA21': last_kline.get('EMA21'),
        'EMA55': last_kline.get('EMA55')
    }
    
    if any(v is None for v in emas.values()):
        return {"description": "部分EMA数据缺失。", "strength": "N/A"}

    prev_emas = {
        'EMA5': prev_kline.get('EMA5'),
        'EMA21': prev_kline.get('EMA21'),
        'EMA55': prev_kline.get('EMA55')
    }

    if any(v is None for v in prev_emas.values()):
        return {"description": "部分历史EMA数据缺失。", "strength": "N/A"}

    description = []
    strength = "中"
    warnings = []

    # 1. EMA排列分析
    ema_values = [emas['EMA5'], emas['EMA21'], emas['EMA55']]
    current_alignment = None
    
    if ema_values[0] > ema_values[1] > ema_values[2]:
        current_alignment = "黄金排列"
        description.append("EMA黄金排列")
        strength = "高"
    elif ema_values[0] < ema_values[1] < ema_values[2]:
        current_alignment = "死亡排列"
        description.append("EMA死亡排列")
        strength = "高"
    else:
        current_alignment = "散乱排列"
        description.append("EMA散乱排列")

    # 2. 趋势强度分析
    trend_strength = {
        'short': abs(emas['EMA5'] - prev_emas['EMA5']) / prev_emas['EMA5'] * 100,
        'medium': abs(emas['EMA21'] - prev_emas['EMA21']) / prev_emas['EMA21'] * 100,
        'long': abs(emas['EMA55'] - prev_emas['EMA55']) / prev_emas['EMA55'] * 100
    }

    # 3. 趋势分析
    trends = []
    
    # 主趋势（EMA55）
    if emas['EMA55'] > prev_emas['EMA55']:
        if trend_strength['long'] > 0.1:
            trends.append("主趋势强势上涨")
        else:
            trends.append("主趋势缓慢向上")
    elif emas['EMA55'] < prev_emas['EMA55']:
        if trend_strength['long'] > 0.1:
            trends.append("主趋势强势下跌")
        else:
            trends.append("主趋势缓慢向下")
    else:
        trends.append("主趋势横盘")

    # 中期趋势（EMA21）
    if emas['EMA21'] > prev_emas['EMA21']:
        if trend_strength['medium'] > 0.2:
            trends.append("中期趋势强势上涨")
        else:
            trends.append("中期趋势向上")
    elif emas['EMA21'] < prev_emas['EMA21']:
        if trend_strength['medium'] > 0.2:
            trends.append("中期趋势强势下跌")
        else:
            trends.append("中期趋势向下")

    # 短期趋势（EMA5）
    if emas['EMA5'] > prev_emas['EMA5']:
        if trend_strength['short'] > 0.3:
            trends.append("短期趋势爆发性上涨")
        else:
            trends.append("短期趋势向上")
    elif emas['EMA5'] < prev_emas['EMA5']:
        if trend_strength['short'] > 0.3:
            trends.append("短期趋势暴跌")
        else:
            trends.append("短期趋势向下")

    # 4. 趋势背离分析
    if current_alignment == "死亡排列" and emas['EMA5'] > prev_emas['EMA5']:
        warnings.append("短期反弹，但仍处于下跌趋势")
    elif current_alignment == "黄金排列" and emas['EMA5'] < prev_emas['EMA5']:
        warnings.append("短期回调，但仍处于上涨趋势")

    # 5. 支撑阻力分析
    price_location = []
    if abs(current_price - emas['EMA5']) / emas['EMA5'] < 0.001:
        price_location.append("价格在EMA5附近徘徊")
    elif abs(current_price - emas['EMA21']) / emas['EMA21'] < 0.001:
        price_location.append("价格在EMA21附近徘徊")
    elif abs(current_price - emas['EMA55']) / emas['EMA55'] < 0.001:
        price_location.append("价格在EMA55附近徘徊")

    # 组合分析结果
    description.extend(trends)
    if warnings:
        description.extend(warnings)
    if price_location:
        description.extend(price_location)

    return {"description": "，".join(description), "strength": strength}

def _analyze_rsi(kline_data_list):
    """
    分析RSI指标，提供更详细的分析。
    """
    if not kline_data_list or len(kline_data_list) < 5:
        return {"description": "K线数据不足以分析RSI。", "strength": "N/A"}

    # 获取最近几个周期的RSI和价格数据
    recent_data = kline_data_list[-5:]
    rsi_values = [float(d.get('RSI', 0)) for d in recent_data]
    close_prices = [float(d.get('close', 0)) for d in recent_data]

    if any(v == 0 for v in rsi_values) or any(v == 0 for v in close_prices):
        return {"description": "RSI数据缺失。", "strength": "N/A"}

    current_rsi = rsi_values[-1]
    prev_rsi = rsi_values[-2]
    description = []
    strength = "中"

    # 1. RSI区域分析（增加更细致的区域划分）
    if current_rsi > 85:
        description.append(f"RSI极度超买（{current_rsi:.1f}），高位风险")
        strength = "极高"
    elif current_rsi > 80:
        description.append(f"RSI严重超买（{current_rsi:.1f}）")
        strength = "极高"
    elif current_rsi > 70:
        description.append(f"RSI超买（{current_rsi:.1f}）")
        strength = "高"
    elif current_rsi < 15:
        description.append(f"RSI极度超卖（{current_rsi:.1f}），反弹机会")
        strength = "极高"
    elif current_rsi < 20:
        description.append(f"RSI严重超卖（{current_rsi:.1f}）")
        strength = "极高"
    elif current_rsi < 30:
        description.append(f"RSI超卖（{current_rsi:.1f}）")
        strength = "高"
    else:
        # 中性区域的细分
        if 45 < current_rsi < 55:
            description.append(f"RSI在中性区域（{current_rsi:.1f}）")
        elif current_rsi >= 55:
            description.append(f"RSI偏强区域（{current_rsi:.1f}）")
        else:
            description.append(f"RSI偏弱区域（{current_rsi:.1f}）")

    # 2. RSI动量分析（更详细的变化描述）
    rsi_change = current_rsi - prev_rsi
    rsi_momentum = abs(rsi_change)
    
    if rsi_change > 0:
        if rsi_momentum > 15:
            description.append(f"RSI爆发性上涨{rsi_momentum:.1f}点，可能短期过热")
            strength = "极高"
        elif rsi_momentum > 10:
            description.append(f"RSI强势上涨{rsi_momentum:.1f}点")
            strength = "高"
        elif rsi_momentum > 5:
            description.append(f"RSI温和上涨{rsi_momentum:.1f}点")
            strength = "中"
        else:
            description.append(f"RSI小幅上涨{rsi_momentum:.1f}点")
    else:
        if rsi_momentum > 15:
            description.append(f"RSI暴跌{rsi_momentum:.1f}点，可能超跌")
            strength = "极高"
        elif rsi_momentum > 10:
            description.append(f"RSI快速下跌{rsi_momentum:.1f}点")
            strength = "高"
        elif rsi_momentum > 5:
            description.append(f"RSI温和下跌{rsi_momentum:.1f}点")
            strength = "中"
        else:
            description.append(f"RSI小幅下跌{rsi_momentum:.1f}点")

    # 3. RSI趋势和背离分析
    price_changes = [close_prices[i] - close_prices[i-1] for i in range(1, len(close_prices))]
    rsi_changes = [rsi_values[i] - rsi_values[i-1] for i in range(1, len(rsi_values))]
    
    # 检查是否存在背离
    price_momentum = sum(price_changes[-2:])
    rsi_momentum = sum(rsi_changes[-2:])
    
    if price_momentum > 0 and rsi_momentum < 0:
        if current_rsi > 70:
            description.append("顶部背离非常明显，强烈卖出信号")
            strength = "极高"
        else:
            description.append("出现顶背离，看跌信号")
            strength = "高"
    elif price_momentum < 0 and rsi_momentum > 0:
        if current_rsi < 30:
            description.append("底部背离非常明显，强烈买入信号")
            strength = "极高"
        else:
            description.append("出现底背离，看涨信号")
            strength = "高"

    # 4. RSI突破分析（增加对突破的详细描述）
    if abs(current_rsi - 50) < 3:
        if rsi_change > 0:
            description.append(f"RSI向上穿越50中轴（位于{current_rsi:.1f}），转多头")
            strength = "高"
        else:
            description.append(f"RSI向下穿越50中轴（位于{current_rsi:.1f}），转空头")
            strength = "高"

    # 5. RSI波动性分析
    rsi_volatility = max(rsi_values) - min(rsi_values)
    avg_volatility = sum([abs(rc) for rc in rsi_changes]) / len(rsi_changes)
    
    if rsi_volatility > 20:
        description.append(f"RSI大幅波动（振幅{rsi_volatility:.1f}点，日均波动{avg_volatility:.1f}点），市场情绪剧烈")
        strength = "高"
    elif rsi_volatility > 10:
        description.append(f"RSI中等波动（振幅{rsi_volatility:.1f}点，日均波动{avg_volatility:.1f}点）")
        strength = "中"
    else:
        description.append(f"RSI波动平稳（振幅{rsi_volatility:.1f}点，日均波动{avg_volatility:.1f}点）")

    # 6. 趋势持续性分析
    rsi_direction_changes = sum(1 for i in range(1, len(rsi_changes)) if rsi_changes[i] * rsi_changes[i-1] < 0)
    if rsi_direction_changes <= 1:
        description.append("RSI趋势连续性强")
    else:
        description.append("RSI频繁转向")

    return {"description": "，".join(description), "strength": strength}

def _analyze_macd(kline_data_list):
    """
    分析MACD指标，提供详细的MACD分析。
    1. MACD柱状值分析
    2. 金叉死叉判断
    3. 趋势强度评估
    4. 背离分析
    5. 信号可靠性评估
    """
    if not kline_data_list or len(kline_data_list) < 5:
        return {"description": "K线数据不足以分析MACD。", "strength": "N/A"}

    # 获取最近几个周期的MACD数据
    recent_data = kline_data_list[-5:]
    try:
        macd_values = [float(d.get('MACD', 0)) for d in recent_data]
        signal_values = [float(d.get('MACD_Signal', 0)) for d in recent_data]
        histogram_values = [float(d.get('MACD_Hist', 0)) for d in recent_data]
        close_prices = [float(d['close']) for d in recent_data]
    except (TypeError, KeyError, ValueError):
        return {"description": "MACD数据缺失或格式错误。", "strength": "N/A"}

    if any(v == 0 for v in macd_values + signal_values):
        return {"description": "MACD数据不完整。", "strength": "N/A"}

    current_macd = macd_values[-1]
    current_signal = signal_values[-1]
    current_hist = histogram_values[-1]
    prev_hist = histogram_values[-2]

    description = []
    strength = "中"

    # 1. MACD柱状值分析
    hist_change = current_hist - prev_hist
    hist_momentum = abs(hist_change)
    
    if current_hist > 0:
        if hist_momentum > 0.1:
            description.append(f"MACD柱形快速增长({hist_momentum:.3f})")
            strength = "高"
        elif hist_momentum > 0.05:
            description.append(f"MACD柱形温和增长({hist_momentum:.3f})")
        else:
            description.append("MACD柱形小幅增长")
    else:
        if hist_momentum > 0.1:
            description.append(f"MACD柱形快速缩短({hist_momentum:.3f})")
            strength = "高"
        elif hist_momentum > 0.05:
            description.append(f"MACD柱形温和缩短({hist_momentum:.3f})")
        else:
            description.append("MACD柱形小幅缩短")

    # 2. 金叉死叉判断
    prev_macd_signal_diff = macd_values[-2] - signal_values[-2]
    current_macd_signal_diff = current_macd - current_signal
    
    if prev_macd_signal_diff < 0 and current_macd_signal_diff > 0:
        description.append("MACD金叉形成")
        strength = "高"
    elif prev_macd_signal_diff > 0 and current_macd_signal_diff < 0:
        description.append("MACD死叉形成")
        strength = "高"
    elif abs(current_macd_signal_diff) < 0.001:
        description.append("MACD与信号线即将交叉")
        strength = "高"

    # 3. 趋势强度评估
    trend_momentum = abs(current_macd)
    if trend_momentum > 0.2:
        description.append(f"MACD趋势强劲({trend_momentum:.3f})")
        strength = "高"
    elif trend_momentum > 0.1:
        description.append(f"MACD趋势温和({trend_momentum:.3f})")
    else:
        description.append("MACD趋势弱势")

    # 4. 背离分析
    price_trend = close_prices[-1] - close_prices[0]
    macd_trend = current_macd - macd_values[0]
    
    if price_trend > 0 and macd_trend < 0:
        description.append("MACD顶背离，可能见顶")
        strength = "高"
    elif price_trend < 0 and macd_trend > 0:
        description.append("MACD底背离，可能见底")
        strength = "高"

    # 5. 趋势加速/减速分析
    if len(histogram_values) >= 3:
        hist_acceleration = (histogram_values[-1] - histogram_values[-2]) - (histogram_values[-2] - histogram_values[-3])
        if abs(hist_acceleration) > 0.05:
            if hist_acceleration > 0:
                description.append("趋势加速")
            else:
                description.append("趋势减速")

    # 6. 零轴分析
    if current_macd > 0 and macd_values[-2] <= 0:
        description.append("MACD突破零轴，转多头")
        strength = "高"
    elif current_macd < 0 and macd_values[-2] >= 0:
        description.append("MACD跌破零轴，转空头")
        strength = "高"

    return {"description": "，".join(description), "strength": strength}

def _analyze_adx(kline_data_list):
    """
    分析ADX(平均趋向指数)，评估趋势强度。
    ADX值范围0-100:
    - 0-25: 无趋势/弱趋势
    - 25-50: 有趋势/强趋势开始
    - 50-75: 强趋势
    - 75-100: 极强趋势
    """
    if not kline_data_list or len(kline_data_list) < 2:
        return {"description": "数据不足，无法分析ADX", "strength": "弱"}

    recent_data = kline_data_list[-5:]  # 获取最近5根K线
    adx_values = [float(d.get('ADX', 0)) for d in recent_data]
    
    if any(v == 0 for v in adx_values):
        return {"description": "ADX数据缺失", "strength": "弱"}

    current_adx = adx_values[-1]
    prev_adx = adx_values[-2]
    adx_change = current_adx - prev_adx
    
    description = []
    strength = "中"

    # 1. ADX趋势强度评估
    if current_adx >= 75:
        description.append("当前处于极强趋势期")
        strength = "强"
    elif current_adx >= 50:
        description.append("当前处于强势趋势期")
        strength = "强"
    elif current_adx >= 25:
        description.append("当前趋势开始形成")
        strength = "中"
    else:
        description.append("当前无明显趋势")
        strength = "弱"

    # 2. ADX动态变化分析
    if abs(adx_change) >= 5:
        if adx_change > 0:
            description.append("趋势强度正在显著增强")
        else:
            description.append("趋势强度正在显著减弱")
    elif abs(adx_change) >= 2:
        if adx_change > 0:
            description.append("趋势强度略有增强")
        else:
            description.append("趋势强度略有减弱")
    
    # 3. ADX趋势持续性分析
    adx_direction_changes = sum(1 for i in range(1, len(adx_values)-1) 
                              if (adx_values[i+1] - adx_values[i]) * 
                                 (adx_values[i] - adx_values[i-1]) < 0)
    
    if adx_direction_changes <= 1:
        if current_adx > prev_adx:
            description.append("趋势增强持续性好")
        else:
            description.append("趋势减弱持续性好")
    else:
        description.append("趋势强度波动频繁，方向不稳定")

    return {"description": "，".join(description), "strength": strength}

def _analyze_stochastic(kline_data_list):
    """
    分析随机指标(KD)。
    K、D值范围0-100:
    - 80以上: 超买区
    - 20以下: 超卖区
    - K线穿越D线: 产生交易信号
    """
    if not kline_data_list or len(kline_data_list) < 5:
        return {"description": "数据不足，无法分析KD", "strength": "弱"}

    # 获取最近几个周期的KD值
    recent_data = kline_data_list[-5:]
    k_values = [float(d.get('Stoch_K', 0)) for d in recent_data]
    d_values = [float(d.get('Stoch_D', 0)) for d in recent_data]

    if any(v == 0 for v in k_values + d_values):
        return {"description": "KD数据缺失", "strength": "弱"}

    current_k = k_values[-1]
    current_d = d_values[-1]
    prev_k = k_values[-2]
    prev_d = d_values[-2]
    
    description = []
    strength = "中"

    # 1. 超买超卖判断
    if current_k > 80 and current_d > 80:
        description.append("KD指标处于超买区域")
        if current_k > 90 and current_d > 90:
            description.append("超买程度极高")
            strength = "强"
    elif current_k < 20 and current_d < 20:
        description.append("KD指标处于超卖区域")
        if current_k < 10 and current_d < 10:
            description.append("超卖程度极高")
            strength = "强"
    else:
        description.append("KD指标在中性区域")

    # 2. 金叉死叉判断
    if prev_k < prev_d and current_k > current_d:
        description.append("KD金叉形成")
        strength = "强"
    elif prev_k > prev_d and current_k < current_d:
        description.append("KD死叉形成")
        strength = "强"

    # 3. 趋势和背离分析
    k_trend = current_k - k_values[0]
    price_trend = float(kline_data_list[-1]['close']) - float(kline_data_list[-5]['close'])
    
    if abs(k_trend) > 20:  # KD变化显著
        if k_trend > 0:
            description.append("KD指标呈上升趋势")
            if price_trend < 0:
                description.append("注意可能存在顶背离")
        else:
            description.append("KD指标呈下降趋势")
            if price_trend > 0:
                description.append("注意可能存在底背离")

    # 4. KD钝化分析
    if abs(current_k - current_d) < 5:
        description.append("KD指标趋于钝化")
        strength = "弱"

    return {"description": "，".join(description), "strength": strength}

def _analyze_long_term_ema(kline_data_list):
    """
    分析长期EMA趋势(EMA144和EMA200)。
    主要用于判断大趋势方向和强度。
    """
    if not kline_data_list or len(kline_data_list) < 5:
        return {"description": "数据不足，无法分析长期EMA", "strength": "弱"}

    recent_data = kline_data_list[-5:]
    try:
        ema144_values = [float(d.get('EMA144', 0)) for d in recent_data]
        ema200_values = [float(d.get('EMA200', 0)) for d in recent_data]
        close_prices = [float(d.get('close', 0)) for d in recent_data]
    except (TypeError, ValueError):
        return {"description": "长期EMA数据异常", "strength": "弱"}

    if any(v == 0 for v in ema144_values + ema200_values + close_prices):
        return {"description": "长期EMA数据缺失", "strength": "弱"}

    current_price = close_prices[-1]
    current_144 = ema144_values[-1]
    current_200 = ema200_values[-1]
    prev_144 = ema144_values[-2]
    prev_200 = ema200_values[-2]

    description = []
    strength = "中"

    # 1. 多空趋势判断
    if current_price > current_144 and current_price > current_200:
        description.append("当前价格位于长期均线上方")
        if current_144 > current_200:
            description.append("长期趋势偏多")
            strength = "强"
    elif current_price < current_144 and current_price < current_200:
        description.append("当前价格位于长期均线下方")
        if current_144 < current_200:
            description.append("长期趋势偏空")
            strength = "强"
    else:
        description.append("价格在长期均线之间震荡")

    # 2. 趋势变化分析
    ema144_change = (current_144 - ema144_values[0]) / ema144_values[0] * 100
    ema200_change = (current_200 - ema200_values[0]) / ema200_values[0] * 100

    if abs(ema144_change) > 2:  # 2%的变化视为显著
        if ema144_change > 0:
            description.append("EMA144呈上升趋势")
        else:
            description.append("EMA144呈下降趋势")

    if abs(ema200_change) > 2:
        if ema200_change > 0:
            description.append("EMA200呈上升趋势")
        else:
            description.append("EMA200呈下降趋势")

    # 3. 均线交叉分析
    if prev_144 <= prev_200 and current_144 > current_200:
        description.append("长期均线金叉，趋势可能转多")
        strength = "强"
    elif prev_144 >= prev_200 and current_144 < current_200:
        description.append("长期均线死叉，趋势可能转空")
        strength = "强"

    # 4. 趋势强度分析
    price_to_ema_ratio = abs((current_price - current_200) / current_200 * 100)
    if price_to_ema_ratio > 5:
        description.append("价格与长期均线偏离较大，注意回归风险")
    
    # 5. 趋势稳定性分析
    if all(abs((p - e) / e) < 0.01 for p, e in zip(close_prices, ema200_values)):
        description.append("价格紧贴200均线，趋势不明确")
        strength = "弱"

    return {"description": "，".join(description), "strength": strength}

def _analyze_stoch_rsi(kline_data_list):
    """
    分析随机RSI指标。
    StochRSI结合了随机指标和RSI的特点，提供更敏感的超买超卖信号。
    值域为0-100:
    - 80以上: 超买区
    - 20以下: 超卖区
    """
    if not kline_data_list or len(kline_data_list) < 5:
        return {"description": "数据不足，无法分析StochRSI", "strength": "弱"}

    # 获取最近几个周期的StochRSI值
    recent_data = kline_data_list[-5:]
    k_values = [d.get('StochRSI_K') for d in recent_data]
    d_values = [d.get('StochRSI_D') for d in recent_data]
    
    # 检查是否存在 None 或 NaN 值
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in k_values + d_values):
        return {"description": "StochRSI数据缺失或无效。", "strength": "弱"}

    # 确保所有值都是 float 类型
    try:
        k_values = [float(v) for v in k_values]
        d_values = [float(v) for v in d_values]
    except (TypeError, ValueError):
         return {"description": "StochRSI数据格式错误。", "strength": "弱"}

    current_k = k_values[-1]
    current_d = d_values[-1]
    prev_k = k_values[-2]
    prev_d = d_values[-2]
    
    description = []
    strength = "中"

    # 1. 超买超卖判断
    if current_k > 80:
        if current_k > 90:
            description.append("StochRSI显示极度超买")
            strength = "强"
        else:
            description.append("StochRSI显示超买")
    elif current_k < 20:
        if current_k < 10:
            description.append("StochRSI显示极度超卖")
            strength = "强"
        else:
            description.append("StochRSI显示超卖")
    
    # 2. 金叉死叉判断
    if prev_k < prev_d and current_k > current_d:
        description.append("StochRSI形成金叉")
        strength = "强"
    elif prev_k > prev_d and current_k < current_d:
        description.append("StochRSI形成死叉")
        strength = "强"

    # 3. 趋势动量分析
    momentum = abs(current_k - k_values[0])
    if momentum > 30:
        if current_k > k_values[0]:
            description.append("StochRSI动能强劲上升")
        else:
            description.append("StochRSI动能强劲下降")
    elif momentum > 15:
        if current_k > k_values[0]:
            description.append("StochRSI温和上升")
        else:
            description.append("StochRSI温和下降")

    # 4. 震荡分析
    if all(20 <= k <= 80 for k in k_values):
        description.append("StochRSI在中性区域震荡")
        strength = "弱"

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
        "long_term_ema": _analyze_long_term_ema(kline_data_list),
        "rsi_analysis": _analyze_rsi(kline_data_list),
        "macd_analysis": _analyze_macd(kline_data_list),
        "adx_analysis": _analyze_adx(kline_data_list),
        "stochastic": _analyze_stochastic(kline_data_list),
        "stoch_rsi": _analyze_stoch_rsi(kline_data_list)
    }
    
    return analysis_results