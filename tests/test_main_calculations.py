import unittest
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import os
from unittest.mock import patch

# We need config values for the calculations
# Mock environment variables to allow config import without errors
with patch.dict(os.environ, {'MEXC_API_KEY': 'mock_api_key', 'MEXC_SECRET_KEY': 'mock_secret'}):
    import config
    # Set specific config values relevant to calculations for testing
    config.STOP_LOSS_PERCENT = 5.0 # 5%
    config.TAKE_PROFIT_PERCENT = 10.0 # 10%

# Note: In a larger project, you might refactor the SL/TP calculation 
# into a separate utility function in main.py or another module 
# to make it easier to test directly.
# Here, we simulate the inputs and replicate the calculation logic 
# from the execute_trade function for testing.

def calculate_sl_tp_for_test(current_price_dec: Decimal, 
                              side: str, 
                              sl_pct_config: float, 
                              tp_pct_config: float, 
                              price_precision: int) -> tuple[Decimal | None, Decimal | None]:
    """Replicates the SL/TP calculation logic from main.execute_trade for testing."""
    sl_price = None
    tp_price = None
    sl_pct = Decimal(str(sl_pct_config)) / Decimal('100')
    tp_pct = Decimal(str(tp_pct_config)) / Decimal('100')
    price_decimal_places = Decimal('1e-' + str(price_precision))

    if side == 'buy':
        if sl_pct > 0:
            sl_price = current_price_dec * (Decimal('1') - sl_pct)
            sl_price = sl_price.quantize(price_decimal_places, rounding=ROUND_DOWN)
        if tp_pct > 0:
            tp_price = current_price_dec * (Decimal('1') + tp_pct)
            tp_price = tp_price.quantize(price_decimal_places, rounding=ROUND_UP)
    elif side == 'sell':
        if sl_pct > 0:
            sl_price = current_price_dec * (Decimal('1') + sl_pct)
            sl_price = sl_price.quantize(price_decimal_places, rounding=ROUND_UP)
        if tp_pct > 0:
            tp_price = current_price_dec * (Decimal('1') - tp_pct)
            tp_price = tp_price.quantize(price_decimal_places, rounding=ROUND_DOWN)
            
    return sl_price, tp_price

class TestMainCalculations(unittest.TestCase):

    def test_sl_tp_calculation_buy(self):
        """Test SL/TP calculation for a BUY order."""
        current_price = Decimal('100.0000')
        price_precision = 2 # e.g., 2 decimal places like 100.00
        sl_pct = 5.0
        tp_pct = 10.0
        
        expected_sl = Decimal('100.0000') * (Decimal('1') - Decimal('0.05')) # 95.0000
        expected_sl = expected_sl.quantize(Decimal('0.01'), rounding=ROUND_DOWN) # 95.00
        
        expected_tp = Decimal('100.0000') * (Decimal('1') + Decimal('0.10')) # 110.0000
        expected_tp = expected_tp.quantize(Decimal('0.01'), rounding=ROUND_UP) # 110.00
        
        sl_price, tp_price = calculate_sl_tp_for_test(current_price, 'buy', sl_pct, tp_pct, price_precision)
        
        self.assertEqual(sl_price, expected_sl)
        self.assertEqual(tp_price, expected_tp)

    def test_sl_tp_calculation_sell(self):
        """Test SL/TP calculation for a SELL order."""
        current_price = Decimal('0.5000') # Example like XRP
        price_precision = 4 # e.g., 4 decimal places like 0.5000
        sl_pct = 5.0
        tp_pct = 10.0
        
        expected_sl = Decimal('0.5000') * (Decimal('1') + Decimal('0.05')) # 0.5250
        expected_sl = expected_sl.quantize(Decimal('0.0001'), rounding=ROUND_UP) # 0.5250
        
        expected_tp = Decimal('0.5000') * (Decimal('1') - Decimal('0.10')) # 0.4500
        expected_tp = expected_tp.quantize(Decimal('0.0001'), rounding=ROUND_DOWN) # 0.4500
        
        sl_price, tp_price = calculate_sl_tp_for_test(current_price, 'sell', sl_pct, tp_pct, price_precision)
        
        self.assertEqual(sl_price, expected_sl)
        self.assertEqual(tp_price, expected_tp)

    def test_sl_tp_calculation_zero_percent(self):
        """Test calculation when SL or TP percentage is zero."""
        current_price = Decimal('2000.00')
        price_precision = 2
        sl_pct_zero = 0.0
        tp_pct_zero = 0.0
        sl_pct_non_zero = 2.0
        tp_pct_non_zero = 3.0

        # Test zero SL, non-zero TP (buy)
        sl_price, tp_price = calculate_sl_tp_for_test(current_price, 'buy', sl_pct_zero, tp_pct_non_zero, price_precision)
        self.assertIsNone(sl_price)
        self.assertIsNotNone(tp_price)
        expected_tp = (current_price * (Decimal('1') + Decimal('0.03'))).quantize(Decimal('0.01'), rounding=ROUND_UP) # 2060.00
        self.assertEqual(tp_price, expected_tp)
        
        # Test non-zero SL, zero TP (sell)
        sl_price, tp_price = calculate_sl_tp_for_test(current_price, 'sell', sl_pct_non_zero, tp_pct_zero, price_precision)
        self.assertIsNotNone(sl_price)
        self.assertIsNone(tp_price)
        expected_sl = (current_price * (Decimal('1') + Decimal('0.02'))).quantize(Decimal('0.01'), rounding=ROUND_UP) # 2040.00
        self.assertEqual(sl_price, expected_sl)

        # Test both zero
        sl_price, tp_price = calculate_sl_tp_for_test(current_price, 'buy', sl_pct_zero, tp_pct_zero, price_precision)
        self.assertIsNone(sl_price)
        self.assertIsNone(tp_price)

    # Add tests for edge cases like very small prices or different precisions if needed

if __name__ == '__main__':
    unittest.main() 