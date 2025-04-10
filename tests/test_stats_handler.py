import unittest
import sys
import os
from decimal import Decimal

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.stats_handler import StatsHandler

class TestStatsHandler(unittest.TestCase):
    """Tests for the StatsHandler class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.stats_handler = StatsHandler()
        
        # Sample position data for tests
        self.long_position = {
            'symbol': 'XRP/USDT:USDT',
            'side': 'buy',
            'size': '100',
            'entry_price': '0.5000',
            'order_id': 'test-order-1'
        }
        
        self.short_position = {
            'symbol': 'XRP/USDT:USDT',
            'side': 'sell',
            'size': '100',
            'entry_price': '0.5000',
            'order_id': 'test-order-2'
        }
    
    def test_initialization(self):
        """Test proper initialization of StatsHandler."""
        self.assertEqual(self.stats_handler.total_realized_pnl, Decimal('0.0'))
        self.assertEqual(self.stats_handler.trade_count, 0)
        self.assertEqual(self.stats_handler.win_count, 0)
    
    def test_calculate_pnl_long_profitable(self):
        """Test PnL calculation for a profitable long position."""
        current_price = Decimal('0.5500')  # 10% increase
        
        pnl_info = self.stats_handler.calculate_pnl(self.long_position, current_price)
        
        self.assertIsNotNone(pnl_info)
        self.assertIn('pnl_percent', pnl_info)
        self.assertAlmostEqual(pnl_info['pnl_percent'], 10.0, places=4)
    
    def test_calculate_pnl_long_losing(self):
        """Test PnL calculation for a losing long position."""
        current_price = Decimal('0.4500')  # 10% decrease
        
        pnl_info = self.stats_handler.calculate_pnl(self.long_position, current_price)
        
        self.assertIsNotNone(pnl_info)
        self.assertIn('pnl_percent', pnl_info)
        self.assertAlmostEqual(pnl_info['pnl_percent'], -10.0, places=4)
    
    def test_calculate_pnl_short_profitable(self):
        """Test PnL calculation for a profitable short position."""
        current_price = Decimal('0.4500')  # 10% decrease
        
        pnl_info = self.stats_handler.calculate_pnl(self.short_position, current_price)
        
        self.assertIsNotNone(pnl_info)
        self.assertIn('pnl_percent', pnl_info)
        self.assertAlmostEqual(pnl_info['pnl_percent'], 10.0, places=4)
    
    def test_calculate_pnl_short_losing(self):
        """Test PnL calculation for a losing short position."""
        current_price = Decimal('0.5500')  # 10% increase
        
        pnl_info = self.stats_handler.calculate_pnl(self.short_position, current_price)
        
        self.assertIsNotNone(pnl_info)
        self.assertIn('pnl_percent', pnl_info)
        self.assertAlmostEqual(pnl_info['pnl_percent'], -10.0, places=4)
    
    def test_calculate_pnl_zero_entry(self):
        """Test PnL calculation with zero entry price (should return None)."""
        position = self.long_position.copy()
        position['entry_price'] = '0'
        
        pnl_info = self.stats_handler.calculate_pnl(position, Decimal('0.5000'))
        
        self.assertIsNone(pnl_info)
    
    def test_calculate_pnl_missing_data(self):
        """Test PnL calculation with missing data (should return None)."""
        # Test with missing entry price
        position_no_entry = self.long_position.copy()
        del position_no_entry['entry_price']
        self.assertIsNone(self.stats_handler.calculate_pnl(position_no_entry, Decimal('0.5000')))
        
        # Test with missing side
        position_no_side = self.long_position.copy()
        del position_no_side['side']
        self.assertIsNone(self.stats_handler.calculate_pnl(position_no_side, Decimal('0.5000')))
        
        # Test with invalid side
        position_invalid_side = self.long_position.copy()
        position_invalid_side['side'] = 'invalid'
        self.assertIsNone(self.stats_handler.calculate_pnl(position_invalid_side, Decimal('0.5000')))
        
        # Test with None current price
        self.assertIsNone(self.stats_handler.calculate_pnl(self.long_position, None))
    
    def test_calculate_pnl_decimal_conversion(self):
        """Test PnL calculation handles decimal conversion correctly."""
        # Test with string entry price (should convert successfully)
        pnl_info = self.stats_handler.calculate_pnl(self.long_position, Decimal('0.5500'))
        self.assertIsNotNone(pnl_info)
        
        # Test with float entry price
        position_float = self.long_position.copy()
        position_float['entry_price'] = 0.5000
        pnl_info = self.stats_handler.calculate_pnl(position_float, Decimal('0.5500'))
        self.assertIsNotNone(pnl_info)

if __name__ == '__main__':
    unittest.main() 