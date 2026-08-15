"""
Tests for scan-service.

Author: Elias
"""

import io
import os
import sys

import pytest


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_file = tmp_path / "test_scans.db"
    blob_dir = tmp_path / "blob"
    monkeypatch.setenv("SCAN_DB_PATH", str(db_file))
    monkeypatch.setenv("LOCAL_BLOB_FALLBACK_DIR", str(blob_dir))
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    # point at a tournament-service that doesn't exist on purpose - the
    # callback is best-effort and must not blow up the request
    monkeypatch.setenv("TOURNAMENT_SERVICE_URL", "http://localhost:59999")
    monkeypatch.setenv("NOTIFY_FUNCTION_URL", "")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "scan-service"))
    for mod in list(sys.modules):
        if mod in ("app", "blob_utils", "blacklist"):
            del sys.modules[mod]
    import app as scan_app

    scan_app.app.config["TESTING"] = True
    with scan_app.app.test_client() as c:
        yield c

    sys.path.pop(0)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["service"] == "scan-service"


def test_scan_missing_fields(client):
    resp = client.post("/api/scans", data={})
    assert resp.status_code == 400


def test_scan_clean_file_is_clear(client):
    data = {
        "registration_id": "reg-1",
        "tournament_id": "t-1",
        "gamertag": "xX_ShadowFrag_Xx",
        "evidence": (io.BytesIO(b"explorer.exe\nsteam.exe\nvalorant.exe\n"), "clean.txt"),
    }
    resp = client.post("/api/scans", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["verdict"] == "clear"
    assert body["matched_signatures"] == []
    assert body["certificate_url"] is not None


def test_scan_flagged_file_matches_keyword(client):
    data = {
        "registration_id": "reg-2",
        "tournament_id": "t-1",
        "gamertag": "qu1ckscope99",
        "evidence": (io.BytesIO(b"steam.exe\ncheatengine-x86_64.exe\naimbot loaded\n"), "suspicious.txt"),
    }
    resp = client.post("/api/scans", data=data, content_type="multipart/form-data")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["verdict"] == "flagged"
    assert "cheatengine" in body["matched_signatures"]
    assert "aimbot" in body["matched_signatures"]


def test_scan_known_bad_hash_is_flagged():
    from importlib import import_module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "scan-service"))
    blacklist = import_module("blacklist")
    import hashlib

    # craft bytes whose sha256 matches nothing real - just prove the lookup
    # function itself works against the known-bad table
    known_hash = list(blacklist.KNOWN_BAD_HASHES.keys())[0]
    assert blacklist.check_hash(known_hash) is not None
    assert blacklist.check_hash("0" * 64) is None
    sys.path.pop(0)


def test_flagged_feed_lists_only_flagged(client):
    client.post(
        "/api/scans",
        data={
            "registration_id": "reg-3",
            "tournament_id": "t-2",
            "gamertag": "cleanplayer",
            "evidence": (io.BytesIO(b"nothing suspicious here"), "ok.txt"),
        },
        content_type="multipart/form-data",
    )
    client.post(
        "/api/scans",
        data={
            "registration_id": "reg-4",
            "tournament_id": "t-2",
            "gamertag": "sketchyplayer",
            "evidence": (io.BytesIO(b"wallhack.dll injected"), "bad.txt"),
        },
        content_type="multipart/form-data",
    )

    resp = client.get("/api/scans/flagged?tournament_id=t-2")
    assert resp.status_code == 200
    flagged = resp.get_json()
    assert len(flagged) == 1
    assert flagged[0]["gamertag"] == "sketchyplayer"
