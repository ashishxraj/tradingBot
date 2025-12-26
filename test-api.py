from binance import Client
import os

api_key = os.getenv("binance_api_key")
api_secret = os.getenv("binance_secret_key")

client = Client(api_key, api_secret)
client.API_URL = 'https://testnet.binancefuture.com/fapi/v1'  # Futures testnet

# Test public endpoint (no secret needed)
print(client.futures_exchange_info())  # Should work

# Test private endpoint
print(client.futures_account())  # Should return account info if keys are valid