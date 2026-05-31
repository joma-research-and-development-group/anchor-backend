from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.legal_acceptance import LegalAcceptance
from app.models.legal_document import LegalDocument

router = APIRouter()


@router.get("/legal/pending")
async def get_pending_legal(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return active legal docs requiring acceptance. SDK: GET /v1/legal/pending"""
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(LegalDocument).where(
            LegalDocument.project_id == session["project_id"],
            LegalDocument.mode_id == session["mode_id"],
            LegalDocument.is_active.is_(True),
            LegalDocument.requires_acceptance.is_(True),
        )
    )
    docs = list(result.scalars().all())
    # Check which are already accepted by this device
    accepted_ids: set[UUID] = set()
    if docs:
        acc_result = await db.execute(
            select(LegalAcceptance.document_id).where(
                LegalAcceptance.device_id == device.id,
                LegalAcceptance.document_id.in_([d.id for d in docs]),
            )
        )
        accepted_ids = {row[0] for row in acc_result.all()}
    # SDK LegalDocument.fromMap expects: id, title, version, url, accepted
    return [
        {
            "id": str(doc.id),
            "title": doc.title,
            "version": str(doc.version),
            "url": doc.content if doc.content.startswith("http") else None,
            "accepted": doc.id in accepted_ids,
        }
        for doc in docs
        if doc.id not in accepted_ids
    ]


@router.post("/legal/{doc_id}/accept")
async def accept_legal(
    doc_id: UUID,
    request: Request,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Accept a legal document. SDK: POST /v1/legal/{doc_id}/accept (no body)"""
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(LegalDocument).where(
            LegalDocument.id == doc_id,
            LegalDocument.project_id == session["project_id"],
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Legal document not found")
    # Check if already accepted
    result = await db.execute(
        select(LegalAcceptance).where(
            LegalAcceptance.document_id == doc_id,
            LegalAcceptance.device_id == device.id,
        )
    )
    if not result.scalar_one_or_none():
        ip = request.client.host if request.client else None
        acceptance = LegalAcceptance(document_id=doc_id, device_id=device.id, ip=ip)
        db.add(acceptance)
        await db.flush()
    return {"status": "accepted"}
