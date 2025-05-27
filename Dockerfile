# Qwen_quant_v1 Dockerfile
# 基于官方 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt ./

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt flask psutil google-generativeai openai okx


# 复制项目全部文件
COPY . .

# 设置环境变量（如有需要可自行修改）
ENV GEMINI_API_KEY="your_Qwen_api_key"
# ENV HTTP_PROXY="http://127.0.0.1:1080"
# ENV HTTPS_PROXY="http://127.0.0.1:1080"

# 暴露Web端口
EXPOSE 5000

# 默认启动Web服务（如需GUI请手动进入容器运行）
# CMD ["python3", "code/web_gui/app.py"]
CMD ["python3", "/code/tradingview_auto_screenshot.py"]
