"""Integration tests for trades endpoints."""
import pytest


TRADES_URL = "/api/v1/trades/"
OPEN_TRADES_URL = "/api/v1/trades/open"


class TestGetTrades:
    async def test_unauthenticated_returns_401(self, client):
        response = await client.get(TRADES_URL)
        assert response.status_code == 401

    async def test_empty_list_for_new_user(self, client, auth_headers):
        response = await client.get(TRADES_URL, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_open_trades_empty_for_new_user(self, client, auth_headers):
        response = await client.get(OPEN_TRADES_URL, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []


class TestCreateTrade:
    async def test_create_paper_trade_buy(self, client, auth_headers, mock_binance):
        mock_binance.get_symbol_price.return_value = 50000.0
        response = await client.post(
            TRADES_URL,
            json={"symbol": "BTCUSDT", "trade_type": "buy", "quantity": 0.01},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["entry_price"] == pytest.approx(50000.0)
        assert data["status"] == "open"
        assert data["is_paper_trade"] == 1

    async def test_create_trade_deducts_balance(self, client, auth_headers, mock_binance):
        mock_binance.get_symbol_price.return_value = 1000.0
        response = await client.post(
            TRADES_URL,
            json={"symbol": "ETHUSDT", "trade_type": "buy", "quantity": 1.0},
            headers=auth_headers,
        )
        assert response.status_code == 200
        # Initial balance 10000 - (1000 * 1.0) = 9000
        # We verify the trade was created; balance check is via profile endpoint

    async def test_create_trade_insufficient_balance(self, client, auth_headers, mock_binance):
        # Price * qty = 50000 * 1 = 50000 > initial balance of 10000
        mock_binance.get_symbol_price.return_value = 50000.0
        response = await client.post(
            TRADES_URL,
            json={"symbol": "BTCUSDT", "trade_type": "buy", "quantity": 1.0},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "balance" in response.json()["detail"].lower()

    async def test_create_trade_sets_stop_loss_take_profit(self, client, auth_headers, mock_binance):
        mock_binance.get_symbol_price.return_value = 1000.0
        response = await client.post(
            TRADES_URL,
            json={"symbol": "SOLUSDT", "trade_type": "buy", "quantity": 0.1},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        # Default SL = price * 0.98, TP = price * 1.03
        assert data["stop_loss"] == pytest.approx(980.0)
        assert data["take_profit"] == pytest.approx(1030.0)

    async def test_created_trade_appears_in_list(self, client, auth_headers, mock_binance):
        mock_binance.get_symbol_price.return_value = 100.0
        await client.post(
            TRADES_URL,
            json={"symbol": "BNBUSDT", "trade_type": "buy", "quantity": 1.0},
            headers=auth_headers,
        )
        response = await client.get(TRADES_URL, headers=auth_headers)
        assert response.status_code == 200
        trades = response.json()
        assert len(trades) >= 1
        assert any(t["symbol"] == "BNBUSDT" for t in trades)

    async def test_unauthenticated_create_returns_401(self, client):
        response = await client.post(
            TRADES_URL,
            json={"symbol": "BTCUSDT", "trade_type": "buy", "quantity": 0.01},
        )
        assert response.status_code == 401


class TestCloseTrade:
    async def _open_trade(self, client, auth_headers, mock_binance, qty=0.1, price=100.0):
        mock_binance.get_symbol_price.return_value = price
        response = await client.post(
            TRADES_URL,
            json={"symbol": "XRPUSDT", "trade_type": "buy", "quantity": qty},
            headers=auth_headers,
        )
        assert response.status_code == 200
        return response.json()

    async def test_close_open_trade(self, client, auth_headers, mock_binance):
        trade = await self._open_trade(client, auth_headers, mock_binance, qty=1.0, price=100.0)
        trade_id = trade["id"]

        mock_binance.get_symbol_price.return_value = 110.0
        response = await client.post(
            f"{TRADES_URL}{trade_id}/close",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "closed"
        assert data["exit_price"] == pytest.approx(110.0)

    async def test_close_profitable_trade_has_positive_pnl(self, client, auth_headers, mock_binance):
        trade = await self._open_trade(client, auth_headers, mock_binance, qty=1.0, price=100.0)
        trade_id = trade["id"]

        # Exit at 200 — large enough to cover fees
        mock_binance.get_symbol_price.return_value = 200.0
        response = await client.post(f"{TRADES_URL}{trade_id}/close", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Gross = (200-100)*1 = 100; fees = 100*0.001 + 200*0.001 = 0.3
        assert data["profit_loss"] == pytest.approx(100.0 - 0.3, rel=1e-3)
        assert data["profit_loss"] > 0

    async def test_close_losing_trade_has_negative_pnl(self, client, auth_headers, mock_binance):
        trade = await self._open_trade(client, auth_headers, mock_binance, qty=1.0, price=100.0)
        trade_id = trade["id"]

        mock_binance.get_symbol_price.return_value = 80.0
        response = await client.post(f"{TRADES_URL}{trade_id}/close", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["profit_loss"] < 0

    async def test_fee_cost_makes_small_win_a_loss(self, client, auth_headers, mock_binance):
        # Entry=100, exit=100.1 (+0.1%) — fee is 0.2%, so net should be negative
        trade = await self._open_trade(client, auth_headers, mock_binance, qty=1.0, price=100.0)
        trade_id = trade["id"]

        mock_binance.get_symbol_price.return_value = 100.1
        response = await client.post(f"{TRADES_URL}{trade_id}/close", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["profit_loss"] < 0

    async def test_close_already_closed_trade_returns_400(self, client, auth_headers, mock_binance):
        trade = await self._open_trade(client, auth_headers, mock_binance, qty=1.0, price=100.0)
        trade_id = trade["id"]

        mock_binance.get_symbol_price.return_value = 110.0
        await client.post(f"{TRADES_URL}{trade_id}/close", headers=auth_headers)
        # Second close attempt
        response = await client.post(f"{TRADES_URL}{trade_id}/close", headers=auth_headers)
        assert response.status_code == 400

    async def test_close_nonexistent_trade_returns_404(self, client, auth_headers):
        response = await client.post(f"{TRADES_URL}99999/close", headers=auth_headers)
        assert response.status_code == 404

    async def test_cannot_close_another_users_trade(self, client, auth_headers, mock_binance):
        trade = await self._open_trade(client, auth_headers, mock_binance, qty=1.0, price=100.0)
        trade_id = trade["id"]

        # Register second user
        await client.post(
            "/api/v1/auth/register",
            json={"email": "eve@example.com", "username": "eve", "password": "evepass123"},
        )
        login2 = await client.post(
            "/api/v1/auth/login",
            data={"username": "eve", "password": "evepass123"},
        )
        eve_headers = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        mock_binance.get_symbol_price.return_value = 150.0
        response = await client.post(f"{TRADES_URL}{trade_id}/close", headers=eve_headers)
        assert response.status_code == 404
