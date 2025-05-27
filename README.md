# 图灵保佑别出bug了


# Gemini金融智能体

本项目为“基于Gemini多模态识别K线的金融智能体”，集成了量化GUI、Web端、数据采集、技术指标、宏观因子、Gemini大模型推理、Telegram Bot等主要功能模块，支持多端一键采集、推理、结构化输出与自检。

---

## 主要亮点

- **Web端流式AI推理**：支持通过Web页面一键采集数据并流式输出Gemini大模型的推理建议，体验AI实时对话式输出。
- **多端支持**：桌面GUI、Web端、Telegram Bot均可发起采集与推理请求，结果多端同步展示。
- **多模态数据采集**：自动采集技术指标、宏观因子、行情快照（如截图），统一输出标准化JSON。
- **结构化输出与自检**：Gemini推理结果严格结构化，支持LaTeX公式、分块展示、自检校验。
- **可扩展与自定义**：系统提示词、输出模板、API Key、代理等均可灵活配置。

---

## Web端流式推理体验

1. 启动Web服务（见下方“快速启动”）。
2. 浏览器访问 `http://localhost:3000`，点击“获取 Gemini 建议”按钮。
3. AI推理内容将以流式方式实时输出在页面，支持长文本、分块、公式等。
4. 支持异常提示、状态反馈、推理完成标记。

---

## 快速启动

1. 安装依赖：
   ```zsh
   pip install -r requirements.txt
   ```
2. 设置Gemini API Key（如有需要可配置代理）：
   ```zsh
   export GEMINI_API_KEY="你的API_KEY"
   # 如需代理：export HTTP_PROXY="http://127.0.0.1:1080"
   ```
3. 启动Web服务：
   ```zsh
   python3 code/web_gui/app.py
   ```
4. 浏览器访问 `http://localhost:3000`，体验流式AI推理。

---

## Docker 打包与运行

### 构建镜像
```zsh
docker build -t qwen_quant_v1 .
```

### 运行 Web 服务
```zsh
docker run -it --rm -p 3000:3000 \
  -e GEMINI_API_KEY=你的API_KEY \
  qwen_quant_v1
```

浏览器访问 http://localhost:3000 体验 Web 端。

### 运行桌面 GUI（可选）
如需在容器内运行 PyQt6 GUI，请确保主机已安装 X11 并允许 X11 转发：
```zsh
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -e GEMINI_API_KEY=你的API_KEY \
  qwen_quant_v1 python start.py
```

> 推荐优先使用 Web 端，GUI 需主机支持图形界面。

---

## 依赖环境

- Python 3.9+
- Flask
- PyQt6（桌面端）
- 其他依赖详见 `requirements.txt`

---

## 主要功能模块

- `main.py`：主采集脚本，自动采集技术指标与宏观因子，输出`data.json`。
- `gemini_api_caller.py`：Gemini API推理与流式输出核心。
- `web_gui/app.py`：Web后端，负责流式推理API。
- `web_gui/static/index.html`：Web前端页面，实时展示AI推理内容。
- `quant_GUI.py`：桌面GUI主程序。
- `telegram_bot.py`：Telegram Bot服务。
- `system_prompt_config.txt`：系统提示词与推理约束。
- `输出格式（markdown）.md`：结构化输出模板。

---

## 典型流程

1. 通过Web端/GUI/Bot发起采集请求。
2. 自动运行`main.py`采集数据，生成`data.json`。
3. Gemini大模型流式推理，输出结构化建议。
4. 结果在Web端流式展示，或同步到GUI/Bot。

---

## 常见问题

- **API Key未设置**：请先设置`GEMINI_API_KEY`环境变量。
- **采集数据失败**：检查`main.py`及依赖环境。
- **推理异常/无响应**：检查API Key、网络、代理设置。
- **自定义输出**：可修改`system_prompt_config.txt`和`输出格式（markdown）.md`。

---

如需详细开发/扩展说明，请参考`code/README.md`及各模块源码与注释。
