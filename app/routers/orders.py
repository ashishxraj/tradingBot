
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.bot import EnhancedTradingBot
import dotenv
import os
dotenv.load_dotenv()

router = APIRouter()

class OrderRequest(BaseModel):
    symbol: str
    side: str
    order_type: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    risk_percentage: Optional[float] = None

def get_bot():
    # This would be a proper dependency in a real implementation
    api_key = os.getenv("binance_api_key")
    api_secret = os.getenv("binance_secret_key")
    return EnhancedTradingBot(api_key, api_secret, testnet=True)

@router.post("/place")
async def place_order(order: OrderRequest, bot: EnhancedTradingBot = Depends(get_bot)):
    try:
        # Calculate quantity if risk percentage is provided
        quantity = order.quantity
        if order.risk_percentage and not quantity:
            quantity = bot.calculate_position_size(order.symbol, order.risk_percentage)
        
        if not quantity:
            raise HTTPException(status_code=400, detail="Quantity or risk percentage required")
        
        # Place the appropriate order type
        if order.order_type == "MARKET":
            result = bot.place_market_order(order.symbol, order.side, quantity)
        elif order.order_type == "LIMIT":
            if not order.price:
                raise HTTPException(status_code=400, detail="Price required for limit orders")
            result = bot.place_limit_order(order.symbol, order.side, quantity, order.price)
        elif order.order_type == "STOP_LIMIT":
            if not order.price or not order.stop_price:
                raise HTTPException(status_code=400, detail="Price and stop_price required for stop-limit orders")
            result = bot.place_stop_limit_order(order.symbol, order.side, quantity, order.price, order.stop_price)
        else:
            raise HTTPException(status_code=400, detail="Unsupported order type")
        
        if result:
            return {"status": "success", "order": result}
        else:
            raise HTTPException(status_code=500, detail="Failed to place order")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/open")
async def get_open_orders(symbol: Optional[str] = None, bot: EnhancedTradingBot = Depends(get_bot)):
    try:
        orders = bot.get_open_orders(symbol)
        return {"orders": orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))