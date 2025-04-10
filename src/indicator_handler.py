from typing import List, Tuple, Optional, Any
import logging
import pandas as pd
import numpy as np
import pandas_ta as ta # Import pandas-ta

# Remove TA-Lib specific import block
# try:
#     import talib
# except ImportError:
#     logging.error("TA-Lib not found...")
#     talib = None

# --- Configuration for Indicators ---
# These could also be moved to config.py
SMA_SHORT_PERIOD = 10
SMA_LONG_PERIOD = 30
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
BBANDS_PERIOD = 20
BBANDS_STDDEV = 2
STOCH_K_PERIOD = 14 # pandas-ta uses 'k'
STOCH_D_PERIOD = 3  # pandas-ta uses 'd'
STOCH_SMOOTH_K = 3 # pandas-ta uses 'smooth_k'
STOCH_OVERBOUGHT = 80
STOCH_OVERSOLD = 20
OBV_SMA_PERIOD = 20 # Period for OBV's own SMA

MIN_DATA_POINTS = max(
    SMA_LONG_PERIOD,
    RSI_PERIOD,
    MACD_SLOW_PERIOD + MACD_SIGNAL_PERIOD, # MACD needs more history for its internal EMAs
    BBANDS_PERIOD,
    STOCH_K_PERIOD + STOCH_SMOOTH_K # Approximation for stoch
) + 10 # Add a buffer for calculations to stabilize

