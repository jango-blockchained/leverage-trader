import logging
import queue
import threading
import time
import os
import pandas as pd
from decimal import Decimal
from collections import deque
from dataclasses import dataclass, field

from rich.text import Text
from textual.app import App, ComposeResult
from textual.message import Message
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, RichLog, Static

# Import project modules (adjust paths if necessary)
import src.config as config
# Assume these modules exist and have necessary functions/classes
from src.mexc_handler import MEXCHandler
from src.data_handler import DataHandler
from src.indicator_handler import IndicatorHandler
from src.trade_executor import TradeExecutor
from src.stats_handler import StatsHandler # If you have one
from src.widgets import (
    ConnectionStatusWidget, 
    PositionHistoryWidget, 
    SettingsPanelWidget, 
    MiniChartWidget, 
    ThemeManager,
    ThemeChangedMessage,
    SettingChangedMessage
)

# --- Constants ---
METRICS_UPDATE_INTERVAL = config.STATS_UPDATE_INTERVAL_SECONDS # Update UI metrics table
LOG_UPDATE_INTERVAL = 0.5 # How often to check the log queue
CONNECTION_CHECK_INTERVAL = 10  # How often to check API connection
UI_UPDATE_THROTTLE = 0.2  # Minimum time between UI updates (seconds)
UI_UPDATE_INTERVAL = 0.2  # How often to check for pending UI updates (seconds)
PREDICTION_ERROR_THROTTLE = 10  # Minimum time between logging same prediction errors (seconds)

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

class NotificationMessage(Message):
    """Message to display a notification in the UI."""
    def __init__(self, message, level="info"):
        """
        Initialize notification message.
        
        Args:
            message: The notification text
            level: Severity level ("info", "warning", "error", "success")
        """
        super().__init__()
        self.message = message
        self.level = level

class ConnectionStatusMessage(Message):
    """Message to update connection status in the UI."""
    def __init__(self, status, error_message=""):
        """
        Initialize connection status message.
        
        Args:
            status: Connection status ("connected", "connecting", "disconnected", "error")
            error_message: Optional error message if status is "error"
        """
        super().__init__()
        self.status = status
        self.error_message = error_message

class ManualTradeMessage:
    """Command message for the background thread."""
    def __init__(self, side):
        self.side = side # 'long' or 'short'

class UpdatePositionHistoryMessage(Message):
    """Message to update position history in the UI."""
    def __init__(self, history):
        super().__init__()
        self.history = history

