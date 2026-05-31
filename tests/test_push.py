import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sdk_auth import create_sdk_session_token
from app.models.device import Device
from app.models.project import Project, ProjectMode


@pytest.fixture
async def test_project(db: AsyncSession, test_org) -> Project:
    project = Project(
        org_id=test_org.id,
        name="Test Project",
        slug="test-project",
        created_by=test_org.created_by,
    )
    db.add(project)
    await db.flush()
    mode = ProjectMode(project_id=project.id, name="production", is_default=True)
    db.add(mode)
    await db.commit()
    await db.refresh(project)
    return project


@pytest.fixture
async def test_mode(db: AsyncSession, test_project: Project) -> ProjectMode:
    from sqlalchemy import select
    result = await db.execute(
        select(ProjectMode).where(ProjectMode.project_id == test_project.id)
    )
    return result.scalar_one()


@pytest.fixture
def sdk_token(test_project: Project, test_mode: ProjectMode) -> str:
    token, _ = create_sdk_session_token(
        test_project.id, test_mode.id, uuid.uuid4(), "android"
    )
    return token


class TestDeviceRegistration:
    @pytest.mark.asyncio
    async def test_register_device(self, authed_client: AsyncClient, sdk_token: str) -> None:
        resp = await authed_client.post(
            "/v1/devices/register",
            json={"token": "fcm-token-abc123", "platform": "android"},
            headers={"Authorization": f"Bearer {sdk_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Device is resolved from the session (install_id auto-generated).
        assert data["install_id"].startswith("sdk-session-")
        assert data["platform"] == "android"
        assert data["push_token"] == "fcm-token-abc123"

    @pytest.mark.asyncio
    async def test_register_device_update(self, authed_client: AsyncClient, sdk_token: str) -> None:
        # First registration
        await authed_client.post(
            "/v1/devices/register",
            json={"token": "tok-1", "platform": "ios"},
            headers={"Authorization": f"Bearer {sdk_token}"},
        )
        # Update with a new token — same session device is reused.
        resp = await authed_client.post(
            "/v1/devices/register",
            json={"token": "tok-2", "platform": "ios"},
            headers={"Authorization": f"Bearer {sdk_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["push_token"] == "tok-2"

    @pytest.mark.asyncio
    async def test_heartbeat(self, authed_client: AsyncClient, sdk_token: str) -> None:
        resp = await authed_client.post(
            "/v1/devices/heartbeat",
            json={},
            headers={"Authorization": f"Bearer {sdk_token}"},
        )
        assert resp.status_code == 200


class TestPushCampaigns:
    @pytest.mark.asyncio
    async def test_create_campaign(
        self, authed_client: AsyncClient, test_project: Project, test_mode: ProjectMode
    ) -> None:
        resp = await authed_client.post(
            f"/admin/orgs/test-org/projects/test-project/push-campaigns",
            json={
                "mode_id": str(test_mode.id),
                "title": "Test Push",
                "body": "Hello world",
                "target_type": "all",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Push"
        assert data["status"] == "draft"

    @pytest.mark.asyncio
    async def test_list_campaigns(
        self, authed_client: AsyncClient, test_project: Project, test_mode: ProjectMode
    ) -> None:
        await authed_client.post(
            f"/admin/orgs/test-org/projects/test-project/push-campaigns",
            json={
                "mode_id": str(test_mode.id),
                "title": "Campaign 1",
                "body": "Body 1",
                "target_type": "all",
            },
        )
        resp = await authed_client.get(
            "/admin/orgs/test-org/projects/test-project/push-campaigns"
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestAnnouncements:
    @pytest.mark.asyncio
    async def test_create_announcement(
        self, authed_client: AsyncClient, test_project: Project, test_mode: ProjectMode
    ) -> None:
        resp = await authed_client.post(
            "/admin/orgs/test-org/projects/test-project/announcements",
            json={
                "mode_id": str(test_mode.id),
                "title": "New Feature",
                "body": "Check out our new feature!",
                "type": "banner",
                "starts_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "New Feature"
        assert data["type"] == "banner"

    @pytest.mark.asyncio
    async def test_update_announcement(
        self, authed_client: AsyncClient, test_project: Project, test_mode: ProjectMode
    ) -> None:
        resp = await authed_client.post(
            "/admin/orgs/test-org/projects/test-project/announcements",
            json={
                "mode_id": str(test_mode.id),
                "title": "Original",
                "body": "Body",
                "type": "modal",
                "starts_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ann_id = resp.json()["id"]
        resp = await authed_client.put(
            f"/admin/orgs/test-org/projects/test-project/announcements/{ann_id}",
            json={"title": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    @pytest.mark.asyncio
    async def test_list_sdk_announcements(
        self, authed_client: AsyncClient, test_project: Project, test_mode: ProjectMode, sdk_token: str
    ) -> None:
        # Create an active announcement
        await authed_client.post(
            "/admin/orgs/test-org/projects/test-project/announcements",
            json={
                "mode_id": str(test_mode.id),
                "title": "SDK Announcement",
                "body": "Visible to SDK",
                "type": "card",
                "starts_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        # Register a device first
        await authed_client.post(
            "/v1/devices/register",
            json={"install_id": "ann-device", "platform": "android"},
            headers={"Authorization": f"Bearer {sdk_token}"},
        )
        resp = await authed_client.get(
            "/v1/announcements?install_id=ann-device",
            headers={"Authorization": f"Bearer {sdk_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_delete_announcement(
        self, authed_client: AsyncClient, test_project: Project, test_mode: ProjectMode
    ) -> None:
        resp = await authed_client.post(
            "/admin/orgs/test-org/projects/test-project/announcements",
            json={
                "mode_id": str(test_mode.id),
                "title": "To Delete",
                "body": "Will be deleted",
                "type": "banner",
                "starts_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ann_id = resp.json()["id"]
        resp = await authed_client.delete(
            f"/admin/orgs/test-org/projects/test-project/announcements/{ann_id}"
        )
        assert resp.status_code == 204
