"""
Theme Manager for the Trading Bot.
"""
from textual.app import App
from textual.message import Message
import src.config as config


class ThemeChangedMessage(Message):
    """Message emitted when a theme is changed."""
    def __init__(self, theme_name):
        super().__init__()
        self.theme_name = theme_name


class ThemeManager:
    """Manages application themes."""
    
    # Define available themes
    THEMES = {
        "default_val": {
            "primary": "#3498db",
            "secondary": "#2ecc71",
            "accent": "#9b59b6",
            "success": "#2ecc71",
            "warning": "#f39c12",
            "error": "#e74c3c",
            "background": "#2c3e50",
            "surface": "#34495e",
            "text": "#ecf0f1",
        },
        "dark": {
            "primary": "#bb86fc",
            "secondary": "#03dac6",
            "accent": "#cf6679",
            "success": "#4caf50",
            "warning": "#ff9800",
            "error": "#f44336",
            "background": "#121212",
            "surface": "#1e1e1e",
            "text": "#ffffff",
        },
        "light": {
            "primary": "#6200ee",
            "secondary": "#03dac6",
            "accent": "#bb86fc",
            "success": "#4caf50",
            "warning": "#ff9800",
            "error": "#f44336",
            "background": "#ffffff",
            "surface": "#f5f5f5",
            "text": "#121212",
        },
        "blue": {
            "primary": "#1976d2",
            "secondary": "#03a9f4",
            "accent": "#bbdefb",
            "success": "#00e676",
            "warning": "#ffeb3b",
            "error": "#f44336",
            "background": "#0d47a1",
            "surface": "#1565c0",
            "text": "#e3f2fd",
        },
        "green": {
            "primary": "#388e3c",
            "secondary": "#4caf50",
            "accent": "#81c784",
            "success": "#00e676",
            "warning": "#ffeb3b",
            "error": "#f44336",
            "background": "#1b5e20",
            "surface": "#2e7d32",
            "text": "#e8f5e9",
        },
    }
    
    def __init__(self, app: App):
        self.app = app
        self.current_theme = "default_val"
        
    def set_theme(self, theme_name: str):
        """Set the application theme."""
        if theme_name not in self.THEMES:
            raise ValueError(f"Unknown theme: {theme_name}")
        
        self.current_theme = theme_name
        theme = self.THEMES[theme_name]
        
        # Apply theme colors to the app
        for color_name, color_value in theme.items():
            self.app.theme_colors[color_name] = color_value
        
        # Notify the app about theme change
        self.app.post_message(ThemeChangedMessage(theme_name))
        
    def cycle_theme(self):
        """Cycle to the next available theme."""
        theme_names = list(self.THEMES.keys())
        current_idx = theme_names.index(self.current_theme)
        next_idx = (current_idx + 1) % len(theme_names)
        self.set_theme(theme_names[next_idx])
        
    def get_theme_names(self):
        """Get list of available theme names."""
        return list(self.THEMES.keys()) 