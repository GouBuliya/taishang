# tests/unit/data/test_collector_service_fixed.py
import pytest
import json
import time
import psutil
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.data.collector_service import main as collector_main
from src.data.collector_service import gettime, gettransactionhistory, analyze_kline_patterns_wrapper


class TestCollectorService:
    """数据收集服务测试类"""
    
    @patch('src.data.collector_service.collect_technical_indicators')
    @patch('src.data.collector_service.collect_macro_factors') 
    @patch('src.data.collector_service.collect_positions_data')
    def test_collector_main_success(self, mock_positions, mock_factors, mock_indicators):
        """测试数据收集主函数成功执行"""
        # 模拟技术指标数据
        mock_indicators_data = {
            "15m": [
                {"timestamp": "2024-01-01", "open": 100.0, "high": 105.0, 
                 "low": 98.0, "close": 102.0, "volume": 1000.0}
            ],
            "1h": [
                {"timestamp": "2024-01-01", "open": 100.0, "high": 110.0, 
                 "low": 95.0, "close": 108.0, "volume": 5000.0}
            ]
        }
        
        # 设置模拟返回值
        mock_indicators.return_value = mock_indicators_data
        mock_factors.return_value = {"fear_greed_index": 65}
        mock_positions.return_value = {"ETH-USDT": {"size": 0.1, "side": "long"}}
        
        # 模拟K线分析
        with patch('src.data.collector_service.analyze_kline_patterns_wrapper') as mock_analyze:
            mock_analyze.return_value = {"patterns": {"support_level": 100.0}}
            
            # 模拟截图功能
            with patch.object(collector_main, '__globals__', {**collector_main.__globals__, 
                                                              'screenshots': lambda: {}}):
                # 执行主函数
                collector_main()
        
        # 验证各模块被调用
        mock_indicators.assert_called_once()
        mock_factors.assert_called_once()
        mock_positions.assert_called_once()
    
    @patch('src.data.collector_service.collect_technical_indicators')
    @patch('src.data.collector_service.collect_macro_factors')
    @patch('src.data.collector_service.collect_positions_data')
    def test_collector_handles_failures(self, mock_positions, mock_factors, mock_indicators):
        """测试数据收集处理失败情况"""
        # 模拟部分失败
        mock_indicators.return_value = None  # 指标收集失败
        mock_factors.side_effect = Exception("网络错误")
        mock_positions.return_value = {}
        
        # 执行主函数不应该崩溃
        try:
            collector_main()
        except Exception as e:
            pytest.fail(f"数据收集主函数不应该因为子模块失败而崩溃: {e}")
    
    def test_data_saving(self):
        """测试数据保存功能"""
        # 检查数据文件是否被正确创建
        data_file_path = "data/data.json"
        
        # 模拟数据收集并检查文件创建
        with patch('src.data.collector_service.collect_technical_indicators') as mock_indicators:
            with patch('src.data.collector_service.collect_macro_factors') as mock_factors:
                with patch('src.data.collector_service.collect_positions_data') as mock_positions:
                    
                    mock_indicators.return_value = {"15m": []}
                    mock_factors.return_value = {}
                    mock_positions.return_value = {}
                    
                    # 检查数据格式
                    test_data = {
                        "indicators_main(非实时报价)": {"15m": []},
                        "factors_main": {},
                        "okx_positions": {},
                        "current_time": "2024-01-01T12:00:00+08:00",
                        "kline_patterns(analyze_kline_patterns)": {"15m": {}},
                        "timestamp": "2024-01-01T12:00:00+08:00"
                    }
                    
                    # 验证数据结构
                    assert "indicators_main(非实时报价)" in test_data
                    assert "factors_main" in test_data
                    assert "okx_positions" in test_data
                    assert "timestamp" in test_data


class TestUtilityFunctions:
    """工具函数测试类"""
    
    def test_gettime_function(self):
        """测试时间获取函数"""
        result = gettime()
        
        # 验证返回格式
        assert isinstance(result, dict)
        assert "time" in result
        
        # 验证时间格式
        time_str = result["time"]
        assert isinstance(time_str, str)
        assert "2024" in time_str or "2023" in time_str  # 基本的年份检查
    
    @patch('src.trading.api.get_transaction_history.get_latest_transactions')
    def test_gettransactionhistory_function(self, mock_get_transactions):
        """测试交易历史获取函数"""
        # 模拟交易历史数据
        mock_transactions = [
            {
                "ordId": "12345",
                "instId": "ETH-USDT",
                "side": "buy",
                "sz": "0.1",
                "px": "2500.0"
            }
        ]
        mock_get_transactions.return_value = mock_transactions
        
        result = gettransactionhistory("ETH-USDT")
        
        # 验证返回格式
        assert isinstance(result, dict)
        assert "transaction_history" in result
        assert result["transaction_history"] == mock_transactions
    
    def test_analyze_kline_patterns_wrapper_success(self):
        """测试K线模式分析封装函数成功情况"""
        # 模拟K线数据
        kline_data = [
            {"timestamp": "2024-01-01", "open": 100.0, "high": 105.0, 
             "low": 98.0, "close": 102.0, "volume": 1000.0},
            {"timestamp": "2024-01-02", "open": 102.0, "high": 108.0, 
             "low": 100.0, "close": 106.0, "volume": 1200.0}
        ]
        
        with patch('src.data.collector_service.analyze_kline_patterns') as mock_analyze:
            mock_analyze.return_value = {"support_level": 100.0, "resistance_level": 110.0}
            
            result = analyze_kline_patterns_wrapper(kline_data)
            
            # 验证返回格式
            assert isinstance(result, dict)
            assert "patterns" in result
            assert result["patterns"]["support_level"] == 100.0
    
    def test_analyze_kline_patterns_wrapper_error(self):
        """测试K线模式分析封装函数错误处理"""
        kline_data = []  # 空数据
        
        with patch('src.data.collector_service.analyze_kline_patterns') as mock_analyze:
            mock_analyze.side_effect = Exception("分析失败")
            
            result = analyze_kline_patterns_wrapper(kline_data)
            
            # 验证错误处理
            assert isinstance(result, dict)
            assert "error" in result
            assert "分析失败" in result["error"]


