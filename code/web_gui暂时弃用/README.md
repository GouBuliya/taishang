# Gemini Quant Web GUI

本项目为基于Flask的量化助手Web端，主要功能：
- 指标及宏观因子采集结果展示（JSON美观渲染）
- 剪切板图片上传与预览
- Gemini操作建议按钮（预留）
- 持仓信息输入与展示
- UI风格仿OKX深色风格

## 快速开始
1. 安装依赖：`pip install flask flask-cors`（如需前端依赖，见前端目录说明）
2. 启动后端：`python app.py`
3. 访问前端页面：`http://localhost:5000`（如为前后端分离，前端请用`npm run dev`等命令启动）

## 目录结构
- app.py         # Flask后端主程序
- static/        # 前端静态资源（HTML/CSS/JS/图片等）
- templates/     # Jinja2模板（如用Flask渲染页面）
- .github/       # Copilot自定义指令

## 说明
- 推荐前后端分离，前端可用Bootstrap/Antd等现代UI框架。
- Gemini相关功能预留API接口，后续可扩展。
