"""CSV export of selected business records."""
from __future__ import annotations

import csv
import io

from flask import Response, request

from . import api, enforce_rate_limit
from .auth import require_auth
from .. import db
from ..db import DatabaseUnavailable
from ..errors import ServiceUnavailable

EXPORT_FIELDS = [
    "business_id",
    "company_name",
    "alternate_names",
    "business_category",
    "product_categories",
    "official_website",
    "business_email",
    "business_phone",
    "linkedin_company_url",
    "founder_name",
    "ceo_name",
    "business_address",
    "city",
    "state",
    "pincode",
    "country",
    "marketplace_profiles",
    "source_urls",
]


def _flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items())
    return str(value)


@api.get("/export")
@require_auth
def export_csv():
    enforce_rate_limit()
    ids = request.args.get("ids")
    query = {}
    if ids:
        wanted = [i.strip() for i in ids.split(",") if i.strip()]
        query = {"business_id": {"$in": wanted}}
    try:
        docs = list(db.businesses().find(query, {"_id": 0}))
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_FIELDS)
    for doc in docs:
        writer.writerow([_flatten(doc.get(field)) for field in EXPORT_FIELDS])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=seller_finder_export.csv"},
    )
