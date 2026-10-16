"""Field-level verification helpers.

The core rule: having a value is not the same as having a *verified* value.
Each important field records where the value came from and its status:

* ``verified``    - confirmed against an authoritative public source
* ``unverified``  - present in the source data but not independently confirmed
* ``unavailable`` - no reliable public value could be found
"""
from __future__ import annotations

from ..utils import utcnow

VERIFIED = "verified"
UNVERIFIED = "unverified"
UNAVAILABLE = "unavailable"

TRACKED_FIELDS = (
    "official_website",
    "business_email",
    "business_phone",
    "linkedin_company_url",
    "founder_name",
    "ceo_name",
    "business_address",
)


def make_status(status: str, source: str | None = None, note: str | None = None) -> dict:
    entry = {
        "status": status,
        "source": source,
        "last_verified_at": utcnow().isoformat() if status == VERIFIED else None,
    }
    if note:
        entry["note"] = note
    return entry


def status_for_value(value, source: str | None) -> dict:
    """Unverified by default -- a well-formatted value is not proof of truth."""
    if value in (None, "", [], {}):
        return make_status(UNAVAILABLE, None)
    return make_status(UNVERIFIED, source)


def build_field_statuses(document: dict, source: str | None = None) -> dict:
    statuses = {}
    for field in TRACKED_FIELDS:
        statuses[field] = status_for_value(document.get(field), source)
    return statuses


def summarize(statuses: dict) -> dict:
    counts = {VERIFIED: 0, UNVERIFIED: 0, UNAVAILABLE: 0}
    for entry in (statuses or {}).values():
        status = (entry or {}).get("status")
        if status in counts:
            counts[status] += 1
    present = counts[VERIFIED] + counts[UNVERIFIED]
    total =present + counts[UNAVAILABLE]
    return {
        "counts": counts,
        "fields_with_data": present,
        "fields_total": total,
        "coverage": round(present / total, 2) if total else 0.0,
    }
