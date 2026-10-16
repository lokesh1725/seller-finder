from app.services import company_research_service

def test_start_research(monkeypatch):
    job = company_research_service.start_research("HelmetShopee")
    assert job["job_id"]
    assert job["company_name"] == "HelmetShopee"
    assert job["status"] == "running"

def test_get_research(monkeypatch):
    job = company_research_service.start_research("Acme")
    got = company_research_service.get_research(job["job_id"])
    assert got is not None
    assert got["company_name"] == "Acme"
