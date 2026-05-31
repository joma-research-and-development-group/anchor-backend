import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sdk_auth import create_sdk_session_token
from app.models.crash_group import CrashGroup
from app.models.device import Device
from app.models.event import Event
from app.models.experiment import Experiment, ExperimentStatusEnum
from app.models.experiment_assignment import ExperimentAssignment
from app.models.experiment_variant import ExperimentVariant
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.services.crash_grouper import generate_fingerprint
from app.services.experiment_assigner import deterministic_assign
from tests.conftest import TestSession


@pytest.fixture
async def project_with_mode(db: AsyncSession, test_user: User, test_org):
    project = Project(
        org_id=test_org.id,
        name="Test App",
        slug="test-app",
        created_by=test_user.id,
    )
    db.add(project)
    await db.flush()
    mode = ProjectMode(project_id=project.id, name="production", is_default=True)
    db.add(mode)
    await db.flush()
    await db.commit()
    await db.refresh(project)
    await db.refresh(mode)
    return project, mode


@pytest.fixture
async def device(db: AsyncSession, project_with_mode):
    project, mode = project_with_mode
    dev = Device(
        project_id=project.id,
        mode_id=mode.id,
        install_id="test-install-001",
        platform="ios",
        os_version="17.0",
        device_model="iPhone 15",
    )
    db.add(dev)
    await db.commit()
    await db.refresh(dev)
    return dev


@pytest.fixture
def sdk_headers(project_with_mode):
    project, mode = project_with_mode
    version_id = uuid.uuid4()
    token, _ = create_sdk_session_token(project.id, mode.id, version_id, "ios")
    return {"Authorization": f"Bearer {token}"}


# --- Event Ingestion Tests ---


