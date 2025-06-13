import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

class TradeHistory:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.trades = self._load_trades()
        
    def _load_trades(self) -> List[Dict[str, Any]]:
        """加载现有交易记录"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"加载交易记录失败: {e}")
            return []
            
    def _save_trades(self):
        """保存交易记录"""
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(self.trades, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存交易记录失败: {e}")
            
    def add_trade(self, 
                  instrument_id: str,
                  side: str,
                  size: float,
                  price: float,
                  order_type: str,
                  order_id: str,
                  stop_loss: Optional[float] = None,
                  take_profits: Optional[List[Dict[str, float]]] = None,
                  extra_info: Optional[Dict[str, Any]] = None):
        """
        记录一笔交易
        """
        trade = {
            "timestamp": datetime.now().isoformat(),
            "instrument_id": instrument_id,
            "side": side,
            "size": size,
            "price": price,
            "order_type": order_type,
            "order_id": order_id,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "extra_info": extra_info or {}
        }
        
        self.trades.append(trade)
        self._save_trades()
        
    def get_trades(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return self.trades
        
    def get_trade_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """通过订单ID查找交易记录"""
        for trade in self.trades:
            if trade["order_id"] == order_id:
                return trade
        return None
