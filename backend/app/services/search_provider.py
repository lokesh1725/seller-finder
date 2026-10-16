"""Modular external web-search provider.

Providers implement a tiny common interface so the aggregator can swap them
without caring which vendor is configured. Credentials are read from the
environment. When no credentials are present the provider reports itself as
unavailable and returns no results -- it never fabricates data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import requests

from ..config import Config
from ..utils import domain_from_url, is_missing
from . import cache

logger = logging.getLogger(__name__)

# Domains that are typically authoritative for company identity / contacts.
_HIGH_TRUST = (
    "linkedin.com", "crunchbase.com", "zaubacorp.com", "indiamart.com",
    "yourstory.com", "thecompanycheck.com", "tofler.in", "mca.gov.in",
    "zauba.com", "glassdoor", "economictimes", "business-standard",
)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    source: str = ""
    domain: str = ""
    trust_score: int = 0
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "domain": self.domain,
            "trust_score": self.trust_score,
        }


class SearchProvider(Protocol):
    name: str

    def available(self) -> bool: ...

    def search(self, query: str, count: int | None = None) -> list[SearchResult]: ...


def _score_result(result: SearchResult, query: str) -> int:
    score = 0
    domain = result.domain or ""
    if any(domain.endswith(t) for t in _HIGH_TRUST):
        score += 3
    # Official-looking domains score higher.
    tokens = [t for t in query.lower().replace(" ", "") if t.isalnum()]
    if tokens and domain.replace("-", "").replace(".", "").startswith("".join(tokens)[:6]):
        score += 2
    if result.snippet:
        score += 1
    return score


class _HttpJsonProvider:
    """Base class for JSON-over-HTTP providers."""

    name = "base"

    def __init__(self):
        self.api_key = Config.SEARCH_API_KEY
        self.timeout = Config.SEARCH_TIMEOUT_SECONDS

    def available(self) -> bool:
        return bool(self.api_key)

    def _request(self, url: str, *, headers: dict, params: dict) -> dict:
        response = requests.get(
            url, headers=headers, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def search(self, query: str, count: int | None = None) -> list[SearchResult]:
        raise NotImplementedError


class BraveProvider(_HttpJsonProvider):
    name = "brave"

    def search(self, query: str, count: int | None = None) -> list[SearchResult]:
        endpoint = (
            Config.SEARCH_API_ENDPOINT
            or "https://api.search.brave.com/res/v1/web/search"
        )
        params = {"q": query, "count": count or Config.SEARCH_MAX_RESULTS}
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        data = self._request(endpoint, headers=headers, params=params)
        results = []
        for item in (data.get("web") or {}).get("results", []):
            results.append(self._normalize(item.get("title", ""), item.get("url", ""), item.get("description", "")))
        return results

    def _normalize(self, title, url, snippet) -> SearchResult:
        domain = domain_from_url(url) or ""
        result = SearchResult(
            title=title, url=url, snippet=snippet, source=self.name, domain=domain
        )
        result.trust_score = _score_result(result, title)
        return result


class BingProvider(_HttpJsonProvider):
    name = "bing"

    def search(self, query: str, count: int | None = None) -> list[SearchResult]:
        endpoint = (
            Config.SEARCH_API_ENDPOINT
            or "https://api.bing.microsoft.com/v7.0/search"
        )
        params = {"q": query, "count": count or Config.SEARCH_MAX_RESULTS, "mkt": "en-IN"}
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        data = self._request(endpoint, headers=headers, params=params)
        results = []
        for item in (data.get("webPages") or {}).get("value", []):
            domain = domain_from_url(item.get("url", "")) or ""
            result = SearchResult(
                title=item.get("name", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                source=self.name,
                domain=domain,
            )
            result.trust_score = _score_result(result, item.get("name", ""))
            results.append(result)
        return results


class NullProvider:
    """Used when no credentials are configured."""

    name = "none"

    def available(self) -> bool:
        return False

    def search(self, query: str, count: int | None = None) -> list[SearchResult]:
        return []


_PROVIDERS = {
    "brave": BraveProvider,
    "bing": BingProvider,
    "none": NullProvider,
}


def get_provider() -> SearchProvider:
    provider_cls = _PROVIDERS.get(Config.SEARCH_PROVIDER.lower(), NullProvider)
    return provider_cls()


def search_web(query: str, count: int | None = None, use_cache: bool = True) -> dict:
    """Search permitted public sources for *query*.

    Returns a dict with ``results`` plus metadata describing whether the
    provider was available. Results are cached to limit API usage. Provider
    errors are caught and returned as structured data rather than raised.
    """
    query = (query or "").strip()
    if is_missing(query):
        return {"provider": "none", "available": False, "results": [], "error": "empty_query"}

    provider = get_provider()
    if not provider.available():
        return {
            "provider": provider.name,
            "available": False,
            "results": [],
            "error": "search_provider_not_configured",
        }

    if use_cache:
        cached = cache.get("web_search", query)
        if cached is not None:
            cached["cached"] = True
            return cached

    try:
        results = provider.search(query, count=count)
    except requests.exceptions.RequestException as exc:
        logger.warning("Search provider '%s' request failed: %s", provider.name, exc)
        return {
            "provider": provider.name,
            "available": True,
            "results": [],
            "error": "provider_request_failed",
        }
    except (ValueError, KeyError) as exc:  # malformed payload
        logger.warning("Search provider '%s' returned bad data: %s", provider.name, exc)
        return {
            "provider": provider.name,
            "available": True,
            "results": [],
            "error": "provider_bad_response",
        }

    results.sort(key=lambda r: r.trust_score, reverse=True)
    payload = {
        "provider": provider.name,
        "available": True,
        "results": [r.to_dict() for r in results],
        "error": None,
        "cached": False,
    }
    if use_cache:
        cache.set("web_search", query, payload)
    return payload
