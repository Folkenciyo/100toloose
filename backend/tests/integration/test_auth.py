"""Integration tests for authentication endpoints."""
import pytest


REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

VALID_USER = {"email": "alice@example.com", "username": "alice", "password": "securepass123"}


class TestRegister:
    async def test_register_success(self, client):
        response = await client.post(REGISTER_URL, json=VALID_USER)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == VALID_USER["email"]
        assert data["username"] == VALID_USER["username"]
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client):
        await client.post(REGISTER_URL, json=VALID_USER)
        duplicate = {**VALID_USER, "username": "different_user"}
        response = await client.post(REGISTER_URL, json=duplicate)
        assert response.status_code == 400
        assert "email" in response.json()["detail"].lower()

    async def test_register_duplicate_username(self, client):
        await client.post(REGISTER_URL, json=VALID_USER)
        duplicate = {**VALID_USER, "email": "other@example.com"}
        response = await client.post(REGISTER_URL, json=duplicate)
        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()

    async def test_register_missing_fields(self, client):
        response = await client.post(REGISTER_URL, json={"email": "x@x.com"})
        assert response.status_code == 422

    async def test_register_invalid_email(self, client):
        response = await client.post(
            REGISTER_URL,
            json={"email": "not-an-email", "username": "bob", "password": "pass123"},
        )
        assert response.status_code == 422

    async def test_register_sets_default_balance(self, client):
        response = await client.post(REGISTER_URL, json=VALID_USER)
        assert response.status_code == 200
        data = response.json()
        assert data["initial_balance"] == 10000.0
        assert data["current_balance"] == 10000.0
        assert data["paper_trading"] is True


class TestLogin:
    async def test_login_success_returns_token(self, client, registered_user):
        response = await client.post(
            LOGIN_URL,
            data={"username": "testuser", "password": "testpassword123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 10

    async def test_login_wrong_password(self, client, registered_user):
        response = await client.post(
            LOGIN_URL,
            data={"username": "testuser", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_unknown_user(self, client):
        response = await client.post(
            LOGIN_URL,
            data={"username": "nobody", "password": "whatever"},
        )
        assert response.status_code == 401

    async def test_login_missing_credentials(self, client):
        response = await client.post(LOGIN_URL, data={})
        assert response.status_code == 422

    async def test_token_can_access_protected_endpoint(self, client, registered_user):
        login = await client.post(
            LOGIN_URL,
            data={"username": "testuser", "password": "testpassword123"},
        )
        token = login.json()["access_token"]
        response = await client.get(
            "/api/v1/trades/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_invalid_token_returns_401(self, client):
        response = await client.get(
            "/api/v1/trades/",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert response.status_code == 401
