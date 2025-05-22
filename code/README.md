# Gemini金融智能体 / code 目录说明

本文件夹为“基于gemini多模态识别K线的金融智能体”项目的核心代码目录，包含量化GUI、数据采集、技术指标、宏观因子、Gemini对接、Telegram Bot等主要功能模块。

## 主要文件说明

- **main.py**  
  主采集脚本，自动调用技术指标与宏观因子采集，输出标准JSON结果。

- **technical_indicator_collector.py**  
  技术指标采集与计算脚本。

- **macro_factor_collector.py**  
  宏观因子采集脚本。

- **quant_gui.py**  
  量化助手桌面GUI主程序，支持持仓信息录入、脚本运行、日志输出、Gemini对话区等。

- **position_info_widget.py**  
  持仓信息录入控件，供主界面复用。

- **telegram_bot.py**  
  Telegram Bot监听与自动化，支持“获取data”指令自动运行采集脚本并分块回复结构化结果。

- **icon.png**  
  桌面GUI窗口图标。

## 典型功能流程

1. 通过GUI录入持仓、参数，或通过Telegram发送“获取data”指令。
2. 自动运行main.py，采集技术指标与宏观因子，输出结构化JSON。
3. 结果可在GUI日志区查看，或由Bot分块、结构化、中文回复。
4. 支持异常标注、格式美化、分块展示等。

## 依赖环境
- Python 3.9+
- PyQt6
- 其他依赖详见各py文件头部注释

