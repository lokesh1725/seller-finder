"""Company research pipeline: async jobs, web search, evidence, caching.

Flow:
1. Normalise the company name and look for a fresh cached ``companies`` record.
2. If fresh, complete immediately with ``from_cache=True`` (no external search).
3. Otherwise create a ``research_jobs`` document (deduplicated per name while a
   job is running) and execute the pipeline in a background thread when
   ``RESEARCH_ASYNC`` is on, otherwise inline (tests / CLI).
4. Pipeline: web search -> page fetch -> extraction (Ollama or deterministic)
   -> field evidence -> persist to ``companies`` + ``source_evidence``.
5. Never delete existing records on provider failure; only merge stronger data
   over weaker data.
"""
from __future__ import annotations

import logging
import threading
from datetime import timedelta
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from .. import db
from ..config import Config
from ..utils import domain_from_url, normalize_name, slugify, utcnow
from . import page_fetcher, search_provider
from .extraction import extract_structured
from .verification_extended import create_field_evidence

logger = logging.getLogger(__name__)

# Prevent concurrent duplicate research for the same normalised name.
_job_locks: dict[str, threading.Lock] = {}
_job_locks_guard = threading.Lock()

STEPS = [
    "Identifying company",
    "Searching online sources",
    "Reading public pages",
    "Finding founder information",
    "Checking evidence",
    "Saving results",
]


def _lock_for(norm: str) -> threading.Lock:
    with _job_locks_guard:
        if norm not in _job_locks:
            _job_locks[norm] = threading.Lock()
        return _job_locks[norm]


def _fresh_window_days() -> int:
    return max(1, Config.RESEARCH_CACHE_TTL_DAYS)


def find_fresh_company(norm: str) -> dict[str, Any] | None:
    """Return a cached company document when still within its refresh window."""
    try:
        doc = db.get_db()["companies"].find_one({"normalized_name": norm})
    except PyMongoError as exc:
        logger.warning("Company cache lookup failed: %s", exc)
        return None
    if not doc:
        return None
    last = doc.get("last_researched_at")
    if last is None:
        return None
    if last.tzinfo is None:
        from datetime import timezone
        last = last.replace(tzinfo=timezone.utc)
    age = utcnow() - last
    if age > timedelta(days=_fresh_window_days()):
        return None
    return doc


