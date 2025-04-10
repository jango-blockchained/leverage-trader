import logging
import queue
import threading
import time
import os
from decimal import Decimal

from rich.text import Text
from textual.app import App, ComposeResult, Message
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, RichLog

# Import project modules (adjust paths if necessary)
import src.config as config
# Assume these modules exist and have necessary functions/classes
from src.mexc_handler import MexcHandler
from src.data_handler import DataHandler
from src.indicator_handler import IndicatorHandler
from src.trade_executor import TradeExecutor
from src.stats_handler import StatsHandler # If you have one

# --- Constants ---
METRICS_UPDATE_INTERVAL = config.STATS_UPDATE_INTERVAL_SECONDS # Update UI metrics table
LOG_UPDATE_INTERVAL = 0.5 # How often to check the log queue

# --- Logging Setup ---
log_queue = queue.Queue()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Add more specific loggers if needed
app_logger = logging.getLogger("TradingBotApp")
# Note: A custom handler will be added in the App to redirect logs to RichLog


# --- Custom Log Handler for Textual ---
class TextualLogHandler(logging.Handler):
    def __init__(self, app_log_queue):
        super().__init__()
        self.app_log_queue = app_log_queue

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.app_log_queue.put(log_entry)
        except Exception:
            self.handleError(record)

# --- Background Task Messages ---
# Use classes or dictionaries for clearer message structure
class UpdateMetricsMessage(Message):
    """Message to update metrics in the UI."""
    def __init__(self, metrics):
        super().__init__()
        self.metrics = metrics

class LogMessage(Message):
    """Message to log text in the UI."""
    def __init__(self, message):
        super().__init__()
        self.message = message

class ManualTradeMessage:
    """Command message for the background thread."""
    def __init__(self, side):
        self.side = side # 'long' or 'short'

# --- Metrics Data Structure ---
# Example - adjust based on actual data needed
class Metrics:
    def __init__(self):
        self.symbol = config.DEFAULT_SYMBOL
        self.current_price: Decimal | None = None
        self.rsi: float | None = None
        self.prediction: str | None = None # e.g., 'LONG', 'SHORT', 'HOLD'
        self.position_size: Decimal | None = None
        self.entry_price: Decimal | None = None
        self.pnl_percent: float | None = None
        self.timestamp = time.time()

