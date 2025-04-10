# MEXC USDT Futures Trading Bot Skeleton

This Python script provides a basic framework for creating an automated trading bot for MEXC USDT-M perpetual futures.

**⚠️ EXTREMELY IMPORTANT WARNINGS ⚠️**

*   **HIGH RISK:** Trading cryptocurrency futures, especially with high leverage (like the requested 200x), is extremely risky and can lead to rapid and significant financial losses (liquidation). **USE AT YOUR OWN RISK.**
*   **NO GUARANTEE:** This script is a structural example. It does **NOT** contain a profitable trading strategy. The prediction logic (`predictor.py`) is a placeholder and **MUST** be implemented by you.
*   **NO FINANCIAL ADVICE:** This code is for educational purposes only and is not financial advice. Do your own research and understand the risks before trading.
*   **SECURITY:** Protect your API keys. Do not share them or commit them directly into version control.
*   **BUGS:** This code is provided as-is without warranty. It may contain bugs or errors. Test thoroughly before use.

## Features

*   Connects to MEXC USDT-M Futures market using `ccxt`.
*   Fetches OHLCV data and current price.
*   Placeholder for custom prediction logic (`predictor.py`).
*   Executes market orders with configurable SL/TP based on prediction signals.
*   Allows manual LONG/SHORT trades using Up/Down arrow keys.
*   Displays basic real-time statistics (Equity, P&L, Trades, Volume) in the terminal.
*   Uses environment variables for API keys (`.env` file).
*   Basic multi-threaded structure for data fetching, prediction, keyboard listening, and statistics updates.

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-directory>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: `pynput` might require additional system packages depending on your OS (e.g., `python3-dev`, `libx11-dev`, `libxtst-dev`, `libpng-dev` on Debian/Ubuntu for the keyboard listener).* Consult `pynput` documentation if installation fails.

4.  **Create `.env` File:**
    Create a file named `.env` in the same directory as the scripts and add your MEXC API keys:
    ```dotenv
    MEXC_API_KEY='YOUR_MEXC_API_KEY'
    MEXC_SECRET_KEY='YOUR_MEXC_SECRET_KEY'
    ```
    *   **Get API keys from your MEXC account settings.** Ensure they have permissions enabled for Futures Trading.
    *   **NEVER commit this `.env` file to Git.** Add `.env` to your `.gitignore` file.

5.  **Configure Parameters (Optional):**
    Review and modify trading parameters in `config.py` (e.g., `DEFAULT_SYMBOL`, `DEFAULT_TIMEFRAME`, `TRADE_AMOUNT_BASE`, leverage, SL/TP percentages).
    **Start with low leverage and small trade amounts for testing!**

## Implement Your Strategy

*   **CRITICAL STEP:** Open `predictor.py`.
*   Replace the placeholder logic within the `get_signal` function with your actual trading strategy.
*   You can use libraries like `pandas`, `numpy`, `TA-Lib`, etc., to analyze the `ohlcv` data.
*   The function should return `'LONG'`, `'SHORT'`, or `'NONE'`. 

## Running the Bot

```bash
python main.py
```

*   The script will ask for the trading symbol, timeframe, and leverage (or use defaults from `config.py`).
*   It will then connect to MEXC, set leverage, and start the trading loop.
*   You will see a table with live statistics.
*   Press the **Up Arrow key** to manually place a LONG market order.
*   Press the **Down Arrow key** to manually place a SHORT market order.
*   Press **Ctrl+C** to gracefully shut down the bot.

## Disclaimer

Trading involves substantial risk. Past performance is not indicative of future results. The developers and contributors of this script are not responsible for any financial losses incurred through its use. Always trade responsibly and never risk more than you can afford to lose. 