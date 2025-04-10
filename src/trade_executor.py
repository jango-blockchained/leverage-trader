import logging
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Optional, Dict, Any

# Assuming MexcHandler is defined in mexc_handler.py
from src.mexc_handler import MexcHandler
import src.config as config # Import config for default percentages

class TradeExecutor:
    """Handles placing and managing trades on the exchange."""

    def __init__(self, mexc_handler: MexcHandler, symbol: str, leverage: int):
        """
        Initializes the TradeExecutor.

        Args:
            mexc_handler: An instance of MexcHandler.
            symbol: The trading symbol.
            leverage: The leverage to use for trades.
        """
        self.mexc_handler = mexc_handler
        self.symbol = symbol
        self.leverage = leverage
        self.market_details = None
        self._load_market_details()

        if self.market_details:
            logging.info(f"TradeExecutor initialized for {symbol} with {leverage}x leverage.")
            # Attempt to set leverage (should ideally be confirmed)
            if not self.mexc_handler.set_leverage(self.symbol, self.leverage):
                 logging.warning(f"TradeExecutor: Failed to set leverage {leverage}x for {symbol} during init. Already set?")
        else:
            # Critical failure if market details can't be loaded
            raise ValueError(f"TradeExecutor: Could not fetch critical market details for {symbol}. Cannot proceed.")

    def _load_market_details(self):
        """Loads and stores market details required for trading."""
        self.market_details = self.mexc_handler.get_market(self.symbol)
        if not self.market_details:
            logging.error(f"TradeExecutor: Could not fetch market details for {self.symbol}. Trading might fail.")
        else:
            logging.debug(f"Market details loaded for {self.symbol}")
            # Pre-calculate or store needed precision/limits
            self.price_precision = self.market_details.get('precision', {}).get('price')
            self.amount_precision = self.market_details.get('precision', {}).get('amount')
            self.min_amount = self.market_details.get('limits', {}).get('amount', {}).get('min')
            
            # Handle potential None values for precision/limits
            if self.price_precision is None:
                 logging.warning(f"Price precision not found for {self.symbol}, defaulting to 2.")
                 self.price_precision = 2 # Default
            if self.amount_precision is None:
                 logging.warning(f"Amount precision not found for {self.symbol}, defaulting to 4.")
                 self.amount_precision = 4 # Default
            if self.min_amount is None:
                 logging.warning(f"Min amount not found for {self.symbol}, defaulting to 0.0001.")
                 self.min_amount = 0.0001 # Default
                 
            try:
                 self.min_amount_decimal = Decimal(str(self.min_amount))
            except Exception:
                 logging.error(f"Could not convert min_amount {self.min_amount} to Decimal. Defaulting to 0.0001")
                 self.min_amount_decimal = Decimal('0.0001')
                 

    def _calculate_trade_params(
        self, 
        amount_base: Decimal, 
        side: str, # 'buy' or 'sell'
        current_price: Optional[Decimal], # Needed for SL/TP calc
        stop_loss_pct: float, 
        take_profit_pct: float
    ) -> Dict[str, Any]:
        """Helper to calculate precise amount, SL price, TP price."""
        params = {
            'final_amount': None,
            'sl_price': None,
            'tp_price': None,
            'error': None
        }

        if not self.market_details:
            params['error'] = "Market details not loaded."
            return params

        # 1. Calculate final amount based on precision and minimums
        try:
            amount_str = str(amount_base.quantize(Decimal('1e-'+str(self.amount_precision)), rounding=ROUND_DOWN))
            final_amount = Decimal(amount_str)

            if final_amount < self.min_amount_decimal:
                params['error'] = f"Trade amount {final_amount} is below minimum {self.min_amount_decimal}."
                logging.error(params['error'])
                return params
            params['final_amount'] = float(final_amount) # Convert to float for ccxt
        except Exception as e:
             params['error'] = f"Error processing trade amount: {e}"
             logging.error(params['error'])
             return params

        # 2. Calculate SL/TP Prices if percentages are provided and current_price exists
        if current_price is None and (stop_loss_pct > 0 or take_profit_pct > 0):
             params['error'] = "Cannot calculate SL/TP without current_price."
             logging.warning(params['error']) # Warning, as order might proceed without SL/TP
             return params
        elif current_price is None:
             return params # No SL/TP needed, amount is calculated
        
        sl_price_decimal = None
        tp_price_decimal = None
        sl_pct_decimal = Decimal(str(stop_loss_pct)) / Decimal('100')
        tp_pct_decimal = Decimal(str(take_profit_pct)) / Decimal('100')

        try:
            if side == 'buy':
                if sl_pct_decimal > 0:
                    sl_price_decimal = current_price * (Decimal('1') - sl_pct_decimal)
                if tp_pct_decimal > 0:
                    tp_price_decimal = current_price * (Decimal('1') + tp_pct_decimal)
            elif side == 'sell':
                if sl_pct_decimal > 0:
                    sl_price_decimal = current_price * (Decimal('1') + sl_pct_decimal)
                if tp_pct_decimal > 0:
                    tp_price_decimal = current_price * (Decimal('1') - tp_pct_decimal)
            
            # Apply price precision
            if sl_price_decimal is not None:
                sl_rounding = ROUND_DOWN if side == 'buy' else ROUND_UP
                sl_price_str = str(sl_price_decimal.quantize(Decimal('1e-'+str(self.price_precision)), rounding=sl_rounding))
                params['sl_price'] = float(sl_price_str) # Convert to float for ccxt

            if tp_price_decimal is not None:
                tp_rounding = ROUND_UP if side == 'buy' else ROUND_DOWN
                tp_price_str = str(tp_price_decimal.quantize(Decimal('1e-'+str(self.price_precision)), rounding=tp_rounding))
                params['tp_price'] = float(tp_price_str) # Convert to float for ccxt

        except Exception as e:
            params['error'] = f"Error calculating SL/TP prices: {e}"
            logging.error(params['error'])
            # Decide if we should proceed without SL/TP or fail
            params['sl_price'] = None 
            params['tp_price'] = None
            # return params # Uncomment to fail if SL/TP calculation fails

        return params

    def execute_trade(self, side: str, amount: float, stop_loss_pct: float, take_profit_pct: float) -> Optional[Dict[str, Any]]:
        """
        Executes an automated market trade with optional SL/TP.
        Assumes `side` is 'buy' or 'sell'.
        """
        if side not in ['buy', 'sell']:
             logging.error(f"Invalid side '{side}' for execute_trade.")
             return None
             
        logging.info(f"Attempting automated {side} trade for {amount} {self.symbol}. SL%={stop_loss_pct}, TP%={take_profit_pct}")

        # 1. Get current price (needed for SL/TP calc)
        # Ideally, pass this in from the main loop to avoid extra API call
        current_price_float = self.mexc_handler.get_current_price(self.symbol)
        if current_price_float is None:
             logging.error("Could not get current price. Cannot execute trade with SL/TP calculation.")
             return None
        current_price = Decimal(str(current_price_float))

        # 2. Calculate parameters
        trade_params = self._calculate_trade_params(
             Decimal(str(amount)), 
             side, 
             current_price, 
             stop_loss_pct, 
             take_profit_pct
        )

        if trade_params['error'] or trade_params['final_amount'] is None:
            logging.error(f"Trade execution failed due to parameter error: {trade_params['error']}")
            return None
            
        final_amount = trade_params['final_amount']
        sl_price = trade_params['sl_price']
        tp_price = trade_params['tp_price']

        # 3. Place order using MEXCHandler
        order_result = self.mexc_handler.place_market_order_with_sl_tp(
            symbol=self.symbol,
            side=side,
            amount=final_amount,
            sl_price=sl_price,
            tp_price=tp_price
        )

        # 4. Parse the result and return position info dict
        if order_result and order_result.get('id'):
            logging.info(f"Automated {side} order placed successfully: ID {order_result.get('id')}")
            # TODO: Fetch order details for accurate fill price and size?
            # For now, estimate entry price and use requested amount
            entry_price_estimate = order_result.get('average') or order_result.get('price') or current_price_float
            position_info = {
                'symbol': self.symbol,
                'side': side,
                'size': final_amount, # Use calculated final amount
                'entry_price': Decimal(str(entry_price_estimate)),
                'order_id': order_result.get('id'),
                'sl_price': sl_price, # Store the calculated SL/TP used
                'tp_price': tp_price,
                'timestamp': order_result.get('timestamp') # Get timestamp if available
            }
            logging.debug(f"Returning position info: {position_info}")
            return position_info
        else:
            logging.error(f"Automated {side} order placement failed. Result: {order_result}")
            return None

    def execute_manual_trade(self, side: str, amount: float) -> Optional[Dict[str, Any]]:
        """
        Executes a manual market trade (typically without SL/TP).
        Handles `side` as 'long' or 'short'.
        """
        trade_side = 'buy' if side == 'long' else 'sell'
        logging.info(f"Attempting manual {side} ({trade_side}) trade for {amount} {self.symbol}.")

        # Calculate only amount parameter (no SL/TP)
        trade_params = self._calculate_trade_params(
            Decimal(str(amount)), 
            trade_side, 
            None, # No current price needed if no SL/TP
            0, # No SL
            0  # No TP
        )

        if trade_params['error'] or trade_params['final_amount'] is None:
            logging.error(f"Manual trade execution failed due to parameter error: {trade_params['error']}")
            return None
            
        final_amount = trade_params['final_amount']

        # Place order using MEXCHandler (without SL/TP params)
        # Assuming place_market_order_with_sl_tp handles None for sl/tp gracefully
        order_result = self.mexc_handler.place_market_order_with_sl_tp(
            symbol=self.symbol,
            side=trade_side,
            amount=final_amount,
            sl_price=None,
            tp_price=None
        )

        # Parse result (similar to execute_trade)
        if order_result and order_result.get('id'):
            logging.info(f"Manual {side} order placed successfully: ID {order_result.get('id')}")
            # Estimate entry price
            current_price_float = self.mexc_handler.get_current_price(self.symbol)
            entry_price_estimate = order_result.get('average') or order_result.get('price') or current_price_float or 0
            position_info = {
                'symbol': self.symbol,
                'side': trade_side,
                'size': final_amount,
                'entry_price': Decimal(str(entry_price_estimate)),
                'order_id': order_result.get('id'),
                'sl_price': None, # No SL/TP for manual trade
                'tp_price': None,
                'timestamp': order_result.get('timestamp')
            }
            logging.debug(f"Returning position info for manual trade: {position_info}")
            return position_info
        else:
            logging.error(f"Manual {side} order placement failed. Result: {order_result}")
            return None

    def check_sl_tp(self, position_info: Dict[str, Any], current_price: Decimal) -> Optional[str]:
        """
        Checks if the current price has hit the SL or TP level for a given position.
        Uses pre-calculated sl_price and tp_price from position_info.
        """
        if not position_info or not current_price:
             return None # Cannot check without position or price
             
        sl_price_stored = position_info.get('sl_price')
        tp_price_stored = position_info.get('tp_price')
        side = position_info.get('side') # 'buy' or 'sell'
        
        # Convert stored SL/TP to Decimal for comparison, handle None
        try:
            sl_price_decimal = Decimal(str(sl_price_stored)) if sl_price_stored is not None else None
            tp_price_decimal = Decimal(str(tp_price_stored)) if tp_price_stored is not None else None
        except Exception as e:
            logging.error(f"Error converting stored SL/TP to Decimal: {e}")
            return None # Cannot compare if conversion fails

        if not sl_price_decimal and not tp_price_decimal:
            # logging.debug("No SL/TP set for position, skipping check.")
            return None # No SL/TP set for this position
        
        logging.debug(f"Checking SL/TP for {side} position: Current={current_price}, SL={sl_price_decimal}, TP={tp_price_decimal}")
        
        try:
            if side == 'buy':
                if sl_price_decimal and current_price <= sl_price_decimal:
                    logging.info(f"Stop Loss triggered for BUY position at {current_price} (SL: {sl_price_decimal})")
                    return 'SL'
                if tp_price_decimal and current_price >= tp_price_decimal:
                    logging.info(f"Take Profit triggered for BUY position at {current_price} (TP: {tp_price_decimal})")
                    return 'TP'
            elif side == 'sell':
                if sl_price_decimal and current_price >= sl_price_decimal:
                    logging.info(f"Stop Loss triggered for SELL position at {current_price} (SL: {sl_price_decimal})")
                    return 'SL'
                if tp_price_decimal and current_price <= tp_price_decimal:
                    logging.info(f"Take Profit triggered for SELL position at {current_price} (TP: {tp_price_decimal})")
                    return 'TP'
        except Exception as e:
            logging.error(f"Error during SL/TP comparison: {e}")
            return None
            
        return None # No trigger

    def close_position(self, position_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Closes the given position with a market order.
        """
        if not position_info:
            logging.error("Cannot close position: position_info is missing.")
            return None
            
        size = position_info.get('size')
        side = position_info.get('side') # Original side ('buy' or 'sell')
        symbol = position_info.get('symbol', self.symbol) # Use position symbol or default

        if not size or not side:
            logging.error(f"Cannot close position for {symbol}: Missing size or side information.")
            return None
        
        try:
             # Ensure size is a float for the order
             amount_to_close = abs(float(size))
        except ValueError as e:
             logging.error(f"Cannot close position: Invalid size format '{size}': {e}")
             return None
             
        close_side = 'sell' if side == 'buy' else 'buy' # Opposite side to close
        logging.info(f"Attempting to close {side} position for {symbol} by placing {close_side} order for {amount_to_close}.")

        # Place closing order (market order, no SL/TP)
        try:
            order_result = self.mexc_handler.place_market_order_with_sl_tp(
                symbol=symbol,
                side=close_side,
                amount=amount_to_close,
                sl_price=None,
                tp_price=None
            )
            if order_result and order_result.get('id'):
                 logging.info(f"Position close order placed successfully: ID {order_result.get('id')}")
                 # Return the closing order details
                 return order_result
            else:
                 logging.error(f"Position close order placement failed. Result: {order_result}")
                 return None
        except Exception as e:
            logging.error(f"Exception during position close order placement: {e}", exc_info=True)
            return None 