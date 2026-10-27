"""MongoDB collection initialisation and index creation.

:func:`ensure_indexes` is idempotent and safe to call on every boot.
"""
from __future__ import annotations

import logging

from pymongo import ASCENDING, TEXT

from . import db

logger = logging.getLogger(__name__)


def ensure_indexes() -> None:
    database = db.get_db()

    businesses = database["businesses"]
    businesses.create_index("business_id", unique=True, name="uniq_business_id")
    businesses.create_index("slug", unique=True, name="uniq_slug")
    businesses.create_index("normalized_name", name="idx_normalized_name")
    businesses.create_index("business_category", name="idx_category")
    businesses.create_index("city", name="idx_city")
    businesses.create_index("state", name="idx_state")
    businesses.create_index("official_domain", name="idx_domain")
    businesses.create_index("lead_priority_score", name="idx_lead_priority")
    # Ranked full-text style search across the important name fields.
    businesses.create_index(
        [
            ("company_name", TEXT),
            ("alternate_names", TEXT),
            ("product_categories", TEXT),
            ("city", TEXT),
        ],
        name="idx_fulltext",
        default_language="none",
    )

    leads = database["leads"]
    leads.create_index("lead_id", unique=True, name="uniq_lead_id")
    leads.create_index("business_id", name="idx_lead_business")
    leads.create_index([("created_at", ASCENDING)], name="idx_lead_created")

    prospects = database["prospects"]
    prospects.create_index("company_name", unique=True, name="uniq_prospect_name")

    import_runs = database["import_runs"]
    import_runs.create_index([("started_at", ASCENDING)], name="idx_import_started")

    search_cache = database["search_cache"]
    search_cache.create_index("cache_key", unique=True, name="uniq_cache_key")
    search_cache.create_index("expires_at", expireAfterSeconds=0, name="ttl_cache")

    logger.info("MongoDB indexes ensured for database '%s'", db.Config.MONGODB_DATABASE)

    # Research and evidence
    research_jobs = database["research_jobs"]
    research_jobs.create_index("job_id", unique=True, name="uniq_research_job_id")
    research_jobs.create_index("company_name_norm", name="idx_research_company_norm")
    research_jobs.create_index([("created_at", ASCENDING)], name="idx_research_created")

    source_evidence = database["source_evidence"]
    source_evidence.create_index("evidence_id", unique=True, name="uniq_evidence_id")
    source_evidence.create_index("company_id", name="idx_evidence_company")

    companies = database["companies"]
    companies.create_index("business_id", unique=True, name="uniq_company_business_id")
    companies.create_index("slug", unique=True, name="uniq_company_slug")
    companies.create_index("normalized_name", name="idx_company_normalized_name")
    companies.create_index("official_domain", name="idx_company_domain")
    companies.create_index([("last_researched_at", ASCENDING)], name="idx_company_last_researched")
    companies.create_index([("next_refresh_at", ASCENDING)], name="idx_company_next_refresh")

    saved_leads = database["saved_leads"]
    saved_leads.create_index("business_id", unique=True, name="uniq_saved_lead_business_id")
    saved_leads.create_index([("saved_at", ASCENDING)], name="idx_saved_lead_saved_at")

    research_jobs.create_index(
        [("company_name_norm", ASCENDING), ("status", ASCENDING)],
        name="idx_research_norm_status",
    )
