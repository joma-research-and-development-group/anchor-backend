import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_owner_can_delete_org(client: AsyncClient) -> None:
    # Signup creates user as owner
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "owner@example.com",
        "password": "pass",
        "full_name": "Owner",
        "org_name": "Delete Me Org",
    })
    token = resp.cookies.get("access_token")
    client.cookies.set("access_token", token)

    # Get org slug
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200

    # Delete org
    resp = await client.delete("/api/v1/orgs/delete-me-org")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_viewer_cannot_delete_org(client: AsyncClient) -> None:
    # Create owner
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "owner2@example.com",
        "password": "pass",
        "full_name": "Owner2",
        "org_name": "Protected Org",
    })
    owner_token = resp.cookies.get("access_token")

    # Create viewer user
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "viewer@example.com",
        "password": "pass",
        "full_name": "Viewer",
        "org_name": "Viewer Org",
    })
    viewer_token = resp.cookies.get("access_token")

    # Viewer tries to delete owner's org - should fail (not a member)
    client.cookies.set("access_token", viewer_token)
    resp = await client.delete("/api/v1/orgs/protected-org")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_and_get_org(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "orgtest@example.com",
        "password": "pass",
        "full_name": "Org Tester",
        "org_name": "My Org",
    })
    token = resp.cookies.get("access_token")
    client.cookies.set("access_token", token)

    resp = await client.get("/api/v1/orgs/my-org")
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Org"


@pytest.mark.asyncio
async def test_update_org(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "update@example.com",
        "password": "pass",
        "full_name": "Updater",
        "org_name": "Update Org",
    })
    token = resp.cookies.get("access_token")
    client.cookies.set("access_token", token)

    resp = await client.patch("/api/v1/orgs/update-org", json={"name": "Updated Org"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Org"
