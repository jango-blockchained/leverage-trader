import ccxt
import time
from typing import Optional, Dict, List, Any
import config
import logging
from src.utils.error_handler import handle_api_errors, APIError, safe_api_call

# --- Early import of config to use ENABLE_TEST_MODE ---
ENABLE_TEST_MODE = getattr(config, 'ENABLE_TEST_MODE', False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MEXCHandler:
    def __init__(self, api_key=None, secret_key=None, test_mode=False):
        self.api_key = api_key or config.MEXC_API_KEY
        self.secret_key = secret_key or config.MEXC_SECRET_KEY
        self.test_mode = test_mode if test_mode is not None else ENABLE_TEST_MODE
        self.markets = {}
        self.current_price = None
        
        if not self.api_key or not self.secret_key:
            raise ValueError("API Key or Secret Key not configured")

        exchange_options = {
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'options': {
                'defaultType': 'swap', # Use 'swap' for USDT-M futures
            }
        }

        # Attempt to enable sandbox mode if configured
        if self.test_mode:
            logger.warning("Attempting to enable test/sandbox mode. This requires MEXC & ccxt support.")
            exchange_options['options']['test'] = True
        
        self.exchange = ccxt.mexc(exchange_options)

        # Log if test mode seems active (based on URLs, might not be reliable)
        if self.test_mode and ('testnet' in self.exchange.urls.get('api', '') or 'sandbox' in self.exchange.urls.get('api', '')):
            logger.info(f"Exchange API URL suggests test mode might be active: {self.exchange.urls.get('api')}")
        elif self.test_mode:
            logger.warning(f"Test mode was requested, but exchange API URL doesn't obviously indicate testnet: {self.exchange.urls.get('api')}. Functionality may use live data.")

        self._initialize_markets()

    @handle_api_errors
    def _initialize_markets(self):
        """Initialize and load markets data from the exchange."""
        self.markets = self.exchange.load_markets()
        logger.info(f"MEXC Handler initialized. Markets loaded. Test Mode Requested: {self.test_mode}")
        return self.markets

    @handle_api_errors
    def get_market(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch market details for a symbol."""
        if symbol in self.markets:
            return self.markets[symbol]
        else:
            logger.warning(f"Market {symbol} not found. Reloading markets.")
            self.markets = self.exchange.load_markets(True) # Force reload
            if symbol in self.markets:
                return self.markets[symbol]
            else:
                logger.error(f"Market {symbol} not found after reload.")
                return None

    @handle_api_errors
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        market = self.get_market(symbol)
        if not market:
            logger.error(f"Cannot set leverage: Market {symbol} not found.")
            return False

        if not market.get('swap', False):
             logger.error(f"Cannot set leverage: Market {symbol} is not a swap/future.")
             return False

        if leverage < 1:
            logger.error("Leverage must be at least 1.")
            return False

        # MEXC requires setting leverage for LONG and SHORT sides separately for isolated margin
        # We assume ISOLATED margin (openType=1)
        params_long = {'openType': 1, 'positionType': 1}
        self.exchange.set_leverage(leverage, symbol, params=params_long)
        logger.info(f"Leverage for {symbol} LONG set to {leverage}x (Isolated)")

        params_short = {'openType': 1, 'positionType': 2}
        self.exchange.set_leverage(leverage, symbol, params=params_short)
        logger.info(f"Leverage for {symbol} SHORT set to {leverage}x (Isolated)")

        # Consider this a success if we get here without exceptions
        return True

    @handle_api_errors
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> Optional[List[List[float]]]:
        """Fetch OHLCV data."""
        if not self.exchange.has['fetchOHLCV']:
            logger.error("Exchange does not support fetchOHLCV")
            return None
            
        # Add retry logic for robustness
        for attempt in range(3): # Retry up to 3 times
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if ohlcv:
                    logger.debug(f"Fetched {len(ohlcv)} candles for {symbol} ({timeframe})")
                    return ohlcv
                logger.warning(f"Attempt {attempt + 1}: Empty OHLCV data received for {symbol}")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                
            # Wait before retrying
            time.sleep(1 * (attempt + 1))
            
        logger.error(f"Failed to fetch OHLCV for {symbol} after 3 attempts")
        return None

    @handle_api_errors
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get the last traded price for a symbol."""
        ticker = self.exchange.fetch_ticker(symbol)
        if ticker and 'last' in ticker:
            self.current_price = float(ticker['last'])
            logger.debug(f"Current price for {symbol}: {self.current_price}")
            return self.current_price
        else:
            logger.warning(f"Could not fetch valid ticker/last price for {symbol}")
            return None

    @handle_api_errors
    def place_market_order_with_sl_tp(self, symbol: str, side: str, amount: float, 
                                     sl_price: Optional[float] = None, 
                                     tp_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Places a market order with Stop Loss and Take Profit.
        """
        if side not in ['buy', 'sell']:
            logger.error(f"Invalid order side: {side}")
            return None

        market = self.get_market(symbol)
        if not market:
            logger.error(f"Cannot place order: Market {symbol} not found.")
            return None

        order_type = 'market'
        params = {}

        # Add SL/TP parameters if provided
        if sl_price:
             params['stopLossPrice'] = self.exchange.price_to_precision(symbol, sl_price)

        if tp_price:
            params['takeProfitPrice'] = self.exchange.price_to_precision(symbol, tp_price)

        logger.info(f"Placing {side} {order_type} order for {amount} {market.get('base', '')} on {symbol} with SL={sl_price}, TP={tp_price}")
        order = self.exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=amount,
            params=params
        )
        logger.info(f"Order placed successfully: {order['id']}")
        return order

    @handle_api_errors
    def get_usdt_balance(self) -> float:
        """Fetch the free USDT balance from the swap/futures account."""
        balance = self.exchange.fetch_balance(params={'type': 'swap'})
        if 'USDT' in balance['free']:
            usdt_balance = float(balance['free']['USDT'])
            logger.debug(f"Free USDT balance: {usdt_balance}")
            return usdt_balance
        else:
            logger.warning("USDT balance not found in swap account.")
            return 0.0  # Return 0 if no USDT found

    @handle_api_errors
    def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch open positions for a specific symbol or all symbols."""
        if not self.exchange.has['fetchPositions']:
            logger.warning("Exchange does not support fetchPositions.")
            return []
            
        symbols = [symbol] if symbol else None
        positions = self.exchange.fetch_positions(symbols=symbols)
        
        # Filter out zero-size positions
        open_positions = [p for p in positions if p.get('contracts') and float(p['contracts']) != 0]
        logger.debug(f"Fetched {len(open_positions)} open positions.")
        return open_positions

    @handle_api_errors
    def get_trade_history(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch trade history for a symbol."""
        if not self.exchange.has['fetchMyTrades']:
            logger.error("Exchange does not support fetchMyTrades")
            return []
            
        trades = self.exchange.fetch_my_trades(symbol=symbol, limit=limit)
        logger.debug(f"Fetched {len(trades)} trades for {symbol}")
        return trades
        
    def close_position(self, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Close an open position."""
        if not position:
            logger.error("Cannot close position: No position data provided")
            return None
            
        symbol = position.get('symbol')
        if not symbol:
            logger.error("Cannot close position: No symbol in position data")
            return None
            
        # Determine the side - to close, we place an opposite order
        position_side = position.get('side')
        if not position_side:
            logger.error("Cannot close position: No side in position data")
            return None
            
        close_side = 'sell' if position_side == 'buy' else 'buy'
        amount = position.get('size', 0)
        
        if not amount:
            logger.error("Cannot close position: No size in position data")
            return None
            
        return safe_api_call(
            self.place_market_order_with_sl_tp,
            symbol, close_side, float(amount)
        )

# Example Usage (for testing)
if __name__ == '__main__':
    try:
        handler = MEXCHandler()

        # --- Test Basic Info ---
        print("Markets loaded.")
        xrp_market = handler.get_market(config.DEFAULT_SYMBOL)
        if xrp_market:
            print(f"Market details for {config.DEFAULT_SYMBOL}: Prec={xrp_market.get('precision', {})}")
        else:
            print(f"Could not get market details for {config.DEFAULT_SYMBOL}")

        # --- Test Balance ---
        balance = handler.get_usdt_balance()
        if balance is not None:
            print(f"Current USDT Balance: {balance}")
        else:
            print("Could not fetch balance.")

        # --- Test Leverage ---
        # WARNING: Setting leverage is a real operation!
        # leverage_set = handler.set_leverage(config.DEFAULT_SYMBOL, config.DEFAULT_LEVERAGE)
        # print(f"Leverage setting attempted: {leverage_set}")

        # --- Test Data Fetching ---
        price = handler.get_current_price(config.DEFAULT_SYMBOL)
        if price:
            print(f"Current Price for {config.DEFAULT_SYMBOL}: {price}")
        else:
            print("Could not fetch price.")

        ohlcv = handler.fetch_ohlcv(config.DEFAULT_SYMBOL, timeframe=config.DEFAULT_TIMEFRAME, limit=5)
        if ohlcv:
            print(f"Fetched last {len(ohlcv)} candles:")
            for candle in ohlcv:
                print(f"  Timestamp: {handler.exchange.iso8601(candle[0])}, O: {candle[1]}, H: {candle[2]}, L: {candle[3]}, C: {candle[4]}, V: {candle[5]}")
        else:
            print("Could not fetch OHLCV.")

        # --- Test Positions ---
        positions = handler.get_positions(config.DEFAULT_SYMBOL)
        if positions is not None:
            if positions:
                print("Open Positions:")
                for pos in positions:
                    print(f"  Symbol: {pos['symbol']}, Side: {pos['side']}, Size: {pos['contracts']}, Entry: {pos['entryPrice']}, PNL: {pos.get('unrealizedPnl', 'N/A')}")
            else:
                print("No open positions found.")
        else:
            print("Could not fetch positions.")

    except ValueError as e:
        print(f"Configuration Error: {e}")
    except APIError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}") 