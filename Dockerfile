# Qwen_quant_v1 Dockerfile for Trading Bot
FROM python:3.12-slim-bookworm

# 设置容器内的工作目录
WORKDIR /app

# 安装必要的系统依赖（用于 Chrome 浏览器和 xclip 等工具）
# 这些依赖是运行 Chromium / Chrome Headless 所必需的
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    chromium \
    chromium-browser-l10n \
    xvfb \
    xclip \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxcomposite1 \
    libxi6 \
    libxrandr2 \
    libxext6 \
    libxkbcommon0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libjpeg-turbo8 \
    libu2f-udev \
    libvulkan1 \
    libxss1 \
    libxshmfence1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libxinerama1 \
    libxmuu1 \
    ca-certificates \
    gnupg \
    apt-transport-https \
    lsb-release && \
    rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 到工作目录，以便安装依赖
COPY requirements.txt ./

# 创建并激活虚拟环境，然后安装 Python 依赖
RUN python -m venv venv && \
    venv/bin/pip install --upgrade pip && \
    venv/bin/pip install --no-cache-dir -r requirements.txt && \
    venv/bin/pip install --no-cache-dir setuptools # 确保 setuptools 存在以解决 distutils 问题

# 将所有项目文件复制到 /app 目录
# 注意：.dockerignore 会在这里生效，排除不需要的文件
COPY . .

# 设置环境变量，确保 Python 解释器指向虚拟环境
ENV VIRTUAL_ENV=/app/venv
ENV PATH="/app/venv/bin:$PATH"

# 设置环境变量用于脚本内部检查和API Key
ENV VIRTUAL_ENV_PYTHON_PATH="/app/venv/bin/python"
# QWEN_API_KEY 不建议在此处硬编码，推荐在 docker run 命令中通过 -e 传递
# ENV QWEN_API_KEY="your_api_key_here" # 如果需要默认值，可以取消注释并修改

# 如果你的应用是 Web 服务（例如 Flask），暴露端口
EXPOSE 3000

# 启动命令
# 明确使用虚拟环境中的 Python 解释器运行你的主脚本
# 请根据你的实际主入口脚本名称和路径进行修改
# 假设你的主入口点是 code/main.py
CMD ["/app/venv/bin/python", "code/main.py"]