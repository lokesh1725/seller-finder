"""Protected administrative endpoints.

Importing data is a privileged operation, guarded by ``ADMIN_API_TOKEN``.
When no token is configured the route is disabled in production.
"""
from __future__ import annotations

from flask import current_app, jsonify, request

from . import api, require_admin
from ..db import DatabaseUnavailable
from ..errors import ServiceUnavailable, ValidationError
from ..services import importer


@api.post("/admin/import")
def admin_import():
    require_admin()
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", False))
    path = body.get("path") or str(importer.DEFAULT_WORKBOOK)
    try:
        summary = importer.import_workbook(path, dry_run=dry_run)
    except FileNotFoundError as exc:
        raise ValidationError(str(exc))
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    except KeyError as exc:
        raise ValidationError(str(exc))
    return jsonify({"dry_run": dry_run, "summary": summary})


@api.get("/admin/cache/clear")
def clear_cache():
    require_admin()
    from ..services import cache
    removed = cache.clear()
    return jsonify({"cleared": removed})
