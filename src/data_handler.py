import logging
import pandas as pd
from typing import List, Optional
from decimal import Decimal
import time

# Assuming MexcHandler is defined in mexc_handler.py
from src.mexc_handler import MEXCHandler # Corrected case

class DataHandler:
    """Handles fetching and preparing market data."""

    def __init__(self, mexc_handler: MEXCHandler, symbol: str, timeframe: str):
        """
        Initializes the DataHandler.

        Args:
            mexc_handler: An instance of MexcHandler.
            symbol: The trading symbol (e.g., 'XRP/USDT:USDT').
            timeframe: The timeframe for OHLCV data (e.g., '1m').
        """
        self.mexc_handler = mexc_handler
        self.symbol = symbol
        self.timeframe = timeframe
        logging.info(f"DataHandler initialized for {symbol} on {timeframe}.")

    def fetch_ohlcv(self, limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetches OHLCV data from the exchange and returns it as a DataFrame.

        Args:
            limit: The maximum number of candles to fetch.

        Returns:
            A pandas DataFrame with OHLCV data [timestamp, open, high, low, close, volume],
            with timestamp as datetime objects and other columns as numeric.
            Returns None if fetching fails after retries.
        """
        # Use the fetch_ohlcv logic from MEXCHandler
        raw_ohlcv = None
        try:
            # Retry logic adapted from MEXCHandler.fetch_ohlcv
            for attempt in range(3): # Retry up to 3 times
                raw_ohlcv = self.mexc_handler.fetch_ohlcv(self.symbol, self.timeframe, limit=limit)
                if raw_ohlcv:
                    logging.debug(f"Fetched {len(raw_ohlcv)} candles for {self.symbol} ({self.timeframe}) on attempt {attempt + 1}")
                    break # Success
                logging.warning(f"Attempt {attempt + 1} failed to fetch OHLCV for {self.symbol}. Retrying after 1s...")
                time.sleep(1) # Wait before retrying
            
            if not raw_ohlcv:
                logging.error(f"Failed to fetch OHLCV for {self.symbol} after retries.")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(raw_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Convert timestamp to datetime (assuming milliseconds from CCXT)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Ensure other columns are numeric, coercing errors
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Optional: Drop rows with NaNs if conversion failed for any column
            # df.dropna(subset=numeric_cols, inplace=True)
            
            return df

        except Exception as e:
            # Catch any unexpected error during fetching or DataFrame conversion
            logging.error(f"Error in fetch_ohlcv method: {e}", exc_info=True)
            return None

    def get_current_price(self, ohlcv_df: Optional[pd.DataFrame] = None) -> Optional[Decimal]:
        """
        Gets the current market price.
        Priority 1: Use the latest close from the provided OHLCV DataFrame.
        Priority 2: Fetch the latest ticker price from the exchange.

        Args:
            ohlcv_df: Optional DataFrame of recent OHLCV data.

        Returns:
            The current price as a Decimal, or None if fetching fails.
        """
        # Priority 1: Use latest close from DataFrame if available and valid
        if ohlcv_df is not None and not ohlcv_df.empty:
            try:
                latest_close = ohlcv_df['close'].iloc[-1]
                if pd.notna(latest_close):
                    price = Decimal(str(latest_close))
                    logging.debug(f"Using latest close price from DataFrame: {price}")
                    return price
                else:
                    logging.debug("Latest close in DataFrame is NaN, falling back to ticker.")
            except (IndexError, KeyError, ValueError, TypeError) as e:
                logging.warning(f"Could not get latest close from DataFrame ({e}), falling back to ticker.")

        # Priority 2: Fetch ticker information using MEXCHandler method
        logging.debug(f"Fetching current ticker price for {self.symbol}")
        try:
            # Use the get_current_price method from the injected mexc_handler instance
            ticker_price_float = self.mexc_handler.get_current_price(self.symbol)
            if ticker_price_float is not None:
                price = Decimal(str(ticker_price_float))
                logging.debug(f"Using ticker price: {price}")
                return price
            else:
                logging.warning(f"Could not get current price for {self.symbol} from ticker.")
                return None
        except Exception as e:
            # Catch errors from the MEXCHandler call
            logging.error(f"Error fetching ticker price via MEXCHandler: {e}", exc_info=True)
            return None 