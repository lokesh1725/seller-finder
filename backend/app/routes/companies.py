"""Company endpoints."""
from __future__ import annotations

from flask import jsonify, request

from . import api, enforce_rate_limit
from .auth import require_auth
from .. import db
from ..errors import ValidationError
from ..utils import normalize_name

@api.get("/companies")
@require_auth
def list_companies():
    enforce_rate_limit()
    q = request.args.get("q", "").strip()
    coll = db.get_db()["companies"]
    if q:
        norm = normalize_name(q)
        cursor = coll.find({"normalized_name": {"$regex": norm, "$options": "i"}}).limit(20)
    else:
        cursor = coll.find({}).limit(50)
    out = []
    for d in cursor:
        d = dict(d)
        d.pop("_id", None)
        out.append(d)
    return jsonify(out)

@api.get("/companies/<company_id>")
@require_auth
def get_company(company_id: str):
    coll = db.get_db()["companies"]
    d = coll.find_one({"business_id": company_id}) or coll.find_one({"slug": company_id})
    if not d:
        raise ValidationError("company not found")
    d = dict(d)
    d.pop("_id", None)
    return jsonify(d)

@api.post("/companies/<company_id>/save")
@require_auth
def save_company(company_id: str):
    coll = db.get_db()["companies"]
    d = coll.find_one({"business_id": company_id}) or coll.find_one({"slug": company_id})
    if not d:
        raise ValidationError("company not found")
    leads = db.get_db()["saved_leads"]
    leads.update_one({"business_id": d.get("business_id")}, {"$set": {"business_id": d.get("business_id"), "slug": d.get("slug"), "company_name": d.get("company_name"), "source": "companies"}}, upsert=True)
    return jsonify({"saved": True})

@api.get("/companies/<company_id>/sources")
@require_auth
def company_sources(company_id: str):
    coll = db.get_db()["companies"]
    d = coll.find_one({"business_id": company_id}) or coll.find_one({"slug": company_id})
    if not d:
        raise ValidationError("company not found")
    return jsonify({"company_id": company_id, "sources": d.get("source_urls", [])})
