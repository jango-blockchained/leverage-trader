import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any

class StatsHandler:
    """Handles calculation and tracking of performance statistics."""

    def __init__(self):
        """
        Initializes the StatsHandler.
        """
        # Initialize stats variables if needed (e.g., total PnL, win rate)
        self.total_realized_pnl = Decimal('0.0')
        self.trade_count = 0
        self.win_count = 0
        logging.info("StatsHandler initialized.")

    def calculate_pnl(self, position_info: Dict[str, Any], current_price: Decimal) -> Optional[Dict[str, Any]]:
        """
        Calculates the unrealized PnL% for a given open position.

        Args:
            position_info: Dictionary containing position details (entry_price, side, size).
            current_price: The current market price.

        Returns:
            A dictionary containing PnL details (e.g., {'pnl_percent': float}),
            or None if calculation fails.
        """
        # Removed placeholder warning log
        entry_price_val = position_info.get('entry_price')
        side = position_info.get('side') # Expect 'buy' or 'sell'
        # Size might not be needed for PnL % calculation, but useful for context
        # size_val = position_info.get('size')

        if entry_price_val is None or side not in ['buy', 'sell'] or current_price is None:
            logging.debug(f"Cannot calculate PnL: Missing data (entry: {entry_price_val}, side: {side}, current: {current_price})")
            return None

        try:
            # Ensure values are Decimals for accurate calculation
            entry_price = Decimal(str(entry_price_val))
            # current_price is already Decimal

            if entry_price == 0: # Avoid division by zero
                logging.warning("Cannot calculate PnL%: Entry price is zero.")
                return None

            pnl_percent = Decimal('0.0')
            if side == 'buy':
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
            elif side == 'sell':
                pnl_percent = ((entry_price - current_price) / entry_price) * 100
            
            logging.debug(f"Calculated PnL%: {pnl_percent:.4f} for {side} position entered at {entry_price}")
            
            return {
                'pnl_percent': float(pnl_percent) # Return as float for simplicity in UI/metrics
            }
            
        except InvalidOperation as e:
             logging.error(f"Error converting PnL values to Decimal: entry='{entry_price_val}', current='{current_price}'. Error: {e}")
             return None
        except Exception as e:
            logging.error(f"Error calculating PnL: {e}", exc_info=True)
            return None

    # TODO: Implement methods to track realized PnL, win rate etc.
    # def update_realized_stats(self, close_price: Decimal, position_info: Dict[str, Any]):
    #     entry_price = Decimal(str(position_info.get('entry_price')))
    #     size = Decimal(str(position_info.get('size')))
    #     side = position_info.get('side')
    #     pnl_value = Decimal('0.0')
    #     if side == 'buy':
    #         pnl_value = (close_price - entry_price) * size
    #     elif side == 'sell':
    #         pnl_value = (entry_price - close_price) * size
    #     
    #     self.total_realized_pnl += pnl_value
    #     self.trade_count += 1
    #     if pnl_value > 0:
    #          self.win_count += 1
    #     logging.info(f"Trade closed. Realized PnL: {pnl_value:.4f}, Total PnL: {self.total_realized_pnl:.4f}, Win Rate: {self.get_win_rate():.2f}%")

    # def get_win_rate(self) -> float:
    #      return (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0.0

    # def get_overall_stats(self) -> Dict[str, Any]:
    #     return {
    #         'total_realized_pnl': float(self.total_realized_pnl),
    #         'trade_count': self.trade_count,
    #         'win_count': self.win_count,
    #         'win_rate': self.get_win_rate()
    #     } 