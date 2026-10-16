def test_export_returns_csv_for_all(client, seeded):
    response = client.get("/api/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["Content-Type"]
    body = response.data.decode("utf-8")
    assert "company_name" in body
    assert "Gulabo Jaipur" in body
    assert "Bunaai" in body


def test_export_filters_by_ids(client, seeded):
    response = client.get("/api/export?ids=gulabo-jaipur")
    body = response.data.decode("utf-8")
    assert "Gulabo Jaipur" in body
    assert "Bunaai" not in body


def test_export_empty_query_selection(client, seeded):
    response = client.get("/api/export?ids=nope")
    body = response.data.decode("utf-8").strip().splitlines()
    # Only the header row when nothing matches.
    assert len(body) == 1
