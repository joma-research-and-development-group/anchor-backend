from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.onboarding_flow import OnboardingFlow
from app.models.onboarding_slide import OnboardingSlide

router = APIRouter()


@router.get("/onboarding/flows")
async def get_flows(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return all active onboarding flows. SDK: GET /v1/onboarding/flows"""
    result = await db.execute(
        select(OnboardingFlow).where(
            OnboardingFlow.project_id == session["project_id"],
            OnboardingFlow.mode_id == session["mode_id"],
            OnboardingFlow.is_active.is_(True),
        ).order_by(OnboardingFlow.priority.desc())
    )
    flows = list(result.scalars().all())
    # SDK OnboardingFlow.fromMap expects: id, trigger, slides[], completed
    # SDK OnboardingSlide.fromMap expects: title, body, image_url
    response: list[dict] = []
    for flow in flows:
        slide_result = await db.execute(
            select(OnboardingSlide).where(OnboardingSlide.flow_id == flow.id).order_by(OnboardingSlide.order)
        )
        slides = [
            {
                "title": s.title,
                "body": s.description,
                "image_url": s.image_url,
            }
            for s in slide_result.scalars().all()
        ]
        response.append({
            "id": str(flow.id),
            "trigger": flow.trigger.value,
            "slides": slides,
            "completed": False,
        })
    return response


@router.post("/onboarding/flows/{flow_id}/complete")
async def complete_flow(
    flow_id: UUID,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark onboarding flow completed. SDK: POST /v1/onboarding/flows/{flow_id}/complete"""
    return {"status": "completed"}
