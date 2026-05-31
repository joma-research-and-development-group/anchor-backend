from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ExperimentVariantCreate(BaseModel):
    name: str
    weight: int = 50
    payload: dict | None = None


class ExperimentVariantResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    name: str
    weight: int
    payload: dict | None = None

    model_config = {"from_attributes": True}


class ExperimentCreate(BaseModel):
    mode_id: UUID
    name: str
    description: str | None = None
    traffic_pct: int = 100
    variants: list[ExperimentVariantCreate] = []


class ExperimentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    traffic_pct: int | None = None


class ExperimentResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    name: str
    description: str | None = None
    status: str
    traffic_pct: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ExperimentWithVariants(ExperimentResponse):
    variants: list[ExperimentVariantResponse] = []


class AssignmentResponse(BaseModel):
    experiment_id: UUID
    experiment_name: str
    variant_id: UUID
    variant_name: str
    payload: dict | None = None


class ExperimentResultVariant(BaseModel):
    variant_id: UUID
    variant_name: str
    assignment_count: int


class ExperimentResults(BaseModel):
    experiment_id: UUID
    total_assignments: int
    variants: list[ExperimentResultVariant]
