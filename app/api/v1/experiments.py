from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.sdk_auth import get_sdk_session
from app.core.sdk_device import get_or_create_session_device
from app.models.event import Event
from app.models.experiment import Experiment, ExperimentStatusEnum
from app.models.experiment_assignment import ExperimentAssignment
from app.models.experiment_variant import ExperimentVariant
from app.services.experiment_assigner import deterministic_assign

router = APIRouter()


class ExposureBody(BaseModel):
    experiment_name: str
    variant: str | None = None


@router.get("/experiments/assignments")
async def get_assignments(
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """SDK: GET /v1/experiments/assignments → {"assignments": [{experiment_name, variant}]}"""
    device = await get_or_create_session_device(db, session)
    result = await db.execute(
        select(Experiment).where(
            Experiment.project_id == session["project_id"],
            Experiment.mode_id == session["mode_id"],
            Experiment.status == ExperimentStatusEnum.running,
        )
    )
    experiments = list(result.scalars().all())
    assignments: list[dict] = []
    for exp in experiments:
        result = await db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.experiment_id == exp.id,
                ExperimentAssignment.device_id == device.id,
            )
        )
        assignment = result.scalar_one_or_none()
        if assignment:
            result = await db.execute(select(ExperimentVariant).where(ExperimentVariant.id == assignment.variant_id))
            variant = result.scalar_one_or_none()
        else:
            result = await db.execute(select(ExperimentVariant).where(ExperimentVariant.experiment_id == exp.id))
            variants = list(result.scalars().all())
            if not variants:
                continue
            variant = deterministic_assign(exp.id, device.id, variants)
            assignment = ExperimentAssignment(experiment_id=exp.id, device_id=device.id, variant_id=variant.id)
            db.add(assignment)
            await db.flush()
        if variant:
            # SDK ExperimentAssignment.fromMap expects: experiment_name, variant
            assignments.append({"experiment_name": exp.name, "variant": variant.name})
    return {"assignments": assignments}


@router.post("/experiments/exposure")
async def track_exposure(
    body: ExposureBody,
    session: dict[str, Any] = Depends(get_sdk_session),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """SDK: POST /v1/experiments/exposure with {experiment_name, variant}"""
    device = await get_or_create_session_device(db, session)
    event = Event(
        project_id=session["project_id"],
        mode_id=session["mode_id"],
        device_id=device.id,
        name=f"experiment_exposure:{body.experiment_name}",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return {"status": "tracked"}
