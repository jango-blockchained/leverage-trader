import os
from dotenv import load_dotenv

# --- Security Warning ---
# DO NOT HARDCODE YOUR API KEYS HERE.
# Use environment variables or a secure configuration management system.
# Create a .env file in the same directory as this script and add:
# MEXC_API_KEY='your_api_key'
# MEXC_SECRET_KEY='your_secret_key'
# ---

load_dotenv() # Load variables from .env file

# --- MEXC API Credentials ---
MEXC_API_KEY = os.getenv('MEXC_API_KEY')
MEXC_SECRET_KEY = os.getenv('MEXC_SECRET_KEY')

if not MEXC_API_KEY or not MEXC_SECRET_KEY:
    print("ERROR: MEXC_API_KEY or MEXC_SECRET_KEY not found in environment variables.")
    print("Please create a .env file and add your keys.")
    # Consider exiting or raising an exception here in a real application
    # exit(1)

# --- Trading Parameters ---
DEFAULT_SYMBOL = 'XRP/USDT:USDT' # Example symbol, adjust as needed
DEFAULT_TIMEFRAME = '1m'          # Example: 1m, 5m, 15m, 1h, 4h, 1d
TRADE_AMOUNT_BASE = 100           # Example: Trade size in base currency (e.g., 100 XRP)
DEFAULT_LEVERAGE = 10             # Example: Default leverage. 200x is EXTREMELY HIGH RISK. Start lower.
MIN_TAKE_PROFIT_PERCENT = 0.1   # Example: Minimum predicted move % to trigger a trade (0.1% = 0.001)
STOP_LOSS_PERCENT = 0.05          # Example: % below entry for SL (0.05% = 0.0005)
TAKE_PROFIT_PERCENT = 0.1         # Example: % above entry for TP (0.1% = 0.001)

# --- Application Settings ---
ENABLE_TEST_MODE = True # Set to True to attempt using MEXC testnet (if supported by ccxt/MEXC)
DATA_FETCH_INTERVAL_SECONDS = 5 # How often to fetch new market data
PREDICTION_INTERVAL_SECONDS = 1 # How often to run the prediction logic
STATS_UPDATE_INTERVAL_SECONDS = 10 # How often to update and display statistics

# --- Keyboard Input ---
MANUAL_TRADE_KEY_UP = 'up'      # Key for manual long trade
MANUAL_TRADE_KEY_DOWN = 'down'  # Key for manual short trade 