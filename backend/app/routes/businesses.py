"""Business profile endpoints."""
from __future__ import annotations

import re

from flask import jsonify, request

from . import api, enforce_rate_limit
from ..db import DatabaseUnavailable
from ..errors import NotFound, ServiceUnavailable, ValidationError
from ..services import aggregator, verification

_IDENTIFIER_RE = re.compile(r"^[a-z0-9\-_.]{1,120}$", re.IGNORECASE)


def _validate_identifier(identifier: str) -> str:
    if not identifier or not _IDENTIFIER_RE.match(identifier):
        raise ValidationError("Invalid business identifier")
    return identifier


@api.get("/businesses/<identifier>")
def get_business(identifier: str):
    enforce_rate_limit()
    _validate_identifier(identifier)
    try:
        doc = aggregator.find_by_slug_or_id(identifier)
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    if not doc:
        raise NotFound("Business not found")
    doc["verification_summary"] = verification.summarize(
        doc.get("field_verification_status", {})
    )
    return jsonify(doc)


@api.post("/businesses/<identifier>/refresh")
def refresh_business(identifier: str):
    enforce_rate_limit()
    _validate_identifier(identifier)
    try:
        result = aggregator.refresh_business(identifier)
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    if not result.get("found"):
        raise NotFound("Business not found")
    return jsonify(result)
