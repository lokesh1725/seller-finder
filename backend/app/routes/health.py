"""Health and readiness endpoints."""
from __future__ import annotations

from flask import jsonify

from . import api
from .. import db


@api.get("/health")
def health():
    db_ok, detail = db.ping()
    return (
        jsonify(
            {
                "status": "ok" if db_ok else "degraded",
                "database": {"connected": db_ok, "detail": detail},
                "service": "seller-finder-api",
            }
        ),
        200 if db_ok else 503,
    )
