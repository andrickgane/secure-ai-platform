from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventRecord(BaseModel):
    id: int

    actor_user_id: int | None

    action: str

    resource_type: str

    resource_name: str | None

    details: dict[str, Any]

    created_at: datetime
