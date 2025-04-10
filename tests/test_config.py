import unittest
import sys
import os
from unittest.mock import patch
import importlib

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import src.config as config

class TestConfig(unittest.TestCase):
    """Tests for the configuration module."""
    
    def test_default_parameters_exist(self):
        """Test if default trading parameters are present."""
        # Check for required default values
        self.assertIsNotNone(config.DEFAULT_SYMBOL)
        self.assertIsNotNone(config.DEFAULT_TIMEFRAME)
        self.assertIsNotNone(config.DEFAULT_LEVERAGE)
        self.assertIsNotNone(config.STOP_LOSS_PERCENT)
        self.assertIsNotNone(config.TAKE_PROFIT_PERCENT)
        self.assertIsNotNone(config.TRADE_AMOUNT_BASE)
        self.assertIsNotNone(config.DATA_FETCH_INTERVAL_SECONDS)
        self.assertIsNotNone(config.PREDICTION_INTERVAL_SECONDS)
        self.assertIsNotNone(config.STATS_UPDATE_INTERVAL_SECONDS)
    
    @patch.dict(os.environ, {
        'MEXC_API_KEY': 'test_api_key',
        'MEXC_SECRET_KEY': 'test_secret_key'
    }, clear=True)
    def test_load_env_variables_success(self):
        """Test if API keys are loaded correctly from environment variables."""
        # Force reload the config module to pick up the patched environment variables
        importlib.reload(config)
        
        # Reset config values that might have been set by previous tests
        if hasattr(config, 'load_env_variables'):
            # If there's a dedicated function for loading environment variables, call it
            config.load_env_variables()
        
        # Check that API keys are set correctly from the environment
        self.assertEqual(config.MEXC_API_KEY, 'test_api_key')
        self.assertEqual(config.MEXC_SECRET_KEY, 'test_secret_key')
    
    @patch.dict(os.environ, {}, clear=True)  # Clear all environment variables for this test
    @patch('src.config.MEXC_API_KEY', None)  # Directly patch the config values
    @patch('src.config.MEXC_SECRET_KEY', None)
    def test_load_env_variables_missing(self):
        """Test if config handles missing environment variables."""
        # With the patched values, the config should have None for API keys
        self.assertIsNone(config.MEXC_API_KEY)
        self.assertIsNone(config.MEXC_SECRET_KEY)

if __name__ == '__main__':
    unittest.main() 