# --- Notification Widget ---
class NotificationWidget(Static):
    """Widget for displaying notifications and alerts."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_hide = True
        self.auto_hide_time = 5  # Default time in seconds
        self.notification_queue = []
        self.current_timer = None
        self.current_priority = 0  # 0=info, 1=success, 2=warning, 3=error
        
    def show_notification(self, message, level="info"):
        """
        Display a notification with the specified level.
        
        Args:
            message: The notification text
            level: Severity level ("info", "warning", "error", "success")
        """
        # Map levels to styles and priorities
        style_map = {
            "info": ("bold blue", 0),
            "success": ("bold green", 1),
            "warning": ("bold yellow", 2),
            "error": ("bold red on white", 3),
        }
        
        style, priority = style_map.get(level, ("bold blue", 0))
        
        # If a higher priority notification is showing, queue this one
        if self.visible and priority <= self.current_priority:
            self.notification_queue.append({
                "message": message,
                "level": level,
                "priority": priority
            })
            return
            
        # If we're replacing a current notification, check if a timer exists
        # but don't explicitly cancel it to avoid the AttributeError
        if self.current_timer:
            # self.cancel_timer(self.current_timer) # Removed problematic line causing AttributeError
            self.current_timer = None # Still clear the handle reference so we don't try to cancel it later
        
        # Update with the new notification
        self.update(f"[{style}]{message}[/]")
        self.current_priority = priority
        
        # Make widget visible
        self.visible = True
        
        # Auto-hide after a delay
        if self.auto_hide:
            self.current_timer = self.set_timer(self.auto_hide_time, self.clear_notification)
    
    def clear_notification(self):
        """Clear the current notification."""
        self.current_timer = None
        self.visible = False
        self.update("")
        self.current_priority = 0
        
        # If there are queued notifications, show the next one
        if self.notification_queue:
            # Sort by priority (highest first)
            self.notification_queue.sort(key=lambda x: x["priority"], reverse=True)
            next_notification = self.notification_queue.pop(0)
            self.show_notification(next_notification["message"], next_notification["level"])

@dataclass
class UIUpdateState:
    """Track UI update state to prevent flicker."""
    last_metrics_update: float = 0.0
    pending_metrics_update: bool = False
    update_metrics_scheduled: bool = False
    log_batch: deque = field(default_factory=lambda: deque(maxlen=100))
    last_log_batch_update: float = 0.0

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
        self.chart_data = None  # For storing OHLCV data for charts
        self.position_history = []  # For storing position history

# --- Textual App ---
class TradingBotApp(App):
    """A Textual app for the Leverage Trading Bot."""

    CSS_PATH = "../main.css" # Load CSS from parent directory
    BINDINGS = [
        ("q", "quit", "Quit App"),
        (config.MANUAL_TRADE_KEY_UP, "manual_trade('long')", "Manual Long"),
        (config.MANUAL_TRADE_KEY_DOWN, "manual_trade('short')", "Manual Short"),
        ("t", "toggle_theme", "Toggle Theme"),
        ("h", "toggle_history", "Position History"),
        ("s", "toggle_settings", "Settings"),
        ("c", "toggle_charts", "Mini Charts"),
        ("r", "refresh_data", "Refresh Data"),
        ("f1", "show_help", "Help"),
        ("escape", "clear_notifications", "Clear Notifications"),
    ]

    # --- Reactive Variables for Metrics ---
    current_metrics = reactive(Metrics(), layout=True)

    def __init__(self):
        super().__init__()
        self.log_widget = RichLog(highlight=True, markup=True)
        self.metrics_table = DataTable(zebra_stripes=True)
        self.notification_widget = NotificationWidget(classes="notification")
        self.notification_widget.visible = False  # Hide initially
        self.connection_status_widget = ConnectionStatusWidget()
        self.position_history_widget = PositionHistoryWidget()
        self.settings_panel_widget = SettingsPanelWidget()
        self.mini_chart_widget = MiniChartWidget()
        self.theme_manager = ThemeManager(self)
        self.background_thread = None
        self.stop_event = threading.Event()
        self.command_queue = queue.Queue()  # Queue for app -> background thread commands
        self.ui_state = UIUpdateState()  # Track UI update state

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield self.connection_status_widget
        yield self.notification_widget
        with Container(id="main-container"):
            yield self.metrics_table
            yield self.log_widget
            # Child containers will be shown/hidden when toggled
            yield self.position_history_widget
            yield self.settings_panel_widget
            yield self.mini_chart_widget
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
        self.update_metrics_table()  # Initial population

        # Initialize connection status
        self.connection_status_widget.update_status("connecting")
        app_logger.info("Connecting to MEXC API...")

        # Start background thread
        self.background_thread = threading.Thread(
            target=run_trading_logic,
            args=(self.command_queue, self.post_message, self.stop_event),
            daemon=True  # Ensure thread exits when main app exits
        )
        self.background_thread.start()
        app_logger.info("Background trading logic thread started.")

        # Set timers
        self.set_interval(LOG_UPDATE_INTERVAL, self.process_log_queue)
        self.set_interval(UI_UPDATE_INTERVAL, self.check_pending_updates)

    def process_log_queue(self) -> None:
        """Process logs from the background thread but batch updates."""
        batch_update_time = 0.2  # Batch log updates
        now = time.time()
        log_entries = []

        # Collect all available log entries
        while not log_queue.empty():
            try:
                record = log_queue.get_nowait()
                log_entries.append(record)
                log_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing log queue: {e}")

        # Add to batch for processing
        if log_entries:
            self.ui_state.log_batch.extend(log_entries)

        # Process batch if enough time has passed since last update
        if (now - self.ui_state.last_log_batch_update >= batch_update_time and 
                self.ui_state.log_batch):
            self._update_log_widget()
            self.ui_state.last_log_batch_update = now

    def _update_log_widget(self) -> None:
        """Update the log widget with all batched entries."""
        if not self.ui_state.log_batch:
            return
        
        # Process all entries in batch at once
        for record in self.ui_state.log_batch:
            # Apply basic styling based on level
            if "ERROR" in record or "CRITICAL" in record:
                self.log_widget.write(Text(record, style="bold red"))
            elif "WARNING" in record:
                self.log_widget.write(Text(record, style="yellow"))
            elif "INFO" in record:
                self.log_widget.write(Text(record, style="green"))
            else:
                self.log_widget.write(record)
        
        # Clear batch after processing
        self.ui_state.log_batch.clear()

    def check_pending_updates(self) -> None:
        """Check and process any pending UI updates."""
        now = time.time()
        
        # Handle metrics table update if pending and throttled
        if (self.ui_state.pending_metrics_update and 
            now - self.ui_state.last_metrics_update >= UI_UPDATE_THROTTLE):
            self.update_metrics_table()
            self.ui_state.pending_metrics_update = False
            self.ui_state.last_metrics_update = now
            self.ui_state.update_metrics_scheduled = False

    def update_metrics_table(self) -> None:
        """
        Updates the DataTable with current metrics.
        Rate-limited to prevent UI flicker.
        """
        now = time.time()
        
        # Check if we should throttle this update
        if now - self.ui_state.last_metrics_update < UI_UPDATE_THROTTLE:
            # Mark update as pending and schedule if not already done
            self.ui_state.pending_metrics_update = True
            if not self.ui_state.update_metrics_scheduled:
                time_to_next_update = UI_UPDATE_THROTTLE - (now - self.ui_state.last_metrics_update)
                self.set_timer(time_to_next_update, self._do_metrics_update)
                self.ui_state.update_metrics_scheduled = True
            return
        
        # Perform the actual update
        self._do_metrics_update()
        self.ui_state.last_metrics_update = now

    def _do_metrics_update(self) -> None:
        """Actually perform the metrics table update."""
        metrics = self.current_metrics
        self.metrics_table.clear(columns=False)  # Keep columns, clear rows
        
        # Add rows with appropriate styling
        self.metrics_table.add_row("Symbol", metrics.symbol or "N/A", key="symbol")
        
        # Format timestamp
        timestamp_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metrics.timestamp))
        self.metrics_table.add_row("Timestamp", timestamp_formatted, key="timestamp")
        
        # Format price with color (green if up from previous, red if down)
        price_text = f"{metrics.current_price:.4f}" if metrics.current_price else "N/A"
        self.metrics_table.add_row("Current Price", Text(price_text, style="bold green" if metrics.current_price else ""), key="price")
        
        # Format RSI with color (green if bullish, red if overbought)
        if metrics.rsi is not None:
            rsi_text = f"{metrics.rsi:.2f}"
            if metrics.rsi < 30:  # Oversold
                rsi_style = "bold green"
            elif metrics.rsi > 70:  # Overbought
                rsi_style = "bold red"
            else:  # Neutral
                rsi_style = "bold yellow"
            self.metrics_table.add_row("RSI", Text(rsi_text, style=rsi_style), key="rsi")
        else:
            self.metrics_table.add_row("RSI", "N/A", key="rsi")
        
        # Format prediction with color based on signal
        if metrics.prediction:
            prediction_text = metrics.prediction
            if "LONG" in prediction_text:
                prediction_style = "bold green"
            elif "SHORT" in prediction_text:
                prediction_style = "bold red"
            else:
                prediction_style = "bold white"
            self.metrics_table.add_row("Prediction", Text(prediction_text, style=prediction_style), key="prediction")
        else:
            self.metrics_table.add_row("Prediction", "N/A", key="prediction")
        
        # Position size
        self.metrics_table.add_row("Position Size", f"{metrics.position_size}" if metrics.position_size else "N/A", key="pos_size")
        
        # Entry price
        self.metrics_table.add_row("Entry Price", f"{metrics.entry_price:.4f}" if metrics.entry_price else "N/A", key="entry")
        
        # PnL with color (green for profit, red for loss)
        if metrics.pnl_percent is not None:
            pnl_text = f"{metrics.pnl_percent:.2f}%"
            pnl_style = "bold green" if metrics.pnl_percent >= 0 else "bold red"
            self.metrics_table.add_row("PnL (%)", Text(pnl_text, style=pnl_style), key="pnl")
        else:
            self.metrics_table.add_row("PnL (%)", "N/A", key="pnl")
            
        app_logger.debug("Metrics table updated.")  # Debug level for frequent updates
        
        # Reset pending state
        self.ui_state.pending_metrics_update = False
        self.ui_state.update_metrics_scheduled = False

    # --- Message Handlers ---
    def on_update_metrics_message(self, message: UpdateMetricsMessage) -> None:
        """Handles metric updates from the background thread."""
        app_logger.debug(f"Received metrics update: {message.metrics}")
        self.current_metrics = message.metrics  # Update reactive variable
        
        # Update mini chart if it's visible
        if self.mini_chart_widget.visible and hasattr(message.metrics, 'chart_data'):
            self.mini_chart_widget.update_data(message.metrics.chart_data)
        
    def on_notification_message(self, message: NotificationMessage) -> None:
        """Handles notification messages."""
        app_logger.debug(f"Received notification: {message.message} ({message.level})")
        
        # Prioritize notifications - errors stay longer
        if message.level == "error":
            auto_hide_time = 10  # 10 seconds for errors
        elif message.level == "warning":
            auto_hide_time = 7   # 7 seconds for warnings
        else:
            auto_hide_time = 5   # 5 seconds for other messages
            
        self.notification_widget.show_notification(message.message, message.level)
        self.notification_widget.auto_hide_time = auto_hide_time
        
    def on_connection_status_message(self, message: ConnectionStatusMessage) -> None:
        """Handles connection status updates."""
        app_logger.debug(f"Received connection status update: {message.status}")
        self.connection_status_widget.update_status(message.status, message.error_message)
        
        # Also show a notification for important status changes
        if message.status == "connected":
            self.notification_widget.show_notification("Connected to MEXC API", "success")
        elif message.status == "error":
            self.notification_widget.show_notification(f"Connection error: {message.error_message}", "error")
        elif message.status == "disconnected":
            self.notification_widget.show_notification("Disconnected from MEXC API", "warning")
    
    def on_update_position_history_message(self, message: UpdatePositionHistoryMessage) -> None:
        """Handle position history updates from the background thread."""
        app_logger.debug(f"Received position history update with {len(message.history)} entries")
        self.position_history_widget.update_history(message.history)

    def on_setting_changed_message(self, message: SettingChangedMessage) -> None:
        """Handle setting changes from the settings panel."""
        app_logger.info(f"Setting changed: {message.setting_name} = {message.new_value}")
        
        # Handle theme changes
        if message.setting_name == "THEME":
            self.theme_manager.set_theme(message.new_value)
        
        # Send settings update to background thread
        self.command_queue.put({"command": "update_setting", "setting": message.setting_name, "value": message.new_value})
        
        # Notify the user
        self.notification_widget.show_notification(f"Setting updated: {message.setting_name}", "info")
        
    def on_theme_changed_message(self, message: ThemeChangedMessage) -> None:
        """Handle theme change notifications."""
        app_logger.info(f"Theme changed to: {message.theme_name}")
        self.notification_widget.show_notification(f"Theme changed to: {message.theme_name}", "info")

    # --- Watch Methods ---
    def watch_current_metrics(self, old_metrics: Metrics, new_metrics: Metrics) -> None:
        """Called when the current_metrics reactive variable changes."""
        # Instead of immediately updating, mark update as pending
        self.ui_state.pending_metrics_update = True

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
        # Provide immediate feedback in the TUI
        self.log_widget.write(f"[bold blue]User initiated manual {side.upper()} trade...[/]")

    def action_toggle_theme(self) -> None:
        """Called when the user presses the theme toggle key."""
        app_logger.info("Toggling theme...")
        self.theme_manager.cycle_theme()
        self.notification_widget.show_notification(f"Theme changed to: {self.theme_manager.current_theme}", "info")
    
    def action_toggle_history(self) -> None:
        """Called when the user presses the history toggle key."""
        app_logger.info("Toggling position history view...")
        # Hide other panels
        self.settings_panel_widget.visible = False
        self.mini_chart_widget.visible = False
        # Toggle history
        self.position_history_widget.toggle()
    
    def action_toggle_settings(self) -> None:
        """Called when the user presses the settings toggle key."""
        app_logger.info("Toggling settings panel...")
        # Hide other panels
        self.position_history_widget.visible = False
        self.mini_chart_widget.visible = False
        # Toggle settings
        self.settings_panel_widget.toggle()
    
    def action_toggle_charts(self) -> None:
        """Called when the user presses the charts toggle key."""
        app_logger.info("Toggling mini charts...")
        # Hide other panels
        self.position_history_widget.visible = False
        self.settings_panel_widget.visible = False
        # Toggle charts
        self.mini_chart_widget.toggle()
    
    def action_refresh_data(self) -> None:
        """Called when the user presses the refresh key."""
        app_logger.info("Manually refreshing data...")
        # Send a command to force refresh data
        self.command_queue.put({"command": "refresh_data"})
        self.notification_widget.show_notification("Manually refreshing market data...", "info")
    
    def action_show_help(self) -> None:
        """Called when the user presses the help key."""
        help_text = """
