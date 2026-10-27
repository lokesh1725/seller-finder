"""Research endpoints: start, poll, refresh, list."""
from __future__ import annotations

from flask import jsonify, request

from . import api, enforce_rate_limit
from .auth import require_auth
from ..config import Config
from ..errors import NotFound, ValidationError
from ..services import company_research_service


@api.post("/research")
@require_auth
def research_start():
    enforce_rate_limit()
    body = request.get_json(silent=True) or {}
    name = (body.get("company_name") or body.get("query") or "").strip()
    force = bool(body.get("force"))
    if not name:
        raise ValidationError("company_name is required")
    if len(name) > 200:
        raise ValidationError("company_name is too long")
    try:
        job = company_research_service.start_research(name, force=force)
    except ValueError as exc:
        raise ValidationError(str(exc))

    # Fresh-cache jobs are already complete; live jobs run in the background.
    if job.get("status") == "running" and Config.RESEARCH_ASYNC:
        company_research_service.run_job_async(job["job_id"], job["company_name"])
        job = company_research_service.get_research(job["job_id"]) or job
    elif job.get("status") == "running":
        try:
            company_research_service.research_company(name, job_id=job["job_id"])
            job = company_research_service.get_research(job["job_id"]) or job
        except Exception:
            job = company_research_service.get_research(job["job_id"]) or job
    return jsonify(job), 202 if job.get("status") == "running" else 200


@api.get("/research")
@require_auth
def research_list():
    enforce_rate_limit()
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify({"jobs": company_research_service.list_research(limit=limit)})


@api.get("/research/<job_id>")
@require_auth
def research_get(job_id: str):
    enforce_rate_limit()
    job = company_research_service.get_research(job_id)
    if not job:
        raise NotFound("Research job not found")
    return jsonify(job)


@api.post("/research/<job_id>/refresh")
@require_auth
def research_refresh(job_id: str):
    enforce_rate_limit()
    job = company_research_service.refresh_research(job_id)
    if not job:
        raise NotFound("Research job not found")
    return jsonify(job), 202 if job.get("status") == "running" else 200
