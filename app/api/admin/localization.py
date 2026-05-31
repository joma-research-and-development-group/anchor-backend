from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.localization import LocalizationEntry
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.localization import (
    LocalizationBulkUpsert,
    LocalizationEntryCreate,
    LocalizationEntryResponse,
    LocalizationEntryUpdate,
)

router = APIRouter()


async def _get_project(db: AsyncSession, org_slug: str, proj_slug: str) -> tuple[Organization, Project]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(select(Project).where(Project.org_id == org.id, Project.slug == proj_slug))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return org, project


@router.get("/{org_slug}/projects/{proj_slug}/localization", response_model=list[LocalizationEntryResponse])
async def list_entries(
    org_slug: str,
    proj_slug: str,
    locale: str | None = Query(None),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[LocalizationEntry]:
    _, project = await _get_project(db, org_slug, proj_slug)
    stmt = select(LocalizationEntry).where(LocalizationEntry.project_id == project.id)
    if locale:
        stmt = stmt.where(LocalizationEntry.locale == locale)
    result = await db.execute(stmt.order_by(LocalizationEntry.key))
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/localization", response_model=LocalizationEntryResponse, status_code=201)
async def create_entry(
    org_slug: str,
    proj_slug: str,
    body: LocalizationEntryCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> LocalizationEntry:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    entry = LocalizationEntry(
        project_id=project.id,
        mode_id=body.mode_id,
        key=body.key,
        locale=body.locale,
        value=body.value,
    )
    db.add(entry)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "localization.created", "localization", str(entry.id), request=request)
    return entry


@router.put("/{org_slug}/projects/{proj_slug}/localization/bulk", response_model=list[LocalizationEntryResponse])
async def bulk_upsert(
    org_slug: str,
    proj_slug: str,
    body: LocalizationBulkUpsert,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> list[LocalizationEntry]:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    results: list[LocalizationEntry] = []
    for item in body.entries:
        result = await db.execute(
            select(LocalizationEntry).where(
                LocalizationEntry.project_id == project.id,
                LocalizationEntry.mode_id == body.mode_id,
                LocalizationEntry.key == item.key,
                LocalizationEntry.locale == item.locale,
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            entry.value = item.value
            entry.updated_at = datetime.now(timezone.utc)
        else:
            entry = LocalizationEntry(
                project_id=project.id,
                mode_id=body.mode_id,
                key=item.key,
                locale=item.locale,
                value=item.value,
            )
            db.add(entry)
        await db.flush()
        results.append(entry)
    await write_audit(db, org.id, current_user.id, "localization.bulk_upsert", "localization", meta={"count": len(body.entries)}, request=request)
    return results


@router.patch("/{org_slug}/projects/{proj_slug}/localization/{entry_id}", response_model=LocalizationEntryResponse)
async def update_entry(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    body: LocalizationEntryUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> LocalizationEntry:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(LocalizationEntry).where(LocalizationEntry.id == entry_id, LocalizationEntry.project_id == project.id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.value = body.value
    entry.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "localization.updated", "localization", str(entry_id), request=request)
    return entry


@router.delete("/{org_slug}/projects/{proj_slug}/localization/{entry_id}", status_code=204)
async def delete_entry(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(LocalizationEntry).where(LocalizationEntry.id == entry_id, LocalizationEntry.project_id == project.id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await write_audit(db, org.id, current_user.id, "localization.deleted", "localization", str(entry_id), request=request)
    await db.delete(entry)
    await db.flush()
