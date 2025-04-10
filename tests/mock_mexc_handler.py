import logging
from typing import Optional, Dict, List, Any
from decimal import Decimal
import time

class MockMEXCHandler:
    """Mock MEXCHandler for testing purposes."""
    
    def __init__(self, api_key=None, secret_key=None, test_mode=True):
        """
        Initialize a mock MEXC handler.
        
        Args:
            api_key: Optional API key (not used in mock)
            secret_key: Optional secret key (not used in mock)
            test_mode: Always True for mock
        """
        self.positions = []
        self.markets = {
            'XRP/USDT:USDT': {
                'symbol': 'XRP/USDT:USDT',
                'base': 'XRP',
                'quote': 'USDT',
                'precision': {'price': 4, 'amount': 2},
                'limits': {'amount': {'min': 0.01}},
                'swap': True
            }
        }
        self.current_price = 0.5456  # Default mock price
        self.balance = {'USDT': 1000.0}
        logging.info("Mock MEXC Handler initialized")
    
    def get_market(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return mock market details."""
        return self.markets.get(symbol)
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Mock setting leverage."""
        if symbol not in self.markets:
            return False
        if leverage < 1:
            return False
        return True
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> Optional[List[List[float]]]:
        """Return mock OHLCV data."""
        # Generate mock OHLCV data
        current_ts = int(time.time() * 1000)  # Current timestamp in ms
        interval_ms = 60000  # 1 minute in ms
        
        mock_data = []
        for i in range(limit):
            # [timestamp, open, high, low, close, volume]
            ts = current_ts - ((limit - i - 1) * interval_ms)
            price = self.current_price + (i % 5 - 2) * 0.01  # Create some small variations
            high = price + 0.005
            low = price - 0.005
            mock_data.append([ts, price, high, low, price, 1000.0 + i])
        
        return mock_data
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Return mock current price."""
        return self.current_price
    
    def place_market_order_with_sl_tp(self, symbol: str, side: str, amount: float, 
                                      sl_price: Optional[float] = None, 
                                      tp_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Mock placing a market order with SL/TP."""
        if side not in ['buy', 'sell']:
            return None
        if symbol not in self.markets:
            return None
        
        # Create mock order result
        order_id = f"mock-order-{int(time.time())}"
        
        # Create a mock position based on the order
        position = {
            'symbol': symbol,
            'side': side,
            'size': amount,
            'entry_price': self.current_price,
            'order_id': order_id,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'timestamp': int(time.time() * 1000)
        }
        
        # Add to mock positions
        self.positions.append(position)
        
        # Return mock order result
        return {
            'id': order_id,
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': self.current_price,
            'timestamp': int(time.time() * 1000)
        }
    
    def get_usdt_balance(self) -> Optional[float]:
        """Return mock USDT balance."""
        return self.balance.get('USDT', 0.0)
    
    def get_positions(self, symbol: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Return mock positions."""
        if symbol:
            return [p for p in self.positions if p['symbol'] == symbol]
        return self.positions
    
    def get_trade_history(self, symbol: str, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Return mock trade history."""
        # Mock empty trade history
        return [] 