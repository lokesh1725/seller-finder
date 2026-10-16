from __future__ import annotations

from typing import Any, Dict


def get_config():
    from ..config import Config
    return Config


REQUIRED_KEYS = [
    "company_name",
    "official_domain",
    "founder_name",
    "founder_designation",
    "founder_linkedin_url",
    "public_professional_email",
    "public_professional_phone",
    "business_email",
    "business_phone",
    "business_address",
    "source_urls",
    "evidence_snippets",
    "verification_status",
    "confidence_score",
]


def _deterministic_from_web(results: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "company_name": results.get("company_name", ""),
        "official_domain": results.get("official_domain", ""),
        "founder_name": (results.get("founders", [{}])[0].get("name", "") if results.get("founders") else ""),
        "founder_designation": (results.get("founders", [{}])[0].get("designation", "") if results.get("founders") else ""),
        "founder_linkedin_url": (results.get("founders", [{}])[0].get("linkedin_url", "") if results.get("founders") else ""),
        "public_professional_email": results.get("contacts", {}).get("founder_email", ""),
        "public_professional_phone": results.get("contacts", {}).get("founder_phone", ""),
        "business_email": results.get("contacts", {}).get("business_email", ""),
        "business_phone": results.get("contacts", {}).get("business_phone", ""),
        "business_address": results.get("business_address", ""),
        "source_urls": results.get("source_urls", []),
        "evidence_snippets": results.get("evidence_snippets", []),
        "verification_status": "partially_verified" if any([results.get("contacts", {}).get("business_email"), results.get("contacts", {}).get("business_phone")]) else "unverified",
        "confidence_score": 0.4,
    }


def extract_structured(results: Dict[str, Any]) -> Dict[str, Any]:
    cfg = get_config()
    if not cfg.AI_API_KEY or not cfg.AI_API_BASE_URL:
        return _deterministic_from_web(results)
    return _deterministic_from_web(results)
