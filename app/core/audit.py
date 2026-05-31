from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def write_audit(
    db: AsyncSession,
    org_id: UUID,
    actor_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    meta: dict | None = None,
    request: Request | None = None,
) -> None:
    ip = None
    user_agent = None
    if request:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    log = AuditLog(
        org_id=org_id,
        actor_user_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        meta=meta or {},
        ip=ip,
        user_agent=user_agent,
    )
    db.add(log)
    await db.flush()
