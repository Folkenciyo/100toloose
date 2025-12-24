import asyncio
from typing import Optional, List, Dict, Any
import aiohttp
import hmac
import hashlib
import time
from urllib.parse import urlencode
from app.core.config import settings


class BinanceService:
    """Service for interacting with Binance API"""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, use_testnet: bool = True):
        """
        Initialize BinanceService
        
        Args:
            api_key: User's Binance API key (if None, uses global settings)
            secret_key: User's Binance secret key (if None, uses global settings)
            use_testnet: If True, use Binance Testnet; if False, use Binance Real
        """
        self.api_key = api_key or settings.BINANCE_API_KEY
        self.secret_key = secret_key or settings.BINANCE_SECRET_KEY
        self.testnet = use_testnet
        
        # Base URLs
        if self.testnet:
            self.base_url = "https://testnet.binance.vision/api/v3"
            self.ws_url = "wss://testnet.binance.vision/ws"
        else:
            self.base_url = "https://api.binance.com/api/v3"
            self.ws_url = "wss://stream.binance.com:9443/ws"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._prices_cache: Dict[str, float] = {}
        self._exchange_info: Optional[Dict] = None
    
    async def initialize(self):
        """Initialize the service"""
        self.session = aiohttp.ClientSession()
        print(f"🔗 Binance service initialized (testnet: {self.testnet})")
    
    async def close(self):
        """Close the service"""
        if self.session:
            await self.session.close()
    
    def _sign_request(self, params: dict) -> str:
        """Sign request with HMAC SHA256"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """
        Make a request to Binance API
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Request parameters
            signed: If True, sign the request with API credentials
        """
        if not self.session:
            await self.initialize()
        
        if params is None:
            params = {}
        
        # Add timestamp and signature for signed requests
        if signed:
            if not self.api_key or not self.secret_key:
                raise Exception("API key and secret key required for signed requests")
            
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign_request(params)
        
        url = f"{self.base_url}{endpoint}"
        headers = {}
        
        if signed:
            headers['X-MBX-APIKEY'] = self.api_key
        
        async with self.session.request(method, url, params=params, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Binance API error: {response.status} - {error_text}")
            return await response.json()
    
    async def get_symbol_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        data = await self._request("GET", "/ticker/price", {"symbol": symbol})
        price = float(data["price"])
        self._prices_cache[symbol] = price
        return price
    
    async def get_all_prices(self) -> Dict[str, float]:
        """Get all symbol prices"""
        data = await self._request("GET", "/ticker/price")
        prices = {item["symbol"]: float(item["price"]) for item in data}
        self._prices_cache.update(prices)
        return prices
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get candlestick/kline data"""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        data = await self._request("GET", "/klines", params)
        
        # Format klines data
        klines = []
        for k in data:
            klines.append({
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
                "quote_volume": float(k[7]),
                "trades": k[8],
            })
        
        return klines
    
    async def get_24h_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get 24h ticker statistics"""
        data = await self._request("GET", "/ticker/24hr", {"symbol": symbol})
        return {
            "symbol": data["symbol"],
            "price_change": float(data["priceChange"]),
            "price_change_percent": float(data["priceChangePercent"]),
            "weighted_avg_price": float(data["weightedAvgPrice"]),
            "last_price": float(data["lastPrice"]),
            "open_price": float(data["openPrice"]),
            "high_price": float(data["highPrice"]),
            "low_price": float(data["lowPrice"]),
            "volume": float(data["volume"]),
            "quote_volume": float(data["quoteVolume"]),
        }
    
    async def get_exchange_symbols(self) -> List[str]:
        """Get list of available trading symbols"""
        if not self._exchange_info:
            self._exchange_info = await self._request("GET", "/exchangeInfo")
        
        symbols = [s["symbol"] for s in self._exchange_info["symbols"] if s["status"] == "TRADING"]
        return symbols
    
    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """Get order book for a symbol"""
        params = {"symbol": symbol, "limit": limit}
        data = await self._request("GET", "/depth", params)
        return {
            "bids": [[float(p), float(q)] for p, q in data["bids"]],
            "asks": [[float(p), float(q)] for p, q in data["asks"]]
        }
    
    async def place_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        order_type: str,  # "MARKET" or "LIMIT"
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        quote_order_qty: Optional[float] = None  # For MARKET orders, amount in quote currency
    ) -> Dict[str, Any]:
        """
        Place an order on Binance
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            order_type: "MARKET" or "LIMIT"
            quantity: Order quantity in base currency (required for LIMIT, optional for MARKET)
            price: Order price (required for LIMIT orders)
            quote_order_qty: Order quantity in quote currency (for MARKET orders)
        
        Returns:
            Order response from Binance
        """
        if not self.api_key or not self.secret_key:
            raise Exception("API key and secret key required to place orders")
        
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper()
        }
        
        if order_type.upper() == "MARKET":
            if quote_order_qty:
                params["quoteOrderQty"] = quote_order_qty
            elif quantity:
                params["quantity"] = quantity
            else:
                raise Exception("Either quantity or quoteOrderQty required for MARKET orders")
        else:  # LIMIT
            if not quantity or not price:
                raise Exception("Quantity and price required for LIMIT orders")
            params["quantity"] = quantity
            params["price"] = price
            params["timeInForce"] = "GTC"  # Good Till Cancel
        
        return await self._request("POST", "/order", params, signed=True)
    
    async def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an order"""
        if not self.api_key or not self.secret_key:
            raise Exception("API key and secret key required to cancel orders")
        
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        
        return await self._request("DELETE", "/order", params, signed=True)
    
    async def get_order_status(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Get order status"""
        if not self.api_key or not self.secret_key:
            raise Exception("API key and secret key required to get order status")
        
        params = {
            "symbol": symbol,
            "orderId": order_id
        }
        
        return await self._request("GET", "/order", params, signed=True)
    
    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balances"""
        if not self.api_key or not self.secret_key:
            raise Exception("API key and secret key required to get account balance")
        
        data = await self._request("GET", "/account", {}, signed=True)
        
        balances = {}
        for balance in data.get("balances", []):
            asset = balance["asset"]
            free = float(balance["free"])
            locked = float(balance["locked"])
            if free > 0 or locked > 0:
                balances[asset] = {
                    "free": free,
                    "locked": locked,
                    "total": free + locked
                }
        
        return balances
    
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.api_key or not self.secret_key:
            raise Exception("API key and secret key required to get account info")
        
        return await self._request("GET", "/account", {}, signed=True)


