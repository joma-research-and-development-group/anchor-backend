from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def health_client() -> AsyncClient:
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@patch("app.api.health.async_session")
@patch("app.api.health.Redis.from_url")
async def test_health_ok(
    mock_redis_cls: AsyncMock, mock_session_cls: AsyncMock, health_client: AsyncClient
) -> None:
    # Mock DB session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session_cls.return_value = mock_session

    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()
    mock_redis_cls.return_value = mock_redis

    response = await health_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] is True
    assert data["redis"] is True
    assert "uptime" in data


@patch("app.api.health.async_session")
@patch("app.api.health.Redis.from_url")
async def test_health_degraded_db(
    mock_redis_cls: AsyncMock, mock_session_cls: AsyncMock, health_client: AsyncClient
) -> None:
    # Mock DB failure
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(side_effect=Exception("DB down"))
    mock_session_cls.return_value = mock_session

    # Mock Redis OK
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.aclose = AsyncMock()
    mock_redis_cls.return_value = mock_redis

    response = await health_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["db"] is False
    assert data["redis"] is True
