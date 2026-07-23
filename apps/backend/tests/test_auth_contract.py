"""Auth contract and realm separation smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_auth_contract_exposes_refresh_and_logout() -> None:
    response = client.get("/api/v1/auth/contract")
    assert response.status_code == 200
    body = response.json()
    assert body["admin_refresh"].endswith("/admin/refresh")
    assert body["voter_logout"].endswith("/voter/logout")
    assert "CSRF" in body["note"]


def test_admin_and_voter_cookies_are_distinct() -> None:
    from app.auth.realms import (
        ADMIN_ACCESS_COOKIE,
        ADMIN_REFRESH_COOKIE,
        VOTER_ACCESS_COOKIE,
        VOTER_REFRESH_COOKIE,
    )

    assert ADMIN_ACCESS_COOKIE != VOTER_ACCESS_COOKIE
    assert ADMIN_REFRESH_COOKIE != VOTER_REFRESH_COOKIE


def test_voter_ballot_requires_auth() -> None:
    response = client.post(
        "/api/v1/voter/elections/00000000-0000-0000-0000-000000000001/ballots",
        json={
            "encrypted_payload": "x" * 40,
            "receipt_hash": "a" * 64,
            "zkp_proof": "development-pilot-proof-" + ("b" * 40),
            "key_version": "v1",
        },
    )
    assert response.status_code == 401


def test_public_verify_rejects_short_hash() -> None:
    response = client.get("/api/v1/public/verify/abcd")
    assert response.status_code == 422