# --- Textual App ---
class TradingBotApp(App):
    """A Textual app for the Leverage Trading Bot."""

    CSS_PATH = "main.css" # Load basic CSS
    BINDINGS = [
        ("q", "quit", "Quit App"),
        (config.MANUAL_TRADE_KEY_UP, "manual_trade('long')", "Manual Long"),
        (config.MANUAL_TRADE_KEY_DOWN, "manual_trade('short')", "Manual Short"),
    ]

    # --- Reactive Variables for Metrics ---
    current_metrics = reactive(Metrics(), layout=True)

    def __init__(self):
        super().__init__()
        self.log_widget = RichLog(highlight=True, markup=True)
        self.metrics_table = DataTable(zebra_stripes=True)
        self.background_thread = None
        self.stop_event = threading.Event()
        self.command_queue = queue.Queue() # Queue for app -> background thread commands

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Container(id="main-container"):
            yield self.metrics_table
            yield self.log_widget
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Setup Logging Handler
        textual_log_handler = TextualLogHandler(log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        textual_log_handler.setFormatter(formatter)
        # Add handler to the root logger or specific loggers
        logging.getLogger().addHandler(textual_log_handler)
        # Optionally remove console handlers if you only want logs in the TUI
        # logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler)]

        app_logger.info("Trading Bot App initializing...")

        # Setup Metrics Table
        self.metrics_table.add_column("Metric", key="metric")
        self.metrics_table.add_column("Value", key="value")
        self.update_metrics_table() # Initial population

        # Start background thread
        self.background_thread = threading.Thread(
            target=run_trading_logic,
            args=(self.command_queue, self.post_message, self.stop_event),
            daemon=True # Ensure thread exits when main app exits
        )
        self.background_thread.start()
        app_logger.info("Background trading logic thread started.")

        # Set timers
        self.set_interval(LOG_UPDATE_INTERVAL, self.process_log_queue)

    def process_log_queue(self) -> None:
        """Process logs from the background thread."""
        while not log_queue.empty():
            try:
                record = log_queue.get_nowait()
                # Apply basic styling based on level (optional)
                if "ERROR" in record or "CRITICAL" in record:
                    self.log_widget.write(Text(record, style="bold red"))
                elif "WARNING" in record:
                    self.log_widget.write(Text(record, style="yellow"))
                elif "INFO" in record:
                     self.log_widget.write(Text(record, style="green")) # Example: style info
                else:
                    self.log_widget.write(record)
                log_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                 # Log errors occurring in the log processing itself (to console maybe)
                 print(f"Error processing log queue: {e}")

    def update_metrics_table(self) -> None:
        """Updates the DataTable with current metrics."""
        metrics = self.current_metrics
        self.metrics_table.clear(columns=False) # Keep columns, clear rows
        self.metrics_table.add_row("Symbol", metrics.symbol or "N/A", key="symbol")
        self.metrics_table.add_row("Timestamp", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metrics.timestamp)), key="timestamp")
        self.metrics_table.add_row("Current Price", f"{metrics.current_price:.4f}" if metrics.current_price else "N/A", key="price")
        self.metrics_table.add_row("RSI", f"{metrics.rsi:.2f}" if metrics.rsi else "N/A", key="rsi")
        self.metrics_table.add_row("Prediction", metrics.prediction or "N/A", key="prediction")
        self.metrics_table.add_row("Position Size", f"{metrics.position_size}" if metrics.position_size else "N/A", key="pos_size")
        self.metrics_table.add_row("Entry Price", f"{metrics.entry_price:.4f}" if metrics.entry_price else "N/A", key="entry")
        self.metrics_table.add_row("PnL (%)", f"{metrics.pnl_percent:.2f}%" if metrics.pnl_percent else "N/A", key="pnl")
        app_logger.debug("Metrics table updated.") # Use debug level for frequent updates

    # --- Message Handlers ---
    def on_update_metrics_message(self, message: UpdateMetricsMessage) -> None:
        """Handles metric updates from the background thread."""
        app_logger.debug(f"Received metrics update: {message.metrics}")
        self.current_metrics = message.metrics # Update reactive variable

    # --- Watch Methods ---
    def watch_current_metrics(self, old_metrics: Metrics, new_metrics: Metrics) -> None:
        """Called when the current_metrics reactive variable changes."""
        # Update the table whenever metrics change
        # No need to call from thread here, watcher runs in the app thread
        self.update_metrics_table()

    # --- Action Methods ---
    def action_quit(self) -> None:
        """Called when the user presses the quit key."""
        app_logger.info("Shutdown requested...")
        self.stop_event.set() # Signal background thread to stop
        if self.background_thread:
            self.background_thread.join(timeout=5) # Wait for thread to finish
            if self.background_thread.is_alive():
                app_logger.warning("Background thread did not stop gracefully.")
        app_logger.info("Exiting application.")
        self.exit()

    def action_manual_trade(self, side: str) -> None:
        """Called when manual trade keys are pressed."""
        if side not in ['long', 'short']:
            app_logger.warning(f"Invalid manual trade side received: {side}")
            return

        app_logger.info(f"Manual {side.upper()} trade requested via keypress.")
        self.command_queue.put(ManualTradeMessage(side=side))
        # Optional: Provide immediate feedback in the TUI
        self.log_widget.write(f"[bold blue]User initiated manual {side.upper()} trade...[/]")


