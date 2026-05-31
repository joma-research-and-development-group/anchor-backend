from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.legal_acceptance import LegalAcceptance
from app.models.legal_document import LegalDocument
from app.models.org_member import OrgMember, RoleEnum
from app.models.organization import Organization
from app.models.project import Project, ProjectMode
from app.models.user import User
from app.schemas.legal import LegalAcceptanceResponse, LegalDocCreate, LegalDocResponse, LegalDocUpdate

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


@router.get("/{org_slug}/projects/{proj_slug}/legal", response_model=list[LegalDocResponse])
async def list_legal_docs(
    org_slug: str,
    proj_slug: str,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[LegalDocument]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(
        select(LegalDocument).where(LegalDocument.project_id == project.id).order_by(LegalDocument.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{org_slug}/projects/{proj_slug}/legal", response_model=LegalDocResponse, status_code=201)
async def create_legal_doc(
    org_slug: str,
    proj_slug: str,
    body: LegalDocCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> LegalDocument:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(ProjectMode).where(ProjectMode.id == body.mode_id, ProjectMode.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Mode not found")
    doc = LegalDocument(
        project_id=project.id,
        mode_id=body.mode_id,
        type=body.type,
        title=body.title,
        content=body.content,
        version=body.version,
        locale=body.locale,
        is_active=body.is_active,
        requires_acceptance=body.requires_acceptance,
        published_at=body.published_at,
        created_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "legal.created", "legal_document", str(doc.id), request=request)
    return doc


@router.patch("/{org_slug}/projects/{proj_slug}/legal/{doc_id}", response_model=LegalDocResponse)
async def update_legal_doc(
    org_slug: str,
    proj_slug: str,
    doc_id: UUID,
    body: LegalDocUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> LegalDocument:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(LegalDocument).where(LegalDocument.id == doc_id, LegalDocument.project_id == project.id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Legal document not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    await db.flush()
    await write_audit(db, org.id, current_user.id, "legal.updated", "legal_document", str(doc_id), request=request)
    return doc


@router.delete("/{org_slug}/projects/{proj_slug}/legal/{doc_id}", status_code=204)
async def delete_legal_doc(
    org_slug: str,
    proj_slug: str,
    doc_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    _member: OrgMember = Depends(require_role(RoleEnum.editor)),
    db: AsyncSession = Depends(get_db),
) -> None:
    org, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(LegalDocument).where(LegalDocument.id == doc_id, LegalDocument.project_id == project.id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Legal document not found")
    await write_audit(db, org.id, current_user.id, "legal.deleted", "legal_document", str(doc_id), request=request)
    await db.delete(doc)
    await db.flush()


@router.get("/{org_slug}/projects/{proj_slug}/legal/{doc_id}/acceptances", response_model=list[LegalAcceptanceResponse])
async def list_acceptances(
    org_slug: str,
    proj_slug: str,
    doc_id: UUID,
    _member: OrgMember = Depends(require_role(RoleEnum.viewer)),
    db: AsyncSession = Depends(get_db),
) -> list[LegalAcceptance]:
    _, project = await _get_project(db, org_slug, proj_slug)
    result = await db.execute(select(LegalDocument).where(LegalDocument.id == doc_id, LegalDocument.project_id == project.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Legal document not found")
    result = await db.execute(
        select(LegalAcceptance).where(LegalAcceptance.document_id == doc_id).order_by(LegalAcceptance.accepted_at.desc())
    )
    return list(result.scalars().all())
