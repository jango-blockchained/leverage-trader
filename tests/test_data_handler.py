import unittest
import sys
import os
import pandas as pd
from decimal import Decimal
from unittest.mock import patch

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_handler import DataHandler
from tests.mock_mexc_handler import MockMEXCHandler

class TestDataHandler(unittest.TestCase):
    """Tests for the DataHandler class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.mock_mexc = MockMEXCHandler()
        self.symbol = "XRP/USDT:USDT"
        self.timeframe = "1m"
        self.data_handler = DataHandler(self.mock_mexc, self.symbol, self.timeframe)
    
    def test_initialization(self):
        """Test proper initialization of DataHandler."""
        self.assertEqual(self.data_handler.symbol, self.symbol)
        self.assertEqual(self.data_handler.timeframe, self.timeframe)
        self.assertEqual(self.data_handler.mexc_handler, self.mock_mexc)
    
    def test_fetch_ohlcv(self):
        """Test fetching OHLCV data."""
        ohlcv_df = self.data_handler.fetch_ohlcv(limit=50)
        
        # Test that the result is a DataFrame
        self.assertIsInstance(ohlcv_df, pd.DataFrame)
        
        # Test that the DataFrame has the expected columns
        expected_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        self.assertListEqual(list(ohlcv_df.columns), expected_columns)
        
        # Test that the DataFrame has the expected number of rows
        self.assertEqual(len(ohlcv_df), 50)
        
        # Verify the timestamp is a datetime object
        self.assertIsInstance(ohlcv_df['timestamp'].iloc[0], pd.Timestamp)
    
    def test_get_current_price_from_ohlcv(self):
        """Test getting current price from OHLCV data."""
        ohlcv_df = self.data_handler.fetch_ohlcv()
        current_price = self.data_handler.get_current_price(ohlcv_df)
        
        # Test that the result is a Decimal
        self.assertIsInstance(current_price, Decimal)
        
        # Check that it's approximately the same as the mock price
        # Converting to float for approximate comparison
        self.assertAlmostEqual(float(current_price), self.mock_mexc.current_price, delta=0.05)
    
    def test_get_current_price_from_ticker(self):
        """Test getting current price directly from ticker when no OHLCV data is provided."""
        current_price = self.data_handler.get_current_price()
        
        # Test that the result is a Decimal
        self.assertIsInstance(current_price, Decimal)
        
        # Check that it's the same as the mock price
        self.assertEqual(float(current_price), self.mock_mexc.current_price)
    
    def test_get_current_price_with_none_ohlcv(self):
        """Test getting current price when None is passed for OHLCV."""
        current_price = self.data_handler.get_current_price(None)
        
        # Test that it falls back to ticker price
        self.assertIsInstance(current_price, Decimal)
        self.assertEqual(float(current_price), self.mock_mexc.current_price)
    
    def test_get_current_price_with_empty_ohlcv(self):
        """Test getting current price when empty DataFrame is passed for OHLCV."""
        empty_df = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        current_price = self.data_handler.get_current_price(empty_df)
        
        # Test that it falls back to ticker price
        self.assertIsInstance(current_price, Decimal)
        self.assertEqual(float(current_price), self.mock_mexc.current_price)

    @patch('src.data_handler.logging')
    def test_fetch_ohlcv_error_handling(self, mock_logging):
        """Test error handling in fetch_ohlcv method."""
        # Make mexc_handler.fetch_ohlcv throw an exception
        self.mock_mexc.fetch_ohlcv = lambda *args, **kwargs: exec('raise Exception("Test error")')
        
        # Call fetch_ohlcv, which should catch the exception
        result = self.data_handler.fetch_ohlcv()
        
        # Check that None is returned on error
        self.assertIsNone(result)
        
        # Verify that the error was logged
        mock_logging.error.assert_called()

if __name__ == '__main__':
    unittest.main() 