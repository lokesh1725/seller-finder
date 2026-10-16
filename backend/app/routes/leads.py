"""Saved leads CRUD.

A "lead" is a user's saved bookmark of a business, plus notes, tags and an
outreach status. There is no authentication layer in this build, so leads are
stored in a single shared workspace. The schema already carries an ``owner``
field so multi-user support can be added without a migration.
"""
from __future__ import annotations

import uuid

from flask import jsonify, request
from pymongo.errors import PyMongoError

from . import api, enforce_rate_limit
from .auth import require_auth
from .. import db
from ..db import DatabaseUnavailable
from ..errors import NotFound, ServiceUnavailable, ValidationError
from ..utils import clean_str, utcnow

OUTREACH_STATES = {"new", "contacted", "replied", "qualified", "won", "lost"}


def _default_lead(business_id: str) -> dict:
    return {
        "lead_id": uuid.uuid4().hex,
        "business_id": business_id,
        "notes": "",
        "tags": [],
        "outreach_status": "new",
        "owner": "default",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    for key in ("created_at", "updated_at"):
        if hasattr(doc.get(key), "isoformat"):
            doc[key] = doc[key].isoformat()
    return doc


@api.get("/leads")
@require_auth
def list_leads():
    enforce_rate_limit()
    try:
        docs = list(db.leads().find({}, {"_id": 0}).sort("created_at", -1))
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    return jsonify({"leads": [_serialize(d) for d in docs], "total": len(docs)})


@api.post("/leads")
@require_auth
def create_lead():
    enforce_rate_limit()
    body = request.get_json(silent=True) or {}
    business_id = clean_str(body.get("business_id"))
    if not business_id:
        raise ValidationError("Field 'business_id' is required")
    if not clean_str(body.get("company_name")) and not _business_exists(business_id):
        raise ValidationError("Unknown business_id")
    try:
        existing = db.leads().find_one({"business_id": business_id})
        if existing:
            return jsonify(_serialize(existing)), 200
        lead = _default_lead(business_id)
        lead["company_name"] = clean_str(body.get("company_name"))
        lead["slug"] = clean_str(body.get("slug"))
        lead["notes"] = clean_str(body.get("notes")) or ""
        lead["tags"] = _clean_tags(body.get("tags"))
        db.leads().insert_one(dict(lead))
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    return jsonify(_serialize(lead)), 201


@api.patch("/leads/<lead_id>")
@require_auth
def update_lead(lead_id: str):
    enforce_rate_limit()
    body = request.get_json(silent=True) or {}
    update: dict = {}
    if "notes" in body:
        update["notes"] = clean_str(body.get("notes")) or ""
    if "tags" in body:
        update["tags"] = _clean_tags(body.get("tags"))
    if "outreach_status" in body:
        status = clean_str(body.get("outreach_status"))
        if status not in OUTREACH_STATES:
            raise ValidationError(f"'outreach_status' must be one of {sorted(OUTREACH_STATES)}")
        update["outreach_status"] = status
    if not update:
        raise ValidationError("No supported fields supplied")
    update["updated_at"] = utcnow()
    try:
        result = db.leads().find_one_and_update(
            {"lead_id": lead_id}, {"$set": update}, return_document=True
        )
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    if not result:
        raise NotFound("Lead not found")
    return jsonify(_serialize(result))


@api.delete("/leads/<lead_id>")
@require_auth
def delete_lead(lead_id: str):
    enforce_rate_limit()
    try:
        result = db.leads().delete_one({"lead_id": lead_id})
    except DatabaseUnavailable as exc:
        raise ServiceUnavailable(str(exc))
    if result.deleted_count == 0:
        raise NotFound("Lead not found")
    return jsonify({"deleted": True, "lead_id": lead_id})


def _clean_tags(tags) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    if not isinstance(tags, list):
        raise ValidationError("'tags' must be a list or comma-separated string")
    cleaned = []
    for tag in tags:
        value = clean_str(tag)
        if value and value not in cleaned:
            cleaned.append(value[:40])
    return cleaned[:20]


def _business_exists(business_id: str) -> bool:
    try:
        return db.businesses().count_documents({"business_id": business_id}, limit=1) > 0
    except PyMongoError:
        return False
