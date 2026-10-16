"""Extended evidence-based verification per field."""
from __future__ import annotations

from typing import Any, Dict
from ..utils import utcnow

STATUSES = {"verified", "officially_published", "partially_verified", "unverified", "not_found", "unavailable"}

def create_field_evidence(field: str, value: Any, source_url: str | None = None, source_type: str | None = None, confidence: float = 0.5, status: str = "unverified", evidence: str = "") -> Dict[str, Any]:
    return {
        "field": field,
        "value": value,
        "source_url": source_url,
        "source_type": source_type,
        "date_checked": utcnow().isoformat(),
        "verification_status": status if status in STATUSES else "unverified",
        "confidence_score": confidence,
        "evidence_snippets": [evidence] if evidence else [],
    }
