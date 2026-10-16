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

@api.get("/export/all")
@require_auth
def export_all():
    enforce_rate_limit()
    from flask import Response
    import csv
    import io
    from .. import db
    from ..utils import utcnow

    business_coll = db.businesses()
    output = io.StringIO()
    fieldnames = [
        "company_name",
        "business_category",
        "official_website",
        "business_email",
        "business_phone",
        "linkedin_company_url",
        "founder_name",
        "ceo_name",
        "founder_linkedin_url",
        "business_address",
        "city",
        "state",
        "pincode",
        "country",
        "official_domain",
        "data_origin",
        "lead_priority_score",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for doc in business_coll.find({}, {"_id":0}):
        writer.writerow({k: doc.get(k) if doc.get(k) not in ([], {}) else "" for k in fieldnames})
    output.seek(0)
    data = output.getvalue()
    filename = f"seller_finder_export_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@api.get("/export/research/<job_id>")
@require_auth
def export_research(job_id: str):
    enforce_rate_limit()
    from flask import Response
    import csv
    import io
    from ..utils import utcnow
    from ..services import company_research_service

    job = company_research_service.get_research(job_id)
    if not job:
        from ..errors import ValidationError
        raise ValidationError("job not found")
    res = job.get("results") or {}
    output = io.StringIO()
    fieldnames = [
        "company_name",
        "founder_name",
        "founder_designation",
        "founder_linkedin_url",
        "public_professional_email",
        "public_professional_phone",
        "business_email",
        "business_phone",
        "business_address",
        "source_urls",
        "confidence",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    f = res.get("founders", [{}])[0] if res.get("founders") else {}
    writer.writerow({
        "company_name": res.get("company_name", job.get("company_name")),
        "founder_name": f.get("name"),
        "founder_designation": f.get("designation"),
        "founder_linkedin_url": f.get("linkedin_url"),
        "public_professional_email": f.get("public_professional_email"),
        "public_professional_phone": f.get("public_professional_phone"),
        "business_email": res.get("contacts", {}).get("business_email"),
        "business_phone": res.get("contacts", {}).get("business_phone"),
        "business_address": res.get("business_address"),
        "source_urls": ";".join(res.get("source_urls", [])),
        "confidence": res.get("confidence"),
    })
    output.seek(0)
    data = output.getvalue()
    filename = f"research_{job_id}_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(data, mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})
