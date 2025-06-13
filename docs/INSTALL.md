# TaiShang 安装指南

本文档详细说明了如何安装和配置TaiShang交易系统。

## 系统要求

### 操作系统
- Linux（推荐Ubuntu 22.04或更高版本）
- 其他Unix系统（macOS等）也应该可以工作

### 系统依赖
1. Python 3.8+
2. Google Chrome浏览器
3. Git（用于克隆代码库）

## 安装步骤

### 1. 安装系统依赖

#### Ubuntu/Debian
```bash
# 更新包列表
sudo apt update

# 安装Python和pip
sudo apt install python3 python3-pip

# 安装Chrome浏览器
sudo apt install google-chrome-stable

# 安装其他必要的系统包
sudo apt install build-essential python3-dev
```

#### macOS
```bash
# 使用Homebrew安装依赖
brew install python
brew install --cask google-chrome
```

### 2. 克隆代码库
```bash
git clone [repository-url]
cd taishang
```

### 3. 创建虚拟环境（推荐）
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
# .\venv\Scripts\activate
```

### 4. 安装Python依赖

```bash
# 升级pip
pip install --upgrade pip

# 安装核心依赖
pip install -r requirements.txt
```

### 5. 配置系统

1. 创建配置文件
```bash
cp config/config.json.example config/config.json
```

2. 编辑配置文件
```bash
# 使用你喜欢的编辑器打开配置文件
nano config/config.json
```

需要配置的关键项目：
- OKX API凭证（从OKX开发者平台获取）
- Gemini API密钥（从Google AI Studio获取）
- 代理设置（如果需要）
- 系统路径配置

### 6. 验证安装

1. 检查Python依赖
```bash
python3 -c "import okx; import google.generativeai; import pandas; print('Dependencies OK')"
```

2. 检查Chrome安装
```bash
google-chrome --version
```

3. 运行系统测试
```bash
python3 -m pytest tests/
```

## 常见问题

### 1. Chrome驱动问题
如果遇到Chrome驱动相关的错误：
```bash
# 手动安装特定版本的undetected-chromedriver
pip install undetected-chromedriver==3.5.5
```

### 2. 依赖冲突
如果遇到依赖冲突：
```bash
# 清理并重新安装依赖
pip freeze > old_requirements.txt
pip uninstall -r old_requirements.txt -y
pip install -r requirements.txt
```

### 3. 权限问题
确保以下目录具有正确的权限：
```bash
# 创建必要的目录
mkdir -p logs data/cache_screenshot

# 设置权限
chmod 755 logs data/cache_screenshot
```

## 更新系统

要更新到最新版本：
```bash
# 获取最新代码
git pull

# 更新依赖
pip install -r requirements.txt --upgrade

# 重新运行测试
python3 -m pytest tests/
```

## 安全建议

1. API密钥安全
- 不要在代码中硬编码API密钥
- 使用环境变量或加密配置文件
- 定期更换API密钥

2. 系统安全
- 保持系统和依赖包更新
- 使用防火墙限制网络访问
- 定期备份配置和数据

## 下一步

安装完成后，请参考：
- [用户手册](./USER_GUIDE.md)：了解如何使用系统
- [配置指南](./CONFIGURATION.md)：了解详细的配置选项
- [开发指南](./DEVELOPMENT.md)：了解如何开发和扩展系统

## 支持

如果遇到问题：
1. 检查[常见问题](#常见问题)部分
2. 查看项目的[问题跟踪器](issues-url)
3. 创建新的问题报告

## 许可证

[添加许可证信息]