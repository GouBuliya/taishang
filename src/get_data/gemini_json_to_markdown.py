# gemini_json_to_markdown.py
"""
将 Gemini API 返回的 JSON 格式化为中文要点 Markdown。
"""
import json

def gemini_json_to_markdown(reply_text: str) -> str:
    """
    将 Gemini API 返回的 JSON 字符串转为 Markdown 格式。
    :param reply_text: Gemini API 返回的字符串（JSON或普通文本）
    :return: Markdown 格式字符串
    """
    try:
        data = json.loads(reply_text)
    except Exception:
        # 非JSON直接返回原文
        return reply_text
    lines = []
    mapping = {
        'short_term_reason': '### 短线分析',
        'mid_term_reason': '### 中线分析',
        'long_term_reason': '### 长线分析',
        'vp_analysis': '### 成交量分布',
        'volume_analysis': '### 量能分析',
        'price_action': '### 价格行为',
        'summary': '### 总结',
        'entry_condition': '### 入场条件',
        'stop_loss': '### 止损',
        'take_profit': '### 止盈目标',
        'risk_management': '### 风控建议',
        'position_action': '### 持仓调整',
        'MARKET': '### 市场状态',
        'symbol': '### 交易对',
        'timeframe': '### 周期',
    }
    for k, label in mapping.items():
        v = data.get(k, None)
        if v is not None:
            if isinstance(v, list):
                v = ', '.join(str(i) for i in v)
            lines.append(f"{label}\n{v}\n")
    # operation子字段
    op = data.get('operation', {})
    if isinstance(op, dict):
        op_map = {
            'type': '操作类型',
            'price': '挂单价格',
            'stop_loss': '止损',
            'take_profit': '止盈目标',
            'size': '仓位大小',
            'expected_winrate': '预计胜率',
            'expected_return': '期望收益',
            'confidence': 'AI置信度',
            'signal_strength': '信号强度',
            'comment': '补充说明',
        }
        op_lines = []
        for k, label in op_map.items():
            v = op.get(k, None)
            if v is not None:
                if isinstance(v, list):
                    v = ', '.join(str(i) for i in v)
                op_lines.append(f"- **{label}**：{v}")
        if op_lines:
            lines.append("#### 操作建议\n" + '\n'.join(op_lines) + '\n')
    return '\n'.join(lines) if lines else reply_text

if __name__ == "__main__":
    # 测试
    s = '{"short_term_reason": "短线看多", "operation": {"type": "买入", "price": "100"}}'
    print(gemini_json_to_markdown(s))
