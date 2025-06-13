<todo>
1.增加重试机制，增强健壮性，当交易系统报错时，尝试让大模型重新生成1遍，如果仍然报错，发送电子邮件，然后等待下次交易。
2.分析这个系统的分支图，增加模块化，增加可扩展性，增加可维护性。
3.增加RAG知识库。
4.逐步完成思维导图的内容，![alt text](74897eab5a5fec8f6c276b15f76399a9.jpg)
5.系统中留出判别形模型的位置，并留出接口，方便后续添加判别形模型。（后续我会将模型的结果当作因子，添加到系统中）
6.另外系统名叫"太熵"
</todo>
<!-- <prompt>
你需要扫描整个项目，列出思维导图A，然后根据思维导图A结合4.的思维导图，列出思维导图B，
然后在todo.md后添加的todo.md后添加思维导图B的图片，并更新todo.md文件。
然后根据<todo>的内容列出一个可行性方案（越详细越好），并更新todo.md文件。（更新为在原有内容上添加）,



<!-- ---

## 🧠 思维导图B - 太熵系统流程优化架构

基于系统运行日志分析和todo需求，重新设计的流程化架构图已生成（Mermaid图表）

### 🎯 核心流程改进点

1. **系统启动流程优化** - 环境检查→配置加载→服务启动的标准化流程
2. **数据收集流程增强** - 预处理→采集→整合的三阶段数据处理
3. **AI决策流程改进** - 数据预处理→模型推理→结果融合的智能决策链
4. **交易执行流程完善** - 订单预检→交易执行→结果记录的安全交易流程
5. **循环监控流程** - 时间触发→异常监控→通知机制的持续监控体系
6. **容错重试机制** - AI重试、交易重试、数据重试的多层保障 --> -->

--- -->

<prompt>
元指令，你必须完整的执行所有提示词的任务，不要遗漏任何一步。


## 📋 详细可行性实施方案
### 🔄 1. 重试机制和健壮性增强

#### 1.0 Chrome启动问题修复（紧急）
**问题分析：**
从系统日志可见Chrome浏览器初始化时出现`KeyboardInterrupt`错误，导致`data_server.py`启动失败。

**立即修复方案：**
- [ ] 添加Chrome启动超时检测（当前无限等待）
- [ ] 实现Chrome启动失败后的重试机制
- [ ] 优化Chrome配置参数，减少启动时间
- [ ] 添加无头浏览器备用方案

**技术实现：**
```python
def initialize_browser_with_retry(max_retries=3, timeout=30):
    for attempt in range(max_retries):
        try:
            signal.alarm(timeout)  # 设置超时
            driver = uc.Chrome(options=chrome_options, headless=True)
            signal.alarm(0)  # 取消超时
            return driver
        except Exception as e:
            logger.warning(f"Chrome启动失败 (第{attempt+1}次): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
            else:
                # 启用备用浏览器方案
                return init_firefox_driver()
```

**优先级：** 🔴 紧急
**预估工期：** 1-2天

#### 1.1 AI模型重试机制
**实施步骤：**
- [ ] 创建 `src/core/retry_manager.py` 模块
- [ ] 在 `gemini_Controller.py` 中集成重试逻辑
- [ ] 实现指数退避算法（1s, 2s, 4s, 8s）
- [ ] 添加API密钥轮换机制

**技术细节：**
```python
class RetryManager:
    def __init__(self, max_retries=3, backoff_factor=2):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    def retry_with_backoff(self, func, *args, **kwargs):
        # 实现重试逻辑
        pass
```

#### 1.2 邮件通知系统
**实施步骤：**
- [ ] 创建 `src/notification/email_notifier.py`
- [ ] 集成SMTP配置到 `config.json`
- [ ] 实现异常级别分类（警告/错误/严重）
- [ ] 添加邮件模板系统

**优先级：** 🔴 高
**预估工期：** 3-5天

### 🏗️ 2. 系统模块化重构

