"""MongoDB connection management and collection access.

The module is intentionally lazy: importing it never performs network I/O, so
the Flask app can boot even when MongoDB is temporarily unreachable. Connection
errors are surfaced through :func:`get_db` and mapped to a 503 by the API.
"""
from __future__ import annotations

import logging
from typing import Optional

from flask import has_app_context, current_app
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from .config import Config

logger = logging.getLogger(__name__)

_clients: dict[str, MongoClient] = {}


class DatabaseUnavailable(RuntimeError):
    """Raised when MongoDB cannot be reached."""


def _setting(name: str, default):
    """Read a setting from the active Flask app (tests) or global Config."""
    if has_app_context():
        value = current_app.config.get(name)
        if value:
            return value
    return getattr(Config, name, default)


def _build_client(uri: str) -> MongoClient:
    timeout = int(_setting("MONGODB_TIMEOUT_MS", 5000))
    return MongoClient(
        uri,
        serverSelectionTimeoutMS=timeout,
        connectTimeoutMS=timeout,
        socketTimeoutMS=timeout * 2,
        uuidRepresentation="standard",
    )


def get_client() -> MongoClient:
    uri = _setting("MONGODB_URI", "mongodb://localhost:27017")
    if uri not in _clients:
        _clients[uri] = _build_client(uri)
    return _clients[uri]


def get_db():
    """Return the configured database handle, or raise DatabaseUnavailable."""
    try:
        client = get_client()
        client.admin.command("ping")
        return client[_setting("MONGODB_DATABASE", "seller_finder")]
    except ServerSelectionTimeoutError as exc:
        logger.error("MongoDB server selection timed out: %s", exc)
        raise DatabaseUnavailable("Database is not reachable") from exc
    except PyMongoError as exc:  # pragma: no cover - defensive
        logger.error("MongoDB error: %s", exc)
        raise DatabaseUnavailable("Database error") from exc


def ping() -> tuple[bool, str]:
    """Return (ok, detail) describing database reachability."""
    try:
        get_client().admin.command("ping")
        return True, "ok"
    except PyMongoError as exc:
        return False, type(exc).__name__
    except Exception as exc:  # pragma: no cover
        return False, type(exc).__name__


# --- Collection accessors ---------------------------------------------------

def businesses():
    return get_db()["businesses"]


def leads():
    return get_db()["leads"]


def prospects():
    return get_db()["prospects"]


def import_runs():
    return get_db()["import_runs"]


def search_cache():
    return get_db()["search_cache"]


def close_clients():
    global _clients
    for client in _clients.values():
        client.close()
    _clients = {}
