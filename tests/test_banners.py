import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sdk_auth import create_sdk_session_token
from app.core.security import create_access_token, hash_password
from app.models.device import Device
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User


@pytest.fixture
async def setup_banner_project(db: AsyncSession) -> dict:
    user = User(email="banner@test.com", password_hash=hash_password("pass123"), full_name="Banner User")
    db.add(user)
    await db.flush()
    org = Organization(name="Banner Org", slug="banner-org", created_by=user.id)
    db.add(org)
    await db.flush()
    member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()
    project = Project(org_id=org.id, name="Banner Project", slug="banner-proj", created_by=user.id)
    db.add(project)
    await db.flush()
    mode = ProjectMode(project_id=project.id, name="production", is_default=True)
    db.add(mode)
    await db.flush()
    device = Device(
        project_id=project.id,
        mode_id=mode.id,
        install_id="device-001",
        platform="android",
    )
    db.add(device)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    await db.refresh(project)
    await db.refresh(mode)
    await db.refresh(device)
    token = create_access_token(str(user.id))
    sdk_token, _ = create_sdk_session_token(project.id, mode.id, uuid.uuid4(), "android")
    return {
        "user": user,
        "org": org,
        "project": project,
        "mode": mode,
        "device": device,
        "token": token,
        "sdk_token": sdk_token,
    }


@pytest.mark.asyncio
async def test_create_banner(client: AsyncClient, setup_banner_project: dict) -> None:
    data = setup_banner_project
    client.cookies.set("access_token", data["token"])
    now = datetime.now(timezone.utc)
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners",
        json={
            "mode_id": str(data["mode"].id),
            "name": "Promo Banner",
            "title": "Big Sale",
            "body": "50% off everything",
            "cta_label": "Shop Now",
            "cta_url": "https://example.com/sale",
            "starts_at": now.isoformat(),
            "frequency_cap": 3,
            "priority": 10,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Promo Banner"
    assert body["frequency_cap"] == 3
    assert body["total_impressions"] == 0


@pytest.mark.asyncio
async def test_list_banners(client: AsyncClient, setup_banner_project: dict) -> None:
    data = setup_banner_project
    client.cookies.set("access_token", data["token"])
    now = datetime.now(timezone.utc)
    await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners",
        json={
            "mode_id": str(data["mode"].id),
            "name": "Banner 1",
            "title": "T1",
            "body": "B1",
            "cta_label": "CTA",
            "cta_url": "https://example.com",
            "starts_at": now.isoformat(),
        },
    )
    resp = await client.get(f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_update_banner(client: AsyncClient, setup_banner_project: dict) -> None:
    data = setup_banner_project
    client.cookies.set("access_token", data["token"])
    now = datetime.now(timezone.utc)
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners",
        json={
            "mode_id": str(data["mode"].id),
            "name": "Old Name",
            "title": "T",
            "body": "B",
            "cta_label": "CTA",
            "cta_url": "https://example.com",
            "starts_at": now.isoformat(),
        },
    )
    banner_id = resp.json()["id"]
    resp = await client.put(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners/{banner_id}",
        json={"name": "New Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_banner(client: AsyncClient, setup_banner_project: dict) -> None:
    data = setup_banner_project
    client.cookies.set("access_token", data["token"])
    now = datetime.now(timezone.utc)
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners",
        json={
            "mode_id": str(data["mode"].id),
            "name": "To Delete",
            "title": "T",
            "body": "B",
            "cta_label": "CTA",
            "cta_url": "https://example.com",
            "starts_at": now.isoformat(),
        },
    )
    banner_id = resp.json()["id"]
    resp = await client.delete(f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners/{banner_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_sdk_banners_with_frequency_cap(client: AsyncClient, setup_banner_project: dict) -> None:
    data = setup_banner_project
    client.cookies.set("access_token", data["token"])
    now = datetime.now(timezone.utc)
    # Create banner with frequency_cap=2
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners",
        json={
            "mode_id": str(data["mode"].id),
            "name": "Capped Banner",
            "title": "Cap",
            "body": "Body",
            "cta_label": "CTA",
            "cta_url": "https://example.com",
            "starts_at": now.isoformat(),
            "frequency_cap": 2,
            "priority": 5,
        },
    )
    assert resp.status_code == 201
    banner_id = resp.json()["id"]

    # SDK: list banners - should see it
    sdk_headers = {"Authorization": f"Bearer {data['sdk_token']}"}
    resp = await client.get("/v1/banners", params={"install_id": "device-001"}, headers=sdk_headers)
    assert resp.status_code == 200
    banners = resp.json()
    assert any(b["id"] == banner_id for b in banners)

    # Record 2 impressions (hitting the cap)
    for _ in range(2):
        resp = await client.post(
            f"/v1/banners/{banner_id}/impression",
            json={"install_id": "device-001"},
            headers=sdk_headers,
        )
        assert resp.status_code == 200

    # Now banner should not appear
    resp = await client.get("/v1/banners", params={"install_id": "device-001"}, headers=sdk_headers)
    assert resp.status_code == 200
    banners = resp.json()
    assert not any(b["id"] == banner_id for b in banners)


@pytest.mark.asyncio
async def test_sdk_banner_click(client: AsyncClient, setup_banner_project: dict) -> None:
    data = setup_banner_project
    client.cookies.set("access_token", data["token"])
    now = datetime.now(timezone.utc)
    resp = await client.post(
        f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners",
        json={
            "mode_id": str(data["mode"].id),
            "name": "Click Banner",
            "title": "Click",
            "body": "Body",
            "cta_label": "CTA",
            "cta_url": "https://example.com",
            "starts_at": now.isoformat(),
            "frequency_cap": 5,
        },
    )
    banner_id = resp.json()["id"]
    sdk_headers = {"Authorization": f"Bearer {data['sdk_token']}"}

    # Record impression then click
    await client.post(f"/v1/banners/{banner_id}/impression", json={"install_id": "device-001"}, headers=sdk_headers)
    resp = await client.post(f"/v1/banners/{banner_id}/click", json={"install_id": "device-001"}, headers=sdk_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "clicked"

    # Check stats
    resp = await client.get(f"/admin/orgs/{data['org'].slug}/projects/{data['project'].slug}/banners/{banner_id}/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_impressions"] == 1
    assert stats["total_clicks"] == 1
