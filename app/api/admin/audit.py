import base64
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.audit_log import AuditLog
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.schemas.audit import AuditListResponse
from app.schemas.audit import AuditLogResponse

router = APIRouter()


@router.get("/{org_slug}/audit", response_model=AuditListResponse)
async def list_audit_logs(
    org_slug: str,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    actor_id: UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    _member: OrgMember = Depends(require_role(RoleEnum.admin)),
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    result = await db.execute(select(Organization).where(Organization.slug == org_slug))
    org = result.scalar_one_or_none()
    if not org:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Organization not found")

    query = select(AuditLog).where(AuditLog.org_id == org.id)

    if action:
        query = query.where(AuditLog.action == action)
    if actor_id:
        query = query.where(AuditLog.actor_user_id == actor_id)
    if date_from:
        query = query.where(AuditLog.at >= date_from)
    if date_to:
        query = query.where(AuditLog.at <= date_to)

    if cursor:
        decoded_id = int(base64.b64decode(cursor).decode())
        query = query.where(AuditLog.id < decoded_id)

    query = query.order_by(AuditLog.id.desc()).limit(limit + 1)
    result = await db.execute(query)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_more and items:
        next_cursor = base64.b64encode(str(items[-1].id).encode()).decode()

    return AuditListResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