def start_research(company_name: str, *, force: bool = False) -> dict[str, Any]:
    """Create (or reuse) a research job for *company_name*."""
    name = (company_name or "").strip()
    if not name:
        raise ValueError("company_name required")
    if len(name) > 200:
        raise ValueError("company_name too long")
    norm = normalize_name(name)
    if not norm:
        raise ValueError("company_name required")

    # Fresh cache short-circuit: build a completed job without external calls.
    if not force:
        fresh = find_fresh_company(norm)
        if fresh:
            job_id = slugify(name)[:40] + "-cached-" + utcnow().strftime("%Y%m%d%H%M%S%f")[:10]
            results = _results_from_company(fresh, job_id, from_cache=True)
            job = {
                "job_id": job_id,
                "company_name": name,
                "company_name_norm": norm,
                "status": "completed",
                "progress": 100,
                "steps": STEPS,
                "current_step": "Completed",
                "from_cache": True,
                "results": results,
                "error": None,
                "created_at": utcnow(),
                "updated_at": utcnow(),
            }
            _insert_job(job)
            return job

    # Deduplicate concurrent jobs for the same name.
    with _lock_for(norm):
        existing = db.get_db()["research_jobs"].find_one(
            {"company_name_norm": norm, "status": "running"},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if existing and not force:
            return existing

        job_id = slugify(name)[:40] + "-" + utcnow().strftime("%Y%m%d%H%M%S%f")[:12]
        job = {
            "job_id": job_id,
            "company_name": name,
            "company_name_norm": norm,
            "status": "running",
            "progress": 0,
            "steps": STEPS,
            "current_step": STEPS[0],
            "from_cache": False,
            "results": None,
            "error": None,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        _insert_job(job)
        return job


def _insert_job(job: dict[str, Any]) -> None:
    try:
        db.get_db()["research_jobs"].insert_one(dict(job))
    except DuplicateKeyError:
        # Extremely rare race: fetch the existing job.
        existing = db.get_db()["research_jobs"].find_one(
            {"job_id": job["job_id"]}, {"_id": 0}
        )
        if existing:
            job.update(existing)


def get_research(job_id: str) -> dict[str, Any] | None:
    return db.get_db()["research_jobs"].find_one({"job_id": job_id}, {"_id": 0})


def list_research(limit: int = 20) -> list[dict[str, Any]]:
    cursor = (
        db.get_db()["research_jobs"]
        .find({}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    return list(cursor)


def _progress(job_id: str, progress: int, current_step: str | None = None) -> None:
    updates = {"progress": progress, "updated_at": utcnow()}
    if current_step:
        updates["current_step"] = current_step
    db.get_db()["research_jobs"].update_one({"job_id": job_id}, {"$set": updates})


def _fail(job_id: str, message: str) -> None:
    db.get_db()["research_jobs"].update_one(
        {"job_id": job_id},
        {"$set": {"status": "failed", "error": message, "updated_at": utcnow()}},
    )


def _complete(job_id: str, results: dict[str, Any], from_cache: bool = False) -> None:
    db.get_db()["research_jobs"].update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": "completed",
                "progress": 100,
                "current_step": "Completed",
                "results": results,
                "from_cache": from_cache,
                "error": None,
                "updated_at": utcnow(),
            }
        },
    )


def run_job_async(job_id: str, company_name: str) -> None:
    """Kick off *job_id* on a daemon thread (fire-and-forget)."""
    def _runner():
        try:
            research_company(company_name, job_id=job_id)
        except Exception as exc:  # noqa: BLE001 - job must never crash the process
            logger.exception("Research job %s failed", job_id)
            try:
                _fail(job_id, "research_failed")
            except Exception:
                pass

    threading.Thread(target=_runner, name=f"research-{job_id[:20]}", daemon=True).start()


def refresh_research(job_id: str) -> dict[str, Any] | None:
    job = get_research(job_id)
    if not job:
        return None
    db.get_db()["research_jobs"].update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": "running",
                "progress": 0,
                "current_step": STEPS[0],
                "from_cache": False,
                "error": None,
                "updated_at": utcnow(),
            }
        },
    )
    if Config.RESEARCH_ASYNC:
        run_job_async(job_id, job["company_name"])
    else:
        try:
            research_company(job["company_name"], job_id=job_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Research refresh failed for %s", job_id)
            _fail(job_id, "research_failed")
    return get_research(job_id)


def _results_from_company(
    company: dict[str, Any], job_id: str, *, from_cache: bool = False
) -> dict[str, Any]:
    founders = []
    if company.get("founder_name"):
        founders.append(
            {
                "name": company.get("founder_name"),
                "designation": company.get("founder_designation") or "Founder",
                "linkedin_url": company.get("founder_linkedin_url") or "",
                "public_professional_email": company.get("founder_email") or "",
                "public_professional_phone": company.get("founder_phone") or "",
                "source_url": (company.get("source_urls") or [""])[0],
            }
        )
    if company.get("ceo_name") and not founders:
        founders.append(
            {
                "name": company.get("ceo_name"),
                "designation": "CEO (founder not confirmed)",
                "linkedin_url": "",
                "public_professional_email": "",
                "public_professional_phone": "",
                "source_url": (company.get("source_urls") or [""])[0],
            }
        )
    elif company.get("ceo_name"):
        founders.append(
            {
                "name": company.get("ceo_name"),
                "designation": "CEO",
                "linkedin_url": "",
                "public_professional_email": "",
                "public_professional_phone": "",
                "source_url": (company.get("source_urls") or [""])[0],
            }
        )

    contacts = {
        "business_email": company.get("business_email") or "",
        "business_phone": company.get("business_phone") or "",
        "linkedin_company_url": company.get("linkedin_company_url") or "",
        "official_website": company.get("official_website") or "",
    }
    return {
        "job_id": job_id,
        "company_name": company.get("company_name"),
        "company_id": company.get("business_id"),
        "slug": company.get("slug"),
        "official_domain": company.get("official_domain") or "",
        "industry": company.get("business_category") or "",
        "description": company.get("description") or "",
        "founders": founders,
        "contacts": contacts,
        "business_address": company.get("business_address") or "",
        "city": company.get("city") or "",
        "source_urls": company.get("source_urls") or [],
        "evidence_snippets": company.get("evidence_snippets") or [],
        "verification": company.get("verification_summary") or {"overall": "unverified"},
        "field_evidence": company.get("field_evidence") or [],
        "confidence": company.get("confidence_score") or 0.0,
        "last_researched_at": company.get("last_researched_at"),
        "from_cache": from_cache,
        "search_provider": company.get("search_provider") or "none",
        "research_status": company.get("research_status") or "completed",
    }


def research_company(company_name: str, job_id: str | None = None) -> dict[str, Any]:
    """Run the full research pipeline for *company_name*."""
    if not job_id:
        job = start_research(company_name)
        job_id = job["job_id"]
        if job.get("status") == "completed" and job.get("from_cache"):
            return job["results"]

    name = company_name
    norm = normalize_name(name)
    lock = _lock_for(norm)
    # Non-blocking for refresh of our own job; blocking only to serialise pipeline.
    with lock:
        try:
            return _run_pipeline(name, norm, job_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Research pipeline failed for %s", name)
            _fail(job_id, "research_failed")
            raise


def _run_pipeline(name: str, norm: str, job_id: str) -> dict[str, Any]:
    # Stage 1: existing DB record (may be stale - used as baseline only).
    _progress(job_id, 5, STEPS[0])
    try:
        existing = db.get_db()["companies"].find_one({"normalized_name": norm})
    except PyMongoError:
        existing = None

    # Stage 2: web search (cached by the provider layer).
    _progress(job_id, 20, STEPS[1])
    web = search_provider.search_web(f"{name} company founder contact")
    if not web.get("available") and not existing:
        # Honest failure: no provider and no stored record.
        results = {
            "job_id": job_id,
            "company_name": name,
            "company_id": None,
            "slug": None,
            "db_matches": 0,
            "web_search": web,
            "official_domain": "",
            "official_website": "",
            "industry": "",
            "description": "",
            "founders": [],
            "contacts": {},
            "business_address": "",
            "source_urls": [],
            "evidence_snippets": [],
            "verification": {"overall": "unavailable"},
            "field_evidence": [],
            "confidence": 0.0,
            "search_provider": web.get("provider", "none"),
            "search_error": web.get("error"),
            "from_cache": False,
            "message": (
                "No stored record and no search provider configured. "
                "Set SEARCH_PROVIDER and SEARCH_API_KEY to enable live research."
                if web.get("error") == "search_provider_not_configured"
                else "External search is currently unavailable."
            ),
        }
        _complete(job_id, results)
        return results

    # Stage 3: fetch top public pages for evidence.
    _progress(job_id, 40, STEPS[2])
    urls = [r.get("url") for r in web.get("results", []) if r.get("url")]
    pages = page_fetcher.fetch_pages(urls)

    # Stage 4: extraction from real evidence only.
    _progress(job_id, 60, STEPS[3])
    payload = {
        "company_name": name,
        "search_results": web.get("results", []),
        "pages": pages,
        "source_urls": urls,
        "evidence_snippets": [
            {"url": r.get("url"), "text": r.get("snippet")}
            for r in web.get("results", [])[:5]
        ],
        "founders": [],
        "contacts": {},
    }
    extracted = extract_structured(payload)

    # Merge with existing: never overwrite non-empty with empty; prefer new
    # values only when present (research refresh fills gaps and updates).
    merged: dict[str, Any] = dict(existing or {})
    for key, value in extracted.items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value

    _progress(job_id, 80, STEPS[4])

    # Field-level evidence for every important field.
    field_evidence = []
    source0 = (extracted.get("source_urls") or [""])[0]
    mapping = [
        ("business_email", extracted.get("business_email")),
        ("business_phone", extracted.get("business_phone")),
        ("business_address", extracted.get("business_address")),
        ("founder_name", extracted.get("founder_name")),
        ("founder_linkedin_url", extracted.get("founder_linkedin_url")),
        ("official_domain", extracted.get("official_domain")),
        ("ceo_name", extracted.get("ceo_name")),
    ]
    for field, value in mapping:
        if not value:
            field_evidence.append(
                create_field_evidence(field, None, source_url=None, status="not_found")
            )
            continue
        status = "partially_verified"
        # Official domain / LinkedIn URLs from search are closer to official.
        if field in ("official_domain", "founder_linkedin_url") and value:
            status = "officially_published"
        field_evidence.append(
            create_field_evidence(
                field,
                value,
                source_url=source0 or None,
                source_type=search_provider.get_provider().name,
                confidence=extracted.get("confidence_score", 0.4),
                status=status,
            )
        )

    # Persist company record.
    _progress(job_id, 92, STEPS[5])
    business_id = slugify(name)[:60]
    now = utcnow()
    contact_updated = now if (extracted.get("business_email") or extracted.get("business_phone")) else (merged.get("contacts_updated_at") or now)
    company_doc = {
        "business_id": business_id,
        "slug": business_id,
        "company_name": name,
        "normalized_name": norm,
        "official_domain": extracted.get("official_domain") or merged.get("official_domain") or "",
        "official_website": (
            f"https://{extracted['official_domain']}"
            if extracted.get("official_domain")
            else merged.get("official_website") or ""
        ),
        "business_category": extracted.get("industry") or merged.get("business_category") or "",
        "description": extracted.get("description") or merged.get("description") or "",
        "business_email": extracted.get("business_email") or merged.get("business_email") or "",
        "business_phone": extracted.get("business_phone") or merged.get("business_phone") or "",
        "business_address": extracted.get("business_address") or merged.get("business_address") or "",
        "founder_name": extracted.get("founder_name") or merged.get("founder_name") or "",
        "founder_designation": extracted.get("founder_designation") or merged.get("founder_designation") or "",
        "founder_linkedin_url": extracted.get("founder_linkedin_url") or merged.get("founder_linkedin_url") or "",
        "founder_email": extracted.get("public_professional_email") or merged.get("founder_email") or "",
        "founder_phone": extracted.get("public_professional_phone") or merged.get("founder_phone") or "",
        "ceo_name": extracted.get("ceo_name") or merged.get("ceo_name") or "",
        "source_urls": extracted.get("source_urls") or merged.get("source_urls") or [],
        "evidence_snippets": extracted.get("evidence_snippets") or merged.get("evidence_snippets") or [],
        "field_evidence": field_evidence,
        "field_verification_status": {
            e["field"]: {
                "status": e["verification_status"],
                "source": e.get("source_url"),
                "last_verified_at": e.get("date_checked"),
            }
            for e in field_evidence
        },
        "verification_summary": {
            "overall": extracted.get("verification_status", "unverified"),
            "checked_at": now.isoformat(),
        },
        "confidence_score": extracted.get("confidence_score", 0.0),
        "search_provider": web.get("provider", "none"),
        "research_status": "completed",
        "data_origin": "web_research",
        "first_discovered_at": (merged.get("first_discovered_at") or now),
        "last_researched_at": now,
        "contacts_updated_at": contact_updated,
        "next_refresh_at": now + timedelta(days=_fresh_window_days()),
        "extraction_method": extracted.get("extraction_method", "deterministic"),
        "updated_at": now,
    }

    try:
        db.get_db()["companies"].update_one(
            {"business_id": business_id},
            {"$set": company_doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except PyMongoError:
        logger.warning("Could not persist company %s", business_id)

    # Persist evidence rows.
    for ev in field_evidence:
        if not ev.get("value"):
            continue
        ev = dict(ev)
        ev["evidence_id"] = slugify(f"{business_id}-{ev['field']}")[:70] + "-" + now.strftime("%Y%m%d%H%M%S%f")[:8]
        ev["company_id"] = business_id
        ev["job_id"] = job_id
        try:
            db.get_db()["source_evidence"].update_one(
                {"evidence_id": ev["evidence_id"]},
                {"$set": ev},
                upsert=True,
            )
        except PyMongoError:
            pass

    results = {
        "job_id": job_id,
        "company_name": name,
        "company_id": business_id,
        "slug": business_id,
        "db_matches": 1 if existing else 0,
        "web_search": {
            "provider": web.get("provider"),
            "available": web.get("available"),
            "cached": web.get("cached"),
            "error": web.get("error"),
            "results": web.get("results", []),
        },
        "official_domain": company_doc["official_domain"],
        "official_website": company_doc["official_website"],
        "industry": company_doc["business_category"],
        "description": company_doc["description"],
        "founders": [
            f
            for f in [
                {
                    "name": company_doc["founder_name"],
                    "designation": company_doc["founder_designation"] or ("Founder" if company_doc["founder_name"] else ""),
                    "linkedin_url": company_doc["founder_linkedin_url"],
                    "public_professional_email": company_doc["founder_email"],
                    "public_professional_phone": company_doc["founder_phone"],
                    "source_url": (company_doc["source_urls"] or [""])[0],
                },
                {
                    "name": company_doc["ceo_name"],
                    "designation": "CEO",
                    "linkedin_url": "",
                    "public_professional_email": "",
                    "public_professional_phone": "",
                    "source_url": (company_doc["source_urls"] or [""])[0],
                }
                if company_doc["ceo_name"]
                else None,
            ]
            if f and f.get("name")
        ],
        "contacts": {
            "business_email": company_doc["business_email"],
            "business_phone": company_doc["business_phone"],
            "linkedin_company_url": company_doc.get("linkedin_company_url", ""),
            "official_website": company_doc["official_website"],
        },
        "business_address": company_doc["business_address"],
        "source_urls": company_doc["source_urls"],
        "evidence_snippets": company_doc["evidence_snippets"],
        "verification": company_doc["verification_summary"],
        "field_evidence": field_evidence,
        "confidence": company_doc["confidence_score"],
        "last_researched_at": now.isoformat(),
        "next_refresh_at": company_doc["next_refresh_at"].isoformat(),
        "from_cache": False,
        "search_provider": company_doc["search_provider"],
        "extraction_method": company_doc["extraction_method"],
        "pages_fetched": len(pages),
        "message": None if web.get("available") or existing else (
            "Search provider not configured - results are limited to stored records."
        ),
    }

    _complete(job_id, results, from_cache=False)
    return results
