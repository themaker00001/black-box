from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _incident_id(at: datetime) -> str:
    return f"{at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


class Incident(BaseModel):
    incident_id: str
    created_at: datetime
    trigger_name: str
    trigger_reason: str
    trigger_details: dict[str, Any] = Field(default_factory=dict)
    output_dir: str
    event_count: int = 0

    @classmethod
    def new(cls, trigger_name: str, trigger_reason: str, trigger_details: dict, base_dir: str) -> "Incident":
        created_at = datetime.now(timezone.utc)
        incident_id = _incident_id(created_at)
        return cls(
            incident_id=incident_id,
            created_at=created_at,
            trigger_name=trigger_name,
            trigger_reason=trigger_reason,
            trigger_details=trigger_details,
            output_dir=f"{base_dir}/{incident_id}",
        )
