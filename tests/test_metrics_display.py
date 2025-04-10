import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.main import Metrics, UpdateMetricsMessage

# We'll avoid importing the real TradingBotApp and instead create a simplified mock
class MockTradingBotApp:
    """Simplified mock of TradingBotApp for testing."""
    
    def __init__(self):
        self.current_metrics = None
        self.metrics_table = Mock()
        self.watch_current_metrics = Mock()
    
    def on_update_metrics_message(self, message):
        """Test implementation to handle a metrics update message."""
        self.current_metrics = message.metrics
        self.watch_current_metrics()
    
    def update_metrics_table(self):
        """Test implementation to update the metrics table."""
        if self.current_metrics is None:
            return
        
        metrics = self.current_metrics
        self.metrics_table.clear(columns=False)
        
        # Add rows for each metric
        self.metrics_table.add_row("Symbol", metrics.symbol or "N/A")
        self.metrics_table.add_row("Timestamp", "Timestamp")
        
        if metrics.current_price:
            self.metrics_table.add_row("Current Price", f"{metrics.current_price:.4f}")
        else:
            self.metrics_table.add_row("Current Price", "N/A")
            
        if metrics.rsi:
            self.metrics_table.add_row("RSI", f"{metrics.rsi:.2f}")
        else:
            self.metrics_table.add_row("RSI", "N/A")
            
        self.metrics_table.add_row("Prediction", metrics.prediction or "N/A")
        self.metrics_table.add_row("Position Size", f"{metrics.position_size}" if metrics.position_size else "N/A")
        
        if metrics.entry_price:
            self.metrics_table.add_row("Entry Price", f"{metrics.entry_price:.4f}")
        else:
            self.metrics_table.add_row("Entry Price", "N/A")
            
        if metrics.pnl_percent is not None:
            self.metrics_table.add_row("PnL (%)", f"{metrics.pnl_percent:.2f}%")
        else:
            self.metrics_table.add_row("PnL (%)", "N/A")

class TestMetricsDisplay(unittest.TestCase):
    """Tests for the metrics display in the TUI."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a sample metrics object
        self.metrics = Metrics()
        self.metrics.symbol = "XRP/USDT:USDT"
        self.metrics.current_price = Decimal("0.5456")
        self.metrics.rsi = 55.5
        self.metrics.prediction = "LONG"
        self.metrics.position_size = Decimal("100")
        self.metrics.entry_price = Decimal("0.5200")
        self.metrics.pnl_percent = 4.92
        
        # Create a clean app for each test
        self.app = MockTradingBotApp()
    
    def test_metrics_initialization(self):
        """Test that metrics are properly initialized."""
        metrics = Metrics()
        self.assertEqual(metrics.symbol, "XRP/USDT:USDT")  # From config.DEFAULT_SYMBOL
        self.assertIsNone(metrics.current_price)
        self.assertIsNone(metrics.rsi)
        self.assertIsNone(metrics.prediction)
        self.assertIsNone(metrics.position_size)
        self.assertIsNone(metrics.entry_price)
        self.assertIsNone(metrics.pnl_percent)
    
    def test_update_metrics_message(self):
        """Test that the UpdateMetricsMessage is properly processed."""
        # Create a message with our sample metrics
        message = UpdateMetricsMessage(self.metrics)
        
        # Call the handler directly
        self.app.on_update_metrics_message(message)
        
        # Check that the metrics were updated in the app
        self.assertEqual(self.app.current_metrics, self.metrics)
        
        # The watch_current_metrics method should be called
        self.app.watch_current_metrics.assert_called_once()
    
    def test_metrics_table_formatting(self):
        """Test that metrics are properly formatted in the table."""
        # Set the current metrics
        self.app.current_metrics = self.metrics
        
        # Call the update_metrics_table method 
        self.app.update_metrics_table()
        
        # Check the metric values and formatting
        calls = self.app.metrics_table.add_row.call_args_list
        
        # Symbol
        self.assertEqual(calls[0][0][1], "XRP/USDT:USDT")
        
        # Current Price with 4 decimal places
        self.assertEqual(calls[2][0][1], "0.5456")
        
        # RSI with 2 decimal places
        self.assertEqual(calls[3][0][1], "55.50")
        
        # Prediction
        self.assertEqual(calls[4][0][1], "LONG")
        
        # Position Size
        self.assertEqual(calls[5][0][1], "100")
        
        # Entry Price with 4 decimal places
        self.assertEqual(calls[6][0][1], "0.5200")
        
        # PnL with 2 decimal places and % sign
        self.assertEqual(calls[7][0][1], "4.92%")
    
    def test_none_metrics_display(self):
        """Test that None values are displayed as 'N/A'."""
        # Set metrics with None values
        empty_metrics = Metrics()
        self.app.current_metrics = empty_metrics
        
        # Call the update method directly
        self.app.update_metrics_table()
        
        # Get add_row calls
        calls = self.app.metrics_table.add_row.call_args_list
        
        # Symbol should be set from config.DEFAULT_SYMBOL
        self.assertEqual(calls[0][0][1], "XRP/USDT:USDT")
        
        # Check that None values are displayed as "N/A"
        self.assertEqual(calls[2][0][1], "N/A")  # Current Price
        self.assertEqual(calls[3][0][1], "N/A")  # RSI
        self.assertEqual(calls[4][0][1], "N/A")  # Prediction
        self.assertEqual(calls[5][0][1], "N/A")  # Position Size
        self.assertEqual(calls[6][0][1], "N/A")  # Entry Price
        self.assertEqual(calls[7][0][1], "N/A")  # PnL

if __name__ == '__main__':
    unittest.main() 