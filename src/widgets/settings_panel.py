"""
Settings Panel Widget for the Trading Bot.
"""
from textual.widgets import Button, Input, Select, Label, Switch
from textual.containers import Container, VerticalScroll
from textual.reactive import reactive
from textual.message import Message
import src.config as config


class SettingChangedMessage(Message):
    """Message emitted when a setting is changed."""
    def __init__(self, setting_name, new_value):
        super().__init__()
        self.setting_name = setting_name
        self.new_value = new_value


class SettingsPanelWidget(Container):
    """Widget for configuring application settings."""
    
    DEFAULT_CSS = """
    SettingsPanelWidget {
        layout: vertical;
        background: $surface;
        height: 100%;
        border: thick $primary;
        padding: 1;
    }
    
    #settings-title {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-style: bold;
        color: $text;
    }
    
    #settings-container {
        height: 1fr;
        width: 100%;
    }
    
    .setting-group {
        margin: 1 0;
        border: wide $surface-lighten-2;
        padding: 1;
    }
    
    .setting-group Label {
        width: 100%;
        text-style: bold;
        padding-bottom: 1;
    }
    
    .setting-row {
        width: 100%;
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    
    .setting-label {
        width: 40%;
        content-align: left middle;
    }
    
    .setting-input {
        width: 60%;
    }
    
    .actions-container {
        width: 100%;
        height: 3;
        layout: horizontal;
        align: center middle;
    }
    
    #save-button {
        background: $success;
    }
    
    #cancel-button {
        background: $error;
    }
    """
    
    # Reactive variable to track visibility
    is_visible = reactive(False)
    
    def __init__(self, name: str = None):
        super().__init__(name=name)
        self.settings = {}
        
    def compose(self):
        """Compose the widget."""
        yield Label("[b]Settings[/b]", id="settings-title")
        
        with VerticalScroll(id="settings-container"):
            # Trading settings group
            with Container(classes="setting-group"):
                yield Label("Trading Settings")
                
                with Container(classes="setting-row"):
                    yield Label("Default Symbol:", classes="setting-label")
                    yield Input(value=config.DEFAULT_SYMBOL, id="default-symbol", classes="setting-input")
                
                with Container(classes="setting-row"):
                    yield Label("Default Timeframe:", classes="setting-label")
                    # Create options list first for clarity
                    timeframe_options = [(tf, tf) for tf in ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]]
                    yield Select(
                        timeframe_options,
                        value=config.DEFAULT_TIMEFRAME,
                        id="default-timeframe",
                        classes="setting-input"
                    )
                
                with Container(classes="setting-row"):
                    yield Label("Default Leverage:", classes="setting-label")
                    yield Input(value=str(config.DEFAULT_LEVERAGE), id="default-leverage", classes="setting-input")
                
                with Container(classes="setting-row"):
                    yield Label("Trade Amount:", classes="setting-label")
                    yield Input(value=str(config.TRADE_AMOUNT_BASE), id="trade-amount", classes="setting-input")
            
            # Risk settings group
            with Container(classes="setting-group"):
                yield Label("Risk Management")
                
                with Container(classes="setting-row"):
                    yield Label("Stop Loss %:", classes="setting-label")
                    yield Input(value=str(config.STOP_LOSS_PERCENT), id="stop-loss", classes="setting-input")
                
                with Container(classes="setting-row"):
                    yield Label("Take Profit %:", classes="setting-label")
                    yield Input(value=str(config.TAKE_PROFIT_PERCENT), id="take-profit", classes="setting-input")
                
                with Container(classes="setting-row"):
                    yield Label("Test Mode:", classes="setting-label")
                    yield Switch(value=config.ENABLE_TEST_MODE, id="test-mode", classes="setting-input")
            
            # Timing settings
            with Container(classes="setting-group"):
                yield Label("Timing Settings")
                
                with Container(classes="setting-row"):
                    yield Label("Data Fetch Interval:", classes="setting-label")
                    yield Input(value=str(config.DATA_FETCH_INTERVAL_SECONDS), id="data-fetch-interval", classes="setting-input")
                
                with Container(classes="setting-row"):
                    yield Label("Prediction Interval:", classes="setting-label")
                    yield Input(value=str(config.PREDICTION_INTERVAL_SECONDS), id="prediction-interval", classes="setting-input")
            
            # UI settings
            with Container(classes="setting-group"):
                yield Label("UI Settings")
                
                with Container(classes="setting-row"):
                    yield Label("Theme:", classes="setting-label")
                    
                    # Create a select with a guaranteed valid initial value
                    theme_select = Select(
                        [
                            ("default_val", "Default"),  # Use a unique key name that isn't in config
                            ("dark", "Dark"),
                            ("light", "Light"),
                            ("blue", "Blue"),
                            ("green", "Green")
                        ],
                        id="theme-select",
                        classes="setting-input"
                    )
                    yield theme_select
            
            # Action buttons
            with Container(classes="actions-container"):
                yield Button("Save", id="save-button")
                yield Button("Cancel", id="cancel-button")
    
    def on_mount(self):
        """Setup widget when mounted."""
        # Hide initially
        self.visible = False
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-button":
            self.save_settings()
        elif event.button.id == "cancel-button":
            self.toggle()
    
    def save_settings(self):
        """Save the current settings and emit change messages."""
        # Collect all setting values
        theme_value = self.query_one("#theme-select", Select).value
        # No need to translate, use the value directly
            
        settings = {
            "DEFAULT_SYMBOL": self.query_one("#default-symbol", Input).value,
            "DEFAULT_TIMEFRAME": self.query_one("#default-timeframe", Select).value,
            "DEFAULT_LEVERAGE": float(self.query_one("#default-leverage", Input).value),
            "TRADE_AMOUNT_BASE": float(self.query_one("#trade-amount", Input).value),
            "STOP_LOSS_PERCENT": float(self.query_one("#stop-loss", Input).value),
            "TAKE_PROFIT_PERCENT": float(self.query_one("#take-profit", Input).value),
            "ENABLE_TEST_MODE": self.query_one("#test-mode", Switch).value,
            "DATA_FETCH_INTERVAL_SECONDS": float(self.query_one("#data-fetch-interval", Input).value),
            "PREDICTION_INTERVAL_SECONDS": float(self.query_one("#prediction-interval", Input).value),
            "THEME": theme_value,
        }
        
        # Emit a message for each changed setting
        for setting_name, new_value in settings.items():
            self.post_message(SettingChangedMessage(setting_name, new_value))
        
        # Hide the panel
        self.toggle()
    
    def toggle(self):
        """Toggle the visibility of the widget."""
        self.visible = not self.visible 