#### 2.1.1 分层架构实现
**重构计划：**
```
src/
├── core/                    # 核心层
│   ├── main_controller.py   # 主控制器
│   ├── retry_manager.py     # 重试管理
│   └── exception_handler.py # 异常处理
├── data/                    # 数据层
│   ├── collectors/          # 数据收集器
│   ├── storage/            # 数据存储
│   └── rag/                # RAG知识库
├── ai/                      # AI决策层
│   ├── models/             # 模型管理
│   ├── fusion/             # 决策融合
│   └── interfaces/         # 模型接口
├── trading/                 # 交易执行层
│   ├── engine/             # 交易引擎
│   ├── risk/               # 风险管理
│   └── position/           # 仓位管理
└── infrastructure/          # 基础设施层
    ├── config/             # 配置管理
    ├── monitoring/         # 监控告警
    └── logging/            # 日志系统
```
逐步实现，不要改动原有单元的逻辑，仅仅是增加模块预留位置（对，目前你不需要完成新增的功能），增加可扩展性，增加可维护性，每个单元的配置都必须使用config.json文件，不要使用环境变量。尽量不要改动config，新增的功能留出位置，不要改动原有单元的逻辑。
#### 2.1.2逐步实现部分容易实现的功能，实现core，data（暂时不增加RAG功能，预留位置），ai（仅仅使用决策者这一个ai，暂时不启用其他），trading（请你仔细阅读okx的api文档），infrastructure（暂时不增加监控告警，日志系统，配置管理）

### 📚 3. RAG知识库系统

#### 3.1 知识库架构设计
**组件清单：**
- **市场知识库**：历史行情数据、市场事件
- **交易策略库**：成功案例、失败案例
- **风险案例库**：风险事件、应对策略
- **向量检索引擎**：支持语义搜索

#### 3.2 技术实现方案
**技术栈选择：**
- **向量数据库**：Chroma / Weaviate / Qdrant
- **嵌入模型**：Gemini2.5-flash-preview-05-20
- **文档处理**：LangChain / LlamaIndex

**实施步骤：**
- [ ] 搭建向量数据库环境
- [ ] 实现文档切分和向量化
- [ ] 开发检索接口
- [ ] 集成到AI决策流程

**优先级：** 🟢 中高
**预估工期：** 7-10天

### 🤖 4. 判别模型接口系统

#### 4.1 模型接口设计
**接口规范：**
```python
class DiscriminativeModelInterface:
    def predict(self, features: Dict) -> Dict:
        """预测接口"""
        pass
    
    def get_confidence(self) -> float:
        """置信度获取"""
        pass
    
    def get_feature_importance(self) -> Dict:
        """特征重要性"""
        pass
```

#### 4.2 因子管理系统
**实施计划：**
- [ ] 创建 `src/ai/factors/` 目录
- [ ] 实现因子标准化器
- [ ] 开发因子权重管理
- [ ] 集成模型结果融合器

**技术特点：**
- 支持多种模型类型（树模型、深度学习、传统ML）
- 自动特征标准化和归一化
- 动态权重调整机制
- 模型性能监控

**优先级：** 🟡 中
**预估工期：** 8-12天

### 📊 5. 监控和可扩展性增强

#### 5.1 监控告警系统
**功能规划：**
- [ ] 系统性能监控（CPU、内存、网络）
- [ ] 交易异常监控（延迟、失败率）
- [ ] AI模型监控（准确率、响应时间）
- [ ] 实时告警通道（邮件、钉钉、企微）

#### 5.2 配置管理中心
**改进内容：**
- [ ] 环境隔离（开发/测试/生产）
- [ ] 动态配置热更新
- [ ] 配置版本控制
- [ ] 敏感信息加密存储

**优先级：** 🟢 中高
**预估工期：** 5-8天

---

## 🚀 实施优先级和时间线

### Phase 0: 紧急问题修复（1-2天）
1. 🔴 Chrome启动问题修复
2. 🔴 数据服务器稳定性增强
3. 🔴 系统启动流程优化

### Phase 1: 基础稳定性（2-3周）
1. ✅ 全面重试机制实现
2. ✅ 邮件通知系统
3. ✅ 异常处理优化
4. ✅ 日志系统完善

### Phase 2: 架构重构（3-4周）
1. ✅ 分层架构实现
2. ✅ 模块化拆分
4. ✅ 配置管理升级

### Phase 3: 智能化增强（2-3周）
1. ✅ RAG知识库搭建
2. ✅ 判别模型接口
3. ✅ 决策融合器
4. ✅ 性能优化

