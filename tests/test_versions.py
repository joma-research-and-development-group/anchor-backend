import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.app_version import AppVersion, PlatformEnum
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User


@pytest.fixture
async def setup_project(db: AsyncSession):
    user = User(email="ver@test.com", password_hash=hash_password("pass"), full_name="V User")
    db.add(user)
    await db.flush()
    org = Organization(name="Ver Org", slug="ver-org", created_by=user.id)
    db.add(org)
    await db.flush()
    member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()
    project = Project(org_id=org.id, name="App", slug="app", created_by=user.id)
    db.add(project)
    await db.flush()
    mode = ProjectMode(project_id=project.id, name="live", is_default=True)
    db.add(mode)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    await db.refresh(project)
    await db.refresh(mode)
    return user, org, project, mode


@pytest.mark.asyncio
async def test_create_and_list_versions(client: AsyncClient, db: AsyncSession, setup_project):
    user, org, project, mode = setup_project
    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/versions",
        json={"semver": "1.0.0", "build_number": 1, "platform": "ios", "mode_id": str(mode.id)},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["semver"] == "1.0.0"
    assert data["platform"] == "ios"

    resp = await client.get("/admin/orgs/ver-org/projects/app/versions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_version(client: AsyncClient, db: AsyncSession, setup_project):
    user, org, project, mode = setup_project
    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/versions",
        json={"semver": "2.0.0", "build_number": 2, "platform": "android", "mode_id": str(mode.id)},
        headers=headers,
    )
    version_id = resp.json()["id"]

    resp = await client.delete(f"/admin/orgs/ver-org/projects/app/versions/{version_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_create_api_key_returns_secret_once(client: AsyncClient, db: AsyncSession, setup_project):
    user, org, project, mode = setup_project
    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Create version first
    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/versions",
        json={"semver": "1.0.0", "build_number": 1, "platform": "ios", "mode_id": str(mode.id)},
        headers=headers,
    )
    version_id = resp.json()["id"]

    # Create API key
    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/versions/{version_id}/api-keys",
        json={"name": "Production Key"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "raw_secret" in data
    assert data["raw_secret"].startswith("anchor_pk_live_")
    assert data["key_prefix"] == data["raw_secret"][:20]

    # List keys should NOT include raw_secret
    resp = await client.get("/admin/orgs/ver-org/projects/app/api-keys", headers=headers)
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) == 1
    assert "raw_secret" not in keys[0]


@pytest.mark.asyncio
async def test_revoke_api_key(client: AsyncClient, db: AsyncSession, setup_project):
    user, org, project, mode = setup_project
    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/versions",
        json={"semver": "1.0.0", "build_number": 1, "platform": "ios", "mode_id": str(mode.id)},
        headers=headers,
    )
    version_id = resp.json()["id"]

    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/versions/{version_id}/api-keys",
        json={"name": "Key"},
        headers=headers,
    )
    key_id = resp.json()["id"]

    resp = await client.post(
        f"/admin/orgs/ver-org/projects/app/api-keys/{key_id}/revoke",
        json={"reason": "Compromised"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"
