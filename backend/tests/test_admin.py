def test_admin_import_runs_dry_run(client, test_db, sample_workbook):
    response = client.post(
        "/api/admin/import", json={"path": str(sample_workbook), "dry_run": True}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["dry_run"] is True
    assert body["summary"]["imported"] == 2


def test_admin_import_missing_file(client, test_db, tmp_path):
    response = client.post("/api/admin/import", json={"path": str(tmp_path / "no.xlsx")})
    assert response.status_code == 422


def test_admin_import_enforces_token_when_configured(app, client, test_db, sample_workbook):
    app.config["ADMIN_API_TOKEN"] = "secret-token"
    app.config["FLASK_ENV"] = "production"
    try:
        denied = client.post("/api/admin/import", json={"path": str(sample_workbook)})
        assert denied.status_code == 401

        allowed = client.post(
            "/api/admin/import",
            json={"path": str(sample_workbook)},
            headers={"X-Admin-Token": "secret-token"},
        )
        assert allowed.status_code == 200

        bearer = client.post(
            "/api/admin/import",
            json={"path": str(sample_workbook)},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert bearer.status_code == 200
    finally:
        app.config["ADMIN_API_TOKEN"] = ""
        app.config["FLASK_ENV"] = "testing"
