"""
Global pytest configuration.

IMPORTANT: env vars MUST be set before any app module is imported so that
pydantic-settings picks up the test values instead of the real .env values.
"""
import os
from cryptography.fernet import Fernet

# Override required settings before any app import
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_100toloose.db"
os.environ["SECRET_KEY"] = "test-secret-key-only-used-in-tests-never-in-production"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_100toloose.db"


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    # Clean up test DB file
    import pathlib
    db_file = pathlib.Path("./test_100toloose.db")
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
async def db_session(test_engine):
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_binance():
    """Mock BinanceService for endpoints that need price data."""
    mock = AsyncMock()
    mock.get_symbol_price.return_value = 50000.0
    mock.get_symbol_filters.return_value = {
        "min_qty": 0.001,
        "max_qty": 9000.0,
        "step_size": 0.001,
        "min_notional": 10.0,
    }
    return mock


@pytest.fixture
async def client(db_session, mock_binance):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.binance = mock_binance

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
async def registered_user(client):
    """Create and return a registered user."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "username": "testuser", "password": "testpassword123"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.fixture
async def auth_headers(client, registered_user):
    """Return Authorization headers for the registered user."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "testpassword123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
