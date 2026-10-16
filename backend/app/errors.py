"""Structured API errors and consistent JSON error responses."""
from __future__ import annotations

import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An error that maps cleanly onto an HTTP status + JSON body."""

    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class NotFound(ApiError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404, "not_found")


class Unauthorized(ApiError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 401, "unauthorized")


class ValidationError(ApiError):
    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, 422, "validation_error")


class ServiceUnavailable(ApiError):
    def __init__(self, message: str = "Service unavailable"):
        super().__init__(message, 503, "service_unavailable")


class RateLimited(ApiError):
    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, 429, "rate_limited")


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        return jsonify({"error": {"code": exc.code, "message": exc.message}}), exc.status_code

    @app.errorhandler(HTTPException)
    def _handle_http_error(exc: HTTPException):
        return (
            jsonify({"error": {"code": exc.name.lower().replace(" ", "_"), "message": exc.description}}),
            exc.code,
        )

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):  # pragma: no cover - defensive
        logger.exception("Unhandled error: %s", exc)
        # Never leak internal error details to clients.
        return (
            jsonify({"error": {"code": "internal_error", "message": "An unexpected error occurred"}}),
            500,
        )