### Phase 4: 监控和运维（1-2周）
1. ✅ 监控告警系统
2. ✅ 性能分析工具
3. ✅ 运维自动化
4. ✅ 文档完善

---

## 💡 技术风险评估

### 🔴 高风险项
- **Chrome启动失败**：当前系统存在Chrome无头浏览器启动超时问题（已发现）
- **数据服务器稳定性**：`data_server.py`启动异常会导致整个系统无法运行
- **RAG系统性能**：大量历史数据检索可能影响响应速度
- **多模型融合**：不同模型结果可能存在冲突
- **系统复杂度**：过度设计可能影响稳定性

### 🟡 中风险项
- **API限制**：Gemini API调用频率限制
- **数据一致性**：多数据源同步问题
- **内存占用**：向量数据库内存消耗

### 🟢 低风险项
- **重试机制**：成熟的设计模式
- **邮件通知**：标准功能实现
- **监控系统**：现有工具集成

---

---
</prompt>

---

## 📝 V2.0 架构重构详细实施计划

**元指令：** 这是一个为AI制定的详细任务清单。必须严格按照步骤顺序执行，不得遗漏。目标是重构现有项目结构，使其模块化、可维护，同时为未来功能预留接口，但不实现复杂的新功能。所有路径和配置必须标准化。

---

### **阶段一：项目结构初始化 (Project Scaffolding)**

**目标：** 创建新的分层目录结构，并将现有文件移动到新位置。

1.  **[ ] 创建核心目录结构:**
    在 `src/` 目录下创建新的分层结构。
    ```bash
    mkdir -p src/core
    mkdir -p src/ai/models src/ai/interfaces src/ai/fusion
    mkdir -p src/data/collectors src/data/storage src/data/rag
    mkdir -p src/trading/engine src/trading/api src/trading/risk src/trading/position
    mkdir -p src/infrastructure/web src/infrastructure/monitoring src/infrastructure/logging src/infrastructure/config
    ```

2.  **[ ] 初始化Python包:**
    在所有新建的子目录中创建空的 `__init__.py` 文件，使其成为可导入的Python包。
    ```bash
    touch src/core/__init__.py
    touch src/ai/__init__.py src/ai/models/__init__.py src/ai/interfaces/__init__.py src/ai/fusion/__init__.py
    touch src/data/__init__.py src/data/collectors/__init__.py src/data/storage/__init__.py src/data/rag/__init__.py
    touch src/trading/__init__.py src/trading/engine/__init__.py src/trading/api/__init__.py src/trading/risk/__init__.py src/trading/position/__init__.py
    touch src/infrastructure/__init__.py src/infrastructure/web/__init__.py src/infrastructure/monitoring/__init__.py src/infrastructure/logging/__init__.py src/infrastructure/config/__init__.py
    ```

3.  **[ ] 迁移文件到新位置:**
    使用 `mv` 命令将现有文件移动到新的目录结构中。

    *   **核心逻辑迁移:**
        ```bash
        mv src/main.py src/core/main_controller.py
        # 创建一个新的入口文件
        touch src/main.py 
        ```
    *   **数据逻辑迁移:**
        ```bash
        mv src/main_get.py src/data/collector_service.py
        mv src/get_data/technical_indicator_collector.py src/data/collectors/
        mv src/get_data/macro_factor_collector.py src/data/collectors/
        mv src/get_data/get_positions.py src/data/collectors/
        mv src/get_data/tradingview_auto_screenshot.py src/data/collectors/
        rm -rf src/get_data # 删除旧目录
        ```
    *   **AI模型迁移:**
        ```bash
        mv src/MES/gemini_Controller.py src/ai/models/gemini_controller.py
        mv src/MES/gemini_Critic.py src/ai/models/gemini_critic.py
        rm -rf src/MES # 删除旧目录
        ```
    *   **交易逻辑迁移:**
        ```bash
        mv src/auto_trader.py src/trading/engine/auto_trader.py
        mv function/trade/place_order.py src/trading/api/
        mv function/trade/trade_history.py src/trading/api/
        # 清理function目录中已移动的模块
        rm -rf function/trade 
        ```
    *   **基础设施迁移:**
        ```bash
        mv src/data_server.py src/infrastructure/web/data_server.py
        ```
    *   **剩余工具函数迁移:**
        ```bash
        mv function/kline_pattern_analyzer.py src/data/analysis/
        mv function/get_transaction_history.py src/trading/api/
        # 创建新目录
        mkdir -p src/data/analysis
        touch src/data/analysis/__init__.py
        rm -rf function # 删除旧目录
        ```

