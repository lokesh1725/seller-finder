"""Search endpoints: GET /api/search and POST /api/search."""
from __future__ import annotations

from flask import jsonify, request

from . import api, enforce_rate_limit
from .auth import require_auth
from ..db import DatabaseUnavailable
from ..errors import ServiceUnavailable, ValidationError
from ..services import aggregator


def _int_arg(name: str, default: int, minimum: int = 1, maximum: int = 100) -> int:
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"'{name}' must be an integer")
    return max(minimum, min(maximum, value))


@api.get("/search")
@require_auth
def search_get():
    enforce_rate_limit()
    query = (request.args.get("q") or "").strip()
    category = request.args.get("category") or None
    city = request.args.get("city") or None
    if not query and not category and not city:
        raise ValidationError("Query parameter 'q' is required")
    if len(query) > 200:
        raise ValidationError("Query is too long")
    try:
        payload = aggregator.search(
            query=query,
            category=category,
            city=city,
            limit=_int_arg("limit", 25),
            offset=_int_arg("offset", 0, minimum=0, maximum=10000),
        )
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    return jsonify(payload)


@api.post("/search")
@require_auth
def search_post():
    enforce_rate_limit()
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or body.get("q") or "").strip()
    if not query:
        raise ValidationError("Field 'query' is required")
    if len(query) > 200:
        raise ValidationError("Query is too long")
    if not isinstance(body.get("allow_web", True), bool):
        raise ValidationError("'allow_web' must be a boolean")
    try:
        payload = aggregator.search(
            query=query,
            category=(body.get("category") or None),
            city=(body.get("city") or None),
            limit=int(body.get("limit", 25)),
            offset=int(body.get("offset", 0)),
            allow_web=body.get("allow_web", True),
        )
    except (TypeError, ValueError):
        raise ValidationError("Numeric search options are invalid")
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    return jsonify(payload)
