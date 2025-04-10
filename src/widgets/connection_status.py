from rich.console import RenderableType
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

class ConnectionStatusWidget(Widget):
    """A widget that displays the current connection status to the MEXC API."""
    
    # Possible states: "connected", "connecting", "disconnected", "error"
    status = reactive("disconnected")
    last_error = reactive("")
    
    DEFAULT_CSS = """
    ConnectionStatusWidget {
        width: 100%;
        height: 1;
        padding: 0 1;
        text-align: center;
    }
    
    ConnectionStatusWidget.-connected {
        background: $success-darken-2;
        color: $text;
    }
    
    ConnectionStatusWidget.-connecting {
        background: $warning-darken-2;
        color: $text;
    }
    
    ConnectionStatusWidget.-disconnected {
        background: $error-darken-2;
        color: $text;
    }
    
    ConnectionStatusWidget.-error {
        background: $error;
        color: $text;
    }
    """
    
    def __init__(self, name: str | None = None):
        super().__init__(name=name)
        self._set_status_class()
    
    def render(self) -> RenderableType:
        """Render the widget based on current status."""
        status_text = f"MEXC API: {self.status.upper()}"
        
        if self.status == "error" and self.last_error:
            status_text += f" - {self.last_error}"
            
        return Text(status_text, justify="center")
    
    def watch_status(self, new_status: str) -> None:
        """React to status changes by updating CSS classes."""
        self._set_status_class()
    
    def _set_status_class(self) -> None:
        """Set the appropriate CSS class based on current status."""
        self.remove_class("-connected", "-connecting", "-disconnected", "-error")
        self.add_class(f"-{self.status}")
    
    def update_status(self, status: str, error_message: str = "") -> None:
        """Update the connection status and error message."""
        self.last_error = error_message
        self.status = status 