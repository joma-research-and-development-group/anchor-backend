import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import get_db
from app.core.security import create_access_token, hash_password
from app.models.user import Base, User
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        full_name="Test User",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def test_org(db: AsyncSession, test_user: User) -> Organization:
    org = Organization(name="Test Org", slug="test-org", created_by=test_user.id)
    db.add(org)
    await db.flush()
    member = OrgMember(org_id=org.id, user_id=test_user.id, role=RoleEnum.owner)
    db.add(member)
    await db.commit()
    await db.refresh(org)
    return org


@pytest.fixture
def auth_cookies(test_user: User) -> dict[str, str]:
    token = create_access_token(str(test_user.id))
    return {"access_token": token}


@pytest.fixture
async def authed_client(client: AsyncClient, auth_cookies: dict[str, str]) -> AsyncClient:
    client.cookies.set("access_token", auth_cookies["access_token"])
    return client