@pytest.mark.asyncio
async def test_event_ingestion(client: AsyncClient, sdk_headers, device):
    response = await client.post(
        "/v1/events",
        json={
            "install_id": "test-install-001",
            "events": [
                {"name": "app_open", "properties": {"source": "push"}},
                {"name": "screen_view", "properties": {"screen": "home"}},
            ],
        },
        headers=sdk_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ingested"] == 2


@pytest.mark.asyncio
async def test_session_event(client: AsyncClient, sdk_headers, device):
    response = await client.post(
        "/v1/events/session",
        json={
            "install_id": "test-install-001",
            "session_id": "sess-abc-123",
            "action": "start",
        },
        headers=sdk_headers,
    )
    assert response.status_code == 200
    assert response.json()["event"] == "session_start"


# --- Crash Grouping Tests ---


def test_fingerprint_generation():
    stacktrace = """at com.app.Main.run(Main.java:42)
at com.app.Handler.handle(Handler.java:15)
at com.app.Router.route(Router.java:88)
at com.app.Server.start(Server.java:10)"""
    fp1 = generate_fingerprint("NullPointerException", stacktrace)
    fp2 = generate_fingerprint("NullPointerException", stacktrace)
    assert fp1 == fp2
    assert len(fp1) == 32

    # Different error type -> different fingerprint
    fp3 = generate_fingerprint("IOException", stacktrace)
    assert fp3 != fp1


def test_fingerprint_first_3_frames():
    st1 = """frame1
frame2
frame3
frame4_different"""
    st2 = """frame1
frame2
frame3
frame4_other"""
    # Same first 3 frames -> same fingerprint
    assert generate_fingerprint("E", st1) == generate_fingerprint("E", st2)


@pytest.mark.asyncio
async def test_crash_submission_creates_group(client: AsyncClient, sdk_headers, device):
    response = await client.post(
        "/v1/crashes",
        json={
            "install_id": "test-install-001",
            "error_type": "NullPointerException",
            "error_message": "Cannot invoke method on null",
            "stacktrace": "at Main.run(Main.java:42)\nat Handler.handle(Handler.java:15)\nat Router.route(Router.java:88)",
            "app_version": "1.0.0",
            "build_number": "100",
            "platform": "android",
            "os_version": "14",
            "device_model": "Pixel 8",
        },
        headers=sdk_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["error_type"] == "NullPointerException"
    assert data["group_id"] is not None


@pytest.mark.asyncio
async def test_crash_same_fingerprint_increments_group(client: AsyncClient, sdk_headers, device, db: AsyncSession):
    crash_body = {
        "install_id": "test-install-001",
        "error_type": "TypeError",
        "error_message": "undefined is not a function",
        "stacktrace": "at app.js:10\nat handler.js:5\nat router.js:20",
        "app_version": "2.0.0",
        "build_number": "200",
        "platform": "ios",
        "os_version": "17",
        "device_model": "iPhone 15",
    }
    r1 = await client.post("/v1/crashes", json=crash_body, headers=sdk_headers)
    assert r1.status_code == 201
    group_id = r1.json()["group_id"]

    r2 = await client.post("/v1/crashes", json=crash_body, headers=sdk_headers)
    assert r2.status_code == 201
    assert r2.json()["group_id"] == group_id

    # Verify count incremented
    async with TestSession() as session:
        result = await session.execute(select(CrashGroup).where(CrashGroup.id == uuid.UUID(group_id)))
        group = result.scalar_one()
        assert group.count == 2


# --- Experiment Assignment Tests ---


def test_deterministic_assignment():
    """Assignment should be deterministic for same experiment+device."""
    exp_id = uuid.uuid4()
    dev_id = uuid.uuid4()

    class MockVariant:
        def __init__(self, vid, name, weight):
            self.id = vid
            self.name = name
            self.weight = weight

    variants = [
        MockVariant(uuid.uuid4(), "control", 50),
        MockVariant(uuid.uuid4(), "treatment", 50),
    ]

    result1 = deterministic_assign(exp_id, dev_id, variants)
    result2 = deterministic_assign(exp_id, dev_id, variants)
    assert result1.id == result2.id

    # Different device may get different variant (probabilistic, but deterministic)
    other_dev = uuid.uuid4()
    result3 = deterministic_assign(exp_id, other_dev, variants)
    # Just verify it returns a valid variant
    assert result3.id in [v.id for v in variants]


@pytest.mark.asyncio
async def test_experiment_assignment_via_api(client: AsyncClient, sdk_headers, device, db: AsyncSession, project_with_mode, test_user):
    project, mode = project_with_mode
    # Create experiment with variants
    experiment = Experiment(
        project_id=project.id,
        mode_id=mode.id,
        name="Button Color Test",
        status=ExperimentStatusEnum.running,
        traffic_pct=100,
        created_by=test_user.id,
    )
    db.add(experiment)
    await db.flush()

    v1 = ExperimentVariant(experiment_id=experiment.id, name="red", weight=50)
    v2 = ExperimentVariant(experiment_id=experiment.id, name="blue", weight=50)
    db.add(v1)
    db.add(v2)
    await db.commit()

    response = await client.get(
        "/v1/experiments/assignments",
        headers=sdk_headers,
    )
    assert response.status_code == 200
    data = response.json()["assignments"]
    assert len(data) == 1
    assert data[0]["experiment_name"] == "Button Color Test"
    assert data[0]["variant"] in ["red", "blue"]

    # Second call should return same assignment
    response2 = await client.get(
        "/v1/experiments/assignments",
        headers=sdk_headers,
    )
    assert response2.json()["assignments"][0]["variant"] == data[0]["variant"]


# --- Deep Link Tests ---


@pytest.mark.asyncio
async def test_deep_link_redirect(client: AsyncClient, db: AsyncSession, project_with_mode, test_user):
    from app.models.deep_link import DeepLink

    project, mode = project_with_mode
    link = DeepLink(
        project_id=project.id,
        mode_id=mode.id,
        slug="promo-summer",
        title="Summer Promo",
        ios_url="https://apps.apple.com/app/123",
        android_url="https://play.google.com/store/apps/details?id=com.app",
        fallback_url="https://example.com/promo",
        created_by=test_user.id,
    )
    db.add(link)
    await db.commit()

    # iOS user-agent
    response = await client.get(
        "/dl/promo-summer",
        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "apps.apple.com" in response.headers["location"]

    # Android user-agent
    response = await client.get(
        "/dl/promo-summer",
        headers={"User-Agent": "Mozilla/5.0 (Linux; Android 14)"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "play.google.com" in response.headers["location"]

    # Desktop -> fallback
    response = await client.get(
        "/dl/promo-summer",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "example.com/promo" in response.headers["location"]


@pytest.mark.asyncio
async def test_deep_link_click_counter(client: AsyncClient, db: AsyncSession, project_with_mode, test_user):
    from app.models.deep_link import DeepLink

    project, mode = project_with_mode
    link = DeepLink(
        project_id=project.id,
        mode_id=mode.id,
        slug="click-test",
        title="Click Test",
        fallback_url="https://example.com",
        created_by=test_user.id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    await client.get("/dl/click-test", follow_redirects=False)
    await client.get("/dl/click-test", follow_redirects=False)

    async with TestSession() as session:
        result = await session.execute(select(DeepLink).where(DeepLink.slug == "click-test"))
        updated = result.scalar_one()
        assert updated.clicks == 2
