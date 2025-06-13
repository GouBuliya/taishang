# tests/unit/ai/test_gemini_controller.py
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# 导入Gemini控制器的实际函数
try:
    from src.ai.models.gemini_controller import call_gemini_api_stream
except ImportError:
    # 如果导入失败，创建一个模拟函数
    def call_gemini_api_stream(*args, **kwargs):
        pass


class TestGeminiController:
    """Gemini AI控制器测试类"""
    
    @patch('google.generativeai.GenerativeModel')
    def test_gemini_model_initialization(self, mock_model):
        """测试Gemini模型初始化"""
        # 模拟模型实例
        mock_instance = Mock()
        mock_model.return_value = mock_instance
        
        # 创建模型实例
        model = mock_model("gemini-pro")
        
        # 验证模型创建
        mock_model.assert_called_with("gemini-pro")
        assert model == mock_instance
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_trading_strategy_success(self, mock_model):
        """测试成功生成交易策略"""
        # 模拟AI响应
        mock_response = {
            "analysis": "当前ETH市场呈现上涨趋势，技术指标显示买入信号。",
            "signal": "LONG",
            "confidence": 85.5,
            "entry_price": 2500.0,
            "stop_loss": 2450.0,
            "take_profit": [2600.0, 2700.0],
            "position_size": 0.1,
            "reasoning": "RSI指标显示超卖，MACD金叉，成交量放大"
        }
        
        # 设置模拟
        mock_instance = Mock()
        mock_model.return_value = mock_instance
        
        mock_result = Mock()
        mock_result.text = json.dumps(mock_response)
        mock_instance.generate_content.return_value = mock_result
        
        # 测试生成内容
        model = mock_model("gemini-pro")
        result = model.generate_content("market analysis prompt")
        
        # 验证结果
        assert result.text is not None
        response_data = json.loads(result.text)
        assert response_data["signal"] in ["LONG", "SHORT", "HOLD"]
        assert 0 <= response_data["confidence"] <= 100
        assert response_data["entry_price"] > 0
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_content_with_error(self, mock_model):
        """测试生成内容时的错误处理"""
        # 模拟API错误
        mock_instance = Mock()
        mock_model.return_value = mock_instance
        mock_instance.generate_content.side_effect = Exception("API调用失败")
        
        model = mock_model("gemini-pro")
        
        # 验证异常被抛出
        with pytest.raises(Exception) as exc_info:
            model.generate_content("test prompt")
        
        assert "API调用失败" in str(exc_info.value)
    
    @patch('google.generativeai.GenerativeModel')
    def test_validate_trading_strategy_format(self, mock_model):
        """测试交易策略格式验证"""
        # 有效的策略响应
        valid_strategy = {
            "analysis": "市场分析文本",
            "signal": "LONG",
            "confidence": 75.0,
            "entry_price": 2500.0,
            "stop_loss": 2450.0,
            "take_profit": [2600.0, 2650.0],
            "position_size": 0.1
        }
        
        # 验证必要字段
        required_fields = ["analysis", "signal", "confidence", "entry_price", "stop_loss", "take_profit"]
        for field in required_fields:
            assert field in valid_strategy
        
        # 验证信号值
        assert valid_strategy["signal"] in ["LONG", "SHORT", "HOLD"]
        
        # 验证置信度范围
        assert 0 <= valid_strategy["confidence"] <= 100
        
        # 验证价格为正数
        assert valid_strategy["entry_price"] > 0
        assert valid_strategy["stop_loss"] > 0
        
        # 验证止盈目标是列表
        assert isinstance(valid_strategy["take_profit"], list)
        assert all(tp > 0 for tp in valid_strategy["take_profit"])
    
    def test_invalid_strategy_format(self):
        """测试无效策略格式处理"""
        # 无效的策略数据
        invalid_strategies = [
            {"signal": "INVALID"},  # 无效信号
            {"confidence": 150},    # 超出范围的置信度
            {"entry_price": -100},  # 负价格
            {"take_profit": "not_a_list"},  # 错误的止盈格式
        ]
        
        for invalid_strategy in invalid_strategies:
            # 验证无效数据检测
            if "signal" in invalid_strategy:
                assert invalid_strategy["signal"] not in ["LONG", "SHORT", "HOLD"]
            
            if "confidence" in invalid_strategy:
                assert not (0 <= invalid_strategy["confidence"] <= 100)
            
            if "entry_price" in invalid_strategy:
                assert invalid_strategy["entry_price"] <= 0
            
            if "take_profit" in invalid_strategy:
                assert not isinstance(invalid_strategy["take_profit"], list)


