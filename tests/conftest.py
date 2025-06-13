# tests/conftest.py
import os
import sys
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 确保项目根目录在Python路径中（避免重复）
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入项目模块
from src.core.config_loader import load_config
from src.core.path_manager import PathManager


@pytest.fixture(scope="session")
def project_root():
    """项目根目录fixture"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_config():
    """测试配置fixture"""
    return {
        "okx": {
            "api_key": "test_api_key",
            "secret_key": "test_secret_key",
            "passphrase": "test_passphrase",
            "sandbox": True
        },
        "gemini": {
            "api_key": "test_gemini_key"
        },
        "proxy": {
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "https://127.0.0.1:7890"
        },
        "trading": {
            "leverage": 10,
            "position_size": 0.1,
            "risk_ratio": 0.02
        },
        "main_log_path": "logs/test.log",
        "cache_screenshot_path": "data/test_screenshots"
    }


@pytest.fixture
def temp_path_manager():
    """临时路径管理器fixture"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 创建临时目录结构
        (temp_path / "config").mkdir()
        (temp_path / "data" / "browser_profiles").mkdir(parents=True)
        (temp_path / "data" / "downloads").mkdir(parents=True)
        (temp_path / "data" / "screenshots").mkdir(parents=True)
        (temp_path / "cache" / "reply").mkdir(parents=True)
        (temp_path / "logs").mkdir()
        
        # 创建临时路径配置
        paths_config = {
            "browser_profiles": {
                "base_dir": "data/browser_profiles",
                "chrome_profile": "data/browser_profiles/chrome_profile"
            },
            "data": {
                "downloads": "data/downloads",
                "screenshots": "data/screenshots"
            },
            "cache": {
                "reply": "cache/reply"
            },
            "logs": {
                "base_dir": "logs",
                "main_log": "logs/test.log"
            }
        }
        
        with open(temp_path / "config" / "paths.json", "w") as f:
            json.dump(paths_config, f, indent=2)
        
        # Mock PathManager
        with patch('src.core.path_manager.get_project_root', return_value=str(temp_path)):
            yield PathManager()


@pytest.fixture
def mock_okx_api():
    """模拟OKX API响应"""
    with patch('okx.Trade') as mock_trade, \
         patch('okx.Account') as mock_account, \
         patch('okx.MarketData') as mock_market:
        
        # 模拟交易API
        mock_trade_instance = Mock()
        mock_trade.return_value = mock_trade_instance
        mock_trade_instance.place_order.return_value = {
            'code': '0',
            'data': [{'ordId': '12345', 'clOrdId': 'test_order'}]
        }
        
        # 模拟账户API
        mock_account_instance = Mock()
        mock_account.return_value = mock_account_instance
        mock_account_instance.get_account_balance.return_value = {
            'code': '0',
            'data': [{'totalEq': '10000', 'availEq': '8000'}]
        }
        
        # 模拟市场数据API
        mock_market_instance = Mock()
        mock_market.return_value = mock_market_instance
        mock_market_instance.get_ticker.return_value = {
            'code': '0',
            'data': [{'last': '2500.5', 'vol24h': '12345'}]
        }
        
        yield {
            'trade': mock_trade_instance,
            'account': mock_account_instance,
            'market': mock_market_instance
        }


@pytest.fixture
def mock_gemini_api():
    """模拟Gemini API响应"""
    mock_response = {
        "analysis": "当前ETH市场呈现上涨趋势，技术指标显示买入信号。",
        "signal": "LONG",
        "confidence": 85.5,
        "entry_price": 2500.0,
        "stop_loss": 2450.0,
        "take_profit": [2600.0, 2700.0],
        "position_size": 0.1
    }
    
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_instance = Mock()
        mock_model.return_value = mock_instance
        
        mock_result = Mock()
        mock_result.text = json.dumps(mock_response)
        mock_instance.generate_content.return_value = mock_result
        
        yield mock_response


@pytest.fixture
def mock_browser():
    """模拟浏览器操作"""
    with patch('selenium.webdriver.Chrome') as mock_chrome:
        mock_driver = Mock()
        mock_chrome.return_value = mock_driver
        
        # 模拟浏览器方法
        mock_driver.get.return_value = None
        mock_driver.save_screenshot.return_value = True
        mock_driver.current_url = "https://cn.tradingview.com"
        mock_driver.page_source = "<html><body>Mock TradingView</body></html>"
        
        yield mock_driver


@pytest.fixture
def sample_kline_data():
    """样本K线数据"""
    return [
        ["1640995200000", "2500.1", "2520.5", "2495.0", "2515.3", "1234.5", "3100000"],
        ["1640998800000", "2515.3", "2535.8", "2510.2", "2530.1", "1456.7", "3200000"],
        ["1641002400000", "2530.1", "2545.0", "2525.0", "2540.5", "1678.9", "3300000"]
    ]


@pytest.fixture
def sample_market_data():
    """样本市场数据"""
    return {
        "price": 2500.5,
        "volume_24h": 12345.67,
        "change_24h": 2.5,
        "fear_greed_index": 65,
        "technical_indicators": {
            "rsi_14": 58.5,
            "ema_20": 2485.3,
            "ema_50": 2465.1,
            "macd": 12.5,
            "atr": 25.8
        }
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    """自动设置测试环境"""
    # 设置测试环境变量
    os.environ['TESTING'] = 'true'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    
    yield
    
    # 清理测试环境
    if 'TESTING' in os.environ:
        del os.environ['TESTING']
    if 'LOG_LEVEL' in os.environ:
        del os.environ['LOG_LEVEL']


@pytest.fixture
def mock_requests():
    """模拟HTTP请求"""
    import responses
    
    with responses.RequestsMock() as rsps:
        # 模拟数据服务器健康检查
        rsps.add(
            responses.GET,
            "http://127.0.0.1:5002/health",
            json={"status": "ok", "message": "Server is healthy"},
            status=200
        )
        
        # 模拟恐惧贪婪指数API
        rsps.add(
            responses.GET,
            "https://api.alternative.me/fng/",
            json={
                "name": "Fear and Greed Index",
                "data": [{"value": "65", "value_classification": "Greed"}]
            },
            status=200
        )
        
        yield rsps


# 测试标记定义
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "e2e: 端到端测试")
    config.addinivalue_line("markers", "performance: 性能测试")
    config.addinivalue_line("markers", "slow: 慢速测试")
    config.addinivalue_line("markers", "fast: 快速测试")
    config.addinivalue_line("markers", "external: 需要外部服务的测试")


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    for item in items:
        # 为单元测试添加快速标记
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.fast)
        
        # 为集成测试添加慢速标记
        if "integration" in str(item.fspath) or "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.slow) 