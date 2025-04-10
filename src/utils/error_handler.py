import logging
import functools
import traceback
from typing import Callable, Any, Optional, TypeVar, cast

# Configure logging
logger = logging.getLogger(__name__)

# Type variables for better type hints
T = TypeVar('T')
R = TypeVar('R')

class APIError(Exception):
    """Base exception for API-related errors."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)
        
    def __str__(self) -> str:
        if self.original_error:
            return f"{self.message} - {str(self.original_error)}"
        return self.message


class ConnectionError(APIError):
    """Exception raised for connection-related issues."""
    pass


class AuthenticationError(APIError):
    """Exception raised for authentication failures."""
    pass


class RateLimitError(APIError):
    """Exception raised when hitting rate limits."""
    pass


class DataError(APIError):
    """Exception raised for data parsing or validity issues."""
    pass


def handle_api_errors(func: Callable[..., R]) -> Callable[..., Optional[R]]:
    """
    Decorator to handle API call errors in a standardized way.
    
    Args:
        func: The function to wrap with error handling.
        
    Returns:
        The wrapped function that handles errors gracefully.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Optional[R]:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the full stack trace for debugging
            logger.error(f"API Error in {func.__name__}: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # Map common exception types to our custom exceptions
            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                raise ConnectionError(f"Connection error in {func.__name__}", e)
            elif "auth" in str(e).lower() or "api key" in str(e).lower():
                raise AuthenticationError(f"Authentication error in {func.__name__}", e)
            elif "rate" in str(e).lower() or "limit" in str(e).lower():
                raise RateLimitError(f"Rate limit error in {func.__name__}", e)
            elif "data" in str(e).lower() or "parse" in str(e).lower():
                raise DataError(f"Data error in {func.__name__}", e)
            else:
                # For unknown errors, re-raise as APIError
                raise APIError(f"Unexpected error in {func.__name__}", e)
    
    return cast(Callable[..., Optional[R]], wrapper)


def safe_api_call(func: Callable[..., R], *args: Any, **kwargs: Any) -> Optional[R]:
    """
    Execute an API call with error handling and return None on failure.
    
    Args:
        func: The function to call.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.
        
    Returns:
        The result of the function call, or None if an error occurred.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"API call failed: {func.__name__} - {str(e)}")
        logger.debug(traceback.format_exc())
        return None 