"""Structured field extraction from retrieved evidence.

The extractor never invents values. It only promotes strings that are present
in the supplied evidence (search snippets + fetched page text). When a local
Ollama model is available it is used to pick fields out of the evidence; on
any failure a deterministic regex extractor runs instead. Both paths are
restricted to facts traceable to the provided sources.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from ..config import Config
from ..utils import EMAIL_RE, PHONE_RE, URL_RE, domain_from_url, extract_emails, extract_phones

logger = logging.getLogger(__name__)

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
    "extraction_method",
]

_FOUNDER_PATTERNS = [
    re.compile(r"(?:co-?founder|founder)\s*[:\-–]\s*([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,3})", re.I),
    re.compile(r"([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,3})\s*[,(]\s*(?:co-?founder|founder)", re.I),
    re.compile(r"founded by\s+([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,3})", re.I),
]

_CEO_PATTERNS = [
    re.compile(r"(?:CEO|Chief Executive Officer)\s*[:\-–]\s*([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,3})", re.I),
    re.compile(r"([A-Z][\w.'\-]+(?:\s+[A-Z][\w.'\-]+){1,3})\s*[,(]\s*(?:CEO|Chief Executive Officer)", re.I),
]

_ADDRESS_RE = re.compile(
    r"\b((?:[A-Z0-9][\w./\-]*\s+){2,}(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|"
    r"Drive|Dr|Nagar|Colony|Marg|Place|Pvt|Limited|Tower|Building|Floor|"
    r"Ground|Sector|Block|Market|Industrial|Area|Park|Complex)"
    r"[^.\n,]{0,120})",
    re.I,
)

_LINKEDIN_PERSON_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?", re.I
)
_LINKEDIN_COMPANY_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/[A-Za-z0-9\-_%]+/?", re.I
)

_NON_EMAIL_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "woff", "woff2"}


def _ollama_available() -> bool:
    if not Config.OLLAMA_ENABLED:
        return False
    try:
        resp = requests.get(
            f"{Config.OLLAMA_BASE_URL}/api/tags",
            timeout=3,
        )
        if resp.status_code != 200:
            return False
        models = [m.get("name", "") for m in resp.json().get("models", [])]
        wanted = Config.OLLAMA_MODEL
        return any(m == wanted or m.startswith(f"{wanted}:") for m in models) or bool(models)
    except (requests.exceptions.RequestException, ValueError, KeyError):
        return False


def _evidence_blob(payload: dict[str, Any], max_chars: int = 12_000) -> str:
    parts: list[str] = []
    for item in payload.get("pages") or []:
        text = (item.get("text") or "")[:4_000]
        url = item.get("url") or ""
        if text:
            parts.append(f"SOURCE: {url}\n{text}")
    for result in payload.get("search_results") or []:
        title = result.get("title") or ""
        snippet = result.get("snippet") or ""
        url = result.get("url") or ""
        if title or snippet:
            parts.append(f"SOURCE: {url}\nTITLE: {title}\n{snippet}")
    blob = "\n\n".join(parts)
    return blob[:max_chars]


def _prompt_for(evidence: str, company_name: str) -> str:
    return (
        "You extract factual company information ONLY from the evidence below. "
        "Never invent values. Use empty string when a fact is absent.\n"
        "Return STRICT JSON with keys: company_name, official_domain, founder_name, "
        "founder_designation, founder_linkedin_url, ceo_name, business_email, "
        "business_phone, business_address, public_professional_email, "
        "public_professional_phone, industry, description, source_url.\n"
        f"Company searched: {company_name}\n"
        f"EVIDENCE:\n{evidence}\n"
        "JSON only:"
    )


def _call_ollama(prompt: str) -> str | None:
    try:
        resp = requests.post(
            f"{Config.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": Config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=Config.OLLAMA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip() or None
    except (requests.exceptions.RequestException, ValueError, KeyError) as exc:
        logger.info("Ollama extraction unavailable: %s", exc)
        return None


def _parse_json_response(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    # Model may wrap JSON in fences or prose.
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _clean_email(value: str | None) -> str:
    if not value:
        return ""
    found = extract_emails(value)
    if not found:
        return ""
    email = found[0]
    tld = email.rsplit(".", 1)[-1].lower()
    if tld in _NON_EMAIL_TLDS:
        return ""
    return email


def _only_if_in_evidence(value: str, evidence: str) -> str:
    """Reject hallucinated contact values that do not appear in the evidence."""
    if not value:
        return ""
    token = value.strip()
    if not token:
        return ""
    # Compare loosely: ignore case and surrounding punctuation.
    hay = evidence.lower()
    needle = token.lower()
    if needle in hay:
        return token
    # For emails/phones allow partial normalisation matches.
    if "@" in needle:
        local, _, domain = needle.partition("@")
        if local in hay and domain in hay:
            return token
    digits = re.sub(r"\D", "", needle)
    if len(digits) >= 8 and digits in re.sub(r"\D", "", hay):
        return token
    return ""


def _deterministic_extract(payload: dict[str, Any]) -> dict[str, Any]:
    evidence = _evidence_blob(payload, max_chars=20_000)
    company_name = payload.get("company_name") or ""

    # Domain: prefer explicit, else from result URLs matching the company.
    official_domain = payload.get("official_domain") or ""
    if not official_domain:
        tokens = set(re.sub(r"[^a-z0-9]", "", company_name.lower()))
        for result in payload.get("search_results") or []:
            url = result.get("url") or ""
            domain = domain_from_url(url) or ""
            if not domain or any(x in domain for x in ("linkedin", "facebook", "twitter", "instagram", "youtube")):
                continue
            slug = set(re.sub(r"[^a-z0-9]", "", domain.split(".")[0]))
            if tokens and slug & tokens:
                official_domain = domain
                break

    founder_name = ""
    founder_designation = ""
    for pattern in _FOUNDER_PATTERNS:
        match = pattern.search(evidence)
        if match:
            founder_name = match.group(1).strip()[:80]
            founder_designation = "Founder"
            break

    ceo_name = ""
    if not founder_name:
        for pattern in _CEO_PATTERNS:
            match = pattern.search(evidence)
            if match:
                ceo_name = match.group(1).strip()[:80]
                break

    founder_linkedin = ""
    linkedin_match = _LINKEDIN_PERSON_RE.search(evidence)
    if linkedin_match:
        founder_linkedin = linkedin_match.group(0)

    emails = [e for e in extract_emails(evidence) if e.rsplit(".", 1)[-1].lower() not in _NON_EMAIL_TLDS]
    phones = extract_phones(evidence)

    # Prefer business-looking emails (info/contact/sales/hello) for the company.
    business_email = ""
    founder_email = ""
    preferred = ("info@", "contact@", "sales@", "hello@", "support@", "enquiry", "enquiries")
    for email in emails:
        local = email.split("@")[0].lower()
        if any(p.rstrip("@") in local for p in preferred) and not business_email:
            business_email = email
    if emails and not business_email:
        # Avoid founder-looking personal names as business email when possible.
        business_email = emails[0]
    if founder_name:
        last = founder_name.split()[-1].lower() if founder_name.split() else ""
        for email in emails:
            if last and last in email.lower() and email != business_email:
                founder_email = email
                break

    business_phone = phones[0] if phones else ""
    founder_phone = phones[1] if len(phones) > 1 else ""

    address_match = _ADDRESS_RE.search(evidence)
    business_address = address_match.group(1).strip()[:200] if address_match else ""

    # Description / industry from first non-empty snippet.
    description = ""
    for result in payload.get("search_results") or []:
        snippet = (result.get("snippet") or "").strip()
        if len(snippet) > 40:
            description = snippet[:300]
            break

    source_urls = []
    for result in payload.get("search_results") or []:
        url = result.get("url")
        if url and url not in source_urls:
            source_urls.append(url)
    for page in payload.get("pages") or []:
        url = page.get("url")
        if url and url not in source_urls:
            source_urls.append(url)

    evidence_snippets = []
    for result in (payload.get("search_results") or [])[:5]:
        snippet = (result.get("snippet") or "").strip()
        if snippet:
            evidence_snippets.append({"url": result.get("url"), "text": snippet[:400]})

    fields_found = sum(
        1
        for v in (founder_name, business_email, business_phone, business_address, founder_linkedin, official_domain)
        if v
    )
    status = "partially_verified" if fields_found >= 2 else ("unverified" if fields_found else "not_found")
    confidence = min(0.9, 0.2 + 0.1 * fields_found)

    return {
        "company_name": company_name,
        "official_domain": official_domain,
        "founder_name": founder_name,
        "founder_designation": founder_designation or ("Founder" if founder_name else ""),
        "founder_linkedin_url": founder_linkedin,
        "ceo_name": ceo_name,
        "public_professional_email": founder_email,
        "public_professional_phone": founder_phone,
        "business_email": business_email,
        "business_phone": business_phone,
        "business_address": business_address,
        "industry": "",
        "description": description,
        "source_urls": source_urls,
        "evidence_snippets": evidence_snippets,
        "verification_status": status,
        "confidence_score": confidence,
        "extraction_method": "deterministic",
    }


def extract_structured(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract structured fields from *payload* evidence without inventing data."""
    evidence = _evidence_blob(payload)
    result: dict[str, Any] | None = None

    if evidence and _ollama_available():
        raw = _call_ollama(_prompt_for(evidence, payload.get("company_name") or ""))
        parsed = _parse_json_response(raw or "")
        if parsed:
            # Drop any value not present in evidence (anti-hallucination).
            checked: dict[str, Any] = {}
            for key in REQUIRED_KEYS:
                if key in ("source_urls", "evidence_snippets", "verification_status",
                           "confidence_score", "extraction_method", "company_name"):
                    continue
                value = parsed.get(key)
                if isinstance(value, str):
                    checked[key] = _only_if_in_evidence(value, evidence)
                elif value is not None:
                    checked[key] = value
            checked["company_name"] = payload.get("company_name") or parsed.get("company_name") or ""
            checked["source_urls"] = payload.get("source_urls") or [
                r.get("url") for r in (payload.get("search_results") or []) if r.get("url")
            ]
            checked["evidence_snippets"] = payload.get("evidence_snippets") or []
            checked["extraction_method"] = "ollama"
            # Re-validate emails/phones with strict parsers.
            checked["business_email"] = _clean_email(checked.get("business_email"))
            checked["public_professional_email"] = _clean_email(checked.get("public_professional_email"))
            if checked.get("business_phone") and not extract_phones(checked["business_phone"]):
                checked["business_phone"] = ""
            if checked.get("public_professional_phone") and not extract_phones(checked["public_professional_phone"]):
                checked["public_professional_phone"] = ""
            found_fields = sum(
                1
                for k in (
                    "founder_name", "business_email", "business_phone",
                    "business_address", "founder_linkedin_url", "official_domain",
                )
                if checked.get(k)
            )
            checked["verification_status"] = (
                "partially_verified" if found_fields >= 2 else ("unverified" if found_fields else "not_found")
            )
            checked["confidence_score"] = min(0.9, 0.2 + 0.1 * found_fields)
            # Ensure all required keys exist.
            for key in REQUIRED_KEYS:
                checked.setdefault(key, [] if key in ("source_urls", "evidence_snippets") else
                                   (0.0 if key == "confidence_score" else
                                    ("unverified" if key == "verification_status" else
                                     ("deterministic" if key == "extraction_method" else ""))))
            result = checked

    if result is None:
        result = _deterministic_extract(payload)
        for key in REQUIRED_KEYS:
            if key not in result:
                result[key] = [] if key in ("source_urls", "evidence_snippets") else ""

    return result
