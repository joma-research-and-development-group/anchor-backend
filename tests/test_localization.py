import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sdk_auth import create_sdk_session_token
from app.core.security import create_access_token, hash_password
from app.models.localization import LocalizationEntry
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User


@pytest.fixture
async def setup_project(db: AsyncSession) -> dict:
    user = User(email="loc@test.com", password_hash=hash_password("pass123"), full_name="Loc User")
    db.add(user)
    await db.flush()
    org = Organization(name="Loc Org", slug="loc-org", created_by=user.id)
    db.add(org)
    await db.flush()
    member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()
    project = Project(org_id=org.id, name="Loc Project", slug="loc-proj", created_by=user.id)
    db.add(project)
    await db.flush()
    mode = ProjectMode(project_id=project.id, name="production", is_default=True)
    db.add(mode)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    await db.refresh(project)
    await db.refresh(mode)
    token = create_access_token(str(user.id))
    sdk_token, _ = create_sdk_session_token(project.id, mode.id, uuid.uuid4(), "android")
    return {
        "user": user,
        "org": org,
        "project": project,
        "mode": mode,
        "token": token,
        "sdk_token": sdk_token,
    }


@pytest.mark.asyncio
async def test_create_localization_entry(client: AsyncClient, setup_project: dict) -> None:
    data = setup_project
    client.cookies.set("access_token", data["token"])
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "greeting", "locale": "en", "value": "Hello"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"] == "greeting"
    assert body["locale"] == "en"
    assert body["value"] == "Hello"


@pytest.mark.asyncio
async def test_list_localization_entries(client: AsyncClient, setup_project: dict) -> None:
    data = setup_project
    client.cookies.set("access_token", data["token"])
    # Create two entries
    await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "hello", "locale": "en", "value": "Hello"},
    )
    await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "hello", "locale": "uz", "value": "Salom"},
    )
    # List all
    resp = await client.get(f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    # Filter by locale
    resp = await client.get(f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization?locale=uz")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["value"] == "Salom"


@pytest.mark.asyncio
async def test_bulk_upsert(client: AsyncClient, setup_project: dict) -> None:
    data = setup_project
    client.cookies.set("access_token", data["token"])
    # Create initial entry
    await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "btn_ok", "locale": "en", "value": "OK"},
    )
    # Bulk upsert: update existing + create new
    resp = await client.put(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization/bulk",
        json={
            "mode_id": str(data["mode"].id),
            "entries": [
                {"key": "btn_ok", "locale": "en", "value": "Okay"},
                {"key": "btn_cancel", "locale": "en", "value": "Cancel"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    values = {e["key"]: e["value"] for e in body}
    assert values["btn_ok"] == "Okay"
    assert values["btn_cancel"] == "Cancel"


@pytest.mark.asyncio
async def test_update_and_delete(client: AsyncClient, setup_project: dict) -> None:
    data = setup_project
    client.cookies.set("access_token", data["token"])
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "title", "locale": "en", "value": "Old"},
    )
    entry_id = resp.json()["id"]
    # Update
    resp = await client.patch(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization/{entry_id}",
        json={"value": "New"},
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "New"
    # Delete
    resp = await client.delete(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization/{entry_id}",
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_sdk_localization_with_etag(client: AsyncClient, setup_project: dict) -> None:
    data = setup_project
    client.cookies.set("access_token", data["token"])
    # Create entries
    await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "welcome", "locale": "en", "value": "Welcome"},
    )
    await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/localization",
        json={"mode_id": str(data["mode"].id), "key": "bye", "locale": "en", "value": "Goodbye"},
    )
    # SDK request
    sdk_headers = {"Authorization": f"Bearer {data['sdk_token']}"}
    resp = await client.get("/v1/localization?locale=en", headers=sdk_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["welcome"] == "Welcome"
    assert body["bye"] == "Goodbye"
    etag = resp.headers.get("etag")
    assert etag is not None
    # Request with matching ETag should return 304
    resp = await client.get("/v1/localization?locale=en", headers={**sdk_headers, "If-None-Match": etag})
    assert resp.status_code == 304
