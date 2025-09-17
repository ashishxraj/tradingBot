import logging
import time
import json
from datetime import datetime
from binance import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from typing import Dict, List, Optional, Tuple
import pandas as pd

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TradingBot")

class EnhancedTradingBot:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initialize the enhanced trading bot with API credentials
        
        Args:
            api_key (str): Binance API key
            api_secret (str): Binance API secret
            testnet (bool): Whether to use testnet (default: True)
        """
        try:
            # Configure client with rate limiting
            self.client = Client(
                api_key, 
                api_secret, 
                testnet=testnet,
                requests_params={'timeout': 10}
            )
            self.rate_limit_delay = 0.1  # 100ms between requests to avoid rate limiting
            self.last_request_time = 0
            logger.info("Enhanced trading bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise

    def _rate_limit(self):
        """Enforce rate limiting between API requests"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def get_account_info(self) -> Optional[Dict]:
        """Get futures account information including balances"""
        try:
            self._rate_limit()
            account_info = self.client.futures_account()
            logger.info("Fetched account information successfully")
            return account_info
        except BinanceAPIException as e:
            logger.error(f"API error getting account info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting account info: {e}")
        return None

    def get_position_info(self, symbol: str = None) -> Optional[Dict]:
        """Get position information for all symbols or a specific symbol"""
        try:
            self._rate_limit()
            positions = self.client.futures_position_information()
            if symbol:
                positions = [p for p in positions if p['symbol'] == symbol]
            logger.info("Fetched position information successfully")
            return positions
        except BinanceAPIException as e:
            logger.error(f"API error getting position info: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting position info: {e}")
        return None

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get information about a trading symbol
        
        Args:
            symbol (str): Trading symbol (e.g., BTCUSDT)
            
        Returns:
            dict: Symbol information or None if not found
        """
        try:
            self._rate_limit()
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    return s
            return None
        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return None

    def validate_quantity(self, symbol: str, quantity: float) -> Tuple[bool, str]:
        """
        Validate order quantity against symbol's step size
        
        Args:
            symbol (str): Trading symbol
            quantity (float): Proposed quantity
            
        Returns:
            tuple: (is_valid, error_message)
        """
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return False, f"Symbol {symbol} not found"
            
        # Check LOT_SIZE filter
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                min_qty = float(filter['minQty'])
                max_qty = float(filter['maxQty'])
                
                # Check if quantity is within min/max bounds
                if quantity < min_qty:
                    return False, f"Quantity {quantity} is less than minimum {min_qty}"
                if quantity > max_qty:
                    return False, f"Quantity {quantity} is greater than maximum {max_qty}"
                
                # Check if quantity is a multiple of step size
                if round(quantity / step_size, 8) % 1 != 0:
                    return False, f"Quantity {quantity} must be a multiple of step size {step_size}"
                
                return True, ""
                
        return True, ""

    def calculate_position_size(self, symbol: str, risk_pct: float, stop_loss: float = None) -> Optional[float]:
        """
        Calculate position size based on account balance and risk percentage
        
        Args:
            symbol (str): Trading symbol
            risk_pct (float): Risk percentage of account balance (0-100)
            stop_loss (float): Stop loss price for risk calculation
            
        Returns:
            float: Recommended position size or None if calculation fails
        """
        try:
            # Get account balance
            account_info = self.get_account_info()
            if not account_info:
                return None
                
            # Find USDT balance
            usdt_balance = None
            for asset in account_info['assets']:
                if asset['asset'] == 'USDT':
                    usdt_balance = float(asset['walletBalance'])
                    break
                    
            if not usdt_balance:
                logger.error("USDT balance not found")
                return None
                
            # Calculate risk amount
            risk_amount = usdt_balance * (risk_pct / 100)
            
            # If no stop loss provided, just return the maximum quantity based on risk amount
            if not stop_loss:
                # Get current price to estimate position size
                self._rate_limit()
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                
                # Calculate position size based on risk amount
                position_size = risk_amount / current_price
                
                # Validate against symbol constraints
                is_valid, error_msg = self.validate_quantity(symbol, position_size)
                if not is_valid:
                    logger.warning(f"Calculated position size {position_size} is invalid: {error_msg}")
                    
                    # Adjust to nearest valid quantity
                    symbol_info = self.get_symbol_info(symbol)
                    for filter in symbol_info['filters']:
                        if filter['filterType'] == 'LOT_SIZE':
                            step_size = float(filter['stepSize'])
                            position_size = round(position_size / step_size) * step_size
                            position_size = max(min(position_size, float(filter['maxQty'])), float(filter['minQty']))
                            break
                
                return position_size
            
            # If stop loss provided, calculate position size based on risk amount and stop distance
            # This would require knowing the entry price and stop loss price to calculate the risk per unit
            # For simplicity, we'll just return the basic calculation
            return self.calculate_position_size(symbol, risk_pct)
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return None

    def place_market_order(self, symbol: str, side: str, quantity: float) -> Optional[Dict]:
        """
        Place a market order
        
        Args:
            symbol (str): Trading symbol (e.g., BTCUSDT)
            side (str): Order side (BUY or SELL)
            quantity (float): Order quantity
            
        Returns:
            dict: Order response from Binance
        """
        try:
            is_valid, error_msg = self.validate_quantity(symbol, quantity)
            if not is_valid:
                logger.error(f"Invalid quantity: {error_msg}")
                return None
                
            logger.info(f"Placing market order: {side} {quantity} {symbol}")
            self._rate_limit()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.FUTURE_ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logger.info(f"Market order placed successfully: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"API error placing market order: {e}")
        except BinanceOrderException as e:
            logger.error(f"Order error placing market order: {e}")
        except Exception as e:
            logger.error(f"Unexpected error placing market order: {e}")
        return None

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, 
                         time_in_force: str = Client.TIME_IN_FORCE_GTC) -> Optional[Dict]:
        """
        Place a limit order
        
        Args:
            symbol (str): Trading symbol (e.g., BTCUSDT)
            side (str): Order side (BUY or SELL)
            quantity (float): Order quantity
            price (float): Order price
            time_in_force (str): Time in force (default: GTC)
            
        Returns:
            dict: Order response from Binance
        """
        try:
            is_valid, error_msg = self.validate_quantity(symbol, quantity)
            if not is_valid:
                logger.error(f"Invalid quantity: {error_msg}")
                return None
                
            logger.info(f"Placing limit order: {side} {quantity} {symbol} @ {price}")
            self._rate_limit()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.FUTURE_ORDER_TYPE_LIMIT,
                timeInForce=time_in_force,
                quantity=quantity,
                price=price
            )
            logger.info(f"Limit order placed successfully: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"API error placing limit order: {e}")
        except BinanceOrderException as e:
            logger.error(f"Order error placing limit order: {e}")
        except Exception as e:
            logger.error(f"Unexpected error placing limit order: {e}")
        return None

    def place_stop_limit_order(self, symbol: str, side: str, quantity: float, 
                              price: float, stop_price: float) -> Optional[Dict]:
        """
        Place a stop-limit order
        
        Args:
            symbol (str): Trading symbol (e.g., BTCUSDT)
            side (str): Order side (BUY or SELL)
            quantity (float): Order quantity
            price (float): Order price
            stop_price (float): Stop price
            
        Returns:
            dict: Order response from Binance
        """
        try:
            is_valid, error_msg = self.validate_quantity(symbol, quantity)
            if not is_valid:
                logger.error(f"Invalid quantity: {error_msg}")
                return None
                
            logger.info(f"Placing stop-limit order: {side} {quantity} {symbol} @ {price} (stop: {stop_price})")
            self._rate_limit()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.FUTURE_ORDER_TYPE_STOP,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=price,
                stopPrice=stop_price
            )
            logger.info(f"Stop-limit order placed successfully: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"API error placing stop-limit order: {e}")
        except BinanceOrderException as e:
            logger.error(f"Order error placing stop-limit order: {e}")
        except Exception as e:
            logger.error(f"Unexpected error placing stop-limit order: {e}")
        return None

    def place_trailing_stop_order(self, symbol: str, side: str, quantity: float, 
                                 callback_rate: float, activation_price: float = None) -> Optional[Dict]:
        """
        Place a trailing stop order
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side (BUY or SELL)
            quantity (float): Order quantity
            callback_rate (float): Callback rate percentage (0.1-5.0)
            activation_price (float): Activation price (optional)
            
        Returns:
            dict: Order response from Binance
        """
        try:
            is_valid, error_msg = self.validate_quantity(symbol, quantity)
            if not is_valid:
                logger.error(f"Invalid quantity: {error_msg}")
                return None
                
            params = {
                'symbol': symbol,
                'side': side,
                'type': Client.FUTURE_ORDER_TYPE_TRAILING_STOP_MARKET,
                'quantity': quantity,
                'callbackRate': callback_rate
            }
            
            if activation_price:
                params['activationPrice'] = activation_price
                
            logger.info(f"Placing trailing stop order: {side} {quantity} {symbol} @ {callback_rate}%")
            self._rate_limit()
            order = self.client.futures_create_order(**params)
            logger.info(f"Trailing stop order placed successfully: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"API error placing trailing stop order: {e}")
        except BinanceOrderException as e:
            logger.error(f"Order error placing trailing stop order: {e}")
        except Exception as e:
            logger.error(f"Unexpected error placing trailing stop order: {e}")
        return None

    def place_oco_order(self, symbol: str, side: str, quantity: float, price: float, 
                       stop_price: float, stop_limit_price: float) -> Optional[Dict]:
        """
        Place an OCO (One-Cancels-Other) order
        
        Args:
            symbol (str): Trading symbol
            side (str): Order side (BUY or SELL)
            quantity (float): Order quantity
            price (float): Limit order price
            stop_price (float): Stop loss trigger price
            stop_limit_price (float): Stop loss limit price
            
        Returns:
            dict: Order response from Binance
        """
        try:
            is_valid, error_msg = self.validate_quantity(symbol, quantity)
            if not is_valid:
                logger.error(f"Invalid quantity: {error_msg}")
                return None
                
            logger.info(f"Placing OCO order: {side} {quantity} {symbol} @ {price} (stop: {stop_price})")
            self._rate_limit()
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                stopPrice=stop_price,
                stopLimitPrice=stop_limit_price,
                stopLimitTimeInForce=Client.TIME_IN_FORCE_GTC,
                type=Client.FUTURE_ORDER_TYPE_STOP_MARKET  # This is a simplified approach
            )
            # Note: Binance Futures doesn't support true OCO orders like Spot does
            # This implementation places a stop market order as a workaround
            logger.info(f"OCO-style order placed successfully: {order}")
            return order
        except BinanceAPIException as e:
            logger.error(f"API error placing OCO order: {e}")
        except BinanceOrderException as e:
            logger.error(f"Order error placing OCO order: {e}")
        except Exception as e:
            logger.error(f"Unexpected error placing OCO order: {e}")
        return None

    def cancel_order(self, symbol: str, order_id: int) -> Optional[Dict]:
        """
        Cancel an open order
        
        Args:
            symbol (str): Trading symbol
            order_id (int): Order ID to cancel
            
        Returns:
            dict: Cancellation response from Binance
        """
        try:
            logger.info(f"Cancelling order {order_id} on {symbol}")
            self._rate_limit()
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order cancelled successfully: {result}")
            return result
        except BinanceAPIException as e:
            logger.error(f"API error cancelling order: {e}")
        except Exception as e:
            logger.error(f"Unexpected error cancelling order: {e}")
        return None

    def get_order_status(self, symbol: str, order_id: int) -> Optional[Dict]:
        """
        Check the status of an order
        
        Args:
            symbol (str): Trading symbol
            order_id (int): Order ID
            
        Returns:
            dict: Order status information
        """
        try:
            logger.info(f"Checking status for order {order_id} on {symbol}")
            self._rate_limit()
            status = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order status: {status}")
            return status
        except BinanceAPIException as e:
            logger.error(f"API error getting order status: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting order status: {e}")
        return None

    def get_open_orders(self, symbol: str = None) -> Optional[List[Dict]]:
        """
        Get all open orders or for a specific symbol
        
        Args:
            symbol (str): Trading symbol (optional)
            
        Returns:
            list: Open orders
        """
        try:
            logger.info(f"Fetching open orders for {symbol if symbol else 'all symbols'}")
            self._rate_limit()
            if symbol:
                orders = self.client.futures_get_open_orders(symbol=symbol)
            else:
                orders = self.client.futures_get_open_orders()
            logger.info(f"Found {len(orders)} open orders")
            return orders
        except BinanceAPIException as e:
            logger.error(f"API error getting open orders: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting open orders: {e}")
        return None

    def get_historical_trades(self, symbol: str, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get historical trade data
        
        Args:
            symbol (str): Trading symbol
            limit (int): Number of trades to retrieve (default: 100)
            
        Returns:
            list: Historical trades
        """
        try:
            logger.info(f"Fetching historical trades for {symbol}")
            self._rate_limit()
            trades = self.client.futures_historical_trades(symbol=symbol, limit=limit)
            logger.info(f"Retrieved {len(trades)} historical trades")
            return trades
        except BinanceAPIException as e:
            logger.error(f"API error getting historical trades: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting historical trades: {e}")
        return None

    def generate_report(self, symbol: str = None, days: int = 7) -> Optional[str]:
        """
        Generate a trading report
        
        Args:
            symbol (str): Trading symbol (optional)
            days (int): Number of days to include in report
            
        Returns:
            str: Formatted report
        """
        try:
            # Get account information
            account_info = self.get_account_info()
            if not account_info:
                return "Failed to generate report: Could not fetch account info"
                
            # Get positions
            positions = self.get_position_info(symbol)
            
            # Get open orders
            orders = self.get_open_orders(symbol)
            
            # Format report
            report = []
            report.append("=" * 60)
            report.append("TRADING BOT REPORT")
            report.append("=" * 60)
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Account Balance: {account_info.get('totalWalletBalance', 'N/A')} USDT")
            report.append(f"Account Equity: {account_info.get('totalMarginBalance', 'N/A')} USDT")
            report.append("")
            
            if positions:
                report.append("POSITIONS:")
                pos_data = []
                for pos in positions:
                    if float(pos['positionAmt']) != 0:
                        pos_data.append([
                            pos['symbol'],
                            pos['positionAmt'],
                            pos['entryPrice'],
                            pos['unRealizedProfit'],
                            pos['leverage']
                        ])
                
                if pos_data:
                    from tabulate import tabulate
                    report.append(tabulate(pos_data, 
                                         headers=['Symbol', 'Amount', 'Entry Price', 'P&L', 'Leverage'],
                                         tablefmt='grid'))
                else:
                    report.append("No open positions")
            report.append("")
            
            if orders:
                report.append("OPEN ORDERS:")
                order_data = []
                for order in orders:
                    order_data.append([
                        order['symbol'],
                        order['side'],
                        order['type'],
                        order['origQty'],
                        order.get('price', 'N/A'),
                        order['status']
                    ])
                
                from tabulate import tabulate
                report.append(tabulate(order_data,
                                     headers=['Symbol', 'Side', 'Type', 'Quantity', 'Price', 'Status'],
                                     tablefmt='grid'))
            else:
                report.append("No open orders")
                
            report.append("")
            report.append("=" * 60)
            
            return "\n".join(report)
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Error generating report: {e}"