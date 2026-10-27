"""Shared pytest fixtures.

Tests run against a dedicated MongoDB database (``seller_finder_test``) so they
never touch real data. A small synthetic workbook is generated on the fly so
importer behaviour is tested deterministically, independent of the production
file. External search calls are mocked so no API credentials are required.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Must be set before the app package imports Config defaults.
os.environ.setdefault("MONGODB_DATABASE", "seller_finder_test")
os.environ.setdefault("SEARCH_PROVIDER", "none")
os.environ.setdefault("FLASK_ENV", "testing")

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app import db as db_module  # noqa: E402


@pytest.fixture(scope="session")
def app():
    application = create_app(TestConfig)
    application.config["MONGODB_DATABASE"] = "seller_finder_test"
    application.config["TESTING"] = True

    # Skip the whole DB-backed suite gracefully if MongoDB is unavailable.
    with application.app_context():
        reachable, _ = db_module.ping()
        if not reachable:
            pytest.skip("MongoDB is not available for tests")
        from app.schema import ensure_indexes
        ensure_indexes()
    yield application
    db_module.close_clients()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    """Log in with default dev credentials and return Authorization headers."""
    resp = client.post(
        "/api/auth/login",
        json={"email": "admin@gmail.com", "password": "Test@123"},
    )
    assert resp.status_code == 200, resp.get_json()
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def test_db(app):
    research_collections = (
        "businesses",
        "leads",
        "prospects",
        "search_cache",
        "import_runs",
        "companies",
        "research_jobs",
        "source_evidence",
        "saved_leads",
    )
    with app.app_context():
        database = db_module.get_client()["seller_finder_test"]
        for name in research_collections:
            database[name].delete_many({})
        yield database
        for name in research_collections:
            database[name].delete_many({})


@pytest.fixture()
def sample_workbook(tmp_path) -> Path:
    """A small workbook mirroring the real file's columns and quirks."""
    leads = pd.DataFrame(
        [
            {
                "#": 1,
                "Company Name": "Gulabo Jaipur",
                "Business Type": "D2C brand (own manufacturing)",
                "Product Category": "Ethnic wear, kidswear",
                "City": "Jaipur",
                "State": "Rajasthan",
                "Website": "https://www.gulabojaipur.com",
                "LinkedIn Company URL": "Not found",
                "Business Email": "sales@gulabojaipur.com (business queries)",
                "Business Phone": "+91 86901 67971",
                "Business Address": "388 Bhojpura Sahkar Road, Jaipur 302015",
                "Founder/CEO": "Not found",
                "Founder/CEO LinkedIn": "Not found",
                "Marketplace Links": "Not found",
                "Sources": "https://www.gulabojaipur.com/pages/contact-us",
            },
            {
                "#": 2,
                "Company Name": "Bunaai (now trading as Bunai)",
                "Business Type": "D2C brand",
                "Product Category": "Women's ethnic wear, sarees",
                "City": "Jaipur",
                "State": "Rajasthan",
                "Website": "https://www.bunai.com",
                "LinkedIn Company URL": "https://www.linkedin.com/company/bunaai-official/",
                "Business Email": "Not found",
                "Business Phone": "Not found",
                "Business Address": "RIICO Industrial Area, Sitapura, Jaipur 302022",
                "Founder/CEO": "Not found",
                "Founder/CEO LinkedIn": "Not found",
                "Marketplace Links": "Not found",
                "Sources": "https://www.bunai.com/pages/contact-us",
            },
            {
                "#": 3,
                "Company Name": "gulabo jaipur",
                "Business Type": "D2C brand",
                "Product Category": "Ethnic wear",
                "City": "Jaipur",
                "State": "Rajasthan",
                "Website": "Not found",
                "LinkedIn Company URL": "Not found",
                "Business Email": "Not found",
                "Business Phone": "Not found",
                "Business Address": "Not found",
                "Founder/CEO": "Not found",
                "Founder/CEO LinkedIn": "Not found",
                "Marketplace Links": "Not found",
                "Sources": "Not found",
            },
        ]
    )
    prospects = pd.DataFrame(
        [{"Rank": 1, "Company Name": "Gulabo Jaipur", "City": "Jaipur", "Why it's a strong prospect for AI product photography": "Large catalogue"}]
    )
    notes = pd.DataFrame({"How to read this sheet": ["Values taken from sources; 'Not found' means nothing reliable was located."]})

    path = tmp_path / "sample_leads.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        leads.to_excel(writer, sheet_name="Leads", index=False)
        prospects.to_excel(writer, sheet_name="Top 10 Prospects", index=False)
        notes.to_excel(writer, sheet_name="Notes", index=False)
    return path


@pytest.fixture()
def seeded(app, test_db, sample_workbook):
    """Import the sample workbook into the test database."""
    from app.services import importer
    with app.app_context():
        summary = importer.import_workbook(sample_workbook)
    return summary