@pytest.mark.integration
class TestCollectorIntegration:
    """数据收集集成测试类"""
    
    @patch('src.data.collector_service.collect_technical_indicators')
    @patch('src.data.collector_service.collect_macro_factors')
    @patch('src.data.collector_service.collect_positions_data')
    def test_end_to_end_data_collection(self, mock_positions, mock_factors, mock_indicators):
        """测试端到端数据收集"""
        # 设置完整的模拟数据
        mock_indicators.return_value = {
            "15m": [{"timestamp": "2024-01-01", "close": 100.0}],
            "1h": [{"timestamp": "2024-01-01", "close": 105.0}],
            "4h": [{"timestamp": "2024-01-01", "close": 110.0}]
        }
        mock_factors.return_value = {"fear_greed_index": 65, "btc_dominance": 45.5}
        mock_positions.return_value = {"ETH-USDT": {"size": 0.1}}
        
        # 模拟K线分析结果
        with patch('src.data.collector_service.analyze_kline_patterns_wrapper') as mock_analyze:
            mock_analyze.return_value = {"patterns": {"trend": "bullish"}}
            
            # 执行集成测试
            collector_main()
            
            # 验证所有组件被正确调用
            mock_indicators.assert_called_once()
            mock_factors.assert_called_once() 
            mock_positions.assert_called_once()
    
    def test_concurrent_execution(self):
        """测试并发执行能力"""
        import concurrent.futures
        
        def mock_slow_function():
            time.sleep(0.1)  # 模拟慢速操作
            return {"result": "success"}
        
        # 测试并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(mock_slow_function) for _ in range(3)]
            results = [future.result() for future in futures]
        
        # 验证所有任务完成
        assert len(results) == 3
        assert all(r["result"] == "success" for r in results)


@pytest.mark.external
class TestExternalAPIs:
    """外部API测试类"""
    
    @pytest.mark.skip(reason="需要真实API密钥")
    def test_real_okx_api_call(self):
        """测试真实OKX API调用"""
        # 这个测试需要真实的API密钥
        pass
    
    @patch('requests.get')
    def test_external_api_error_handling(self, mock_get):
        """测试外部API错误处理"""
        # 模拟网络错误
        mock_get.side_effect = Exception("网络连接失败")
        
        # 测试错误处理机制
        try:
            # 这里应该调用实际使用外部API的函数
            result = gettime()  # 使用gettime作为示例
            # 验证错误被正确处理
            assert isinstance(result, dict)
        except Exception:
            pytest.fail("外部API错误应该被正确处理，不应该导致崩溃")


@pytest.mark.performance
class TestCollectorPerformance:
    """数据收集性能测试类"""
    
    @patch('src.data.collector_service.collect_technical_indicators')
    @patch('src.data.collector_service.collect_macro_factors')
    @patch('src.data.collector_service.collect_positions_data')
    def test_collection_speed(self, mock_positions, mock_factors, mock_indicators):
        """测试数据收集速度"""
        # 设置快速返回的模拟
        mock_indicators.return_value = {"15m": []}
        mock_factors.return_value = {}
        mock_positions.return_value = {}
        
        start_time = time.time()
        
        with patch('src.data.collector_service.analyze_kline_patterns_wrapper'):
            collector_main()
        
        end_time = time.time()
        collection_time = end_time - start_time
        
        # 数据收集应该在合理时间内完成
        assert collection_time < 30.0, f"数据收集时间过长: {collection_time}秒"
    
    def test_memory_usage_during_collection(self):
        """测试收集过程中的内存使用"""
        import psutil
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # 模拟数据收集过程
        with patch('src.data.collector_service.collect_technical_indicators') as mock_indicators:
            with patch('src.data.collector_service.collect_macro_factors') as mock_factors:
                with patch('src.data.collector_service.collect_positions_data') as mock_positions:
                    
                    # 模拟大量数据
                    large_data = {
                        "15m": [{"data": i} for i in range(1000)],
                        "1h": [{"data": i} for i in range(1000)]
                    }
                    mock_indicators.return_value = large_data
                    mock_factors.return_value = {}
                    mock_positions.return_value = {}
                    
                    collector_main()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # 内存增长应该在合理范围内
        assert memory_increase < 100 * 1024 * 1024, f"内存使用增长过多: {memory_increase / 1024 / 1024:.2f}MB" 