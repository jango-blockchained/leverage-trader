"""
Position History Widget for the Trading Bot.
"""
from textual.widgets import DataTable
from textual.containers import Container
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text


class PositionHistoryWidget(Container):
    """Widget to display position history."""
    
    DEFAULT_CSS = """
    PositionHistoryWidget {
        layout: vertical;
        background: $surface;
        height: 100%;
        border: thick $primary;
        padding: 1;
    }
    
    #history-title {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-style: bold;
        color: $text;
    }
    
    #position-history-table {
        width: 100%;
        height: 1fr;
    }
    
    .profit {
        color: #00ff00;
    }
    
    .loss {
        color: #ff0000;
    }
    """
    
    # Reactive variable to track visibility
    is_visible = reactive(False)
    
    def __init__(self, name: str = None):
        super().__init__(name=name)
        self.history_table = DataTable(id="position-history-table", zebra_stripes=True)
        
    def compose(self):
        """Compose the widget."""
        yield Static("[b]Position History[/b]", id="history-title")
        yield self.history_table
    
    def on_mount(self):
        """Set up the table columns when mounted."""
        self.history_table.add_column("Date/Time")
        self.history_table.add_column("Symbol")
        self.history_table.add_column("Side")
        self.history_table.add_column("Size")
        self.history_table.add_column("Entry")
        self.history_table.add_column("Exit")
        self.history_table.add_column("PnL")
        self.history_table.add_column("Duration")
        
        # Hide initially
        self.visible = False
        
    def update_history(self, positions):
        """Update the position history with new data."""
        self.history_table.clear(columns=False)
        
        for position in positions:
            # Format PnL with color
            pnl = position.get('pnl', 0)
            pnl_text = Text(f"{pnl:.2f}%", style="green" if pnl >= 0 else "red")
            
            # Add row with all position data
            self.history_table.add_row(
                position.get('timestamp', 'N/A'),
                position.get('symbol', 'N/A'),
                position.get('side', 'N/A'),
                f"{position.get('size', 0)}",
                f"{position.get('entry_price', 0):.4f}",
                f"{position.get('exit_price', 0):.4f}",
                pnl_text,
                position.get('duration', 'N/A')
            )
    
    def toggle(self):
        """Toggle the visibility of the widget."""
        self.visible = not self.visible
        

from textual.widgets import Static 