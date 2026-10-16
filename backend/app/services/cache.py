"""Lightweight MongoDB-backed cache for external search results.

Caching keeps us inside free-tier API quotas and makes repeat searches fast.
A TTL index on ``expires_at`` lets MongoDB evict stale documents automatically.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from pymongo.errors import PyMongoError

from .. import db
from ..config import Config
from ..utils import utcnow

logger = logging.getLogger(__name__)


def _key(namespace: str, value: str) -> str:
    raw = f"{namespace}:{value.strip().lower()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get(namespace: str, value: str):
    try:
        doc = db.search_cache().find_one({"cache_key": _key(namespace, value)})
    except PyMongoError as exc:  # cache must never break the request path
        logger.warning("Cache read failed: %s", exc)
        return None
    if not doc:
        return None
    if doc.get("expires_at") and doc["expires_at"] < utcnow():
        return None
    return doc.get("payload")


def set(namespace: str, value: str, payload, ttl_hours: int | None = None):
    ttl = ttl_hours if ttl_hours is not None else Config.SEARCH_CACHE_TTL_HOURS
    try:
        db.search_cache().update_one(
            {"cache_key": _key(namespace, value)},
            {
                "$set": {
                    "cache_key": _key(namespace, value),
                    "namespace": namespace,
                    "payload": payload,
                    "expires_at": utcnow() + timedelta(hours=ttl),
                    "updated_at": utcnow(),
                }
            },
            upsert=True,
        )
    except PyMongoError as exc:  # pragma: no cover - defensive
        logger.warning("Cache write failed: %s", exc)


def clear(namespace: str | None = None):
    query = {"namespace": namespace} if namespace else {}
    try:
        return db.search_cache().delete_many(query).deleted_count
    except PyMongoError:  # pragma: no cover
        return 0
