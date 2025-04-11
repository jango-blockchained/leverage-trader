"""
Mini Chart Widget for displaying price charts in the Trading Bot.
Uses simple ASCII/Unicode art for price visualization in the terminal.
"""
from textual.widget import Widget
from textual.reactive import reactive
import pandas as pd
import numpy as np
from rich.text import Text


class MiniChartWidget(Widget):
    """Simple chart widget using Unicode block characters."""
    
    DEFAULT_CSS = """
    MiniChartWidget {
        height: 10;
        width: 100%;
        border: wide $primary-darken-2;
        padding: 0;
        background: $surface-darken-1;
    }
    """
    
    # Reactive variable to track data and visibility
    data = reactive(None)
    is_visible = reactive(False)
    
    def __init__(self, name: str = None):
        super().__init__(name=name)
        self.chart_width = 80
        self.chart_height = 8
        self.title = "Price Chart"
        self.style_bullish = "bold green"
        self.style_bearish = "bold red"
        self.style_neutral = "bold white"
        
    def on_mount(self):
        """Initial setup on widget mount."""
        # Hide initially
        self.visible = False
        
    def update_data(self, ohlcv_data: pd.DataFrame, indicator=None):
        """Update the chart with new OHLCV data."""
        if ohlcv_data is not None and not ohlcv_data.empty:
            self.data = ohlcv_data
            self.refresh()
    
    def render(self):
        """Render the chart with the current data."""
        if self.data is None or self.data.empty:
            return Text("No chart data available")
        
        # Extract most recent candles that fit in our chart width
        candles = self.data.iloc[-self.chart_width:] if len(self.data) > self.chart_width else self.data
        
        # Determine min and max for scaling
        min_price = candles['low'].min()
        max_price = candles['high'].max()
        price_range = max_price - min_price
        
        # Create chart canvas
        chart = []
        header = f"{self.title} - {candles.index[-1].strftime('%Y-%m-%d %H:%M')} - "
        header += f"O: {candles['open'].iloc[-1]:.4f} H: {candles['high'].iloc[-1]:.4f} L: {candles['low'].iloc[-1]:.4f} C: {candles['close'].iloc[-1]:.4f}"
        
        # Fill chart with candles
        chart_text = Text(header + "\n")
        
        # Create price axis labels
        price_labels = []
        for i in range(self.chart_height):
            price = max_price - (i / (self.chart_height - 1)) * price_range
            price_labels.append(f"{price:.4f}")
        
        # Draw chart grid
        grid = []
        for i in range(self.chart_height):
            row = [" "] * len(candles)
            grid.append(row)
        
        # Plot candles
        for idx, (_, candle) in enumerate(candles.iterrows()):
            # Skip if out of bounds
            if idx >= len(grid[0]):
                continue
                
            # Normalize candle values to chart height
            open_y = int(((candle['open'] - min_price) / price_range) * (self.chart_height - 1))
            close_y = int(((candle['close'] - min_price) / price_range) * (self.chart_height - 1))
            high_y = int(((candle['high'] - min_price) / price_range) * (self.chart_height - 1))
            low_y = int(((candle['low'] - min_price) / price_range) * (self.chart_height - 1))
            
            # Invert Y axis (0 is top in terminal)
            open_y = self.chart_height - 1 - open_y
            close_y = self.chart_height - 1 - close_y
            high_y = self.chart_height - 1 - high_y
            low_y = self.chart_height - 1 - low_y
            
            # Ensure values are within bounds
            open_y = max(0, min(open_y, self.chart_height - 1))
            close_y = max(0, min(close_y, self.chart_height - 1))
            high_y = max(0, min(high_y, self.chart_height - 1))
            low_y = max(0, min(low_y, self.chart_height - 1))
            
            # Determine candle direction
            is_bullish = candle['close'] >= candle['open']
            
            # Draw candle body
            body_start = min(open_y, close_y)
            body_end = max(open_y, close_y)
            
            for y in range(self.chart_height):
                if y == open_y and y == close_y:
                    grid[y][idx] = "─"  # Doji
                elif y >= body_start and y <= body_end:
                    grid[y][idx] = "█"  # Body
                elif y >= high_y and y <= low_y:
                    grid[y][idx] = "│"  # Wick
        
        # Convert grid to text
        for i, row in enumerate(grid):
            line = f"{price_labels[i]} "
            for cell in row:
                line += cell
            chart_text.append(line + "\n")
            
        # Add time axis
        time_axis = "       "  # Align with price labels
        time_points = [candles.index[0].strftime('%H:%M'), candles.index[-1].strftime('%H:%M')]
        time_axis += time_points[0] + " " * (len(candles) - len(time_points[0]) - len(time_points[1])) + time_points[1]
        chart_text.append(time_axis)
        
        return chart_text
        
    def toggle(self):
        """Toggle the visibility of the chart."""
        self.visible = not self.visible 