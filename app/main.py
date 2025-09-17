# app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import logging
import asyncio
from datetime import datetime

from app.routers import orders, account, ws
from app.bot import EnhancedTradingBot

# Initialize FastAPI app
app = FastAPI(title="CryptoTrader Pro", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(account.router, prefix="/api/account", tags=["account"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])

# Serve static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("app/static/index.html")

# Global bot instance (in production, use proper dependency injection)
bot_instance = None

def get_bot():
    global bot_instance
    if bot_instance is None:
        # Initialize with environment variables or config
        api_key = "your_testnet_api_key"
        api_secret = "your_testnet_api_secret"
        bot_instance = EnhancedTradingBot(api_key, api_secret, testnet=True)
    return bot_instance

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)