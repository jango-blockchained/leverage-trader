import unittest
import os
from unittest.mock import patch, MagicMock, PropertyMock
import sys
from decimal import Decimal

# Mock config before importing mexc_handler
# Ensure necessary config values are set for the tests
with patch.dict(os.environ, {'MEXC_API_KEY': 'mock_api_key', 'MEXC_SECRET_KEY': 'mock_secret'}):
    import config
    config.DEFAULT_SYMBOL = 'XRP/USDT:USDT' # Ensure a default is set for tests
    config.STOP_LOSS_PERCENT = 1.0 # Example
    config.TAKE_PROFIT_PERCENT = 1.0 # Example
    # Mock the mexc_handler module after setting mock environment variables
    from mexc_handler import MEXCHandler

import ccxt # Import ccxt itself for exception types if needed

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.mock_mexc_handler import MockMEXCHandler

# --- Helper Function to create Mock CCXT Exchange ---
def create_mock_exchange():
    mock_exchange = MagicMock()
    mock_exchange.options = {'defaultType': 'swap'}
    mock_exchange.has = {'fetchOHLCV': True, 'fetchPositions': True, 'fetchMyTrades': True}
    mock_exchange.markets = {
        'XRP/USDT:USDT': {
            'symbol': 'XRP/USDT:USDT',
            'base': 'XRP',
            'quote': 'USDT',
            'settle': 'USDT',
            'id': 'XRP_USDT',
            'swap': True,
            'precision': {'price': 4, 'amount': 1},
            'limits': {'amount': {'min': 1, 'max': 100000}, 'price': {'min': 0.0001, 'max': 100}},
            'info': {} # Add more info if needed by handler logic
        },
        'BTC/USDT:USDT': {
            'symbol': 'BTC/USDT:USDT',
            'base': 'BTC',
            'quote': 'USDT',
            'settle': 'USDT',
            'id': 'BTC_USDT',
            'swap': True,
            'precision': {'price': 2, 'amount': 4},
            'limits': {'amount': {'min': 0.0001, 'max': 1000}, 'price': {'min': 0.01, 'max': 100000}},
            'info': {}
        }
    }
    mock_exchange.load_markets.return_value = mock_exchange.markets

    # Default behaviors for mocked methods
    mock_exchange.fetch_ticker.return_value = {'last': 0.5000, 'symbol': 'XRP/USDT:USDT'}
    mock_exchange.fetch_ohlcv.return_value = [[1678886400000, 0.5, 0.51, 0.49, 0.505, 1000]]
    mock_exchange.set_leverage.return_value = {'info': 'Leverage set'} # Simulate success
    mock_exchange.create_order.return_value = {'id': 'mock_order_123', 'info': 'Order created'}
    mock_exchange.fetch_balance.return_value = {
        'free': {'USDT': 1000.0, 'BTC': 0.1},
        'total': {'USDT': 1100.0, 'BTC': 0.1}
    }
    mock_exchange.fetch_positions.return_value = [] # Default to no open positions
    mock_exchange.fetch_my_trades.return_value = [] # Default to no trade history

    # Allow mocking price_to_precision
    mock_exchange.price_to_precision = MagicMock(side_effect=lambda symbol, price: f"{price:.4f}") # Simple mock

    return mock_exchange


