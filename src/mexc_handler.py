import ccxt
import time
from typing import Optional, Dict, List, Any
import config
import logging

# --- Early import of config to use ENABLE_TEST_MODE ---
ENABLE_TEST_MODE = getattr(config, 'ENABLE_TEST_MODE', False)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MEXCHandler:
    def __init__(self):
        if not config.MEXC_API_KEY or not config.MEXC_SECRET_KEY:
            raise ValueError("API Key or Secret Key not configured in config.py")

        exchange_options = {
            'apiKey': config.MEXC_API_KEY,
            'secret': config.MEXC_SECRET_KEY,
            'options': {
                'defaultType': 'swap', # Use 'swap' for USDT-M futures
            }
        }

        # Attempt to enable sandbox mode if configured
        if ENABLE_TEST_MODE:
            logging.warning("Attempting to enable test/sandbox mode. This requires MEXC & ccxt support.")
            # Common ccxt approach - may vary or not be supported for MEXC futures
            exchange_options['options']['test'] = True # General test flag
            # Or sometimes directly via a property:
            # self.exchange = ccxt.mexc(exchange_options)
            # try:
            #     self.exchange.set_sandbox_mode(True)
            #     logging.info("ccxt sandbox mode enabled.")
            # except Exception as e:
            #     logging.error(f"Failed to enable ccxt sandbox mode explicitly: {e}")
            #     # Continue without explicit sandbox mode set, rely on options
        
        self.exchange = ccxt.mexc(exchange_options)

        # Log if test mode seems active (based on URLs, might not be reliable)
        if ENABLE_TEST_MODE and ('testnet' in self.exchange.urls.get('api', '') or 'sandbox' in self.exchange.urls.get('api', '')):
            logging.info(f"Exchange API URL suggests test mode might be active: {self.exchange.urls.get('api')}")
        elif ENABLE_TEST_MODE:
            logging.warning(f"Test mode was requested, but exchange API URL doesn\'t obviously indicate testnet: {self.exchange.urls.get('api')}. Functionality may use live data.")

        try:
             self.exchange.load_markets()
             logging.info(f"MEXC Handler initialized. Markets loaded. Test Mode Requested: {ENABLE_TEST_MODE}")
        except ccxt.AuthenticationError as e:
             logging.error(f"Authentication Error during init: {e}. Check API keys.")
             # If using testnet, ensure keys are for the testnet environment.
             raise # Re-raise to prevent handler use
        except Exception as e:
             logging.error(f"Error loading markets during init: {e}")
             raise # Re-raise to prevent handler use

    def get_market(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch market details for a symbol."""
        try:
            if symbol in self.exchange.markets:
                return self.exchange.markets[symbol]
            else:
                logging.warning(f"Market {symbol} not found. Reloading markets.")
                self.exchange.load_markets(True) # Force reload
                if symbol in self.exchange.markets:
                    return self.exchange.markets[symbol]
                else:
                    logging.error(f"Market {symbol} not found after reload.")
                    return None
        except ccxt.NetworkError as e:
            logging.error(f"Network error fetching market {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error fetching market {symbol}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching market {symbol}: {e}")
            return None

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol."""
        market = self.get_market(symbol)
        if not market:
            logging.error(f"Cannot set leverage: Market {symbol} not found.")
            return False

        if not market.get('swap', False):
             logging.error(f"Cannot set leverage: Market {symbol} is not a swap/future.")
             return False

        if leverage < 1:
            logging.error("Leverage must be at least 1.")
            return False
        # Add check for max leverage if available in market data?
        # max_leverage = market.get('info', {}).get('maxLeverage') # Path depends on ccxt/exchange

        try:
            # MEXC requires setting leverage for LONG and SHORT sides separately for isolated margin
            # We assume ISOLATED margin (openType=1)
            params_long = {'openType': 1, 'positionType': 1}
            self.exchange.set_leverage(leverage, symbol, params=params_long)
            logging.info(f"Leverage for {symbol} LONG set to {leverage}x (Isolated)")

            params_short = {'openType': 1, 'positionType': 2}
            self.exchange.set_leverage(leverage, symbol, params=params_short)
            logging.info(f"Leverage for {symbol} SHORT set to {leverage}x (Isolated)")

            # Optional verification step can be added here if needed, might require fetching positions
            return True

        except ccxt.NetworkError as e:
            logging.error(f"Network error setting leverage for {symbol}: {e}")
            return False
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error setting leverage for {symbol}: {e} - Check if leverage is valid for the symbol.")
            # Example: MEXC might return {'code': 2008, 'msg': 'Leverage must be between 1 and 200'}
            return False
        except Exception as e:
            logging.error(f"Unexpected error setting leverage for {symbol}: {e}")
            return False

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> Optional[List[List[float]]]:
        """Fetch OHLCV data."""
        if not self.exchange.has['fetchOHLCV']:
            logging.error("Exchange does not support fetchOHLCV")
            return None
        try:
            # Add retry logic for robustness
            for _ in range(3): # Retry up to 3 times
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                if ohlcv:
                    logging.debug(f"Fetched {len(ohlcv)} candles for {symbol} ({timeframe})")
                    return ohlcv
                time.sleep(1) # Wait before retrying
            logging.warning(f"Failed to fetch OHLCV for {symbol} after retries.")
            return None
        except ccxt.NetworkError as e:
            logging.error(f"Network error fetching OHLCV for {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error fetching OHLCV for {symbol}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching OHLCV for {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get the last traded price for a symbol."""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            if ticker and 'last' in ticker:
                logging.debug(f"Current price for {symbol}: {ticker['last']}")
                return float(ticker['last'])
            else:
                logging.warning(f"Could not fetch valid ticker/last price for {symbol}")
                return None
        except ccxt.NetworkError as e:
            logging.error(f"Network error fetching ticker for {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error fetching ticker for {symbol}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching ticker for {symbol}: {e}")
            return None

    def place_market_order_with_sl_tp(self, symbol: str, side: str, amount: float, sl_price: Optional[float] = None, tp_price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Places a market order with Stop Loss and Take Profit.
        NOTE: SL/TP support via `params` varies by exchange and ccxt implementation.
              This might require placing separate SL/TP orders after the market order.
        """
        if side not in ['buy', 'sell']:
            logging.error(f"Invalid order side: {side}")
            return None

        market = self.get_market(symbol)
        if not market:
            logging.error(f"Cannot place order: Market {symbol} not found.")
            return None

        # CCXT uses 'buy'/'sell', MEXC API might use 'open_long'/'open_short', etc. CCXT should handle this.
        order_type = 'market'
        params = {
            # 'positionSide': 'long' if side == 'buy' else 'short' # Needed? ccxt usually handles
        }

        # --- MEXC Specific SL/TP Params (Example - Needs Verification!) ---
        # Check MEXC API docs & ccxt implementation for exact `params` keys
        # This is a common pattern but might be different for MEXC swaps.
        if sl_price:
             params['stopLossPrice'] = self.exchange.price_to_precision(symbol, sl_price)
             # MEXC might require a trigger price type as well
             # params['slTrigger'] = 'market_price' # or 'mark_price', 'index_price'

        if tp_price:
            params['takeProfitPrice'] = self.exchange.price_to_precision(symbol, tp_price)
             # params['tpTrigger'] = 'market_price' # or 'mark_price', 'index_price'
        # --- End MEXC Specific Params ---

        try:
            logging.info(f"Placing {side} {order_type} order for {amount} {market.get('base', '')} on {symbol} with SL={sl_price}, TP={tp_price}, Params: {params}")
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount, # Amount in base currency (e.g., XRP)
                params=params
            )
            logging.info(f"Order placed successfully: {order['id']}")
            # It's crucial to fetch the order details after placement
            # to confirm execution, filled price, and actual SL/TP settings if possible.
            # fetched_order = self.exchange.fetch_order(order['id'], symbol)
            # logging.info(f"Fetched order details: {fetched_order}")
            return order

        except ccxt.InsufficientFunds as e:
            logging.error(f"Insufficient funds to place order for {symbol}: {e}")
            return None
        except ccxt.InvalidOrder as e:
            logging.error(f"Invalid order for {symbol}: {e} - Check amount precision, price, SL/TP params.")
            # If SL/TP params cause this, might need the alternative strategy.
            return None
        except ccxt.NetworkError as e:
            logging.error(f"Network error placing order for {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error placing order for {symbol}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error placing order for {symbol}: {e}")
            return None

    def get_usdt_balance(self) -> Optional[float]:
        """Fetch the free USDT balance from the swap/futures account."""
        try:
            balance = self.exchange.fetch_balance(params={'type': 'swap'}) # Specify swap account
            if 'USDT' in balance['free']:
                usdt_balance = float(balance['free']['USDT'])
                logging.debug(f"Free USDT balance: {usdt_balance}")
                return usdt_balance
            else:
                logging.warning("USDT balance not found in swap account.")
                return 0.0 # Return 0 if no USDT found
        except ccxt.NetworkError as e:
            logging.error(f"Network error fetching balance: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error fetching balance: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching balance: {e}")
            return None

    def get_positions(self, symbol: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Fetch open positions for a specific symbol or all symbols."""
        try:
            if self.exchange.has['fetchPositions']:
                symbols = [symbol] if symbol else None
                positions = self.exchange.fetch_positions(symbols=symbols)
                # Filter out zero-size positions often returned by exchanges
                open_positions = [p for p in positions if p.get('contracts') and float(p['contracts']) != 0]
                logging.debug(f"Fetched {len(open_positions)} open positions.")
                return open_positions
            else:
                logging.warning("Exchange does not support fetchPositions.")
                return None
        except ccxt.NetworkError as e:
            logging.error(f"Network error fetching positions: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error fetching positions: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching positions: {e}")
            return None

    def get_trade_history(self, symbol: str, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """Fetch trade history for a symbol."""
        if not self.exchange.has['fetchMyTrades']:
            logging.error("Exchange does not support fetchMyTrades")
            return None
        try:
            trades = self.exchange.fetch_my_trades(symbol=symbol, limit=limit)
            logging.debug(f"Fetched {len(trades)} trades for {symbol}")
            return trades
        except ccxt.NetworkError as e:
            logging.error(f"Network error fetching trade history for {symbol}: {e}")
            return None
        except ccxt.ExchangeError as e:
            logging.error(f"Exchange error fetching trade history for {symbol}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching trade history for {symbol}: {e}")
            return None

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

        # --- Test Trade History ---
        # trades = handler.get_trade_history(config.DEFAULT_SYMBOL, limit=10)
        # if trades is not None:
        #     if trades:
        #         print("Recent Trades:")
        #         for trade in trades:
        #             print(f"  ID: {trade['id']}, Time: {trade['datetime']}, Side: {trade['side']}, Amount: {trade['amount']}, Price: {trade['price']}, Fee: {trade['fee']}")
        #     else:
        #         print("No recent trades found.")
        # else:
        #      print("Could not fetch trade history.")

        # --- Test Placing Order (DANGEROUS - DO NOT RUN UNATTENDED) ---
        # print("\\nWARNING: The next step attempts to place a REAL order.")
        # confirm = input("Type 'yes' to place a small test buy order: ")
        # if confirm.lower() == 'yes' and price:
        #     test_amount = 0.1 # Minimal amount for testing - adjust based on symbol's minimum order size
        #     sl_test = price * (1 - 0.01) # 1% SL
        #     tp_test = price * (1 + 0.01) # 1% TP
        #     order_info = handler.place_market_order_with_sl_tp(
        #         symbol=config.DEFAULT_SYMBOL,
        #         side='buy',
        #         amount=test_amount,
        #         sl_price=sl_test,
        #         tp_price=tp_test
        #     )
        #     if order_info:
        #         print(f"Test order placed: {order_info}")
        #     else:
        #         print("Test order placement failed.")
        # else:
        #     print("Skipping test order placement.")


    except ValueError as e:
        print(f"Configuration Error: {e}")
    except ccxt.AuthenticationError:
        print("Authentication Error: Please check your API keys in the .env file.")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}") 