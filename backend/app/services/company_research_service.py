"""Company research service."""
from __future__ import annotations

from typing import Any, Dict

from .. import db
from ..utils import normalize_name, slugify, utcnow
from . import search_provider
from .extraction import extract_structured
from .enrichment import enrich_with_hunter
from .verification_extended import create_field_evidence

def start_research(company_name: str) -> Dict[str, Any]:
    name = (company_name or "").strip()
    if not name:
        raise ValueError("company_name required")
    norm = normalize_name(name)
    job_id = slugify(name)[:40] + "-" + utcnow().strftime("%Y%m%d%H%M%S%f")[:12]
    job = {
        "job_id": job_id,
        "company_name": name,
        "company_name_norm": norm,
        "status": "running",
        "progress": 0,
        "steps": [
            "Identifying company",
            "Searching online sources",
            "Finding founder information",
            "Discovering available professional contacts",
            "Checking evidence",
            "Saving results",
        ],
        "current_step": "Identifying company",
        "results": None,
        "error": None,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    db.get_db()["research_jobs"].insert_one(job)
    return job

def get_research(job_id: str) -> Dict[str, Any] | None:
    return db.get_db()["research_jobs"].find_one({"job_id": job_id}, {"_id": 0})

def _progress(job_id: str, progress: int, current_step: str | None = None):
    updates = {"progress": progress, "updated_at": utcnow()}
    if current_step:
        updates["current_step"] = current_step
    db.get_db()["research_jobs"].update_one({"job_id": job_id}, {"$set": updates})

def refresh_research(job_id: str) -> Dict[str, Any] | None:
    job = get_research(job_id)
    if not job:
        return None
    db.get_db()["research_jobs"].update_one(
        {"job_id": job_id},
        {"$set": {"status": "running", "current_step": "Searching online sources", "updated_at": utcnow()}},
    )
    try:
        research_company(job["company_name"], job_id=job_id)
    except Exception:
        pass
    return get_research(job_id)

def research_company(company_name: str, job_id: str | None = None) -> Dict[str, Any]:
    if not job_id:
        job = start_research(company_name)
        job_id = job["job_id"]
    _progress(job_id, 10, "Identifying company")

    # Stage 1: DB lookup (existing)
    norm = normalize_name(company_name)
    db_res = list(db.get_db()["companies"].find({"normalized_name": norm}).limit(3))

    # Stage 2: web search
    _progress(job_id, 25, "Searching online sources")
    web = search_provider.search_web(company_name)

    # Stage 3: AI extraction
    _progress(job_id, 50, "Finding founder information")
    extracted = extract_structured(
        {
            "company_name": company_name,
            "founders": [],
            "contacts": {},
            "source_urls": [r.get("url") for r in web.get("results", [])][:10],
        }
    )

    # Stage 4: enrichment
    _progress(job_id, 70, "Discovering available professional contacts")
    enrich_with_hunter(extracted.get("official_domain"), extracted.get("founder_name"))

    # Stage 5: evidence
    _progress(job_id, 85, "Checking evidence")
    evidence = []
    for field in ["business_email", "business_phone", "founder_linkedin_url", "business_address"]:
        if extracted.get(field):
            evidence.append(create_field_evidence(field, extracted.get(field), source_url=extracted.get("source_urls", [""])[0] if extracted.get("source_urls") else None, status="partially_verified" if extracted.get("confidence_score", 0.4) > 0.3 else "unverified"))

    res = {
        "job_id": job_id,
        "company_name": company_name,
        "db_matches": len(db_res),
        "web_search": web,
        "founders": [{"name": extracted.get("founder_name"), "designation": extracted.get("founder_designation"), "linkedin_url": extracted.get("founder_linkedin_url"), "public_professional_email": extracted.get("public_professional_email"), "public_professional_phone": extracted.get("public_professional_phone")}],
        "contacts": {"business_email": extracted.get("business_email"), "business_phone": extracted.get("business_phone")},
        "business_address": extracted.get("business_address"),
        "source_urls": extracted.get("source_urls", []),
        "evidence_snippets": extracted.get("evidence_snippets", []),
        "verification": {"overall": extracted.get("verification_status", "unverified")},
        "confidence": extracted.get("confidence_score", 0.0),
        "field_evidence": evidence,
    }

    # Stage 6: save
    _progress(job_id, 95, "Saving results")
    try:
        db.get_db()["research_jobs"].update_one(
            {"job_id": job_id},
            {"$set": {"status": "completed", "progress": 100, "current_step": "Completed", "results": res, "updated_at": utcnow()}},
        )
        # write evidence
        for ev in evidence:
            ev["evidence_id"] = slugify(f"{job_id}-{ev['field']}")[:60] + "-" + utcnow().strftime("%Y%m%d%H%M%S%f")[:8]
            db.get_db()["source_evidence"].update_one({"evidence_id": ev["evidence_id"]}, {"$set": ev}, upsert=True)
    except Exception:
        pass

    return res
