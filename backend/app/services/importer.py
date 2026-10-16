"""Idempotent Excel importer.

Reads every worksheet of the source workbook:

* ``Leads``            -> business documents
* ``Top 10 Prospects`` -> prospect ranking metadata
* ``Notes``            -> reference text (stored with the import run, not as companies)

Import rules:
* Company names are normalised and duplicates are merged.
* Re-running the import never creates duplicate companies.
* Valid existing values are never overwritten by empty spreadsheet cells.
* Spreadsheet values are treated as *unverified*; nothing is fabricated.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .. import db
from ..utils import (
    clean_str,
    clean_url,
    domain_from_url,
    extract_emails,
    extract_parenthetical_aliases,
    extract_phones,
    extract_pincode,
    extract_urls,
    is_missing,
    normalize_name,
    slugify,
    utcnow,
)
from . import verification

logger = logging.getLogger(__name__)

DEFAULT_WORKBOOK = Path(__file__).resolve().parents[3] / "data" / "India_Product_Photography_Leads.xlsx"

LEAD_COLUMNS = {
    "index": "#",
    "company_name": "Company Name",
    "business_type": "Business Type",
    "product_category": "Product Category",
    "city": "City",
    "state": "State",
    "website": "Website",
    "linkedin": "LinkedIn Company URL",
    "email": "Business Email",
    "phone": "Business Phone",
    "address": "Business Address",
    "founder": "Founder/CEO",
    "founder_linkedin": "Founder/CEO LinkedIn",
    "marketplace": "Marketplace Links",
    "sources": "Sources",
}

# Keyword -> normalised category label.
_CATEGORY_RULES = [
    (("d2c", "direct to consumer", "direct-to-consumer"), "Fashion D2C Brand"),
    (("marketplace seller", "amazon", "flipkart", "myntra", "meesho", "e-commerce"), "E-commerce Seller"),
    (("manufactur", "exporter", "wholesaler", "supplier", "private label", "private-label", "oem", "odm", "knit", "dyeing", "printing", "embroidery"), "Manufacturer / Supplier"),
]


def classify_business_type(raw: str | None) -> str:
    if is_missing(raw):
        return "Uncategorised"
    text = str(raw).lower()
    matched = []
    for keywords, label in _CATEGORY_RULES:
        if any(k in text for k in keywords):
            matched.append(label)
    if not matched:
        return "Uncategorised"
    if len(matched) > 1:
        return " / ".join(matched)
    return matched[0]


def _split_categories(value) -> list[str]:
    text = clean_str(value)
    if not text:
        return []
    parts = []
    for chunk in text.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _parse_marketplace(value) -> list[dict]:
    text = clean_str(value)
    if not text:
        return []
    profiles = []
    for chunk in text.replace("|", ";").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        url_match = extract_urls(chunk)
        label = chunk.split(":")[0].strip() if ":" in chunk else chunk
        profiles.append({
            "label": label[:80],
            "url": url_match[0] if url_match else None,
        })
    return profiles


def build_document(row: dict, source_urls: list[str]) -> dict:
    raw_name = clean_str(row.get("company_name")) or ""
    base_name, aliases = extract_parenthetical_aliases(raw_name)
    business_type = clean_str(row.get("business_type"))
    addresses = clean_str(row.get("address"))

    emails = extract_emails(row.get("email"))
    phones = extract_phones(row.get("phone"))
    website = clean_url(extract_urls(row.get("website"))[0]) if extract_urls(row.get("website")) else None
    linkedin = clean_url(extract_urls(row.get("linkedin"))[0]) if extract_urls(row.get("linkedin")) else None
    founder = clean_str(row.get("founder"))
    founder_linkedin = clean_url(extract_urls(row.get("founder_linkedin"))[0]) if extract_urls(row.get("founder_linkedin")) else None

    export_capable = None
    if business_type and "export" in business_type.lower():
        export_capable = True

    manufacturer_caps: list[str] = []
    if business_type and any(k in business_type.lower() for k in ("manufactur", "knit", "dyeing", "printing", "embroidery")):
        manufacturer_caps.append(business_type)

    doc = {
        "company_name": base_name or raw_name,
        "alternate_names": aliases,
        "alternate_names_norm": [normalize_name(a) for a in aliases],
        "normalized_name": normalize_name(base_name or raw_name),
        "business_type_raw": business_type,
        "business_category": classify_business_type(business_type),
        "product_categories": _split_categories(row.get("product_category")),
        "official_website": website,
        "official_domain": domain_from_url(website),
        "business_email": emails[0] if emails else None,
        "business_emails": emails,
        "business_email_note": clean_str(row.get("email")) if emails else None,
        "business_phone": clean_str(row.get("phone")),
        "business_phones": phones,
        "linkedin_company_url": linkedin,
        "founder_name": founder,
        "founder_linkedin_url": founder_linkedin,
        "ceo_name": None,
        "business_address": addresses,
        "city": clean_str(row.get("city")),
        "state": clean_str(row.get("state")),
        "pincode": extract_pincode(addresses) or extract_pincode(row.get("city")),
        "country": "India",
        "marketplace_profiles": _parse_marketplace(row.get("marketplace")),
        "manufacturer_capabilities": manufacturer_caps,
        "minimum_order_quantity": None,
        "export_capability": export_capable,
        "source_urls": source_urls,
        "data_origin": "excel_import",
        "source_row": row.get("index"),
        "last_verified_at": None,
    }
    doc["field_verification_status"] = verification.build_field_statuses(
        doc, source_urls[0] if source_urls else None
    )
    doc["verification_summary"] = verification.summarize(doc["field_verification_status"])
    return doc


def _read_sheet(xls: pd.ExcelFile, name: str) -> pd.DataFrame:
    for sheet in xls.sheet_names:
        if sheet.strip().lower() == name.lower():
            return xls.parse(sheet)
    raise KeyError(f"Sheet '{name}' not found in workbook. Sheets: {xls.sheet_names}")


def _row_dict(row: pd.Series) -> dict:
    return {key: row.get(col) for key, col in LEAD_COLUMNS.items()}


def import_workbook(path: str | Path = DEFAULT_WORKBOOK, dry_run: bool = False) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Workbook not found at {path}. Place India_Product_Photography_Leads.xlsx in the data/ folder."
        )

    started = utcnow()
    xls = pd.ExcelFile(path)
    leads_df = _read_sheet(xls, "Leads")
    leads_df = leads_df.where(pd.notnull(leads_df), None)

    businesses = db.businesses()
    summary = {
        "workbook": str(path),
        "sheets_read": xls.sheet_names,
        "imported": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "duplicates": 0,
        "incomplete": 0,
        "prospects": 0,
        "errors": [],
        "started_at": started.isoformat(),
    }

    seen: dict[str, dict] = {}
    ordered: list[dict] = []
    for _, row in leads_df.iterrows():
        if row.isnull().all():
            continue
        data = _row_dict(row)
        if is_missing(data.get("company_name")):
            summary["skipped"] += 1
            continue
        source_urls = extract_urls(data.get("sources"))
        doc = build_document(data, source_urls)
        norm = doc["normalized_name"]
        if not norm:
            summary["skipped"] += 1
            continue
        if norm in seen:
            # Merge duplicate rows within the workbook rather than importing twice.
            summary["duplicates"] += 1
            existing = seen[norm]
            for key, value in doc.items():
                if existing.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                    existing[key] = value
            continue
        seen[norm] = doc
        ordered.append(doc)

    # Assign deterministic, collision-free business ids / slugs.
    used_ids: set[str] = set()
    for doc in ordered:
        base_slug = slugify(doc["company_name"])
        candidate = base_slug
        counter = 2
        while candidate in used_ids:
            candidate = f"{base_slug}-{counter}"
            counter += 1
        used_ids.add(candidate)
        doc["business_id"] = candidate
        doc["slug"] = candidate

        missing_fields = [
            f for f in verification.TRACKED_FIELDS if not doc.get(f)
        ]
        if missing_fields:
            summary["incomplete"] += 1

        if dry_run:
            summary["imported"] += 1
            continue

        existing = businesses.find_one({"normalized_name": doc["normalized_name"]})
        now = utcnow()
        if existing:
            # Preserve existing valid values; only fill gaps.
            update = {}
            for key, value in doc.items():
                if value in (None, "", [], {}):
                    continue
                if existing.get(key) in (None, "", [], {}):
                    update[key] = value
            update["updated_at"] = now
            # Keep the original id/slug stable.
            update.pop("business_id", None)
            update.pop("slug", None)
            changed = [k for k in update if k != "updated_at"]
            if changed:
                businesses.update_one({"_id": existing["_id"]}, {"$set": update})
                summary["updated"] += 1
            else:
                summary["unchanged"] += 1
        else:
            doc["created_at"] = now
            doc["updated_at"] = now
            try:
                businesses.insert_one(dict(doc))
                summary["imported"] += 1
            except Exception as exc:  # duplicate key safety
                summary["errors"].append(f"{doc['company_name']}: {exc}")
                summary["skipped"] += 1

    # --- Top 10 Prospects sheet ---
    try:
        prospects_df = _read_sheet(xls, "Top 10 Prospects")
        prospects_df = prospects_df.where(pd.notnull(prospects_df), None)
        prospect_coll = db.prospects()
        for _, row in prospects_df.iterrows():
            company = clean_str(row.get("Company Name"))
            if not company:
                continue
            prospect_coll.update_one(
                {"company_name": company},
                {
                    "$set": {
                        "company_name": company,
                        "rank": int(row.get("Rank")) if row.get("Rank") is not None else None,
                        "city": clean_str(row.get("City")),
                        "rationale": clean_str(
                            row.get("Why it's a strong prospect for AI product photography")
                        ),
                        "updated_at": utcnow(),
                    },
                    "$setOnInsert": {"created_at": utcnow()},
                },
                upsert=True,
            )
            summary["prospects"] += 1
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"Top 10 Prospects: {exc}")

    # --- Notes sheet (reference only) ---
    notes: list[str] = []
    try:
        notes_df = _read_sheet(xls, "Notes")
        for _, row in notes_df.iterrows():
            for value in row.tolist():
                text = clean_str(value)
                if text:
                    notes.append(text)
    except Exception as exc:  # noqa: BLE001
        summary["errors"].append(f"Notes: {exc}")
    summary["notes"] = notes

    summary["finished_at"] = utcnow().isoformat()
    if not dry_run:
        try:
            db.import_runs().insert_one({
                "started_at": started,
                "finished_at": utcnow(),
                "workbook": str(path),
                "summary": {k: v for k, v in summary.items() if k not in ("notes",)},
            })
        except Exception:  # pragma: no cover
            pass
    return summary
