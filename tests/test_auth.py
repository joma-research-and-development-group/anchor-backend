import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "new@example.com",
        "password": "securepass",
        "full_name": "New User",
        "org_name": "New Org",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert resp.cookies.get("access_token") is not None


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/signup", json={
        "email": "dup@example.com",
        "password": "pass",
        "full_name": "Dup",
        "org_name": "Org",
    })
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "dup@example.com",
        "password": "pass",
        "full_name": "Dup",
        "org_name": "Org2",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/signup", json={
        "email": "login@example.com",
        "password": "mypass",
        "full_name": "Login User",
        "org_name": "Login Org",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "mypass",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_invalid(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient) -> None:
    signup_resp = await client.post("/api/v1/auth/signup", json={
        "email": "me@example.com",
        "password": "pass",
        "full_name": "Me User",
        "org_name": "Me Org",
    })
    token = signup_resp.cookies.get("access_token")
    client.cookies.set("access_token", token)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Logged out"


@pytest.mark.asyncio
async def test_refresh(client: AsyncClient) -> None:
    signup_resp = await client.post("/api/v1/auth/signup", json={
        "email": "refresh@example.com",
        "password": "pass",
        "full_name": "Refresh",
        "org_name": "Ref Org",
    })
    refresh_token = signup_resp.cookies.get("refresh_token")
    resp = await client.post("/api/v1/auth/refresh", params={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
