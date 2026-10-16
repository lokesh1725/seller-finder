"""Research endpoints."""
from __future__ import annotations

from flask import jsonify, request

from . import api, enforce_rate_limit
from .auth import require_auth
from ..errors import ValidationError
from ..services import company_research_service

@api.post("/research")
@require_auth
def research_start():
    enforce_rate_limit()
    body = request.get_json(silent=True) or {}
    name = (body.get("company_name") or body.get("query") or "").strip()
    if not name:
        raise ValidationError("company_name is required")
    job = company_research_service.start_research(name)
    # optionally run async stub
    try:
        company_research_service.research_company(name, job_id=job["job_id"])
    except Exception:
        pass
    return jsonify(company_research_service.get_research(job["job_id"]))

@api.get("/research/<job_id>")
@require_auth
def research_get(job_id: str):
    job = company_research_service.get_research(job_id)
    if not job:
        raise ValidationError("job not found")
    return jsonify(job)

@api.post("/research/<job_id>/refresh")
@require_auth
def research_refresh(job_id: str):
    job = company_research_service.refresh_research(job_id)
    if not job:
        raise ValidationError("job not found")
    return jsonify(job)
