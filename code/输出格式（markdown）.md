## 标的：{symbol}
  #### 主周期：{timeframe}
  #### 当前时间：{timestamp}
  #### 市场状态：{MARKET}

  #### 交易策略：
  {operation.strategy}
  #### 量化特征值：
  {quant_features_output}
  #### 量化特征值分析：
  ##### 低阶反思：
  - 短期分析：{short_term_reason}
  - 中期分析：{mid_term_reason}
  - 长期分析：{long_term_reason}
  - 成交量分析：{volume_analysis}
  - 价格行为分析：{price_action}
  - 指标分析：{indicators_analysis}
  - 成交量分布分析：{vp_analysis}
  ##### 高级策略：
  {advanced_strategy}
  #### 胜率与期望收益计算：
  - 胜率：{expected_winrate}
  - 期望收益：{expected_return}
  $$
\boxed{
\begin{aligned}
&\underbrace{z}_{\text{log-odds}}
\;=\; w_0 \;+\; \sum_{i=1}^{n} w_i X_i, \\[6pt]
&\underbrace{p}_{\text{胜率}}
\;=\;\sigma(z)
\;=\;\frac{1}{1 + e^{-z}}, \\[6pt]
&\underbrace{\mathbb{E}[R]}_{\text{期望收益}}
\;=\; p \times \underbrace{\biggl(\frac{\mathrm{TP}-\mathrm{Entry}}{\mathrm{Entry}}\biggr)}_{R_{gain}}\;-
(1-p)\times \underbrace{\biggl(\frac{\mathrm{Entry}-\mathrm{SL}}{\mathrm{Entry}}\biggr)}_{R_{loss}}.
\end{aligned}
}
$$ 
% > 注意：公式中的 Entry、SL、TP 等为变量，实际输出时请用具体数值替换。
  - 胜率公式：$p=\sigma(z)=\frac{1}{1+e^{-z}}$
  - 期望收益公式：$\mathbb{E}[R]=p\cdot R_{gain} - (1-p)\cdot R_{loss}$
  - 胜率：$p=\sigma(z)=\frac{1}{1+e^{-z}}$
  #### 自检与一致性校验：
  - 检查结果：{self_check}
  - 内部协调：{internal_coordination}
  - 逻辑验证：{logic_validation}
  - 合理性验证：{rationality_validation}
  #### 数据整理：
  - 数据格式：{data_format}
  - 数据完整性：{data_integrity}  

  #### 数据来源：
  {data_source}

  #### 交易操作：
  {operation.comment}
  - 操作类型：{operation.type}
  - 挂单价：{operation.price}
  - 止损价：{operation.stop_loss}
  - 止盈目标：{operation.take_profit}
  - 仓位大小：{operation.size}
  - 预计胜率：{operation.expected_winrate}
  - 期望收益：{operation.expected_return}
  - 风险收益比：{operation.trade_RR_ratio}
  - AI信心度：{operation.confidence}
  - 信号强度：{operation.signal_strength}