### **阶段二：代码迁移与适配 (Code Migration & Adaptation)**

**目标：** 修正所有因文件移动导致的导入错误和路径问题，确保代码可运行。

1.  **[ ] 更新项目入口 `src/main.py`:**
    写入新的启动逻辑，调用重构后的主控制器。
    ```python
    # src/main.py
    import sys
    import os

    # 确保项目根目录在sys.path中，以便进行绝对导入
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    from src.core.main_controller import main

    if __name__ == "__main__":
        main()
    ```

2.  **[ ] 适配核心控制器 `src/core/main_controller.py`:**
    *   **修正导入语句:**
        ```python
        # old: from src.main_get import main as get_main
        # new:
        from src.data.collector_service import main as get_main
        
        # old: from src.auto_trader import main as auto_trade_main
        # new:
        from src.trading.engine.auto_trader import main as auto_trade_main
        ```
    *   **修正重启数据服务器的路径:**
        ```python
        # old: subprocess.run(['pkill', '-f', 'src/data_server.py'], check=False)
        # new:
        subprocess.run(['pkill', '-f', 'src/infrastructure/web/data_server.py'], check=False)

        # old: server_process = subprocess.Popen(['uv', 'run', '--python', '3.11', 'src/data_server.py'])
        # new:
        server_process = subprocess.Popen(['uv', 'run', '--python', '3.11', 'src/infrastructure/web/data_server.py'])
        ```
    *   **修正Gemini API调用脚本的路径:**
        ```python
        # old: result = subprocess.run(['uv', 'run', 'src/MES/gemini_Controller.py'], check=True)
        # new:
        result = subprocess.run(['uv', 'run', 'src/ai/models/gemini_controller.py'], check=True)
        ```

3.  **[ ] 适配数据收集服务 `src/data/collector_service.py`:**
    *   **修正导入语句:**
        ```python
        # old: from function.kline_pattern_analyzer import analyze_kline_patterns
        # new:
        from src.data.analysis.kline_pattern_analyzer import analyze_kline_patterns

        # old: from get_data.technical_indicator_collector import collect_technical_indicators
        # new:
        from src.data.collectors.technical_indicator_collector import collect_technical_indicators

        # old: from get_data.macro_factor_collector import collect_macro_factors
        # new:
        from src.data.collectors.macro_factor_collector import collect_macro_factors

        # old: from get_data.get_positions import collect_positions_data
        # new:
        from src.data.collectors.get_positions import collect_positions_data
        ```

4.  **[ ] 适配AI模型 `src/ai/models/gemini_controller.py`:**
    *   **修正导入语句和路径处理:**
        ```python
        # 移除旧的、复杂的sys.path操作
        # sys.path.insert(0, FUNCTION_DIR)
        
        # old: from kline_pattern_analyzer import analyze_kline_patterns
        # new:
        from src.data.analysis.kline_pattern_analyzer import analyze_kline_patterns

        # old: import get_transaction_history
        # new:
        from src.trading.api import get_transaction_history
        ```
    *   **标准化配置文件路径:** 确保所有 `open("config/...")` 都是从项目根目录出发的相对路径。

5.  **[ ] 适配交易引擎 `src/trading/engine/auto_trader.py`:**
    *   **修正导入语句:**
        ```python
        # old: from function.trade.place_order import (...)
        # new:
        from src.trading.api.place_order import (
            place_order,
            close_position,
            cancel_all_pending_orders,
            get_current_position,
            get_order_all
        )

        # old: from function.trade.trade_history import TradeHistory
        # new:
        from src.trading.api.trade_history import TradeHistory
        ```