class IndicatorHandler:
    """Handles calculation of technical indicators and signal generation."""

    def __init__(self):
        """Initialize the IndicatorHandler."""
        # Add any initialization parameters if needed in the future
        logging.info("IndicatorHandler initialized.")

    def calculate_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Calculates technical indicators using pandas-ta and adds them to the DataFrame."""
        
        required_length = MIN_DATA_POINTS
        if len(df) < required_length:
            logging.warning(f"Not enough data points ({len(df)}) to calculate indicators reliably (min: {required_length}).")
            return None

        try:
            # Ensure standard OHLCV column names if not already present (pandas-ta prefers lowercase)
            df.rename(columns={
                'timestamp': 'timestamp', # Keep timestamp if needed
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            }, inplace=True, errors='ignore') # Ignore errors if columns don't exist
            # Ensure required columns exist and are numeric
            required_cols_ohlcv = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols_ohlcv:
                if col not in df.columns:
                    logging.error(f"Missing required column for indicators: {col}")
                    return None
                # Convert to numeric, coercing errors (like empty strings) to NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Drop rows with NaN in essential price/volume data AFTER conversion
            df.dropna(subset=required_cols_ohlcv, inplace=True)
            if len(df) < required_length:
                logging.warning(f"Data points reduced to {len(df)} after cleaning NaNs, insufficient for indicators (min: {required_length}).")
                return None

            # --- Calculate Indicators using df.ta --- 
            # Strategy Example: Calculate SMA, RSI, MACD, Bollinger Bands, Stochastic, OBV
            # This calculates and appends columns directly to the DataFrame `df`
            df.ta.sma(length=SMA_SHORT_PERIOD, append=True) # Appends as SMA_10
            df.ta.sma(length=SMA_LONG_PERIOD, append=True) # Appends as SMA_30
            df.ta.rsi(length=RSI_PERIOD, append=True) # Appends as RSI_14
            df.ta.macd(fast=MACD_FAST_PERIOD, slow=MACD_SLOW_PERIOD, signal=MACD_SIGNAL_PERIOD, append=True) # Appends as MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
            df.ta.bbands(length=BBANDS_PERIOD, std=BBANDS_STDDEV, append=True) # Appends as BBL_20_2.0, BBM_20_2.0, BBU_20_2.0, BBB_20_2.0, BBP_20_2.0
            df.ta.stoch(k=STOCH_K_PERIOD, d=STOCH_D_PERIOD, smooth_k=STOCH_SMOOTH_K, append=True) # Appends as STOCHk_14_3_3, STOCHd_14_3_3
            df.ta.obv(append=True) # Appends as OBV
            # Calculate SMA of OBV separately using the DataFrame accessor
            obv_sma_series = df.ta.sma(close=df['OBV'], length=OBV_SMA_PERIOD, append=False) # Calculate separately
            df[f'OBV_SMA_{OBV_SMA_PERIOD}'] = obv_sma_series # Assign to the new column name

            # Rename columns for consistency with previous logic (Optional, but helps reuse strategy code)
            # Check exact names pandas-ta uses via df.columns after calculation if needed
            df.rename(columns={
                f'SMA_{SMA_SHORT_PERIOD}': 'sma_short',
                f'SMA_{SMA_LONG_PERIOD}': 'sma_long',
                f'RSI_{RSI_PERIOD}': 'rsi',
                f'MACD_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}': 'macd',
                f'MACDh_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}': 'macdhist',
                f'MACDs_{MACD_FAST_PERIOD}_{MACD_SLOW_PERIOD}_{MACD_SIGNAL_PERIOD}': 'macdsignal',
                f'BBL_{BBANDS_PERIOD}_{float(BBANDS_STDDEV)}': 'bb_lower',
                f'BBM_{BBANDS_PERIOD}_{float(BBANDS_STDDEV)}': 'bb_middle',
                f'BBU_{BBANDS_PERIOD}_{float(BBANDS_STDDEV)}': 'bb_upper',
                f'STOCHk_{STOCH_K_PERIOD}_{STOCH_D_PERIOD}_{STOCH_SMOOTH_K}': 'slowk',
                f'STOCHd_{STOCH_K_PERIOD}_{STOCH_D_PERIOD}_{STOCH_SMOOTH_K}': 'slowd',
                f'OBV_SMA_{OBV_SMA_PERIOD}': 'obv_sma'
                # Keep original 'OBV' as is
            }, inplace=True, errors='ignore') # Ignore errors if a col wasn't generated (e.g., older pandas-ta)

            logging.debug("Indicators calculated successfully using pandas-ta.")
            return df

        except Exception as e:
            logging.error(f"Error calculating indicators with pandas-ta: {e}", exc_info=True)
            return None

    def get_signal(self, ohlcv: List[List[float]]) -> str:
        """
        Analyzes market data using multiple indicators (calculated by pandas-ta)
        and returns a trading signal based on confluence.

        Args:
            ohlcv: A list of lists [timestamp, open, high, low, close, volume].

        Returns:
            'LONG', 'SHORT', or 'NONE'.
        """
        if not ohlcv:
            logging.warning("No OHLCV data provided to predictor.")
            return 'NONE'

        # Convert to DataFrame (Timestamp may not be needed as index by pandas-ta)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Calculate Indicators using the updated function
        df_indicators = self.calculate_indicators(df)

        if df_indicators is None:
            logging.warning("Failed to calculate indicators or insufficient data, cannot generate signal.")
            return 'NONE'

        # --- Combined Strategy Logic (using renamed columns) ---
        if len(df_indicators) < 2:
            logging.warning("Need at least two rows with indicators for signal generation.")
            return 'NONE'
        latest = df_indicators.iloc[-1]
        previous = df_indicators.iloc[-2]

        # Check for NaN values in the latest required indicators
        # Use the renamed columns
        required_cols = [
            'sma_short', 'sma_long', 'rsi', 'macd', 'macdsignal',
            'slowk', 'slowd', 'OBV', 'obv_sma' # OBV column name might be just 'OBV'
        ]
        # Check if columns exist before checking for NaN
        if not all(col in latest.index for col in required_cols):
            # Attempt to get the actual missing columns for better logging
            missing_cols = [col for col in required_cols if col not in latest.index]
            logging.error(f"One or more required indicator columns missing after calculation: {missing_cols}. Available: {latest.index.tolist()}")
            return 'NONE'
        
        if latest[required_cols].isnull().any() or previous[required_cols].isnull().any():
            logging.warning(f"Latest or previous indicator data contains NaN. Waiting for more data.")
            return 'NONE'

        # --- Define Signal Conditions (Example Confluence Strategy) ---

        # Trend Conditions:
        sma_trend_up = latest['sma_short'] > latest['sma_long']
        sma_trend_down = latest['sma_short'] < latest['sma_long']
        macd_trend_up = latest['macd'] > latest['macdsignal'] # MACD line above signal line
        macd_trend_down = latest['macd'] < latest['macdsignal']

        # Momentum Conditions:
        rsi_not_overbought = latest['rsi'] < RSI_OVERBOUGHT
        rsi_not_oversold = latest['rsi'] > RSI_OVERSOLD
        # Stochastic Crossover:
        stoch_crossed_up = previous['slowk'] <= previous['slowd'] and latest['slowk'] > latest['slowd']
        stoch_crossed_down = previous['slowk'] >= previous['slowd'] and latest['slowk'] < latest['slowd']
        stoch_bullish_zone = latest['slowk'] > STOCH_OVERSOLD and latest['slowd'] > STOCH_OVERSOLD
        stoch_bearish_zone = latest['slowk'] < STOCH_OVERBOUGHT and latest['slowd'] < STOCH_OVERBOUGHT

        # Volume Condition (Confirmation):
        obv_rising = latest['OBV'] > latest['obv_sma'] # OBV above its own short-term SMA
        obv_falling = latest['OBV'] < latest['obv_sma']

        # --- Combine Conditions for Signals --- 
        
        # LONG Signal: Need upward trend, supportive momentum, and volume confirmation
        is_long_signal = (
            (sma_trend_up or macd_trend_up) # At least one trend indicator bullish
            and rsi_not_overbought          # Momentum not exhausted
            # and stoch_bullish_zone        # Optional: Stochastic in bullish zone
            and (stoch_crossed_up or (latest['slowk'] > latest['slowd'])) # Stochastic crossed up or is bullish
            and obv_rising                 # Volume confirms upward pressure
        )

        # SHORT Signal: Need downward trend, supportive momentum, and volume confirmation
        is_short_signal = (
            (sma_trend_down or macd_trend_down) # At least one trend indicator bearish
            and rsi_not_oversold           # Momentum not exhausted
            # and stoch_bearish_zone         # Optional: Stochastic in bearish zone
            and (stoch_crossed_down or (latest['slowk'] < latest['slowd'])) # Stochastic crossed down or is bearish
            and obv_falling                # Volume confirms downward pressure
        )

        # --- Generate Final Signal --- 
        if is_long_signal:
            # Add extra checks? e.g., Price bounced off lower BBand? Avoid if price hit upper BBand?
            # if latest['close'] > latest['bb_upper']: # Example: Avoid long if near upper band
            #     logging.debug(f"Potential LONG signal for {symbol} ignored: Price near upper BBand.")
            #     return 'NONE'
            logging.info(f"Prediction: LONG signal generated.")
            return 'LONG'

        elif is_short_signal:
            # Add extra checks? e.g., Price hit upper BBand? Avoid if price bounced off lower BBand?
            # if latest['close'] < latest['bb_lower']: # Example: Avoid short if near lower band
            #     logging.debug(f"Potential SHORT signal for {symbol} ignored: Price near lower BBand.")
            #     return 'NONE'
            logging.info(f"Prediction: SHORT signal generated.")
            return 'SHORT'

        else:
            logging.debug(f"No clear signal based on current strategy rules.")
            return 'NONE'

# --- Example Usage (for testing within this file) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Generate slightly more realistic dummy data
    num_points = MIN_DATA_POINTS + 100
    timestamps = pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=num_points, freq='1min').astype(np.int64) // 10**6
    
    # Simulate some price movement
    price_path = np.zeros(num_points)
    price_path[0] = 50.0
    for i in range(1, num_points):
        price_path[i] = price_path[i-1] + np.random.randn() * 0.1 # Random walk component
        # Add a slight sine wave trend component
        price_path[i] += np.sin(i / 50.0) * 0.2 

    opens = price_path
    closes = price_path + (np.random.rand(num_points) - 0.5) * 0.05 # Small noise around path
    highs = np.maximum(opens, closes) + np.random.rand(num_points) * 0.05
    lows = np.minimum(opens, closes) - np.random.rand(num_points) * 0.05
    volumes = np.random.randint(100, 1000, size=num_points).astype(float)
    # Simulate some volume correlation with price changes
    price_diff = np.diff(closes, prepend=closes[0])
    volumes[price_diff > 0] *= (1 + np.random.rand(np.sum(price_diff > 0)) * 0.5) 
    volumes[price_diff < 0] *= (1 + np.random.rand(np.sum(price_diff < 0)) * 0.3)

    dummy_ohlcv = [[ts, o, h, l, c, v] for ts, o, h, l, c, v in zip(timestamps, opens, highs, lows, closes, volumes)]

    print(f"--- Testing IndicatorHandler with {len(dummy_ohlcv)} dummy data points ---")
    handler = IndicatorHandler() # Instantiate the handler
    df_test = pd.DataFrame(dummy_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_test_indicators = handler.calculate_indicators(df_test.copy()) # Call method on instance

    if df_test_indicators is not None:
        print("Indicators calculated. Checking latest values (last 5 rows):")
        # Select only the columns used in the strategy to check for NaNs
        check_cols = ['sma_short', 'sma_long', 'rsi', 'macd', 'macdsignal', 'slowk', 'slowd', 'OBV', 'obv_sma', 'bb_lower', 'bb_middle', 'bb_upper']
        # Ensure columns exist before trying to print them
        existing_check_cols = [col for col in check_cols if col in df_test_indicators.columns]
        print(df_test_indicators[existing_check_cols].tail())
        signal = handler.get_signal(dummy_ohlcv)
        print(f"Generated signal: {signal}")
    else:
        print("Indicator calculation failed for the main test.")

    print("\n--- Testing with insufficient data ---")
    signal_insufficient = handler.get_signal(dummy_ohlcv[:MIN_DATA_POINTS-1])
    print(f"Generated signal (insufficient data): {signal_insufficient}")

    print("\n--- Testing with no data ---")
    signal_no_data = handler.get_signal([])
    print(f"Generated signal (no data): {signal_no_data}")

    print("\n--- Testing with data containing NaN (should fail calculation) ---")
    dummy_ohlcv_nan = dummy_ohlcv[:MIN_DATA_POINTS+10]
    if dummy_ohlcv_nan: # Ensure list is not empty before trying to index
        dummy_ohlcv_nan[-1][4] = np.nan # Introduce NaN in close price
    signal_nan = handler.get_signal(dummy_ohlcv_nan)
    print(f"Generated signal (with NaN): {signal_nan}") 