from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ModelUsage(BaseModel):
    model: str
    requests: int
    total_tokens: int


class ProfileUsage(BaseModel):
    profile: str
    requests: int
    total_tokens: int


class UserUsage(BaseModel):
    user_id: int
    email: str | None = None
    requests: int
    total_tokens: int


class RecentActivity(BaseModel):
    id: int
    actor_user_id: int | None
    actor_email: str | None
    action: str
    resource_type: str
    resource_name: str | None
    created_at: datetime


class DashboardSummary(BaseModel):
    total_users: int

    active_users: int

    total_deployments: int

    active_deployments: int

    total_requests: int

    total_prompt_tokens: int

    total_completion_tokens: int

    total_tokens: int

    usage_by_model: list[ModelUsage]

    usage_by_profile: list[ProfileUsage]

    usage_by_user: list[UserUsage]

    recent_activity: list[RecentActivity]