[bold]Trading Bot Keyboard Shortcuts[/bold]
q - Quit application
t - Toggle theme
h - Show position history
s - Show settings panel
c - Show mini charts
r - Refresh market data
ESC - Clear notifications
F1 - Show this help
"""
        app_logger.info("Showing help screen...")
        self.log_widget.clear()
        self.log_widget.write(help_text)
    
    def action_clear_notifications(self) -> None:
        """Called when the user presses the Escape key."""
        self.notification_widget.clear_notification()


# --- Background Trading Logic ---
def run_trading_logic(command_queue: queue.Queue, post_message_callback, stop_event: threading.Event):
    """
    The main loop for fetching data, calculating indicators,
    making predictions, and executing trades.
    Runs in a separate thread.
    """
    # --- Initialize Handlers --- Initialize these properly!
    app_logger.info("Background thread: Initializing handlers...")
    mexc = None
    data_handler = None
    indicator_handler = None
    trade_executor = None
    stats_handler = None
    
    # Error tracking for throttling
    last_prediction_error_time = 0
    last_prediction_error_msg = ""
    
    try:
        mexc = MEXCHandler(api_key=config.MEXC_API_KEY, secret_key=config.MEXC_SECRET_KEY, test_mode=config.ENABLE_TEST_MODE)
        data_handler = DataHandler(mexc, symbol=config.DEFAULT_SYMBOL, timeframe=config.DEFAULT_TIMEFRAME)
        indicator_handler = IndicatorHandler()
        trade_executor = TradeExecutor(mexc, symbol=config.DEFAULT_SYMBOL, leverage=config.DEFAULT_LEVERAGE)
        stats_handler = StatsHandler() # Initialize your stats handler
        app_logger.info("Background thread: Handlers initialized successfully.")
        post_message_callback(ConnectionStatusMessage("connected"))
    except Exception as e:
        app_logger.critical(f"Background thread: Failed to initialize handlers: {e}. Stopping thread.")
        post_message_callback(ConnectionStatusMessage("error", str(e)))
        return # Stop the thread if handlers fail

    last_data_fetch = 0
    last_prediction_run = 0
    last_connection_check = 0
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
                        # Send notification for successful trade
                        post_message_callback(NotificationMessage(f"Manual {command.side.upper()} trade executed", "success"))
                    else:
                        app_logger.error(f"Manual {command.side} trade failed.")
                        # Send notification for failed trade
                        post_message_callback(NotificationMessage(f"Manual {command.side.upper()} trade failed", "error"))
                        # Keep old prediction/state or set to failed?
                        # metrics.prediction = f"Manual {command.side.upper()} FAILED"
                except Exception as trade_error:
                    app_logger.error(f"Background thread: Error executing manual trade: {trade_error}")
                    # Send notification for error
                    post_message_callback(NotificationMessage(f"Error executing trade: {str(trade_error)}", "error"))
                # --- End Execute Manual Trade ---
            elif isinstance(command, dict):
                # Handle dictionary-based commands
                if command.get("command") == "refresh_data":
                    app_logger.info("Background thread: Manual data refresh requested")
                    try:
                        # Force immediate data fetch
                        fetched_ohlcv = data_handler.fetch_ohlcv()
                        if fetched_ohlcv is not None and not fetched_ohlcv.empty:
                            ohlcv = fetched_ohlcv  # Store the fetched data
                            current_price = data_handler.get_current_price(ohlcv)
                            if current_price:
                                metrics.current_price = current_price
                                metrics.chart_data = ohlcv  # Store for charts
                                app_logger.info(f"Background thread: Data fetched. Current price: {current_price}")
                                post_message_callback(NotificationMessage("Data refreshed successfully", "success"))
                            else:
                                app_logger.warning("Background thread: Could not determine current price from OHLCV.")
                                post_message_callback(NotificationMessage("Could not determine current price", "warning"))
                        else:
                            app_logger.warning("Background thread: No OHLCV data fetched.")
                            post_message_callback(NotificationMessage("No data fetched", "warning"))
                    except Exception as e:
                        app_logger.error(f"Background thread: Error refreshing data: {e}")
                        post_message_callback(NotificationMessage(f"Error refreshing data: {str(e)}", "error"))
                elif command.get("command") == "update_setting":
                    # Handle setting updates
                    setting_name = command.get("setting")
                    new_value = command.get("value")
                    app_logger.info(f"Background thread: Setting update {setting_name}={new_value}")
                    
                    # Apply setting changes
                    try:
                        if hasattr(config, setting_name):
                            setattr(config, setting_name, new_value)
                            app_logger.info(f"Background thread: Updated setting {setting_name}={new_value}")
                            
                            # Apply specific setting changes immediately if needed
                            if setting_name == "DEFAULT_SYMBOL":
                                # Update data handler for new symbol
                                data_handler = DataHandler(mexc, symbol=new_value, timeframe=config.DEFAULT_TIMEFRAME)
                                trade_executor = TradeExecutor(mexc, symbol=new_value, leverage=config.DEFAULT_LEVERAGE)
                                metrics.symbol = new_value
                            elif setting_name == "DEFAULT_TIMEFRAME":
                                # Update data handler for new timeframe
                                data_handler = DataHandler(mexc, symbol=config.DEFAULT_SYMBOL, timeframe=new_value)
                            elif setting_name == "DEFAULT_LEVERAGE":
                                # Update trade executor for new leverage
                                trade_executor = TradeExecutor(mexc, symbol=config.DEFAULT_SYMBOL, leverage=new_value)
                                
                            post_message_callback(NotificationMessage(f"Setting {setting_name} updated", "success"))
                        else:
                            app_logger.warning(f"Background thread: Unknown setting {setting_name}")
                            post_message_callback(NotificationMessage(f"Unknown setting: {setting_name}", "warning"))
                    except Exception as e:
                        app_logger.error(f"Background thread: Error updating setting {setting_name}: {e}")
                        post_message_callback(NotificationMessage(f"Error updating setting: {str(e)}", "error"))

            command_queue.task_done()
        except queue.Empty:
            pass # No command waiting
        except Exception as e:
            app_logger.error(f"Background thread: Error processing command: {e}")

        # --- Check API connection periodically ---
        if now - last_connection_check >= CONNECTION_CHECK_INTERVAL:
            try:
                # Simple check - try to get the current price directly
                connection_test = mexc.get_current_price(config.DEFAULT_SYMBOL)
                if connection_test:
                    post_message_callback(ConnectionStatusMessage("connected"))
                else:
                    app_logger.warning("Background thread: Connection test failed - null result.")
                    post_message_callback(ConnectionStatusMessage("error", "API returned null result"))
            except Exception as conn_error:
                app_logger.error(f"Background thread: Connection test failed: {conn_error}")
                post_message_callback(ConnectionStatusMessage("error", str(conn_error)))
            
            last_connection_check = now

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
                        metrics.chart_data = ohlcv  # Store for charts
                        app_logger.debug(f"Background thread: Data fetched. Current price: {current_price}")
                    else:
                         app_logger.warning("Background thread: Could not determine current price from OHLCV.")
                         # metrics.current_price = None # Or keep the old one?
                # --- End Fetch Data ---
                # Removed dummy data assignment
                last_data_fetch = now

            except Exception as e:
                app_logger.error(f"Background thread: Error fetching data: {e}")
                post_message_callback(ConnectionStatusMessage("error", f"Data fetch error: {str(e)}"))
                time.sleep(config.DATA_FETCH_INTERVAL_SECONDS / 2) # Wait a bit before retrying


        # --- Run Prediction Logic Periodically --- Ensure data is available
        if now - last_prediction_run >= config.PREDICTION_INTERVAL_SECONDS and ohlcv is not None and not ohlcv.empty and metrics.current_price is not None:
            try:
                app_logger.debug("Background thread: Running prediction logic...")
                # --- Calculate Indicators & Predict --- Integrate with IndicatorHandler
                indicators = indicator_handler.calculate_indicators(ohlcv)
                if indicators is not None:  # We'll let generate_signal handle the DataFrame type
                    prediction = indicator_handler.generate_signal(indicators)
                    # Update metrics with indicator values if available
                    if isinstance(indicators, pd.DataFrame) and not indicators.empty:
                        metrics.rsi = indicators['rsi'].iloc[-1] if 'rsi' in indicators.columns else None
                    elif isinstance(indicators, dict):
                        metrics.rsi = indicators.get('rsi')
                    
                    metrics.prediction = prediction
                    app_logger.debug(f"Background thread: Prediction: {prediction}, RSI: {metrics.rsi:.2f}" if metrics.rsi is not None else f"Prediction: {prediction}, RSI: N/A")
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
                            
                            # Add to position history when a position is closed
                            if trade_result.get('status') == 'closed' and trade_result.get('exit_price'):
                                # Format position for history
                                position_history_entry = {
                                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                                    'symbol': metrics.symbol,
                                    'side': trade_result.get('side', 'unknown'),
                                    'size': trade_result.get('size', 0),
                                    'entry_price': trade_result.get('entry_price', 0),
                                    'exit_price': trade_result.get('exit_price', 0),
                                    'pnl': trade_result.get('pnl', 0),
                                    'duration': trade_result.get('duration', 'N/A')
                                }
                                # Add to history and limit size
                                metrics.position_history.insert(0, position_history_entry)
                                if len(metrics.position_history) > 50:  # Keep last 50 positions
                                    metrics.position_history = metrics.position_history[:50]
                                
                                # Update position history widget if it exists
                                post_message_callback(UpdatePositionHistoryMessage(metrics.position_history))
                            
                            # Send notification for successful automated trade
                            post_message_callback(NotificationMessage(f"Automated {prediction} trade executed", "success"))
                        else:
                            app_logger.error(f"Automated {prediction} trade failed.")
                            # Send notification for failed automated trade
                            post_message_callback(NotificationMessage(f"Automated {prediction} trade failed", "error"))
                    except Exception as auto_trade_error:
                         app_logger.error(f"Background thread: Error executing automated trade: {auto_trade_error}")
                         # Send notification for error
                         post_message_callback(NotificationMessage(f"Error executing trade: {str(auto_trade_error)}", "error"))
                    # else:
                    #    app_logger.debug(f"Automated {prediction} signal ignored: Predicted move too small.")
                elif current_position and prediction != 'HOLD':
                    # Optional: Log if signal contradicts current position but not acting
                    current_side = current_position.get('side', 'unknown').upper()
                    if (prediction == 'LONG' and current_side != 'BUY') or \
                       (prediction == 'SHORT' and current_side != 'SELL'):
                        app_logger.debug(f"Signal {prediction} contradicts current {current_side} position. Holding.")
                # --- End Execute Automated Trade ---

                # Update UI with current metrics
                post_message_callback(UpdateMetricsMessage(metrics))
                last_prediction_run = now
            except Exception as e:
                error_msg = str(e)
                current_time = time.time()
                
                # Only log and notify about errors if different from the last one or enough time has passed
                if (error_msg != last_prediction_error_msg or 
                    current_time - last_prediction_error_time >= PREDICTION_ERROR_THROTTLE):
                    app_logger.error(f"Background thread: Error in prediction logic: {error_msg}")
                    post_message_callback(NotificationMessage(f"Prediction error: {error_msg}", "error"))
                    last_prediction_error_msg = error_msg
                    last_prediction_error_time = current_time

        # Slight delay to avoid burning CPU
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

.notification {
    background: $surface;
    height: 1;
    dock: top;
    text-align: center;
    margin: 0 2;
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
    try:
        app.run() 
    except Exception as e:
        print(f"Error starting app: {e}")
        print("Attempting to start app with fallback settings...")
        # Update config to use guaranteed working values
        config.CURRENT_THEME = "default_val"
        app = TradingBotApp()
        app.run() 