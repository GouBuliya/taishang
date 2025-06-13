# TaiShang - AI驱动的加密货币量化交易系统

TaiShang是一个基于Google Gemini AI的自动化加密货币交易系统，专门设计用于OKX交易所的交易。系统结合了技术分析、市场数据和AI决策支持，提供智能化的交易执行服务。

## 主要特性

- 🤖 AI驱动的交易决策（基于Google Gemini）
- 📊 自动化技术分析和市场数据收集
- 📈 实时K线模式识别和趋势分析
- 💹 自动化交易执行（开仓/平仓）
- ⚡ 实时市场监控和风险控制
- 📝 详细的交易日志和分析报告

## 系统架构

```mermaid
graph TD
    A["太熵量化交易系统"] --> B["主控模块 (main.py)"]
    B --> C["核心控制器 (main_controller.py)"]
    B --> D["数据收集服务 (collector_service.py)"]
    B --> E["AI决策模块 (gemini_controller.py)"]
    B --> F["交易执行引擎 (auto_trader.py)"]
    
    C --> C1["系统模式管理"]
    C --> C2["日志记录"]
    C --> C3["异常处理"]
    
    D --> D1["技术指标收集"]
    D --> D2["宏观因子分析"]
    D --> D3["持仓信息获取"]
    D --> D4["K线模式识别"]
    
    E --> E1["Gemini API集成"]
    E --> E2["交易策略生成"]
    E --> E3["指令文件输出"]
    
    F --> F1["OKX交易API"]
    F --> F2["订单管理"]
    F --> F3["风险控制"]
    
    G["配置管理"] --> B
    H["日志系统"] --> B
    I["基础设施服务"] --> B
    
    J["外部服务"] --> J1["OKX交易所"]
    J --> J2["Google Gemini AI"]
    J --> J3["TradingView"]
```

### 核心模块说明

1. **主控模块 (main.py)** - 系统入口点，初始化并启动各子系统
2. **核心控制器 (main_controller.py)** - 系统主控制器，管理运行模式和模块协调
3. **数据收集服务 (collector_service.py)** - 整合技术指标、宏观因子和持仓数据收集
4. **AI决策模块 (gemini_controller.py)** - 基于Gemini AI的交易策略生成系统
5. **交易执行引擎 (auto_trader.py)** - 执行交易指令、管理订单和风险控制
6. **K线模式分析** - 识别K线形态和趋势
7. **基础设施服务** - 提供Web服务等基础设施支持

## 安装指南

1. 克隆仓库
```bash
git clone [repository-url]
cd taishang
```

2. 创建并激活虚拟环境（推荐）
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置系统
- 复制`config/config.json.example`到`config/config.json`
- 填写必要的配置信息：
  * OKX API凭证（api_key, secret_key, passphrase）
  * Gemini API密钥（在MODEL_CONFIG部分）
  * 代理设置（如需要）
  * 数据文件路径配置
  * 日志文件路径配置

## 使用指南

1. 启动系统
```bash
python src/main.py
```

2. 系统模式
- 生产模式：执行真实交易
- 调试模式：仅模拟交易

3. 监控交易
- 查看`logs/main.log`获取系统运行状态
- 查看`logs/trade_history.json`获取交易历史
- 查看`logs/ai_decisions.md`获取AI决策过程

## 开发指南

### 项目结构
```
taishang/
├── config/                 # 配置文件
├── data/                   # 数据文件
├── src/                    # 源代码
│   ├── ai/                # AI相关模块
│   ├── core/              # 核心控制逻辑
│   ├── data/              # 数据收集服务
│   ├── infrastructure/    # 基础设施
│   ├── trading/           # 交易执行模块
│   └── main.py            # 系统入口
├── logs/                  # 日志文件
└── tests/                 # 测试代码
```

## 安全提示

1. API密钥安全
- 使用环境变量或加密配置文件存储敏感信息
- 设置最小必要权限的API密钥
- 定期更换API密钥

2. 风险控制
- 设置合理的交易限额
- 启用止损保护
- 定期检查系统日志

## 免责声明

本系统仅供学习和研究使用。使用本系统进行实际交易时，请注意风险控制，作者不对任何交易损失负责。