"""
谏官数据整合器
将现有的分散数据整合成谏官所需的结构化输入格式
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from decimal import Decimal
from src.core.path_manager import path_manager
from src.core.config_loader import load_config

logger = logging.getLogger("GeminiQuant")

class CriticDataIntegrator:
    """谏官数据整合器"""
    
    def __init__(self):
        self.config = load_config()
        self.project_root = path_manager.project_root
        
    def integrate_critic_data(
        self, 
        decision_maker_output: Dict[str, Any],
        current_iteration: int = 1,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        整合谏官所需的完整数据结构
        
        Args:
            decision_maker_output: 决策者的输出
            current_iteration: 当前迭代次数
            max_iterations: 最大迭代次数
            
        Returns:
            谏官所需的完整数据结构
        """
        try:
            # 1. 读取原始市场数据
            raw_market_data = self._load_raw_market_data()
            
            # 2. 生成K线图像上下文描述
            kline_images_context = self._generate_kline_images_context(raw_market_data)
            
            # 3. 获取系统配置
            system_configs = self._get_system_configs()
            
            # 4. 计算系统性能摘要
            system_performance_summary = self._calculate_system_performance()
            
            # 5. 构建当前迭代信息
            current_iteration_info = {
                "current_review_iteration": current_iteration,
                "max_iterations_allowed": max_iterations
            }
            
            # 6. 获取外部上下文（可选）
            retrieved_external_context = self._get_external_context()
            
            # 7. 整合完整数据结构
            integrated_data = {
                "decision_maker_output": decision_maker_output,
                "raw_market_data": raw_market_data,
                "kline_images_context": kline_images_context,
                "system_configs": system_configs,
                "system_performance_summary": system_performance_summary,
                "current_iteration_info": current_iteration_info
            }
            
            # 添加外部上下文（如果有）
            if retrieved_external_context:
                integrated_data["retrieved_external_context"] = retrieved_external_context
                
            logger.info("谏官数据整合完成")
            return integrated_data
            
        except Exception as e:
            logger.error(f"谏官数据整合失败: {e}")
            raise
    
    def _load_raw_market_data(self) -> Dict[str, Any]:
        """加载原始市场数据"""
        try:
            data_path = os.path.join(self.project_root, "data", "data.json")
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 提取并重新组织数据
            raw_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "indicators": data.get("indicators_main(非实时报价)", {}),
                "factors": data.get("factors_main", {}),
                "data_summary": data.get("data_summary", {}),
                "okx_positions": data.get("okx_positions", {})
            }
            
            return raw_data
            
        except Exception as e:
            logger.error(f"加载原始市场数据失败: {e}")
            return {}
    
    def _generate_kline_images_context(self, raw_market_data: Dict[str, Any]) -> str:
        """生成K线图像上下文描述"""
        try:
            indicators = raw_market_data.get("indicators", {})
            context_parts = []
            
            # 分析各时间框架的K线模式
            for timeframe, klines in indicators.items():
                if not isinstance(klines, list) or not klines:
                    continue
                    
                latest_kline = klines[-1] if klines else {}
                if not latest_kline:
                    continue
                
                # 基于技术指标生成描述
                rsi = latest_kline.get("RSI", 50)
                macd = latest_kline.get("MACD", 0)
                ema5 = latest_kline.get("EMA5", 0)
                ema21 = latest_kline.get("EMA21", 0)
                
                # 生成趋势描述
                trend = "震荡"
                if ema5 > ema21:
                    trend = "上涨" if macd > 0 else "弱势上涨"
                elif ema5 < ema21:
                    trend = "下跌" if macd < 0 else "弱势下跌"
                
                # 生成超买超卖描述
                rsi_status = "中性"
                if rsi > 70:
                    rsi_status = "超买"
                elif rsi < 30:
                    rsi_status = "超卖"
                
                context_parts.append(
                    f"{timeframe}时间框架：{trend}趋势，RSI显示{rsi_status}状态({rsi:.1f})，"
                    f"MACD为{macd:.3f}，EMA5({ema5:.2f}){'高于' if ema5 > ema21 else '低于'}EMA21({ema21:.2f})"
                )
            
            return "；".join(context_parts) if context_parts else "K线图像分析暂不可用"
            
        except Exception as e:
            logger.error(f"生成K线图像上下文失败: {e}")
            return "K线图像分析出错"
    
    def _get_system_configs(self) -> Dict[str, Any]:
        """获取系统配置信息"""
        try:
            # 从配置文件获取关键参数
            inst_id = self.config.get("instId", "ETH-USDT-SWAP")
            
            # 根据交易对确定lot_size（这里需要根据实际情况调整）
            lot_size_map = {
                "ETH-USDT-SWAP": "0.1",
                "BTC-USDT-SWAP": "0.001",
            }
            
            system_configs = {
                "lot_size": lot_size_map.get(inst_id, "0.1"),
                "decimal_precision_rules": "使用Decimal类型进行所有数量计算，量化到lot_size精度",
                "max_loss_percentage": 0.02,  # 2%最大损失
                "max_leverage": 100,
                "heuristic_rules_definitions": {
                    "description": "启发式规则定义，用于信号贡献度计算",
                    "X1_to_X7": "多时间框架技术指标权重分配规则"
                },
                "confidence_mapping_function": "置信度映射函数：基于信号强度和市场条件",
                "expected_return_formula_parameters": {
                    "risk_free_rate": 0.03,
                    "market_volatility_factor": 1.2,
                    "position_sizing_method": "固定风险百分比"
                }
            }
            
            return system_configs
            
        except Exception as e:
            logger.error(f"获取系统配置失败: {e}")
            return {}
    
    def _calculate_system_performance(self) -> Dict[str, Any]:
        """计算系统性能摘要"""
        try:
            # 这里应该从交易历史数据计算，暂时使用模拟数据
            # TODO: 集成真实的交易历史分析
            
            performance_summary = {
                "overall_win_rate_last_week": 0.65,  # 65%胜率
                "total_pnl_last_month": 1250.50,    # 上月总盈亏
                "max_drawdown_last_month": -320.75,  # 最大回撤
                "current_competition_rank": 0        # 当前排名（如果适用）
            }
            
            return performance_summary
            
        except Exception as e:
            logger.error(f"计算系统性能摘要失败: {e}")
            return {}
    
    def _get_external_context(self) -> Optional[str]:
        """获取外部上下文信息（可选）"""
        try:
            # 这里可以集成RAG系统或外部数据源
            # 暂时返回None，表示没有外部上下文
            return None
            
        except Exception as e:
            logger.error(f"获取外部上下文失败: {e}")
            return None

# 全局实例
critic_data_integrator = CriticDataIntegrator()

def integrate_data_for_critic(
    decision_maker_output: Dict[str, Any],
    current_iteration: int = 1,
    max_iterations: int = 3
) -> Dict[str, Any]:
    """
    为谏官整合数据的便捷函数
    
    Args:
        decision_maker_output: 决策者输出
        current_iteration: 当前迭代次数
        max_iterations: 最大迭代次数
        
    Returns:
        整合后的数据
    """
    return critic_data_integrator.integrate_critic_data(
        decision_maker_output, current_iteration, max_iterations
    ) 