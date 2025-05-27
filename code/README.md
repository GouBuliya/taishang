# Gemini金融智能体 / code 目录说明

本项目为“基于Gemini多模态识别K线的金融智能体”，集成了量化GUI、Web端、数据采集、技术指标、宏观因子、Gemini大模型推理、Telegram Bot等主要功能模块，支持多端一键采集、推理、结构化输出与自检。

---

## 一、项目整体架构与数据流

1. **主控流程**：
   - 用户通过GUI、Web或Telegram Bot发起采集请求。
   - 自动运行`main.py`，依次调用技术指标采集（`technical_indicator_collector.py`）、宏观因子采集（`macro_factor_collector.py`）、行情快照采集（如截图），合并输出为标准化JSON（`data.json`）。
   - Gemini推理模块（`gemini_api_caller.py`）读取`data.json`，结合系统提示词（`system_prompt_config.txt`），调用Gemini大模型进行多轮推理与自检，输出结构化建议（支持markdown/LaTeX公式）。
   - 结果可在GUI、Web端、Telegram等多端展示。

2. **模块关系与数据流**：
   - `main.py` → 采集数据 → `data.json`
   - `gemini_api_caller.py` → 读取`data.json`+系统提示词 → Gemini API → 结构化建议
   - `quant_GUI.py`、`web_gui/app.py`、`telegram_bot.py` → 调用主控链路，展示推理结果

---

## 二、主要文件说明

- **main.py**  
  主采集脚本，自动调用技术指标与宏观因子采集，输出标准JSON结果（data.json）。
- **technical_indicator_collector.py**  
  技术指标采集与计算脚本。
- **macro_factor_collector.py**  
  宏观因子采集脚本。
- **quant_GUI.py**  
  量化助手桌面GUI主程序，支持持仓信息录入、脚本运行、日志输出、Gemini对话区等。
- **web_gui/app.py**  
  Web端后端服务，支持一键采集与推理，前端见`web_gui/static/`。
- **telegram_bot.py**  
  Telegram Bot监听与自动化，支持“获取data”指令自动运行采集脚本并分块回复结构化结果。
- **system_prompt_config.txt**  
  系统提示词与推理约束配置，影响AI风格、输出格式、字段完整性等。
- **输出格式（markdown）.md**  
  结构化输出模板，支持LaTeX公式、分块展示、自检校验等。
- **data.json**  
  采集与推理的标准化中间数据文件。

---

## 三、典型功能流程

1. 通过GUI录入持仓、参数，或通过Web/Telegram发送“获取data”指令。
2. 自动运行main.py，采集技术指标与宏观因子，输出结构化JSON（data.json）。
3. Gemini大模型推理，输出结构化建议（支持markdown/LaTeX公式、自检与一致性校验）。
4. 结果可在GUI、Web端、Telegram等多端查看，支持异常标注、格式美化、分块展示等。

---

## 四、关键配置与自检机制

- **API KEY与代理**：
  - Gemini API Key通过环境变量`GEMINI_API_KEY`设置，支持多用户切换。
  - 支持全局HTTP/HTTPS代理（如`http://127.0.0.1:1080`），可在`start.py`、`web_gui/app.py`等处配置。
- **系统提示词与输出格式**：
  - `system_prompt_config.txt`严格约束推理流程、字段完整性、输出格式（如无数据输出N/A），并内置自检与一致性校验机制。
  - 输出格式详见`输出格式（markdown）.md`，支持分块、LaTeX公式、逻辑与合理性验证等。
- **日志与异常处理**：
  - 全链路日志输出至`gemini_quant.log`，便于调试与追溯。

---

## 五、依赖环境与启动方式

- **依赖环境**：
  - Python 3.9+
  - PyQt6
  - Flask（Web端）
  - 其他依赖详见各py文件头部注释与`requirements.txt`

- **一键启动**：
  - 推荐通过`start.py`自动设置环境变量并启动主界面。
  - 也可分别运行`quant_GUI.py`（桌面GUI）、`web_gui/app.py`（Web服务）、`telegram_bot.py`（Bot服务）。

---

## 六、常见问题与扩展

- **多端并发采集与推理**：支持多端同时发起采集与推理请求，自动管理API Key与代理。
- **自定义系统提示词与输出模板**：可根据需求修改`system_prompt_config.txt`与`输出格式（markdown）.md`，实现风格定制。
- **数据完整性与自检**：推理结果自动进行字段完整性、逻辑一致性、合理性等多重校验。

---

如需详细开发/扩展说明，请参考各模块源码与注释。

