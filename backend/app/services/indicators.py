"""
Technical Analysis Indicators
Implements RSI, MACD, Bollinger Bands, EMA, and more
"""
from typing import List, Dict, Any
import numpy as np


def calculate_sma(prices: List[float], period: int) -> List[float]:
    """Calculate Simple Moving Average"""
    if len(prices) < period:
        return []
    
    sma = []
    for i in range(period - 1, len(prices)):
        avg = sum(prices[i - period + 1:i + 1]) / period
        sma.append(avg)
    
    return sma


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return []
    
    multiplier = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]  # Start with SMA
    
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    
    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> Dict[str, Any]:
    """
    Calculate Relative Strength Index
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    if len(prices) < period + 1:
        return {"value": 50, "signal": "neutral", "overbought": False, "oversold": False}
    
    # Calculate price changes
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    
    # Separate gains and losses
    gains = [max(0, c) for c in changes]
    losses = [abs(min(0, c)) for c in changes]
    
    # Calculate average gain and loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Calculate subsequent values using smoothed method
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    # Calculate RSI
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    # Determine signal
    if rsi >= 70:
        signal = "overbought"
    elif rsi <= 30:
        signal = "oversold"
    elif rsi >= 50:
        signal = "bullish"
    else:
        signal = "bearish"
    
    return {
        "value": round(rsi, 2),
        "signal": signal,
        "overbought": rsi >= 70,
        "oversold": rsi <= 30
    }


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, Any]:
    """
    Calculate MACD (Moving Average Convergence Divergence)
    MACD Line = 12-day EMA - 26-day EMA
    Signal Line = 9-day EMA of MACD Line
    Histogram = MACD Line - Signal Line
    """
    if len(prices) < slow_period + signal_period:
        return {"macd": 0, "signal": 0, "histogram": 0, "trend": "neutral"}
    
    # Calculate EMAs
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    
    # Align EMAs (ema_slow starts later)
    offset = slow_period - fast_period
    ema_fast_aligned = ema_fast[offset:]
    
    # Calculate MACD line
    macd_line = [f - s for f, s in zip(ema_fast_aligned, ema_slow)]
    
    # Calculate signal line (EMA of MACD)
    signal_line = calculate_ema(macd_line, signal_period)
    
    if not signal_line:
        return {"macd": 0, "signal": 0, "histogram": 0, "trend": "neutral"}
    
    # Get latest values
    macd_value = macd_line[-1]
    signal_value = signal_line[-1]
    histogram = macd_value - signal_value
    
    # Determine trend
    if histogram > 0 and macd_value > 0:
        trend = "strong_bullish"
    elif histogram > 0:
        trend = "bullish"
    elif histogram < 0 and macd_value < 0:
        trend = "strong_bearish"
    else:
        trend = "bearish"
    
    return {
        "macd": round(macd_value, 6),
        "signal": round(signal_value, 6),
        "histogram": round(histogram, 6),
        "trend": trend
    }


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    std_dev: float = 2.0
) -> Dict[str, Any]:
    """
    Calculate Bollinger Bands
    Middle Band = 20-day SMA
    Upper Band = Middle Band + (2 * 20-day standard deviation)
    Lower Band = Middle Band - (2 * 20-day standard deviation)
    """
    if len(prices) < period:
        return {"upper": 0, "middle": 0, "lower": 0, "bandwidth": 0, "position": "middle"}
    
    # Calculate SMA (middle band)
    recent_prices = prices[-period:]
    middle = sum(recent_prices) / period
    
    # Calculate standard deviation
    variance = sum((p - middle) ** 2 for p in recent_prices) / period
    std = variance ** 0.5
    
    # Calculate bands
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    # Calculate bandwidth
    bandwidth = ((upper - lower) / middle) * 100
    
    # Determine position of current price
    current_price = prices[-1]
    if current_price >= upper:
        position = "above_upper"
    elif current_price <= lower:
        position = "below_lower"
    elif current_price >= middle:
        position = "upper_half"
    else:
        position = "lower_half"
    
    return {
        "upper": round(upper, 6),
        "middle": round(middle, 6),
        "lower": round(lower, 6),
        "bandwidth": round(bandwidth, 2),
        "position": position,
        "current_price": current_price
    }


def calculate_indicators(klines: List[Dict]) -> Dict[str, Any]:
    """Calculate all indicators from kline data"""
    # Extract close prices
    close_prices = [k["close"] for k in klines]
    high_prices = [k["high"] for k in klines]
    low_prices = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]
    
    # Calculate indicators
    rsi = calculate_rsi(close_prices)
    macd = calculate_macd(close_prices)
    bollinger = calculate_bollinger_bands(close_prices)
    
    # Calculate EMAs
    ema_9 = calculate_ema(close_prices, 9)
    ema_21 = calculate_ema(close_prices, 21)
    ema_50 = calculate_ema(close_prices, 50) if len(close_prices) >= 50 else []
    
    # EMA crossover signal
    ema_signal = "neutral"
    if ema_9 and ema_21:
        if ema_9[-1] > ema_21[-1]:
            ema_signal = "bullish"
        else:
            ema_signal = "bearish"
    
    # Overall signal
    signals = []
    if rsi["oversold"]:
        signals.append("buy")
    elif rsi["overbought"]:
        signals.append("sell")
    
    if macd["trend"] in ["strong_bullish", "bullish"]:
        signals.append("buy")
    elif macd["trend"] in ["strong_bearish", "bearish"]:
        signals.append("sell")
    
    if bollinger["position"] == "below_lower":
        signals.append("buy")
    elif bollinger["position"] == "above_upper":
        signals.append("sell")
    
    # Determine overall recommendation
    buy_signals = signals.count("buy")
    sell_signals = signals.count("sell")
    
    if buy_signals > sell_signals and buy_signals >= 2:
        recommendation = "STRONG_BUY"
    elif buy_signals > sell_signals:
        recommendation = "BUY"
    elif sell_signals > buy_signals and sell_signals >= 2:
        recommendation = "STRONG_SELL"
    elif sell_signals > buy_signals:
        recommendation = "SELL"
    else:
        recommendation = "HOLD"
    
    return {
        "current_price": close_prices[-1],
        "rsi": rsi,
        "macd": macd,
        "bollinger_bands": bollinger,
        "ema": {
            "ema_9": round(ema_9[-1], 6) if ema_9 else None,
            "ema_21": round(ema_21[-1], 6) if ema_21 else None,
            "ema_50": round(ema_50[-1], 6) if ema_50 else None,
            "signal": ema_signal
        },
        "volume": {
            "current": volumes[-1],
            "average": sum(volumes) / len(volumes),
            "trend": "high" if volumes[-1] > sum(volumes) / len(volumes) else "low"
        },
        "recommendation": recommendation,
        "signals_summary": {
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "total_signals": len(signals)
        }
    }


