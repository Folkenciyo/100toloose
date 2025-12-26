from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional

from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/price/{symbol}")
async def get_symbol_price(
    symbol: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get current price for a symbol"""
    binance_service = request.app.state.binance
    
    try:
        price = await binance_service.get_symbol_price(symbol.upper())
        return {"symbol": symbol.upper(), "price": price}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/klines/{symbol}")
async def get_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 100,
    request: Request = None,
    current_user: User = Depends(get_current_user)
):
    """Get candlestick/kline data for a symbol"""
    binance_service = request.app.state.binance
    
    try:
        klines = await binance_service.get_klines(symbol.upper(), interval, limit)
        return {"symbol": symbol.upper(), "interval": interval, "klines": klines}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ticker/24h/{symbol}")
async def get_24h_ticker(
    symbol: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get 24h ticker statistics for a symbol"""
    binance_service = request.app.state.binance
    
    try:
        ticker = await binance_service.get_24h_ticker(symbol.upper())
        return ticker
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/symbols")
async def get_available_symbols(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get list of available trading symbols"""
    binance_service = request.app.state.binance
    
    try:
        symbols = await binance_service.get_exchange_symbols()
        # Filter to USDT pairs only for simplicity
        usdt_symbols = [s for s in symbols if s.endswith("USDT")]
        
        # Priorizar símbolos populares al inicio
        popular_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT', 'MATICUSDT', 'AVAXUSDT']
        other_symbols = [s for s in usdt_symbols if s not in popular_symbols]
        
        # Combinar: populares primero, luego el resto
        sorted_symbols = popular_symbols + other_symbols
        
        return {"symbols": sorted_symbols[:200]}  # Aumentado a 200 para incluir más símbolos
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analysis/{symbol}")
async def get_technical_analysis(
    symbol: str,
    interval: str = "1h",
    request: Request = None,
    current_user: User = Depends(get_current_user)
):
    """Get technical analysis for a symbol"""
    binance_service = request.app.state.binance
    
    try:
        # Get klines for analysis
        klines = await binance_service.get_klines(symbol.upper(), interval, 100)
        
        # Calculate indicators
        from app.services.indicators import calculate_indicators
        analysis = calculate_indicators(klines)
        
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


