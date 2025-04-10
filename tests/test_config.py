import unittest
import os
import sys
from unittest.mock import patch

# We need to import config *after* patching the environment
# or reload it if it was already imported.

class TestConfig(unittest.TestCase):

    @patch.dict(os.environ, {'MEXC_API_KEY': 'test_api_key', 'MEXC_SECRET_KEY': 'test_secret'}, clear=True)
    def test_load_env_variables_success(self):
        """Test if API keys are loaded correctly from environment variables."""
        # Import or reload config module *within* the patched context
        import importlib
        import config
        importlib.reload(config)

        self.assertEqual(config.MEXC_API_KEY, 'test_api_key')
        self.assertEqual(config.MEXC_SECRET_KEY, 'test_secret')

    @patch.dict(os.environ, {}, clear=True) # No env vars set
    def test_load_env_variables_missing(self):
        """Test if config handles missing environment variables."""
        # Redirect print output to check the error message
        from io import StringIO
        with patch('sys.stdout', new=StringIO()) as fake_out:
            import importlib
            # It's tricky because config prints errors on import if vars are missing.
            # We expect the variables to be None after the failed import.
            try:
                # Ensure config is freshly imported or reloaded
                if 'config' in sys.modules:
                    del sys.modules['config']
                import config
                # In a real app, the initial check might exit or raise. Here we check the state after.
                self.assertIsNone(config.MEXC_API_KEY)
                self.assertIsNone(config.MEXC_SECRET_KEY)
                # Check if the error message was printed
                output = fake_out.getvalue().strip()
                self.assertIn("ERROR: MEXC_API_KEY or MEXC_SECRET_KEY not found", output)
            except ImportError:
                 self.fail("Config module failed to import, check structure.")
            finally:
                 # Clean up module cache if needed
                 if 'config' in sys.modules:
                    del sys.modules['config']

    def test_default_parameters_exist(self):
        """Test if default trading parameters are present."""
        # Temporarily set env vars to allow import without error print
        with patch.dict(os.environ, {'MEXC_API_KEY': 'temp', 'MEXC_SECRET_KEY': 'temp'}, clear=True):
            import importlib
            import config
            importlib.reload(config)

            self.assertIsInstance(config.DEFAULT_SYMBOL, str)
            self.assertIsInstance(config.DEFAULT_TIMEFRAME, str)
            self.assertIsInstance(config.TRADE_AMOUNT_BASE, (int, float))
            self.assertIsInstance(config.DEFAULT_LEVERAGE, int)
            self.assertIsInstance(config.MIN_TAKE_PROFIT_PERCENT, (int, float))
            self.assertIsInstance(config.STOP_LOSS_PERCENT, (int, float))
            self.assertIsInstance(config.TAKE_PROFIT_PERCENT, (int, float))
            self.assertIsInstance(config.DATA_FETCH_INTERVAL_SECONDS, int)
            self.assertIsInstance(config.PREDICTION_INTERVAL_SECONDS, int)
            self.assertIsInstance(config.STATS_UPDATE_INTERVAL_SECONDS, int)
            self.assertIsInstance(config.MANUAL_TRADE_KEY_UP, str)
            self.assertIsInstance(config.MANUAL_TRADE_KEY_DOWN, str)

if __name__ == '__main__':
    unittest.main() 