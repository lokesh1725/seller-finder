"""Shared helpers: text normalisation, parsing and security validation."""
from __future__ import annotations

import ipaddress
import re
import socket
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

# Values used in the source workbook to mean "no reliable public data".
_MISSING_MARKERS = {
    "not found",
    "notfound",
    "n/a",
    "na",
    "none",
    "null",
    "-",
    "--",
    "",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s;|)]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{7,}\d)")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_missing(value) -> bool:
    """Return True when a spreadsheet value carries no usable information."""
    if value is None:
        return True
    if isinstance(value, (int, float)):
        return False
    return str(value).strip().lower() in _MISSING_MARKERS


def clean_str(value) -> str | None:
    """Trim a value, returning None when it is effectively empty."""
    if value is None:
        return None
    text = str(value).strip()
    if is_missing(text):
        return None
    return text


def normalize_name(value: str) -> str:
    """Normalise a company name for case-insensitive, punctuation-insensitive
    matching and duplicate detection.

    Example: "Bunaai (now trading as Bunai)" -> "bunaai now trading as bunai"
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.lower()
    # Company suffixes are not significant for matching.
    for token in (
        "pvt ltd", "private limited", "pvt. ltd.", "limited", "llp",
        "inc", "ltd", "co", "company",
    ):
        text = text.replace(token, " ")
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(text.split())


def slugify(value: str) -> str:
    """Create a URL-safe, stable slug from a company name."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.lower()
    text = _NON_ALNUM.sub("-", text).strip("-")
    return re.sub(r"-{2,}", "-", text) or "business"


def extract_parenthetical_aliases(name: str) -> tuple[str, list[str]]:
    """Split "Bunaai (now trading as Bunai)" into base name + aliases."""
    if not name:
        return "", []
    aliases = re.findall(r"\(([^)]+)\)", name)
    base = re.sub(r"\([^)]*\)", " ", name).strip()
    cleaned = []
    for alias in aliases:
        alias = re.sub(r"^(now trading as|formerly|aka|also known as)\s+", "", alias, flags=re.I)
        alias = alias.strip()
        if alias:
            cleaned.append(alias)
    return base, cleaned


def extract_emails(value) -> list[str]:
    if is_missing(value):
        return []
    found = EMAIL_RE.findall(str(value))
    # De-duplicate while preserving order.
    seen: list[str] = []
    for email in found:
        low = email.lower()
        if low not in seen:
            seen.append(low)
    return seen


def extract_urls(value) -> list[str]:
    if is_missing(value):
        return []
    found = URL_RE.findall(str(value))
    cleaned: list[str] = []
    for url in found:
        url = url.rstrip(".,;")
        if url not in cleaned:
            cleaned.append(url)
    return cleaned


def extract_phones(value) -> list[str]:
    if is_missing(value):
        return []
    found = PHONE_RE.findall(str(value))
    cleaned = []
    for phone in found:
        phone = re.sub(r"\s+", " ", phone).strip()
        if phone not in cleaned:
            cleaned.append(phone)
    return cleaned


def extract_pincode(value) -> str | None:
    if is_missing(value):
        return None
    match = re.search(r"\b(\d{6})\b", str(value))
    return match.group(1) if match else None


def domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def clean_url(url: str | None) -> str | None:
    """Validate and normalise an http(s) URL. Returns None if invalid."""
    if not url:
        return None
    url = str(url).strip().rstrip(".,;")
    if not url:
        return None
    # Reject dangerous / non-web schemes (javascript:, data:, ftp:, file:, ...).
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):", url)
    if scheme_match:
        if scheme_match.group(1).lower() not in ("http", "https"):
            return None
    else:
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    # A hostname is required (rejects "https://javascript:alert(1)").
    if "." not in (parsed.hostname or "") and parsed.hostname != "localhost":
        return None
    return url


# --- SSRF protection -------------------------------------------------------

_PRIVATE_HOST_SUFFIXES = (".local", ".internal", ".localhost")


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def is_safe_public_url(url: str) -> bool:
    """Guard against Server-Side Request Forgery by rejecting URLs that point
    at localhost, private ranges or non-public hostnames."""
    checked = clean_url(url)
    if not checked:
        return False
    host = urlparse(checked).hostname or ""
    if not host or host.lower().endswith(_PRIVATE_HOST_SUFFIXES):
        return False
    if _is_private_ip(host):
        return False
    # Resolve the host and ensure every answer is a public address.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        if _is_private_ip(info[4][0]):
            return False
    return True


def merge_non_empty(existing: dict, incoming: dict) -> tuple[dict, list[str]]:
    """Fill only missing / empty fields from *incoming*.

    Existing non-empty values are preserved so an idempotent import never
    overwrites good data with empty spreadsheet cells.
    """
    merged = dict(existing)
    changed: list[str] = []
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        current = merged.get(key)
        if current in (None, "", [], {}):
            merged[key] = value
            changed.append(key)
    return merged, changed
