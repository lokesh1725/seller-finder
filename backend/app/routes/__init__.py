"""Blueprint and shared request helpers."""
from __future__ import annotations

from flask import Blueprint, current_app, request

from ..errors import RateLimited, Unauthorized
from ..limiter import get_limiter

api = Blueprint("api", __name__, url_prefix="/api")


def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def enforce_rate_limit():
    if current_app.config.get("TESTING"):
        return
    if not get_limiter().allow(client_ip()):
        raise RateLimited()


def require_admin():
    """Protect administrative endpoints with a bearer token."""
    token = current_app.config.get("ADMIN_API_TOKEN") or ""
    if not token:
        # If no token configured, admin routes are disabled in production but
        # allowed in development for convenience.
        if current_app.config.get("FLASK_ENV") == "production":
            raise Unauthorized("Admin API is not configured")
        return
    supplied = request.headers.get("X-Admin-Token") or ""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        supplied = auth[7:]
    if supplied != token:
        raise Unauthorized("Invalid admin token")


# Import route modules so their blueprints register on `api`.
from . import health, search, businesses, leads, export, admin  # noqa: E402,F401
