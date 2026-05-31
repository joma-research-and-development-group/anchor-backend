import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.core.sdk_auth import create_sdk_session_token
from app.models.config_entry import ConfigEntry, ConfigValueTypeEnum
from app.models.config_override import ConfigOverride
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.services.config_evaluator import compute_etag, evaluate_config


@pytest.fixture
async def config_setup(db: AsyncSession):
    user = User(email="cfg@test.com", password_hash=hash_password("pass"), full_name="Cfg User")
    db.add(user)
    await db.flush()
    org = Organization(name="Cfg Org", slug="cfg-org", created_by=user.id)
    db.add(org)
    await db.flush()
    member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
    db.add(member)
    await db.flush()
    project = Project(org_id=org.id, name="CfgApp", slug="cfgapp", created_by=user.id)
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


def test_evaluate_config_default():
    entries = [{"key": "feature_x", "default_value": True, "overrides": []}]
    result = evaluate_config(entries, {"app_version": "1.0.0", "platform": "ios"})
    assert result == {"feature_x": True}


def test_evaluate_config_with_override_match():
    entries = [{
        "key": "feature_x",
        "default_value": False,
        "overrides": [
            {"conditions": {"platform": ["ios"]}, "value": True, "priority": 1},
            {"conditions": {"platform": ["android"]}, "value": False, "priority": 0},
        ],
    }]
    result = evaluate_config(entries, {"app_version": "1.0.0", "platform": "ios"})
    assert result == {"feature_x": True}


def test_evaluate_config_priority():
    entries = [{
        "key": "limit",
        "default_value": 10,
        "overrides": [
            {"conditions": {"platform": ["ios"]}, "value": 50, "priority": 5},
            {"conditions": {"platform": ["ios"]}, "value": 20, "priority": 10},
        ],
    }]
    result = evaluate_config(entries, {"app_version": "1.0.0", "platform": "ios"})
    assert result == {"limit": 20}


def test_evaluate_config_version_condition():
    entries = [{
        "key": "new_ui",
        "default_value": False,
        "overrides": [
            {"conditions": {"min_version": "2.0.0"}, "value": True, "priority": 1},
        ],
    }]
    # Below min_version
    result = evaluate_config(entries, {"app_version": "1.5.0", "platform": "ios"})
    assert result == {"new_ui": False}
    # At or above min_version
    result = evaluate_config(entries, {"app_version": "2.0.0", "platform": "ios"})
    assert result == {"new_ui": True}


def test_compute_etag_deterministic():
    d = {"a": 1, "b": "hello"}
    assert compute_etag(d) == compute_etag(d)
    assert compute_etag(d) != compute_etag({"a": 2})


@pytest.mark.asyncio
async def test_config_crud(client: AsyncClient, db: AsyncSession, config_setup):
    user, org, project, mode = config_setup
    token = create_access_token(str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    # Create entry
    resp = await client.post(
        "/admin/orgs/cfg-org/projects/cfgapp/config",
        json={"key": "dark_mode", "value_type": "bool", "default_value": False, "mode_id": str(mode.id)},
        headers=headers,
    )
    assert resp.status_code == 201
    entry_id = resp.json()["id"]
    assert resp.json()["key"] == "dark_mode"

    # Add override
    resp = await client.post(
        f"/admin/orgs/cfg-org/projects/cfgapp/config/{entry_id}/overrides",
        json={"conditions": {"platform": ["ios"]}, "value": True, "priority": 1},
        headers=headers,
    )
    assert resp.status_code == 201
    override_id = resp.json()["id"]

    # List config
    resp = await client.get("/admin/orgs/cfg-org/projects/cfgapp/config", headers=headers)
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert len(entries[0]["overrides"]) == 1

    # Delete override
    resp = await client.delete(
        f"/admin/orgs/cfg-org/projects/cfgapp/config/{entry_id}/overrides/{override_id}",
        headers=headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_sdk_config_etag_304(client: AsyncClient, db: AsyncSession, config_setup):
    user, org, project, mode = config_setup
    # Add a config entry
    entry = ConfigEntry(
        project_id=project.id, mode_id=mode.id, key="flag",
        value_type=ConfigValueTypeEnum.bool, default_value=True,
    )
    db.add(entry)
    await db.commit()

    # Get SDK session token
    sdk_token, _ = create_sdk_session_token(project.id, mode.id, project.id, "ios")
    headers = {"Authorization": f"Bearer {sdk_token}"}

    # First request
    resp = await client.get("/v1/config", headers=headers)
    assert resp.status_code == 200
    etag = resp.headers["etag"].strip('"')

    # Second request with If-None-Match
    resp = await client.get("/v1/config", headers={**headers, "If-None-Match": etag})
    assert resp.status_code == 304