# --- Test Class ---
# Patch ccxt.mexc globally for all tests in this class
@patch('ccxt.mexc', new_callable=create_mock_exchange)
class TestMEXCHandler(unittest.TestCase):

    def setUp(self): # Runs before each test method
        """Instantiate the handler with the mocked exchange."""
        # The patch is active here, so MEXCHandler init will use the mock
        self.handler = MockMEXCHandler()
        # Keep a reference to the mock object if needed for asserts
        self.mock_exchange = self.handler.exchange 

    def test_init_success(self, mock_ccxt_mexc_instance):
        """Test successful initialization and market loading."""
        self.assertIsNotNone(self.handler.exchange)
        mock_ccxt_mexc_instance.load_markets.assert_called_once()
        self.assertIn('XRP/USDT:USDT', self.handler.exchange.markets)

    def test_get_market_found(self, mock_ccxt_mexc_instance):
        """Test fetching details for an existing market."""
        market = self.handler.get_market('XRP/USDT:USDT')
        self.assertIsNotNone(market)
        self.assertEqual(market['symbol'], 'XRP/USDT:USDT')
        self.assertEqual(market['base'], 'XRP')

    def test_get_market_not_found(self, mock_ccxt_mexc_instance):
        """Test fetching details for a non-existent market (after reload attempt)."""
        # Configure mock to simulate market not found even after reload
        mock_ccxt_mexc_instance.load_markets.side_effect = [mock_ccxt_mexc_instance.markets, mock_ccxt_mexc_instance.markets] # Allow reload
        # Ensure 'NONEXISTENT' is not in the initial markets
        del mock_ccxt_mexc_instance.markets['NONEXISTENT'] # if it somehow existed
        
        market = self.handler.get_market('NONEXISTENT/USDT:USDT')
        self.assertIsNone(market)
        # Check that load_markets was called twice (initial + reload attempt)
        self.assertEqual(mock_ccxt_mexc_instance.load_markets.call_count, 2) # Should be initial load_markets in __init__ + 1 in get_market
        # Reset call count for subsequent tests if needed, or manage setup/teardown better
        mock_ccxt_mexc_instance.load_markets.reset_mock() 
        mock_ccxt_mexc_instance.load_markets.return_value = self.mock_exchange.markets # Restore simple return
        mock_ccxt_mexc_instance.load_markets.side_effect = None # Clear side effect


    def test_set_leverage_success(self, mock_ccxt_mexc_instance):
        """Test setting leverage successfully."""
        symbol = 'XRP/USDT:USDT'
        leverage = 10
        result = self.handler.set_leverage(symbol, leverage)
        self.assertTrue(result)
        mock_ccxt_mexc_instance.set_leverage.assert_called_once_with(leverage, symbol)

    def test_set_leverage_exchange_error(self, mock_ccxt_mexc_instance):
        """Test setting leverage when the exchange returns an error."""
        symbol = 'XRP/USDT:USDT'
        leverage = 0 # Assume this is invalid
        # Configure the mock to raise an ExchangeError
        mock_ccxt_mexc_instance.set_leverage.side_effect = ccxt.ExchangeError("Leverage too high")
        result = self.handler.set_leverage(symbol, leverage)
        self.assertFalse(result)
        mock_ccxt_mexc_instance.set_leverage.assert_called_once_with(leverage, symbol)
        # Reset side effect for other tests
        mock_ccxt_mexc_instance.set_leverage.side_effect = None
        mock_ccxt_mexc_instance.set_leverage.return_value = {'info': 'Leverage set'}

    def test_get_current_price_success(self, mock_ccxt_mexc_instance):
        """Test fetching the current price successfully."""
        symbol = 'XRP/USDT:USDT'
        self.mock_exchange.fetch_ticker.return_value = {'last': 0.5123, 'symbol': symbol}
        price = self.handler.get_current_price(symbol)
        self.assertEqual(price, 0.5123)
        mock_ccxt_mexc_instance.fetch_ticker.assert_called_once_with(symbol)

    def test_get_current_price_error(self, mock_ccxt_mexc_instance):
        """Test fetching price when the API fails."""
        symbol = 'XRP/USDT:USDT'
        mock_ccxt_mexc_instance.fetch_ticker.side_effect = ccxt.NetworkError("Timeout")
        price = self.handler.get_current_price(symbol)
        self.assertIsNone(price)
        mock_ccxt_mexc_instance.fetch_ticker.assert_called_once_with(symbol)
        # Reset side effect
        mock_ccxt_mexc_instance.fetch_ticker.side_effect = None
        mock_ccxt_mexc_instance.fetch_ticker.return_value = {'last': 0.5000, 'symbol': 'XRP/USDT:USDT'}


    def test_place_market_order_success(self, mock_ccxt_mexc_instance):
        """Test placing a simple market order."""
        symbol = 'XRP/USDT:USDT'
        side = 'buy'
        amount = 100.0
        order = self.handler.place_market_order_with_sl_tp(symbol, side, amount)
        self.assertIsNotNone(order)
        self.assertEqual(order['id'], 'mock_order_123')
        mock_ccxt_mexc_instance.create_order.assert_called_once_with(
            symbol=symbol, type='market', side=side, amount=amount, params={}
        )

    def test_place_market_order_with_sl_tp_success(self, mock_ccxt_mexc_instance):
        """Test placing a market order with SL and TP prices."""
        symbol = 'XRP/USDT:USDT'
        side = 'buy'
        amount = 100.0
        sl_price = 0.4500
        tp_price = 0.5500

        # Mock price_to_precision more accurately if needed
        def mock_prec(sym, price):
           if sym == symbol:
               return f"{Decimal(str(price)):.4f}" # 4 decimal places for XRP
           return str(price)
        mock_ccxt_mexc_instance.price_to_precision.side_effect = mock_prec

        order = self.handler.place_market_order_with_sl_tp(symbol, side, amount, sl_price, tp_price)
        self.assertIsNotNone(order)
        self.assertEqual(order['id'], 'mock_order_123')
        mock_ccxt_mexc_instance.create_order.assert_called_once_with(
            symbol=symbol,
            type='market',
            side=side,
            amount=amount,
            params={ # Check if params match expected format (adjust based on handler logic)
                'stopLossPrice': '0.4500', # Assuming price_to_precision formats correctly
                'takeProfitPrice': '0.5500'
            }
        )
        # Reset price_to_precision mock
        mock_ccxt_mexc_instance.price_to_precision.side_effect = lambda sym, price: f"{price:.4f}"

    def test_place_order_insufficient_funds(self, mock_ccxt_mexc_instance):
        """Test placing an order with insufficient funds."""
        symbol = 'XRP/USDT:USDT'
        side = 'buy'
        amount = 1000000.0 # Large amount
        mock_ccxt_mexc_instance.create_order.side_effect = ccxt.InsufficientFunds("Not enough USDT")
        order = self.handler.place_market_order_with_sl_tp(symbol, side, amount)
        self.assertIsNone(order)
        # Reset side effect
        mock_ccxt_mexc_instance.create_order.side_effect = None
        mock_ccxt_mexc_instance.create_order.return_value = {'id': 'mock_order_123', 'info': 'Order created'}

    def test_get_usdt_balance_success(self, mock_ccxt_mexc_instance):
        """Test fetching USDT balance successfully."""
        self.mock_exchange.fetch_balance.return_value = {
            'free': {'USDT': 1234.56, 'XRP': 500},
            'total': {'USDT': 1300.0, 'XRP': 500}
        }
        balance = self.handler.get_usdt_balance()
        self.assertEqual(balance, 1234.56)
        mock_ccxt_mexc_instance.fetch_balance.assert_called_once_with(params={'type': 'swap'})

    def test_get_usdt_balance_no_usdt(self, mock_ccxt_mexc_instance):
        """Test fetching balance when USDT key is missing."""
        self.mock_exchange.fetch_balance.return_value = {
            'free': {'BTC': 0.1, 'ETH': 2.0},
            'total': {'BTC': 0.1, 'ETH': 2.0}
        }
        balance = self.handler.get_usdt_balance()
        self.assertEqual(balance, 0.0) # Should return 0.0 if no USDT
        mock_ccxt_mexc_instance.fetch_balance.assert_called_once_with(params={'type': 'swap'})

    def test_get_positions_success_no_positions(self, mock_ccxt_mexc_instance):
        """Test fetching positions when there are none open."""
        mock_ccxt_mexc_instance.fetch_positions.return_value = []
        positions = self.handler.get_positions('XRP/USDT:USDT')
        self.assertEqual(positions, [])
        mock_ccxt_mexc_instance.fetch_positions.assert_called_once_with(symbols=['XRP/USDT:USDT'])

    def test_get_positions_success_with_positions(self, mock_ccxt_mexc_instance):
        """Test fetching positions when there are open positions."""
        mock_position_data = [
            {'symbol': 'XRP/USDT:USDT', 'side': 'long', 'contracts': 100.0, 'entryPrice': 0.5, 'unrealizedPnl': 5.0},
            {'symbol': 'BTC/USDT:USDT', 'side': 'short', 'contracts': 0.1, 'entryPrice': 30000, 'unrealizedPnl': -15.0},
            {'symbol': 'ETH/USDT:USDT', 'side': 'long', 'contracts': 0.0, 'entryPrice': 1800, 'unrealizedPnl': 0.0} # Zero size position
        ]
        mock_ccxt_mexc_instance.fetch_positions.return_value = mock_position_data
        positions = self.handler.get_positions()
        self.assertIsNotNone(positions)
        self.assertEqual(len(positions), 2) # Should filter out the zero-size position
        self.assertEqual(positions[0]['symbol'], 'XRP/USDT:USDT')
        self.assertEqual(positions[1]['symbol'], 'BTC/USDT:USDT')
        mock_ccxt_mexc_instance.fetch_positions.assert_called_once_with(symbols=None)

    # Add more tests for fetch_ohlcv, get_trade_history, error handling etc.

if __name__ == '__main__':
    unittest.main() 