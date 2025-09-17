import logging
import argparse
from binance import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

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

class BasicBot:
    def __init__(self, api_key, api_secret, testnet=True):
        """
        Initialize the trading bot with API credentials
        
        Args:
            api_key (str): Binance API key
            api_secret (str): Binance API secret
            testnet (bool): Whether to use testnet (default: True)
        """
        try:
            self.client = Client(api_key, api_secret, testnet=testnet)
            logger.info("Trading bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise

    def get_symbol_info(self, symbol):
        """
        Get information about a trading symbol
        
        Args:
            symbol (str): Trading symbol (e.g., BTCUSDT)
            
        Returns:
            dict: Symbol information or None if not found
        """
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    return s
            return None
        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return None

    def validate_quantity(self, symbol, quantity):
        """
        Validate order quantity against symbol's step size
        
        Args:
            symbol (str): Trading symbol
            quantity (float): Proposed quantity
            
        Returns:
            bool: True if quantity is valid, False otherwise
        """
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            return False
            
        # Check LOT_SIZE filter
        for filter in symbol_info['filters']:
            if filter['filterType'] == 'LOT_SIZE':
                step_size = float(filter['stepSize'])
                # Check if quantity is a multiple of step size
                if quantity % step_size != 0:
                    logger.error(f"Quantity {quantity} must be a multiple of step size {step_size}")
                    return False
                return True
                
        return True

    def place_market_order(self, symbol, side, quantity):
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
            if not self.validate_quantity(symbol, quantity):
                return None
                
            logger.info(f"Placing market order: {side} {quantity} {symbol}")
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

    def place_limit_order(self, symbol, side, quantity, price):
        """
        Place a limit order
        
        Args:
            symbol (str): Trading symbol (e.g., BTCUSDT)
            side (str): Order side (BUY or SELL)
            quantity (float): Order quantity
            price (float): Order price
            
        Returns:
            dict: Order response from Binance
        """ 
        try:
            if not self.validate_quantity(symbol, quantity):
                return None
                
            logger.info(f"Placing limit order: {side} {quantity} {symbol} @ {price}")
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.FUTURE_ORDER_TYPE_LIMIT,
                timeInForce=Client.TIME_IN_FORCE_GTC,
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

    def place_stop_limit_order(self, symbol, side, quantity, price, stop_price):
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
            if not self.validate_quantity(symbol, quantity):
                return None
                
            logger.info(f"Placing stop-limit order: {side} {quantity} {symbol} @ {price} (stop: {stop_price})")
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

    def get_order_status(self, symbol, order_id):
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
            status = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order status: {status}")
            return status
        except BinanceAPIException as e:
            logger.error(f"API error getting order status: {e}")
        except Exception as e:
            logger.error(f"Unexpected error getting order status: {e}")
        return None

def main():
    """Main function to handle command-line interface"""
    parser = argparse.ArgumentParser(description="Binance Futures Trading Bot")
    
    # Required arguments
    parser.add_argument("--api_key", required=True, help="Binance API Key")
    parser.add_argument("--api_secret", required=True, help="Binance API Secret")
    
    # Order arguments
    parser.add_argument("--symbol", required=True, help="Trading symbol (e.g., BTCUSDT)")
    parser.add_argument("--side", required=True, choices=["BUY", "SELL"], help="Order side")
    parser.add_argument("--type", required=True, choices=["MARKET", "LIMIT", "STOP_LIMIT"], 
                        help="Order type")
    parser.add_argument("--quantity", required=True, type=float, help="Order quantity")
    
    # Optional arguments
    parser.add_argument("--price", type=float, help="Order price (required for LIMIT and STOP_LIMIT)")
    parser.add_argument("--stop_price", type=float, help="Stop price (required for STOP_LIMIT)")
    parser.add_argument("--order_id", type=int, help="Order ID to check status")
    
    args = parser.parse_args()
    
    # Validate arguments based on order type
    if args.type in ["LIMIT", "STOP_LIMIT"] and not args.price:
        parser.error(f"{args.type} order requires --price")
    
    if args.type == "STOP_LIMIT" and not args.stop_price:
        parser.error("STOP_LIMIT order requires --stop_price")
    
    # Initialize the bot
    try:
        bot = BasicBot(args.api_key, args.api_secret)
    except Exception as e:
        print(f"Failed to initialize trading bot: {e}")
        return
    
    # Check order status if order_id is provided
    if args.order_id:
        status = bot.get_order_status(args.symbol, args.order_id)
        if status:
            print(f"Order Status: {status['status']}")
            print(f"Executed Quantity: {status['executedQty']}")
            if 'avgPrice' in status and status['avgPrice'] != '0.0':
                print(f"Average Price: {status['avgPrice']}")
        return
    
    # Place new order
    if args.type == "MARKET":
        result = bot.place_market_order(args.symbol, args.side, args.quantity)
    elif args.type == "LIMIT":
        result = bot.place_limit_order(args.symbol, args.side, args.quantity, args.price)
    elif args.type == "STOP_LIMIT":
        result = bot.place_stop_limit_order(args.symbol, args.side, args.quantity, args.price, args.stop_price)
    
    if result:
        print(f"Order placed successfully!")
        print(f"Order ID: {result['orderId']}")
        print(f"Symbol: {result['symbol']}")
        print(f"Side: {result['side']}")
        print(f"Type: {result['type']}")
        print(f"Quantity: {result['origQty']}")
        if 'price' in result:
            print(f"Price: {result['price']}")
        if 'stopPrice' in result:
            print(f"Stop Price: {result['stopPrice']}")
    else:
        print("Failed to place order. Check logs for details.")

if __name__ == "__main__":
    main()