# --- Background Trading Logic ---
def run_trading_logic(command_queue: queue.Queue, post_message_callback, stop_event: threading.Event):
    """
    The main loop for fetching data, calculating indicators,
    making predictions, and executing trades.
    Runs in a separate thread.
    """
    # --- Initialize Handlers --- Initialize these properly!
    app_logger.info("Background thread: Initializing handlers...")
    try:
        mexc = MexcHandler(api_key=config.MEXC_API_KEY, secret_key=config.MEXC_SECRET_KEY, test_mode=config.ENABLE_TEST_MODE)
        data_handler = DataHandler(mexc, symbol=config.DEFAULT_SYMBOL, timeframe=config.DEFAULT_TIMEFRAME)
        indicator_handler = IndicatorHandler()
        trade_executor = TradeExecutor(mexc, symbol=config.DEFAULT_SYMBOL, leverage=config.DEFAULT_LEVERAGE)
        stats_handler = StatsHandler() # Initialize your stats handler
        app_logger.info("Background thread: Handlers initialized successfully.")
    except Exception as e:
        app_logger.critical(f"Background thread: Failed to initialize handlers: {e}. Stopping thread.")
        # Optionally post a critical error message to the UI
        # post_message_callback(LogMessage(f"CRITICAL ERROR: Handler Initialization Failed: {e}"))
        return # Stop the thread if handlers fail

    last_data_fetch = 0
    last_prediction_run = 0
    current_position = None # Track current position state (e.g., dict from trade_executor)
    ohlcv = None # Store fetched OHLCV data

    metrics = Metrics()
    metrics.symbol = config.DEFAULT_SYMBOL # Set symbol initially

    app_logger.info("Background thread: Starting main loop.")

    while not stop_event.is_set():
        now = time.time()
        command = None

        # --- Check for commands from the main app ---
        try:
            command = command_queue.get_nowait()
            if isinstance(command, ManualTradeMessage):
                app_logger.info(f"Background thread: Received manual {command.side} trade command.")
                # --- Execute Manual Trade --- Integrate with TradeExecutor
                try:
                    result = trade_executor.execute_manual_trade(command.side, config.TRADE_AMOUNT_BASE)
                    if result:
                        current_position = result # Update position state (assuming result is position info dict)
                        app_logger.info(f"Manual {command.side} trade executed: {result}")
                        metrics.position_size = result.get('size') # Adjust keys based on actual return value
                        metrics.entry_price = result.get('entry_price') # Adjust keys
                        metrics.prediction = f"Manual {command.side.upper()}" # Update status
                        metrics.pnl_percent = None # Reset PnL on new trade
                    else:
                        app_logger.error(f"Manual {command.side} trade failed.")
                        # Keep old prediction/state or set to failed?
                        # metrics.prediction = f"Manual {command.side.upper()} FAILED"
                except Exception as trade_error:
                    app_logger.error(f"Background thread: Error executing manual trade: {trade_error}")
                # --- End Execute Manual Trade ---

            command_queue.task_done()
        except queue.Empty:
            pass # No command waiting
        except Exception as e:
            app_logger.error(f"Background thread: Error processing command: {e}")


        # --- Fetch Data Periodically ---
        if now - last_data_fetch >= config.DATA_FETCH_INTERVAL_SECONDS:
            try:
                app_logger.debug("Background thread: Fetching market data...")
                # --- Fetch Data --- Integrate with DataHandler
                fetched_ohlcv = data_handler.fetch_ohlcv()
                if fetched_ohlcv is None or fetched_ohlcv.empty:
                    app_logger.warning("Background thread: No OHLCV data fetched.")
                    # Keep using old data? Or wait?
                    # time.sleep(1) # Avoid busy-waiting if fetch fails - handled by main loop sleep
                else:
                    ohlcv = fetched_ohlcv # Store the fetched data
                    current_price = data_handler.get_current_price(ohlcv)
                    if current_price:
                        metrics.current_price = current_price
                        app_logger.debug(f"Background thread: Data fetched. Current price: {current_price}")
                    else:
                         app_logger.warning("Background thread: Could not determine current price from OHLCV.")
                         # metrics.current_price = None # Or keep the old one?
                # --- End Fetch Data ---
                # Removed dummy data assignment
                last_data_fetch = now

            except Exception as e:
                app_logger.error(f"Background thread: Error fetching data: {e}")
                time.sleep(config.DATA_FETCH_INTERVAL_SECONDS / 2) # Wait a bit before retrying


        # --- Run Prediction Logic Periodically --- Ensure data is available
        if now - last_prediction_run >= config.PREDICTION_INTERVAL_SECONDS and ohlcv is not None and not ohlcv.empty and metrics.current_price is not None:
            try:
                app_logger.debug("Background thread: Running prediction logic...")
                # --- Calculate Indicators & Predict --- Integrate with IndicatorHandler
                indicators = indicator_handler.calculate_indicators(ohlcv)
                if indicators:
                    metrics.rsi = indicators.get('rsi') # Adjust key if needed
                    prediction = indicator_handler.generate_signal(indicators) # Example: 'LONG', 'SHORT', 'HOLD'
                    metrics.prediction = prediction
                    app_logger.debug(f"Background thread: Prediction: {prediction}, RSI: {metrics.rsi:.2f}" if metrics.rsi else f"Prediction: {prediction}, RSI: N/A")
                else:
                     app_logger.warning("Background thread: Indicator calculation failed.")
                     metrics.prediction = "Calc Error"
                     metrics.rsi = None
                     prediction = "HOLD" # Default to HOLD if calculation fails
                # --- End Calculate Indicators & Predict ---


                # --- Execute Automated Trade (if prediction warrants and no position) ---
                if prediction in ['LONG', 'SHORT'] and not current_position: # Example logic: Only trade if flat
                    # Add any additional checks, e.g., predicted move > threshold
                    # predicted_move_pct = indicator_handler.get_predicted_move_pct(indicators) # Assuming this method exists
                    # if predicted_move_pct is not None and abs(predicted_move_pct) > config.MIN_TAKE_PROFIT_PERCENT:
                    app_logger.info(f"Background thread: Triggering automated {prediction} trade.")
                    try:
                        trade_result = trade_executor.execute_trade(
                            side=prediction.lower(),
                            amount=config.TRADE_AMOUNT_BASE,
                            stop_loss_pct=config.STOP_LOSS_PERCENT,
                            take_profit_pct=config.TAKE_PROFIT_PERCENT
                        )
                        if trade_result:
                            current_position = trade_result # Update position state
                            app_logger.info(f"Automated {prediction} trade executed: {trade_result}")
                            metrics.position_size = trade_result.get('size') # Adjust keys
                            metrics.entry_price = trade_result.get('entry_price') # Adjust keys
                            metrics.pnl_percent = None # Reset PnL on new trade
                        else:
                            app_logger.error(f"Automated {prediction} trade failed.")
                    except Exception as auto_trade_error:
                         app_logger.error(f"Background thread: Error executing automated trade: {auto_trade_error}")
                    # else:
                    #    app_logger.debug(f"Automated {prediction} signal ignored: Predicted move too small.")
                elif current_position and prediction != 'HOLD':
                    # Optional: Log if signal contradicts current position but not acting
                    current_side = current_position.get('side', 'unknown').upper()
                    if (prediction == 'LONG' and current_side != 'BUY') or \
                       (prediction == 'SHORT' and current_side != 'SELL'):
                        app_logger.debug(f"Signal {prediction} contradicts current {current_side} position. Holding.")
                # --- End Execute Automated Trade ---

                # Removed dummy data assignments
                last_prediction_run = now

            except Exception as e:
                app_logger.error(f"Background thread: Error in prediction/trade logic: {e}")


        # --- Update PnL if position exists --- Ensure current price is available
        if current_position and metrics.current_price:
             try:
                 # --- Calculate PnL --- Integrate with StatsHandler
                 # Assume stats_handler.calculate_pnl returns a dict like {'pnl_percent': float}
                 pnl_info = stats_handler.calculate_pnl(current_position, metrics.current_price)
                 if pnl_info and 'pnl_percent' in pnl_info:
                      metrics.pnl_percent = pnl_info['pnl_percent']
                 else:
                      app_logger.warning("Background thread: Could not calculate PnL.")
                      metrics.pnl_percent = None
                 # --- End Calculate PnL ---
             except Exception as pnl_error:
                  app_logger.error(f"Background thread: Error calculating PnL: {pnl_error}")
                  metrics.pnl_percent = None
        else:
             # Ensure PnL is None when no position or no current price
             metrics.pnl_percent = None


        # --- Send metrics update to the main thread ---
        metrics.timestamp = time.time()
        try:
            # Create a copy to avoid potential race conditions if metrics object is modified elsewhere
            metrics_copy = Metrics()
            metrics_copy.symbol = metrics.symbol
            metrics_copy.current_price = metrics.current_price
            metrics_copy.rsi = metrics.rsi
            metrics_copy.prediction = metrics.prediction
            metrics_copy.position_size = metrics.position_size
            metrics_copy.entry_price = metrics.entry_price
            metrics_copy.pnl_percent = metrics.pnl_percent
            metrics_copy.timestamp = metrics.timestamp

            post_message_callback(UpdateMetricsMessage(metrics_copy))
        except Exception as e:
             app_logger.error(f"Background thread: Error sending metrics update: {e}")


        # --- Check SL/TP (if position exists) --- Ensure current price is available
        if current_position and metrics.current_price:
            try:
                # --- Check and close position if SL/TP hit --- Integrate with TradeExecutor
                close_reason = trade_executor.check_sl_tp(current_position, metrics.current_price)
                if close_reason:
                    app_logger.info(f"Closing position due to {close_reason}")
                    try:
                        close_result = trade_executor.close_position(current_position) # Assumes close_position needs position info
                        if close_result:
                            app_logger.info(f"Position closed successfully via SL/TP check: {close_result}")
                            current_position = None
                            metrics.position_size = None
                            metrics.entry_price = None
                            metrics.pnl_percent = None # Reset PnL after closing
                            metrics.prediction = f"Closed ({close_reason})" # Update status
                        else:
                            app_logger.error("Failed to close position after SL/TP hit detected.")
                            # Maybe retry closing? Or leave position state as is?
                    except Exception as close_error:
                        app_logger.error(f"Error closing position after SL/TP hit: {close_error}")
                # --- End Check SL/TP ---
            except Exception as sltp_error:
                 app_logger.error(f"Background thread: Error checking SL/TP: {sltp_error}")


        # Small sleep to prevent high CPU usage in the loop
        time.sleep(0.1)

    app_logger.info("Background thread: Stopping.")


if __name__ == "__main__":
    # Create a basic CSS file if it doesn't exist
    css_file_path = "main.css"
    if not os.path.exists(css_file_path):
        css_content = """
Screen {
    layout: vertical;
}

Header {
    dock: top;
    height: 1;
}

Footer {
    dock: bottom;
    height: 1;
}

#main-container {
    grid-size: 2;
    grid-gutter: 1 2;
    grid-rows: auto 1fr; /* Metrics table auto height, Log takes rest */
    padding: 1; /* Add some padding around the container */
}

DataTable {
    width: 1fr;
    /* Removed fixed height, let it adjust or set via grid */
    border: thick $accent;
    margin-bottom: 1; /* Add space below the table */
}

RichLog {
    width: 1fr;
    height: 1fr; /* Take remaining vertical space */
    border: thick $accent;
}
"""
        try:
            with open(css_file_path, "w") as f:
                f.write(css_content)
            print(f"Created default CSS file: {css_file_path}")
        except IOError as e:
            print(f"Warning: Could not write {css_file_path}: {e}")
    else:
         print(f"CSS file already exists: {css_file_path}")


    # Run the app
    app = TradingBotApp()
    app.run() 