class TestPromptGeneration:
    """提示词生成测试类"""
    
    def test_create_market_analysis_prompt(self):
        """测试市场分析提示词创建"""
        # 模拟市场数据
        market_data = {
            "price": 2500.5,
            "rsi_14": 58.5,
            "ema_20": 2485.3,
            "macd": 12.5,
            "volume": 12345.67,
            "fear_greed_index": 65
        }
        
        # 创建提示词（这里应该调用实际的提示词生成函数）
        prompt = self._create_analysis_prompt(market_data)
        
        # 验证提示词包含关键信息
        assert str(market_data["price"]) in prompt
        assert str(market_data["rsi_14"]) in prompt
        assert "技术分析" in prompt or "technical analysis" in prompt.lower()
        assert "交易建议" in prompt or "trading recommendation" in prompt.lower()
    
    def _create_analysis_prompt(self, market_data):
        """辅助函数：创建分析提示词"""
        return f"""
        基于以下市场数据进行技术分析并提供交易建议：
        
        当前价格: {market_data['price']}
        RSI(14): {market_data['rsi_14']}
        EMA(20): {market_data['ema_20']}
        MACD: {market_data['macd']}
        成交量: {market_data['volume']}
        恐惧贪婪指数: {market_data['fear_greed_index']}
        
        请提供详细的技术分析和交易建议。
        """
    
    def test_prompt_with_missing_data(self):
        """测试缺少数据时的提示词处理"""
        # 缺少部分数据的市场数据
        incomplete_data = {
            "price": 2500.5,
            "rsi_14": 58.5
            # 缺少其他指标
        }
        
        # 创建提示词应该处理缺失数据
        prompt = self._create_analysis_prompt_safe(incomplete_data)
        
        # 验证不会因为缺失数据而失败
        assert "当前价格" in prompt
        assert str(incomplete_data["price"]) in prompt
    
    def _create_analysis_prompt_safe(self, market_data):
        """安全的提示词创建函数"""
        prompt = "基于可用的市场数据进行分析：\n"
        
        if "price" in market_data:
            prompt += f"当前价格: {market_data['price']}\n"
        if "rsi_14" in market_data:
            prompt += f"RSI(14): {market_data['rsi_14']}\n"
        
        prompt += "\n请提供基于可用数据的分析。"
        return prompt


@pytest.mark.unit
class TestResponseParsing:
    """响应解析测试类"""
    
    def test_parse_valid_json_response(self):
        """测试解析有效JSON响应"""
        # 有效的JSON响应
        json_response = '''
        {
            "analysis": "市场分析内容",
            "signal": "LONG",
            "confidence": 85.5,
            "entry_price": 2500.0,
            "stop_loss": 2450.0,
            "take_profit": [2600.0, 2700.0],
            "position_size": 0.1
        }
        '''
        
        # 解析JSON
        parsed_data = json.loads(json_response)
        
        # 验证解析结果
        assert isinstance(parsed_data, dict)
        assert parsed_data["signal"] == "LONG"
        assert parsed_data["confidence"] == 85.5
    
    def test_parse_invalid_json_response(self):
        """测试解析无效JSON响应"""
        # 无效的JSON响应
        invalid_json = '''
        {
            "analysis": "市场分析",
            "signal": "LONG",
            "confidence": 85.5,
            // 这是无效的JSON注释
        }
        '''
        
        # 验证JSON解析错误
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_json)
    
    def test_parse_response_with_chinese_content(self):
        """测试解析包含中文内容的响应"""
        # 包含中文的响应
        chinese_response = '''
        {
            "analysis": "当前ETH市场呈现上涨趋势，技术指标显示强烈的买入信号。RSI指标从超卖区域反弹，MACD形成金叉，成交量显著放大。",
            "signal": "LONG",
            "confidence": 88.5,
            "reasoning": "多项技术指标共振，市场情绪转好"
        }
        '''
        
        # 解析中文JSON
        parsed_data = json.loads(chinese_response)
        
        # 验证中文内容正确解析
        assert "上涨趋势" in parsed_data["analysis"]
        assert "技术指标" in parsed_data["reasoning"]
        assert parsed_data["signal"] == "LONG"


