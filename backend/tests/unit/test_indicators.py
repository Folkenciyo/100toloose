"""Unit tests for technical analysis indicators."""
import pytest
from app.services.indicators import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_indicators,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_prices(value: float = 100.0, n: int = 50) -> list[float]:
    return [value] * n


def _rising_prices(start: float = 50.0, n: int = 50) -> list[float]:
    return [start + i for i in range(n)]


def _falling_prices(start: float = 100.0, n: int = 50) -> list[float]:
    return [start - i for i in range(n)]


def _klines_from_prices(prices: list[float]) -> list[dict]:
    return [
        {"open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": 1000.0}
        for p in prices
    ]


# ---------------------------------------------------------------------------
# calculate_sma
# ---------------------------------------------------------------------------

class TestCalculateSma:
    def test_insufficient_data_returns_empty(self):
        assert calculate_sma([1.0, 2.0], period=5) == []

    def test_exact_minimum_data(self):
        result = calculate_sma([1.0, 2.0, 3.0], period=3)
        assert len(result) == 1
        assert result[0] == pytest.approx(2.0)

    def test_correct_values(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_sma(prices, period=3)
        assert result == pytest.approx([2.0, 3.0, 4.0])

    def test_flat_prices_returns_same_value(self):
        prices = _flat_prices(100.0, 10)
        result = calculate_sma(prices, period=5)
        assert all(v == pytest.approx(100.0) for v in result)

    def test_period_one_returns_all_prices(self):
        prices = [1.0, 2.0, 3.0]
        assert calculate_sma(prices, period=1) == pytest.approx(prices)


# ---------------------------------------------------------------------------
# calculate_ema
# ---------------------------------------------------------------------------

class TestCalculateEma:
    def test_insufficient_data_returns_empty(self):
        assert calculate_ema([1.0, 2.0], period=5) == []

    def test_first_value_is_sma(self):
        prices = [2.0, 4.0, 6.0, 8.0, 10.0]
        ema = calculate_ema(prices, period=3)
        # First EMA = SMA of first 3 prices = (2+4+6)/3 = 4.0
        assert ema[0] == pytest.approx(4.0)

    def test_flat_prices_ema_equals_price(self):
        prices = _flat_prices(100.0, 30)
        ema = calculate_ema(prices, period=10)
        assert all(v == pytest.approx(100.0) for v in ema)

    def test_rising_prices_ema_below_last_price(self):
        prices = _rising_prices(1.0, 30)
        ema = calculate_ema(prices, period=10)
        # EMA lags price in a rising series
        assert ema[-1] < prices[-1]

    def test_length_is_correct(self):
        prices = list(range(1, 21))  # 20 prices
        ema = calculate_ema(prices, period=5)
        # Should have len(prices) - period + 1 = 16 values
        assert len(ema) == 16


# ---------------------------------------------------------------------------
# calculate_rsi
# ---------------------------------------------------------------------------

class TestCalculateRsi:
    def test_insufficient_data_returns_neutral(self):
        result = calculate_rsi([1.0, 2.0], period=14)
        assert result["value"] == 50
        assert result["signal"] == "neutral"
        assert result["overbought"] is False
        assert result["oversold"] is False

    def test_overbought_signal_above_70(self):
        # Consistent price increase → RSI high
        prices = _rising_prices(100.0, 40)
        result = calculate_rsi(prices)
        assert result["overbought"] is True
        assert result["value"] >= 70
        assert result["signal"] == "overbought"

    def test_oversold_signal_below_30(self):
        # Consistent price decrease → RSI low
        prices = _falling_prices(200.0, 40)
        result = calculate_rsi(prices)
        assert result["oversold"] is True
        assert result["value"] <= 30
        assert result["signal"] == "oversold"

    def test_flat_prices_no_loss_gives_rsi_100(self):
        # All gains = 0, avg_loss = 0 → RSI = 100
        prices = _flat_prices(100.0, 20)
        # Flat → no changes → avg_gain = avg_loss = 0 → RSI = 100
        result = calculate_rsi(prices)
        assert result["value"] == pytest.approx(100.0)

    def test_result_keys_present(self):
        result = calculate_rsi(_flat_prices(n=20))
        assert {"value", "signal", "overbought", "oversold"} <= result.keys()

    def test_rsi_value_bounded(self):
        for prices in [_rising_prices(n=50), _falling_prices(n=50), _flat_prices(n=50)]:
            result = calculate_rsi(prices)
            assert 0 <= result["value"] <= 100


# ---------------------------------------------------------------------------
# calculate_macd
# ---------------------------------------------------------------------------

class TestCalculateMacd:
    def test_insufficient_data_returns_neutral(self):
        result = calculate_macd([1.0, 2.0, 3.0])
        assert result == {"macd": 0, "signal": 0, "histogram": 0, "trend": "neutral"}

    def test_result_keys_present(self):
        result = calculate_macd(_rising_prices(n=50))
        assert {"macd", "signal", "histogram", "trend"} <= result.keys()

    def test_strong_uptrend_gives_bullish_trend(self):
        prices = _rising_prices(100.0, 60)
        result = calculate_macd(prices)
        assert result["trend"] in ("bullish", "strong_bullish")

    def test_strong_downtrend_gives_bearish_trend(self):
        prices = _falling_prices(200.0, 60)
        result = calculate_macd(prices)
        assert result["trend"] in ("bearish", "strong_bearish")

    def test_histogram_equals_macd_minus_signal(self):
        prices = _rising_prices(50.0, 60)
        result = calculate_macd(prices)
        expected_hist = round(result["macd"] - result["signal"], 6)
        assert result["histogram"] == pytest.approx(expected_hist, abs=1e-5)


# ---------------------------------------------------------------------------
# calculate_bollinger_bands
# ---------------------------------------------------------------------------

class TestCalculateBollingerBands:
    def test_insufficient_data_returns_zeros(self):
        result = calculate_bollinger_bands([1.0, 2.0], period=20)
        assert result["upper"] == 0
        assert result["middle"] == 0
        assert result["lower"] == 0

    def test_result_keys_present(self):
        result = calculate_bollinger_bands(_flat_prices(n=30))
        assert {"upper", "middle", "lower", "bandwidth", "position", "current_price"} <= result.keys()

    def test_flat_prices_tight_bands(self):
        prices = _flat_prices(100.0, 30)
        result = calculate_bollinger_bands(prices)
        # Std dev = 0, so all bands equal the price
        assert result["upper"] == pytest.approx(100.0)
        assert result["middle"] == pytest.approx(100.0)
        assert result["lower"] == pytest.approx(100.0)
        assert result["bandwidth"] == pytest.approx(0.0)

    def test_price_above_upper_band(self):
        prices = _flat_prices(100.0, 30)
        # Spike the last price way above
        prices[-1] = 200.0
        result = calculate_bollinger_bands(prices)
        assert result["position"] == "above_upper"

    def test_price_below_lower_band(self):
        prices = _flat_prices(100.0, 30)
        prices[-1] = 1.0
        result = calculate_bollinger_bands(prices)
        assert result["position"] == "below_lower"

    def test_upper_above_middle_above_lower(self):
        prices = _rising_prices(80.0, 30)
        result = calculate_bollinger_bands(prices)
        assert result["upper"] >= result["middle"] >= result["lower"]


# ---------------------------------------------------------------------------
# calculate_indicators (integration of all)
# ---------------------------------------------------------------------------

class TestCalculateIndicators:
    def test_result_has_all_top_level_keys(self):
        klines = _klines_from_prices(_flat_prices(100.0, 50))
        result = calculate_indicators(klines)
        assert {"current_price", "rsi", "macd", "bollinger_bands", "ema", "volume", "recommendation", "signals_summary"} <= result.keys()

    def test_recommendation_values_are_valid(self):
        valid = {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"}
        for prices in [_flat_prices(n=50), _rising_prices(n=50), _falling_prices(n=50)]:
            result = calculate_indicators(_klines_from_prices(prices))
            assert result["recommendation"] in valid

    def test_strong_uptrend_recommends_buy(self):
        prices = _rising_prices(50.0, 50)
        result = calculate_indicators(_klines_from_prices(prices))
        assert result["recommendation"] in ("BUY", "STRONG_BUY")

    def test_strong_downtrend_recommends_sell(self):
        prices = _falling_prices(200.0, 50)
        result = calculate_indicators(_klines_from_prices(prices))
        assert result["recommendation"] in ("SELL", "STRONG_SELL")

    def test_current_price_matches_last_kline(self):
        prices = _rising_prices(10.0, 40)
        klines = _klines_from_prices(prices)
        result = calculate_indicators(klines)
        assert result["current_price"] == prices[-1]

    def test_volume_trend_detected(self):
        prices = _flat_prices(100.0, 40)
        klines = _klines_from_prices(prices)
        # Spike last volume
        klines[-1]["volume"] = 999999.0
        result = calculate_indicators(klines)
        assert result["volume"]["trend"] == "high"

    def test_signals_summary_counts_non_negative(self):
        klines = _klines_from_prices(_flat_prices(n=50))
        result = calculate_indicators(klines)
        summary = result["signals_summary"]
        assert summary["buy_signals"] >= 0
        assert summary["sell_signals"] >= 0
        assert summary["total_signals"] == summary["buy_signals"] + summary["sell_signals"]
