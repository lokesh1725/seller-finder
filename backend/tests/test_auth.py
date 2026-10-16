"""Authentication tests.

Covers the login endpoint, token-verified /auth/me, and enforcement of
require_auth on protected endpoints. The suite runs with TESTING=True which
bypasses the auth guard for convenience; these tests temporarily set
AUTH_REQUIRED=True to assert the guard actually blocks anonymous requests.
"""
from __future__ import annotations

import pytest


def login(client, email="admin@gmail.com", password="Test@123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_success_returns_token_and_user(client):
    resp = login(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["token"]
    assert body["user"]["email"] == "admin@gmail.com"


def test_login_is_case_insensitive_for_email(client):
    resp = login(client, email="Admin@Gmail.com")
    assert resp.status_code == 200


def test_login_wrong_password_rejected(client):
    resp = login(client, password="wrong")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "unauthorized"


def test_login_wrong_email_rejected(client):
    resp = login(client, email="nobody@example.com")
    assert resp.status_code == 401


def test_login_missing_fields_rejected(client):
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 422


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_token(client):
    token = login(client).get_json()["token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "admin@gmail.com"


def test_me_with_garbage_token_rejected(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


@pytest.fixture()
def auth_required(app):
    previous = app.config.get("AUTH_REQUIRED")
    app.config["AUTH_REQUIRED"] = True
    yield
    app.config["AUTH_REQUIRED"] = previous


def test_protected_search_blocked_without_token(client, auth_required):
    resp = client.get("/api/search?q=denim")
    assert resp.status_code == 401


def test_protected_search_allowed_with_token(client, auth_required):
    token = login(client).get_json()["token"]
    resp = client.get(
        "/api/search?q=denim", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200


def test_public_business_profile_stays_open(client, auth_required):
    # A non-existent slug still proves the route is reachable without auth
    # (404 rather than 401 means the auth guard did not block it).
    resp = client.get("/api/businesses/does-not-exist")
    assert resp.status_code in (404,)