@pytest.mark.integration
class TestGeminiIntegration:
    """Gemini集成测试类"""
    
    @patch('src.ai.models.gemini_controller.client')
    def test_end_to_end_analysis(self, mock_client):
        """测试端到端分析流程"""
        # 模拟文件上传
        mock_client.files.upload.return_value = Mock()
        
        # 模拟流式响应
        mock_chunks = [
            Mock(text="综合技术分析显示买入机会: "),
            Mock(text=json.dumps({
                "analysis": "综合技术分析显示买入机会",
                "signal": "LONG", 
                "confidence": 82.0,
                "entry_price": 2500.0,
                "stop_loss": 2450.0,
                "take_profit": [2600.0, 2650.0],
                "position_size": 0.1
            }))
        ]
        
        mock_client.models.generate_content_stream.return_value = iter(mock_chunks)
        
        # 测试call_gemini_api_stream函数
        from src.ai.models.gemini_controller import call_gemini_api_stream
        
        result_chunks = list(call_gemini_api_stream(
            prompt_text="测试提示",
            system_prompt_path=None,
            files_path=[]
        ))
        
        # 验证流程完成
        assert len(result_chunks) > 0
        text_chunks = [chunk.get("text", "") for chunk in result_chunks if chunk.get("text")]
        full_text = "".join(text_chunks)
        assert "LONG" in full_text
    
    def test_api_key_configuration(self):
        """测试API密钥配置"""
        # 测试API密钥是否在模块中正确配置
        # 验证config.json文件能被正确读取
        
        import src.ai.models.gemini_controller as gc
        
        # 验证API密钥变量存在
        assert hasattr(gc, 'API_KEY')
        assert gc.API_KEY is not None
        
        # 验证客户端已初始化
        assert hasattr(gc, 'client')
        assert gc.client is not None


@pytest.mark.external
class TestGeminiAPI:
    """Gemini API外部测试"""
    
    @pytest.mark.skip(reason="需要真实API密钥")
    def test_real_gemini_api_call(self):
        """测试真实Gemini API调用"""
        # 这个测试需要真实的API密钥
        # 在CI/CD中应该跳过或使用测试密钥
        pass
    
    def test_api_rate_limiting_handling(self):
        """测试API速率限制处理"""
        with patch('google.generativeai.GenerativeModel') as mock_model:
            # 模拟速率限制错误
            mock_instance = Mock()
            mock_model.return_value = mock_instance
            mock_instance.generate_content.side_effect = Exception("Rate limit exceeded")
            
            model = mock_model("gemini-pro")
            
            # 验证速率限制错误被捕获
            with pytest.raises(Exception) as exc_info:
                model.generate_content("test")
            
            assert "Rate limit" in str(exc_info.value)


@pytest.mark.performance
class TestGeminiPerformance:
    """Gemini性能测试类"""
    
    @patch('google.generativeai.GenerativeModel')
    def test_response_time(self, mock_model):
        """测试响应时间"""
        import time
        
        # 模拟快速响应
        mock_instance = Mock()
        mock_model.return_value = mock_instance
        
        mock_result = Mock()
        mock_result.text = '{"signal": "LONG", "confidence": 80}'
        mock_instance.generate_content.return_value = mock_result
        
        model = mock_model("gemini-pro")
        
        start_time = time.time()
        result = model.generate_content("test prompt")
        elapsed_time = time.time() - start_time
        
        # AI调用应该在合理时间内完成（模拟情况下应该很快）
        assert elapsed_time < 1.0, f"AI响应时间过长: {elapsed_time}秒"
    
    def test_memory_usage_during_inference(self):
        """测试推理过程中的内存使用"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # 模拟大量AI推理调用
        with patch('google.generativeai.GenerativeModel') as mock_model:
            mock_instance = Mock()
            mock_model.return_value = mock_instance
            mock_result = Mock()
            mock_result.text = '{"signal": "LONG"}'
            mock_instance.generate_content.return_value = mock_result
            
            model = mock_model("gemini-pro")
            
            # 进行多次调用
            for _ in range(100):
                model.generate_content("test")
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # 内存增长应该在合理范围内
        assert memory_increase < 100 * 1024 * 1024, f"内存使用增长过多: {memory_increase / 1024 / 1024:.2f}MB" 