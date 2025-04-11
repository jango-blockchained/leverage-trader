from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, Static
from textual.reactive import reactive
from textual.screen import ModalScreen

class ConfirmationResponse(Message):
    """Message sent when the user responds to the confirmation dialog."""
    
    def __init__(self, confirmed: bool, dialog_id: str, context: dict = None) -> None:
        """
        Initialize the confirmation response message.
        
        Args:
            confirmed: Whether the user confirmed the action
            dialog_id: Unique identifier for the dialog that was responded to
            context: Optional context data associated with the confirmation
        """
        super().__init__()
        self.confirmed = confirmed
        self.dialog_id = dialog_id
        self.context = context or {}

class ConfirmationDialog(ModalScreen):
    """A modal confirmation dialog."""
    
    DEFAULT_CSS = """
    ConfirmationDialog {
        align: center middle;
    }
    
    #dialog-container {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    
    #title {
        text-align: center;
        color: $accent;
        text-style: bold;
        width: 100%;
        background: $surface-lighten-1;
        margin-bottom: 1;
    }
    
    #message {
        text-align: center;
        margin-bottom: 1;
        width: 100%;
    }
    
    #button-container {
        width: 100%;
        align-horizontal: center;
        height: 3;
    }
    
    Button {
        width: 15;
        margin-right: 2;
    }
    
    #confirm {
        background: $success;
    }
    
    #cancel {
        background: $error;
    }
    """
    
    title = reactive("Confirmation")
    message = reactive("Are you sure?")
    context = reactive({})
    dialog_id = reactive("default")
    
    def __init__(self, 
                title: str = "Confirmation", 
                message: str = "Are you sure?", 
                dialog_id: str = "default",
                context: dict = None):
        """
        Initialize a confirmation dialog.
        
        Args:
            title: The dialog title
            message: The dialog message
            dialog_id: A unique identifier for this dialog instance
            context: Optional context data to include with the response
        """
        super().__init__()
        self.title = title
        self.message = message
        self.dialog_id = dialog_id
        self.context = context or {}
    
    def compose(self) -> ComposeResult:
        """Create the dialog components."""
        with Vertical(id="dialog-container"):
            yield Label(self.title, id="title")
            yield Label(self.message, id="message")
            with Horizontal(id="button-container"):
                yield Button("Confirm", id="confirm", variant="success")
                yield Button("Cancel", id="cancel", variant="error")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "confirm":
            self.dismiss(ConfirmationResponse(True, self.dialog_id, self.context))
        elif button_id == "cancel":
            self.dismiss(ConfirmationResponse(False, self.dialog_id, self.context))
    
    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "escape":
            self.dismiss(ConfirmationResponse(False, self.dialog_id, self.context)) 