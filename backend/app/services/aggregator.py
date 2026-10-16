"""Search aggregation: database-first, then permitted public web sources.

The database is always queried first so saved profiles are returned without
wasting external API calls. Only when nothing (or too little) is found do we
consult the configured web-search provider.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pymongo.errors import PyMongoError

from .. import db
from ..config import Config
from ..utils import clean_str, clean_url, domain_from_url, is_missing, normalize_name, slugify
from . import search_provider, verification

logger = logging.getLogger(__name__)


def _rank_match(query_norm: str, doc: dict) -> int:
    """Higher is more relevant. Exact > prefix > contains."""
    name = doc.get("normalized_name") or normalize_name(doc.get("company_name", ""))
    if name == query_norm:
        return 100
    if name.startswith(query_norm):
        return 80
    if query_norm in name:
        return 60
    for alias in doc.get("alternate_names", []) or []:
        alias_norm = normalize_name(alias)
        if alias_norm == query_norm:
            return 95
        if alias_norm and (alias_norm.startswith(query_norm) or query_norm in alias_norm):
            return 50
    if query_norm and query_norm in normalize_name(doc.get("product_categories", "") if isinstance(doc.get("product_categories"), str) else " ".join(doc.get("product_categories") or [])):
        return 20
    return 10


def _public_projection() -> dict:
    return {"_id": 0}


def _summary(doc: dict) -> dict:
    """Compact record for list/search views."""
    return {
        "business_id": doc.get("business_id"),
        "slug": doc.get("slug"),
        "company_name": doc.get("company_name"),
        "alternate_names": doc.get("alternate_names", []),
        "business_category": doc.get("business_category"),
        "product_categories": doc.get("product_categories", []),
        "city": doc.get("city"),
        "state": doc.get("state"),
        "official_website": doc.get("official_website"),
        "has_email": bool(doc.get("business_email")),
        "has_phone": bool(doc.get("business_phone")),
        "has_linkedin": bool(doc.get("linkedin_company_url")),
        "data_origin": doc.get("data_origin"),
        "last_verified_at": doc.get("last_verified_at"),
        "lead_priority_score": doc.get("lead_priority_score"),
    }


def search_database(query: str, category: str | None = None, city: str | None = None,
                    limit: int = 25, offset: int = 0) -> tuple[list[dict], int]:
    """Case-insensitive, partial-name DB search with relevance ranking.

    With an empty *query* the function behaves as a filtered browse (category
    and/or city required).
    """
    query_norm = normalize_name(query)

    mongo_query: dict[str, Any] = {}
    if query_norm:
        # Escape user input before using it inside a regex (injection safety).
        escaped = re.escape(query_norm)
        regex = re.compile(escaped, re.IGNORECASE)
        mongo_query["$or"] = [
            {"normalized_name": regex},
            {"alternate_names_norm": regex},
            {"company_name": {"$regex": re.escape(query), "$options": "i"}},
        ]
    elif not (category or city):
        return [], 0

    if category:
        mongo_query["business_category"] = re.compile(re.escape(category), re.IGNORECASE)
    if city:
        mongo_query["city"] = re.compile(re.escape(city), re.IGNORECASE)

    try:
        cursor = db.businesses().find(mongo_query, _public_projection())
        docs = list(cursor)
    except PyMongoError as exc:
        logger.error("DB search failed: %s", exc)
        raise

    if query_norm:
        for doc in docs:
            doc["_relevance"] = _rank_match(query_norm, doc)
        docs.sort(key=lambda d: (-d["_relevance"], d.get("company_name") or ""))
    else:
        docs.sort(key=lambda d: d.get("company_name") or "")
    total = len(docs)
    window = docs[offset: offset + limit]
    for doc in window:
        doc.pop("_relevance", None)
    return window, total


def find_by_slug_or_id(identifier: str) -> dict | None:
    if not identifier:
        return None
    return db.businesses().find_one(
        {"$or": [{"slug": identifier}, {"business_id": identifier}]},
        _public_projection(),
    )


def _web_candidate_from_results(query: str, web: dict) -> dict:
    """Build a transparent, clearly-unverified candidate from web results.

    Nothing is invented: only fields that appear in the returned titles /
    snippets are surfaced, and every field points back at its source URL.
    """
    results = web.get("results", [])
    sources = []
    domain = None
    emails: list[str] = []
    phones: list[str] = []
    linkedin = None
    for item in results:
        url = clean_url(item.get("url"))
        if url and url not in sources:
            sources.append(url)
        if not domain and item.get("domain"):
            domain = item["domain"]
        haystack = f"{item.get('title', '')} {item.get('snippet', '')}"
        for email in re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", haystack):
            if email.lower() not in [e.lower() for e in emails]:
                emails.append(email)
        if "linkedin.com/company" in (item.get("url") or "") and not linkedin:
            linkedin = item["url"]

    if not sources and not emails:
        return None

    slug = slugify(query)
    candidate = {
        "business_id": f"web-{slug}",
        "slug": slug,
        "company_name": query,
        "alternate_names": [],
        "business_category": None,
        "product_categories": [],
        "official_website": None,
        "business_email": emails[0] if emails else None,
        "business_phone": None,
        "linkedin_company_url": linkedin,
        "founder_name": None,
        "ceo_name": None,
        "business_address": None,
        "city": None,
        "state": None,
        "country": "India",
        "source_urls": sources,
        "data_origin": "web_search",
        "field_verification_status": {
            field: verification.make_status(verification.UNVERIFIED, sources[0] if sources else None)
            for field in verification.TRACKED_FIELDS
        },
        "last_verified_at": None,
    }
    return candidate


def search(query: str, category: str | None = None, city: str | None = None,
           limit: int = 25, offset: int = 0, allow_web: bool = True) -> dict:
    """Full search pipeline. Returns DB hits plus, when needed, web candidates."""
    query = clean_str(query) or ""
    db_results, total = search_database(query, category, city, limit, offset)

    response = {
        "query": query,
        "results": [_summary(doc) for doc in db_results],
        "total": total,
        "source": "database",
        "web_search": None,
    }

    # Only reach for the web when there is a name query and no confident match.
    exact = any(
        normalize_name(r.get("company_name", "")) == normalize_name(query)
        for r in db_results
    )
    if query and (not db_results or not exact) and allow_web:
        web = search_provider.search_web(query)
        response["web_search"] = {
            "provider": web.get("provider"),
            "available": web.get("available"),
            "error": web.get("error"),
            "count": len(web.get("results", [])),
        }
        if web.get("results"):
            candidate = _web_candidate_from_results(query, web)
            if candidate:
                response["results"].append(_summary(candidate))
                response.setdefault("web_candidates", []).append(candidate)
                response["source"] = "database+web" if db_results else "web"
    return response


def refresh_business(identifier: str) -> dict:
    """Attempt to fill missing public fields from permitted web sources."""
    doc = find_by_slug_or_id(identifier)
    if not doc:
        return {"found": False, "updated_fields": [], "messages": ["Business not found"]}

    query = doc.get("company_name") or identifier
    web = search_provider.search_web(f"{query} official website contact email")

    updated_fields: list[str] = []
    source_urls = list(doc.get("source_urls") or [])
    if web.get("available") and web.get("results"):
        for item in web["results"]:
            url = clean_url(item.get("url"))
            if url and url not in source_urls:
                source_urls.append(url)
        if not doc.get("official_website"):
            # Prefer an official-looking domain that is not a directory.
            for item in web["results"]:
                d = item.get("domain") or ""
                if d and not any(d.endswith(t) for t in (
                    "linkedin.com", "indiamart.com", "facebook.com", "instagram.com",
                    "wikipedia.org", "yourstory.com",
                )):
                    doc["official_website"] = clean_url(item.get("url"))
                    doc["official_domain"] = d
                    updated_fields.append("official_website")
                    break

    from ..utils import utcnow
    update = {
        "source_urls": source_urls,
        "official_website": doc.get("official_website"),
        "official_domain": domain_from_url(doc.get("official_website")),
        "updated_at": utcnow(),
    }
    if updated_fields:
        db.businesses().update_one({"business_id": doc["business_id"]}, {"$set": update})

    return {
        "found": True,
        "updated_fields": updated_fields,
        "source_urls": source_urls,
        "provider": web.get("provider"),
        "provider_available": web.get("available"),
        "messages": (
            ["No new public information found"] if not updated_fields else []
        ),
    }
