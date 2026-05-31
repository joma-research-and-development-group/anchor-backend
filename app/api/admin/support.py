from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project
from app.models.support_conversation import ConversationStatusEnum, SupportConversation
from app.models.support_message import SenderTypeEnum, SupportMessage
from app.models.user import User
from app.schemas.support import ConversationResponse, MessageCreate, MessageResponse

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


@router.get("/{org_slug}/projects/{proj_slug}/support/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    org_slug: str,
    proj_slug: str,
    status: ConversationStatusEnum | None = Query(None),
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[SupportConversation]:
    _, project = await _get_project(db, org_slug, proj_slug)
    stmt = select(SupportConversation).where(SupportConversation.project_id == project.id)
    if status:
        stmt = stmt.where(SupportConversation.status == status)
    stmt = stmt.order_by(SupportConversation.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{org_slug}/projects/{proj_slug}/support/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    org_slug: str,
    proj_slug: str,
    conv_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[SupportMessage]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(SupportConversation).where(SupportConversation.id == conv_id, SupportConversation.project_id == project.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await db.execute(
        select(SupportMessage).where(SupportMessage.conversation_id == conv_id).order_by(SupportMessage.created_at.asc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/support/conversations/{conv_id}/messages", response_model=MessageResponse, status_code=201)
async def reply_to_conversation(
    org_slug: str,
    proj_slug: str,
    conv_id: UUID,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> SupportMessage:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(SupportConversation).where(SupportConversation.id == conv_id, SupportConversation.project_id == project.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msg = SupportMessage(
        conversation_id=conv_id,
        sender_type=SenderTypeEnum.admin,
        sender_id=current_user.id,
        body=body.body,
        attachment_url=body.attachment_url,
    )
    db.add(msg)
    conv.status = ConversationStatusEnum.waiting
    conv.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return msg
