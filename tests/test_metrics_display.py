import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.main import Metrics, TradingBotApp, UpdateMetricsMessage

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
        
        # Create a mock app with properly mocked methods
        self.app = TradingBotApp()
        # Replace the metrics_table and update_metrics_table method with mocks
        self.app.metrics_table = Mock()
        self.app.update_metrics_table = Mock()
        # Mock the watch_current_metrics method to prevent automatic calls
        self.app.watch_current_metrics = Mock()
    
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
        
        # Check that watch_current_metrics was called with the old and new metrics
        # This will be None for old metrics since it's the initial update
        self.app.watch_current_metrics.assert_called_once()
    
    def test_metrics_table_formatting(self):
        """Test that metrics are properly formatted in the table."""
        app = TradingBotApp()
        app.metrics_table = Mock()
        
        # Set the current metrics
        app.current_metrics = self.metrics
        
        # Create a copy of the original update_metrics_table method
        original_update = app.update_metrics_table
        
        # Now call the original method directly
        original_update()
        
        # Verify add_row was called with the expected formatted values
        calls = app.metrics_table.add_row.call_args_list
        
        # Check the metrics_table was cleared first
        app.metrics_table.clear.assert_called_once()
        
        # Check all the expected rows were added with correctly formatted values
        # Symbol
        self.assertEqual(calls[0][0][0], "Symbol")
        self.assertEqual(calls[0][0][1], "XRP/USDT:USDT")
        
        # Current Price with 4 decimal places
        self.assertEqual(calls[2][0][0], "Current Price")
        self.assertEqual(calls[2][0][1], "0.5456")
        
        # RSI with 2 decimal places
        self.assertEqual(calls[3][0][0], "RSI")
        self.assertEqual(calls[3][0][1], "55.50")
        
        # Prediction
        self.assertEqual(calls[4][0][0], "Prediction") 
        self.assertEqual(calls[4][0][1], "LONG")
        
        # Position Size
        self.assertEqual(calls[5][0][0], "Position Size")
        self.assertEqual(calls[5][0][1], "100")
        
        # Entry Price with 4 decimal places
        self.assertEqual(calls[6][0][0], "Entry Price")
        self.assertEqual(calls[6][0][1], "0.5200")
        
        # PnL with 2 decimal places and % sign
        self.assertEqual(calls[7][0][0], "PnL (%)")
        self.assertEqual(calls[7][0][1], "4.92%")
    
    def test_none_metrics_display(self):
        """Test that None values are displayed as 'N/A'."""
        # Create an app with mocked DataTable
        app = TradingBotApp()
        app.metrics_table = Mock()
        
        # Set metrics with None values
        empty_metrics = Metrics()
        app.current_metrics = empty_metrics
        
        # Call the update method directly
        app.update_metrics_table()
        
        # Verify table was cleared
        app.metrics_table.clear.assert_called_once_with(columns=False)
        
        # Get add_row calls
        calls = app.metrics_table.add_row.call_args_list
        
        # Symbol should be set from config.DEFAULT_SYMBOL
        self.assertEqual(calls[0][0][1], "XRP/USDT:USDT")
        
        # Verify None values are displayed as "N/A"
        self.assertEqual(calls[2][0][1], "N/A")  # Current Price
        self.assertEqual(calls[3][0][1], "N/A")  # RSI
        self.assertEqual(calls[4][0][1], "N/A")  # Prediction
        self.assertEqual(calls[5][0][1], "N/A")  # Position Size
        self.assertEqual(calls[6][0][1], "N/A")  # Entry Price
        self.assertEqual(calls[7][0][1], "N/A")  # PnL

if __name__ == '__main__':
    unittest.main() 