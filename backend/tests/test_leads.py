def test_leads_crud_flow(client, seeded):
    assert client.get("/api/leads").get_json()["total"] == 0

    created = client.post(
        "/api/leads",
        json={"business_id": "gulabo-jaipur", "company_name": "Gulabo Jaipur", "tags": ["d2c", "priority"]},
    )
    assert created.status_code == 201
    lead = created.get_json()
    lead_id = lead["lead_id"]
    assert lead["outreach_status"] == "new"
    assert lead["tags"] == ["d2c", "priority"]

    listed = client.get("/api/leads").get_json()
    assert listed["total"] == 1

    updated = client.patch(
        f"/api/leads/{lead_id}",
        json={"outreach_status": "contacted", "notes": "Called founder", "tags": "d2c"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["outreach_status"] == "contacted"
    assert updated.get_json()["tags"] == ["d2c"]

    assert client.delete(f"/api/leads/{lead_id}").status_code == 200
    assert client.get("/api/leads").get_json()["total"] == 0


def test_create_lead_requires_business_id(client, seeded):
    assert client.post("/api/leads", json={}).status_code == 422


def test_create_lead_unknown_business_rejected(client, seeded):
    assert client.post("/api/leads", json={"business_id": "nope"}).status_code == 422


def test_create_lead_is_idempotent(client, seeded):
    payload = {"business_id": "bunaai", "company_name": "Bunaai"}
    first = client.post("/api/leads", json=payload)
    second = client.post("/api/leads", json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.get_json()["lead_id"] == second.get_json()["lead_id"]


def test_invalid_outreach_status_rejected(client, seeded):
    lead = client.post("/api/leads", json={"business_id": "bunaai"}).get_json()
    response = client.patch(f"/api/leads/{lead['lead_id']}", json={"outreach_status": "bogus"})
    assert response.status_code == 422


def test_update_missing_lead_returns_404(client, seeded):
    assert client.patch("/api/leads/missing", json={"notes": "x"}).status_code == 404
    assert client.delete("/api/leads/missing").status_code == 404
