"""
Tests for tournament-service.

Run from the repo root with:
    PYTHONPATH=services/tournament-service pytest tests/test_tournament_service.py

Author: Elias
"""

import importlib
import os
import sys
import tempfile

import pytest


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # Point the service at a throwaway sqlite db + local blob folder so
    # tests never touch real data or need Azure credentials.
    db_file = tmp_path / "test_tournaments.db"
    blob_dir = tmp_path / "blob"
    monkeypatch.setenv("TOURNAMENT_DB_PATH", str(db_file))
    monkeypatch.setenv("LOCAL_BLOB_FALLBACK_DIR", str(blob_dir))
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "tournament-service"))
    # force a fresh import so the env vars above take effect
    for mod in list(sys.modules):
        if mod in ("app", "blob_utils"):
            del sys.modules[mod]
    import app as tournament_app

    tournament_app.app.config["TESTING"] = True
    with tournament_app.app.test_client() as c:
        yield c

    sys.path.pop(0)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["service"] == "tournament-service"


def test_list_packages(client):
    resp = client.get("/api/packages")
    assert resp.status_code == 200
    packages = resp.get_json()
    assert len(packages) == 3
    ids = {p["id"] for p in packages}
    assert ids == {"bronze", "silver", "gold"}


def test_create_tournament_requires_fields(client):
    resp = client.post("/api/tournaments", json={"name": "Missing stuff"})
    assert resp.status_code == 400


def test_create_and_fetch_tournament(client):
    payload = {
        "name": "Berlin Winter Cup",
        "game": "Valorant",
        "format": "online",
        "organizer_name": "Elias",
        "start_date": "2026-09-01",
        "package_id": "silver",
    }
    resp = client.post("/api/tournaments", json=payload)
    assert resp.status_code == 201
    tournament = resp.get_json()
    assert tournament["status"] == "pending_payment"

    resp2 = client.get(f"/api/tournaments/{tournament['id']}")
    assert resp2.status_code == 200
    assert resp2.get_json()["package"]["id"] == "silver"


def test_unknown_package_rejected(client):
    payload = {
        "name": "Bad Cup",
        "game": "Chess",
        "organizer_name": "Elias",
        "start_date": "2026-09-01",
        "package_id": "platinum",  # doesn't exist
    }
    resp = client.post("/api/tournaments", json=payload)
    assert resp.status_code == 400


def test_purchase_activates_tournament(client):
    create_resp = client.post(
        "/api/tournaments",
        json={
            "name": "LAN Finals",
            "game": "CS2",
            "format": "lan",
            "organizer_name": "Elias",
            "start_date": "2026-10-01",
            "package_id": "bronze",
        },
    )
    tournament_id = create_resp.get_json()["id"]

    purchase_resp = client.post(f"/api/tournaments/{tournament_id}/purchase")
    assert purchase_resp.status_code == 201
    assert purchase_resp.get_json()["amount_usd"] == 49

    check = client.get(f"/api/tournaments/{tournament_id}")
    assert check.get_json()["status"] == "active"


def test_registration_flow_and_cap(client):
    create_resp = client.post(
        "/api/tournaments",
        json={
            "name": "Tiny Cup",
            "game": "Rocket League",
            "organizer_name": "Elias",
            "start_date": "2026-09-15",
            "package_id": "bronze",  # cap = 16, we'll just test one registration
        },
    )
    tournament_id = create_resp.get_json()["id"]

    reg_resp = client.post(
        f"/api/tournaments/{tournament_id}/registrations",
        json={"gamertag": "xX_ShadowFrag_Xx", "email": "shadow@example.com"},
    )
    assert reg_resp.status_code == 201
    registration = reg_resp.get_json()
    assert registration["scan_status"] == "not_submitted"

    list_resp = client.get(f"/api/tournaments/{tournament_id}/registrations")
    assert len(list_resp.get_json()) == 1


def test_scan_status_callback(client):
    create_resp = client.post(
        "/api/tournaments",
        json={
            "name": "Callback Cup",
            "game": "Chess",
            "organizer_name": "Elias",
            "start_date": "2026-09-20",
            "package_id": "gold",
        },
    )
    tournament_id = create_resp.get_json()["id"]
    reg_resp = client.post(
        f"/api/tournaments/{tournament_id}/registrations",
        json={"gamertag": "player1", "email": "p1@example.com"},
    )
    registration_id = reg_resp.get_json()["id"]

    patch_resp = client.patch(
        f"/api/registrations/{registration_id}/scan-status", json={"scan_status": "flagged"}
    )
    assert patch_resp.status_code == 200

    check = client.get(f"/api/registrations/{registration_id}")
    assert check.get_json()["scan_status"] == "flagged"
