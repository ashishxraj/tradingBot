# app/routers/account.py
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from app.bot import EnhancedTradingBot
import dotenv
import os

dotenv.load_dotenv()

router = APIRouter()

def get_bot():
    api_key = os.getenv("binance_api_key")
    api_secret = os.getenv("binance_secret_key")
    return EnhancedTradingBot(api_key, api_secret, testnet=True)

@router.get("/balance")
async def get_balance(bot: EnhancedTradingBot = Depends(get_bot)):
    try:
        info = bot.get_account_info()
        return {"balance": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_positions(symbol: Optional[str] = None, bot: EnhancedTradingBot = Depends(get_bot)):
    try:
        positions = bot.get_position_info(symbol)
        return {"positions": positions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))