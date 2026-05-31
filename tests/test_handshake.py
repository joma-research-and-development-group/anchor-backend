from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.key_gen import generate_api_key
from app.core.security import create_access_token, hash_password
from app.models.api_key import ApiKey, ApiKeyStatusEnum
from app.models.app_version import AppVersion, PlatformEnum
from app.models.maintenance_window import MaintenanceWindow
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.models.version_policy import VersionPolicy


@pytest.fixture
async def handshake_setup(db: AsyncSession):
    user = User(email="hs@test.com", password_hash=hash_password("pass"), full_name="HS User")
    db.add(user)
    await db.flush()
    org = Organization(name="HS Org", slug="hs-org", created_by=user.id)
    db.add(org)
    await db.flush()
    member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()
    project = Project(org_id=org.id, name="HSApp", slug="hsapp", created_by=user.id)
    db.add(project)
    await db.flush()
    mode = ProjectMode(project_id=project.id, name="live", is_default=True)
    db.add(mode)
    await db.flush()
    version = AppVersion(
        project_id=project.id, mode_id=mode.id, platform=PlatformEnum.ios,
        semver="1.0.0", build_number=1, created_by=user.id,
    )
    db.add(version)
    await db.flush()
    raw_secret, prefix, key_hash = generate_api_key("live")
    api_key = ApiKey(
        project_id=project.id, mode_id=mode.id, version_id=version.id,
        name="Test Key", key_prefix=prefix, key_hash=key_hash, created_by=user.id,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(version)
    await db.refresh(api_key)
    await db.refresh(project)
    await db.refresh(mode)
    return {
        "user": user, "org": org, "project": project, "mode": mode,
        "version": version, "api_key": api_key, "raw_secret": raw_secret,
    }


@pytest.mark.asyncio
async def test_handshake_ok(client: AsyncClient, db: AsyncSession, handshake_setup):
    data = handshake_setup
    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "1.0.0", "build_number": 1, "platform": "ios"},
        headers={"X-Anchor-Key": data["raw_secret"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"]["action"] == "ok"
    assert body["maintenance"]["active"] is False
    assert body["session"]["jwt"]
    # Verify JWT claims
    payload = jwt.decode(body["session"]["jwt"], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert payload["project_id"] == str(data["project"].id)
    assert payload["platform"] == "ios"
    assert payload["type"] == "sdk_session"


@pytest.mark.asyncio
async def test_handshake_revoked_key(client: AsyncClient, db: AsyncSession, handshake_setup):
    data = handshake_setup
    data["api_key"].status = ApiKeyStatusEnum.revoked
    db.add(data["api_key"])
    await db.commit()

    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "1.0.0", "build_number": 1, "platform": "ios"},
        headers={"X-Anchor-Key": data["raw_secret"]},
    )
    assert resp.status_code == 200
    assert resp.json()["version"]["action"] == "force_update"


@pytest.mark.asyncio
async def test_handshake_version_mismatch(client: AsyncClient, db: AsyncSession, handshake_setup):
    data = handshake_setup
    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "2.0.0", "build_number": 99, "platform": "ios"},
        headers={"X-Anchor-Key": data["raw_secret"]},
    )
    assert resp.status_code == 200
    assert resp.json()["version"]["action"] == "force_update"


@pytest.mark.asyncio
async def test_handshake_below_min_version(client: AsyncClient, db: AsyncSession, handshake_setup):
    data = handshake_setup
    # Set version to match so we don't get version mismatch first
    data["version"].semver = "0.9.0"
    data["version"].build_number = 1
    db.add(data["version"])
    await db.flush()
    # Add policy with min_supported
    policy = VersionPolicy(
        project_id=data["project"].id, mode_id=data["mode"].id,
        platform=PlatformEnum.ios, min_supported_semver="1.0.0", latest_semver="2.0.0",
        message_force="Please update",
    )
    db.add(policy)
    await db.commit()

    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "0.9.0", "build_number": 1, "platform": "ios"},
        headers={"X-Anchor-Key": data["raw_secret"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"]["action"] == "force_update"
    assert body["version"]["message"] == "Please update"


@pytest.mark.asyncio
async def test_handshake_soft_update(client: AsyncClient, db: AsyncSession, handshake_setup):
    data = handshake_setup
    policy = VersionPolicy(
        project_id=data["project"].id, mode_id=data["mode"].id,
        platform=PlatformEnum.ios, min_supported_semver="0.5.0", latest_semver="2.0.0",
        message_soft="New version available",
    )
    db.add(policy)
    await db.commit()

    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "1.0.0", "build_number": 1, "platform": "ios"},
        headers={"X-Anchor-Key": data["raw_secret"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"]["action"] == "soft_update"
    assert body["version"]["message"] == "New version available"


@pytest.mark.asyncio
async def test_handshake_maintenance_active(client: AsyncClient, db: AsyncSession, handshake_setup):
    data = handshake_setup
    window = MaintenanceWindow(
        project_id=data["project"].id, mode_id=data["mode"].id,
        title="Scheduled Maintenance", message="Back soon",
        starts_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
        created_by=data["user"].id,
    )
    db.add(window)
    await db.commit()

    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "1.0.0", "build_number": 1, "platform": "ios"},
        headers={"X-Anchor-Key": data["raw_secret"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["maintenance"]["active"] is True
    assert body["maintenance"]["title"] == "Scheduled Maintenance"


@pytest.mark.asyncio
async def test_handshake_invalid_key(client: AsyncClient, db: AsyncSession, handshake_setup):
    resp = await client.post(
        "/v1/handshake",
        json={"app_version": "1.0.0", "build_number": 1, "platform": "ios"},
        headers={"X-Anchor-Key": "anchor_pk_live_invalidinvalidinvalid"},
    )
    assert resp.status_code == 401
