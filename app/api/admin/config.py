from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.config_entry import ConfigEntry
from app.models.config_override import ConfigOverride
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.config import (
    ConfigEntryCreate,
    ConfigEntryResponse,
    ConfigEntryUpdate,
    ConfigOverrideCreate,
    ConfigOverrideResponse,
    ConfigOverrideUpdate,
)

router = APIRouter()


async def _get_project(db: AsyncSession, org_slug: str, proj_slug: str) -> tuple[Organization, Project]:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = await db.execute(
        select(Project).where(Project.org_id == org.id, Project.slug == proj_slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return org, project


async def _build_entry_response(db: AsyncSession, entry: ConfigEntry) -> dict:
    result = await db.execute(
        select(ConfigOverride).where(ConfigOverride.entry_id == entry.id).order_by(ConfigOverride.priority.desc())
    )
    overrides = list(result.scalars().all())
    return {
        "id": entry.id,
        "project_id": entry.project_id,
        "mode_id": entry.mode_id,
        "key": entry.key,
        "value_type": entry.value_type,
        "default_value": entry.default_value,
        "description": entry.description,
        "updated_at": entry.updated_at,
        "overrides": overrides,
    }


@router.get("/{org_slug}/projects/{proj_slug}/config", response_model=list[ConfigEntryResponse])
async def list_config(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ConfigEntry).where(ConfigEntry.project_id == project.id).order_by(ConfigEntry.key)
    )
    entries = list(result.scalars().all())
    return [await _build_entry_response(db, e) for e in entries]


@router.post("/{org_slug}/projects/{proj_slug}/config", response_model=ConfigEntryResponse, status_code=201)
async def create_config_entry(
    org_slug: str,
    proj_slug: str,
    body: ConfigEntryCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org, project = await _get_project(db, org_slug, proj_slug)
    # Verify mode
    result = await db.execute(
        select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    entry = ConfigEntry(
        project_id=project.id,
        mode_id=body.mode_id,
        key=body.key,
        value_type=body.value_type,
        default_value=body.default_value,
        description=body.description,
    )
    db.add(entry)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "config.created", "config_entry", str(entry.id), request=request)
    return await _build_entry_response(db, entry)


@router.patch("/{org_slug}/projects/{proj_slug}/config/{entry_id}", response_model=ConfigEntryResponse)
async def update_config_entry(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    body: ConfigEntryUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ConfigEntry).where(ConfigEntry.id == entry_id, ConfigEntry.project_id == project.id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Config entry not found")
    if body.default_value is not None:
        entry.default_value = body.default_value
    if body.description is not None:
        entry.description = body.description
    entry.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "config.updated", "config_entry", str(entry_id), request=request)
    return await _build_entry_response(db, entry)


@router.delete("/{org_slug}/projects/{proj_slug}/config/{entry_id}", status_code=204)
async def delete_config_entry(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ConfigEntry).where(ConfigEntry.id == entry_id, ConfigEntry.project_id == project.id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Config entry not found")
    await write_audit(db, org.id, current_user.id, "config.deleted", "config_entry", str(entry_id), request=request)
    await db.delete(entry)
    await db.flush()


@router.post("/{org_slug}/projects/{proj_slug}/config/{entry_id}/overrides", response_model=ConfigOverrideResponse, status_code=201)
async def create_override(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    body: ConfigOverrideCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> ConfigOverride:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ConfigEntry).where(ConfigEntry.id == entry_id, ConfigEntry.project_id == project.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Config entry not found")
    override = ConfigOverride(
        entry_id=entry_id,
        conditions=body.conditions,
        value=body.value,
        priority=body.priority,
    )
    db.add(override)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "config_override.created", "config_override", str(override.id), request=request)
    return override


@router.patch("/{org_slug}/projects/{proj_slug}/config/{entry_id}/overrides/{override_id}", response_model=ConfigOverrideResponse)
async def update_override(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    override_id: UUID,
    body: ConfigOverrideUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> ConfigOverride:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ConfigOverride).where(ConfigOverride.id == override_id, ConfigOverride.entry_id == entry_id)
    )
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")
    if body.conditions is not None:
        override.conditions = body.conditions
    if body.value is not None:
        override.value = body.value
    if body.priority is not None:
        override.priority = body.priority
    await db.flush()
    await write_audit(db, org.id, current_user.id, "config_override.updated", "config_override", str(override_id), request=request)
    return override


@router.delete("/{org_slug}/projects/{proj_slug}/config/{entry_id}/overrides/{override_id}", status_code=204)
async def delete_override(
    org_slug: str,
    proj_slug: str,
    entry_id: UUID,
    override_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(ConfigOverride).where(ConfigOverride.id == override_id, ConfigOverride.entry_id == entry_id)
    )
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")
    await write_audit(db, org.id, current_user.id, "config_override.deleted", "config_override", str(override_id), request=request)
    await db.delete(override)
    await db.flush()
