"""Seed script: creates demo data for development."""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session
from app.core.security import hash_password
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User


async def seed() -> None:
    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(User).where(User.email == "admin@anchor.dev"))
        if result.scalar_one_or_none():
            print("Already seeded.")
            return

        user = User(
            email="admin@anchor.dev",
            password_hash=hash_password("password123"),
            full_name="Anchor Admin",
        )
        db.add(user)
        await db.flush()

        org = Organization(name="Acme Corp", slug="acme-org", created_by=user.id)
        db.add(org)
        await db.flush()

        member = OrgMember(org_id=org.id, user_id=user.id, role=RoleEnum.owner)
        db.add(member)
        await db.flush()

        project = Project(
            org_id=org.id, name="Demo App", slug="demo-app", created_by=user.id
        )
        db.add(project)
        await db.flush()

        for mode_name, is_default in [("dev", True), ("beta", False), ("prod", False)]:
            mode = ProjectMode(project_id=project.id, name=mode_name, is_default=is_default)
            db.add(mode)

        await db.commit()
        print("Seeded: admin@anchor.dev / password123, acme-org, demo-app (dev/beta/prod)")


if __name__ == "__main__":
    asyncio.run(seed())
