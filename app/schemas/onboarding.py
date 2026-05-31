from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.onboarding_flow import OnboardingTriggerEnum


class OnboardingSlideCreate(BaseModel):
    order: int
    title: str
    description: str
    image_url: str | None = None
    bg_color: str | None = None
    action_label: str | None = None
    action_url: str | None = None


class OnboardingSlideUpdate(BaseModel):
    order: int | None = None
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    bg_color: str | None = None
    action_label: str | None = None
    action_url: str | None = None


class OnboardingSlideResponse(BaseModel):
    id: UUID
    flow_id: UUID
    order: int
    title: str
    description: str
    image_url: str | None = None
    bg_color: str | None = None
    action_label: str | None = None
    action_url: str | None = None

    model_config = {"from_attributes": True}


class OnboardingFlowCreate(BaseModel):
    mode_id: UUID
    name: str
    trigger: OnboardingTriggerEnum
    target_version: str | None = None
    is_active: bool = True
    priority: int = 0
    slides: list[OnboardingSlideCreate] = []


class OnboardingFlowUpdate(BaseModel):
    name: str | None = None
    trigger: OnboardingTriggerEnum | None = None
    target_version: str | None = None
    is_active: bool | None = None
    priority: int | None = None


class OnboardingFlowResponse(BaseModel):
    id: UUID
    project_id: UUID
    mode_id: UUID
    name: str
    trigger: OnboardingTriggerEnum
    target_version: str | None = None
    is_active: bool
    priority: int
    created_by: UUID
    created_at: datetime
    slides: list[OnboardingSlideResponse] = []

    model_config = {"from_attributes": True}
