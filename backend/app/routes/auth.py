"""Authentication for the web app.

A single configured account (email/password from the environment) is used to
gate the application. On a successful login the server issues a signed,
time-limited token (itsdangerous) that the SPA stores and sends as a Bearer
token. This keeps credentials off the client and tokens tamper-proof.

Default credentials (override with AUTH_EMAIL / AUTH_PASSWORD env vars):
    email:    admin@gmail.com
    password: Test@123
"""
from __future__ import annotations

from functools import wraps

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import api, enforce_rate_limit
from ..errors import Unauthorized, ValidationError

_SALT = "seller-finder-auth"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_SALT)


def issue_token(email: str) -> str:
    return _serializer().dumps({"email": email})


def verify_token(token: str) -> str:
    max_age = current_app.config.get("AUTH_TOKEN_MAX_AGE", 60 * 60 * 24 * 7)
    try:
        data = _serializer().loads(token, max_age=max_age)
    except SignatureExpired as exc:
        raise Unauthorized("Session expired, please log in again") from exc
    except BadSignature as exc:
        raise Unauthorized("Invalid session") from exc
    email = data.get("email")
    if not email:
        raise Unauthorized("Invalid session")
    return email


def _extract_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Auth-Token") or None


def require_auth(fn):
    """Protect an endpoint. Disabled under automated tests unless AUTH_REQUIRED."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        config = current_app.config
        if config.get("TESTING") and not config.get("AUTH_REQUIRED"):
            return fn(*args, **kwargs)
        token = _extract_token()
        if not token:
            raise Unauthorized("Authentication required")
        request.auth_email = verify_token(token)  # type: ignore[attr-defined]
        return fn(*args, **kwargs)

    return wrapper


@api.post("/auth/login")
def login():
    enforce_rate_limit()
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if not email or not password:
        raise ValidationError("Email and password are required")

    expected_email = str(current_app.config.get("AUTH_EMAIL", "")).strip().lower()
    expected_password = str(current_app.config.get("AUTH_PASSWORD", ""))
    if email != expected_email or password != expected_password:
        # A single generic message avoids revealing which field was wrong.
        raise Unauthorized("Invalid email or password")

    return jsonify({"token": issue_token(email), "user": {"email": email}})


@api.get("/auth/me")
def me():
    token = _extract_token()
    if not token:
        raise Unauthorized("Authentication required")
    email = verify_token(token)
    return jsonify({"user": {"email": email}})
