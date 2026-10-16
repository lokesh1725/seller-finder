from app.services import importer


def test_import_creates_businesses_and_dedupes(app, test_db, sample_workbook):
    with app.app_context():
        summary = importer.import_workbook(sample_workbook)
    # 3 rows, two of which normalise to the same company -> 2 companies.
    assert summary["imported"] == 2
    assert summary["duplicates"] == 1
    assert test_db["businesses"].count_documents({}) == 2


def test_import_is_idempotent(app, test_db, sample_workbook):
    with app.app_context():
        first = importer.import_workbook(sample_workbook)
        second = importer.import_workbook(sample_workbook)
    assert first["imported"] == 2
    assert second["imported"] == 0
    assert second["updated"] == 0
    assert second["unchanged"] == 2
    assert test_db["businesses"].count_documents({}) == 2


def test_import_does_not_overwrite_valid_values(app, test_db, sample_workbook):
    with app.app_context():
        importer.import_workbook(sample_workbook)
        test_db["businesses"].update_one(
            {"normalized_name": "gulabo jaipur"},
            {"$set": {"business_email": "verified@official.com"}},
        )
        # Re-import must preserve the stored (valid) value, not the sheet value.
        importer.import_workbook(sample_workbook)
        doc = test_db["businesses"].find_one({"normalized_name": "gulabo jaipur"})
    assert doc["business_email"] == "verified@official.com"


def test_import_populates_prospects_and_notes(app, test_db, sample_workbook):
    with app.app_context():
        summary = importer.import_workbook(sample_workbook)
    assert summary["prospects"] == 1
    assert len(summary["notes"]) == 1
    assert test_db["prospects"].count_documents({}) == 1


def test_import_fields_are_marked_unverified(app, test_db, sample_workbook):
    with app.app_context():
        importer.import_workbook(sample_workbook)
        doc = test_db["businesses"].find_one({"normalized_name": "gulabo jaipur"})
    assert doc["field_verification_status"]["business_email"]["status"] == "unverified"
    assert doc["last_verified_at"] is None


def test_import_missing_file_raises(app, test_db, tmp_path):
    with app.app_context():
        try:
            importer.import_workbook(tmp_path / "missing.xlsx")
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass


def test_classify_business_type():
    assert importer.classify_business_type("D2C brand") == "Fashion D2C Brand"
    assert "Manufacturer" in importer.classify_business_type("Manufacturer / Exporter")
    assert importer.classify_business_type("D2C brand + marketplace seller").startswith(
        "Fashion D2C Brand"
    )