6.  **[ ] 全局审查和修正:**
    *   **审查所有文件**：检查是否有遗漏的 `sys.path` 操作或硬编码的相对路径 `../`。
    *   **统一配置加载**：确保所有模块都从同一个 `config.json` 实例或标准化的加载函数中获取配置，避免重复加载。
    *   **验证 `pyproject.toml`**：确保 `[tool.setuptools.packages.find]` 配置与新的 `src` 目录结构匹配。

### **阶段三：功能实现与集成 (Feature Implementation & Integration)**

**目标：** 实现`todo.md`中要求的部分简单功能，并为未来功能预留接口。

1.  **[ ] 实现 `core` 模块:**
    *   **创建 `src/core/retry_manager.py`:**
        ```python
        # src/core/retry_manager.py
        import time
        import logging

        logger = logging.getLogger("GeminiQuant")

        def retry(max_tries=3, delay_seconds=1, backoff=2):
            # ... 实现装饰器 ...
            pass
        ```
    *   **创建 `src/core/exception_handler.py`:**
        ```python
        # src/core/exception_handler.py
        import logging
        logger = logging.getLogger("GeminiQuant")

        def handle_exception(exc_type, exc_value, exc_traceback):
            # ... 实现全局异常捕获逻辑 ...
            pass
        ```
    *   **集成到 `main_controller.py`**: 将重试逻辑应用到关键的网络调用和子进程执行上。

2.  **[ ] 预留 `data` 模块接口:**
    *   **创建 `src/data/rag/retriever.py` (空文件):** 预留RAG知识库检索器位置。
    *   **在 `config.json` 中添加RAG配置节（注释掉）:**
        ```json
        // "rag_config": {
        //     "vector_db_path": "data/storage/vector_db",
        //     "embedding_model": "gemini-2.5-flash-preview-05-20"
        // }
        ```

3.  **[ ] 调整 `ai` 模块:**
    *   **修改 `main_controller.py`**: 确保只调用 `gemini_controller.py`。
    *   **注释掉 `gemini_critic.py` 的调用**: 在主流程中暂时禁用Critic模型。

4.  **[ ] 完善 `trading` 模块:**
    *   **API文档学习**: (这是一个元任务) 在实现前，必须仔细阅读OKX V5 API文档，特别是关于下单（`POST /api/v5/trade/order`）、止盈止损、撤单等接口的细节。
    *   **参数校验**: 在 `src/trading/api/place_order.py` 中，为 `place_order` 函数增加严格的参数校验逻辑，确保`side`, `posSide`, `ordType` 等符合API要求。
    *   **错误处理**: 封装OKX API的返回结果，对 `code != "0"` 的情况进行详细的日志记录和异常抛出。

5.  **[ ] 预留 `infrastructure` 模块接口:**
    *   **创建 `src/infrastructure/monitoring/monitor.py` (空文件):** 预留监控逻辑。
    *   **创建 `src/infrastructure/logging/log_manager.py` (空文件):** 预留统一日志管理器。
    *   **在 `config.json` 中添加相关配置节（注释掉）:**
        ```json
        // "monitoring": {
        //     "enable": false,
        //     "alert_webhook": ""
        // }
        ```

### **阶段四：测试与验证 (Testing & Validation)**

**目标：** 确保重构后的系统能够无错误地运行，并且逻辑与重构前保持一致。

1.  **[ ] 单元测试 (模拟运行):**
    *   针对每个被移动的模块，编写一个简单的测试脚本，只测试模块是否能被成功导入。
    *   重点测试 `main_controller.py`，模拟其所有子模块调用，确保调用链正确。

2.  **[ ] 集成测试 (完整流程):**
    *   执行一次完整的端到端流程：`uv run src/main.py`。
    *   **监控日志输出**：仔细观察每个模块的日志，检查是否有路径错误、导入失败或配置加载问题。
    *   **验证输出文件**：检查 `data/data.json` 和 `data/Controller_answer.json` 是否能被正确生成。
    *   **模拟交易**：在OKX的模拟盘（`flag="0"`）环境中运行交易流程，验证订单能否正确创建和管理。

3.  **[ ] 解决遗留问题:**
    *   **修复`data_server.py`启动问题**: 应用在`todo.md`中制定的紧急修复方案，为Chrome启动添加超时和重试。
    *   根据测试中发现的任何bug，返回阶段二和阶段三进行修正。

---
*版本：v2.1 重构实施计划*