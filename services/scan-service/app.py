"""
MatchGuard - Scan Service
--------------------------
Second microservice. Owns evidence upload, hashing, keyword scanning against
the blacklist, and the flagged-incidents feed the organizer dashboard reads
from. Talks to:
  - Azure Blob Storage (evidence files + generated certificates)
  - tournament-service, over REST, to update a registration's scan_status
  - the notify-function (Azure Function, serverless), over HTTP, to generate
    a verification certificate once a verdict is reached

Author: Elias
Course: Cloud Computing - Final Project (Aug 2026)
"""

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import requests
from flask import Flask, g, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
    HAS_FLASK_CORS = True
except ImportError:  # pragma: no cover
    HAS_FLASK_CORS = False

from blacklist import check_hash, scan_text_for_keywords
from blob_utils import upload_bytes, LOCAL_FALLBACK_DIR

DB_PATH = os.environ.get("SCAN_DB_PATH", os.path.join(os.path.dirname(__file__), "scans.db"))
EVIDENCE_CONTAINER = os.environ.get("EVIDENCE_CONTAINER_NAME", "scan-evidence")

# Where the other pieces of the system live. Inside docker-compose / k8s
# these are service DNS names, e.g. http://tournament-service:5001
TOURNAMENT_SERVICE_URL = os.environ.get("TOURNAMENT_SERVICE_URL", "http://localhost:5001")
NOTIFY_FUNCTION_URL = os.environ.get("NOTIFY_FUNCTION_URL", "")  # empty = not deployed yet, use local fallback

app = Flask(__name__)

if HAS_FLASK_CORS:
    CORS(app)
else:
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
        return response


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id TEXT PRIMARY KEY,
            registration_id TEXT NOT NULL,
            tournament_id TEXT NOT NULL,
            gamertag TEXT,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            verdict TEXT NOT NULL,          -- 'clear' or 'flagged'
            matched_signatures TEXT,        -- JSON list
            evidence_url TEXT NOT NULL,
            certificate_url TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row):
    d = {k: row[k] for k in row.keys()}
    if d.get("matched_signatures"):
        d["matched_signatures"] = json.loads(d["matched_signatures"])
    else:
        d["matched_signatures"] = []
    return d


@app.get("/api/health")
def health():
    return jsonify({"service": "scan-service", "status": "ok", "time": now_iso()})


@app.get("/local-blob/<container>/<path:blob_name>")
def serve_local_blob(container, blob_name):
    """Only used when AZURE_STORAGE_CONNECTION_STRING isn't configured."""
    return send_from_directory(os.path.join(LOCAL_FALLBACK_DIR, container), blob_name)


def _notify_tournament_service(registration_id, scan_status):
    """Best-effort callback - if tournament-service is briefly unreachable we
    don't want to fail the whole scan, the organizer dashboard just won't be
    perfectly up to date until the next retry. Logged, not raised."""
    try:
        requests.patch(
            f"{TOURNAMENT_SERVICE_URL}/api/registrations/{registration_id}/scan-status",
            json={"scan_status": scan_status},
            timeout=5,
        )
    except requests.RequestException as exc:
        app.logger.warning("could not reach tournament-service to update scan status: %s", exc)


def _generate_certificate(scan_record):
    """Calls the serverless notify-function to generate a verification
    certificate. If the function isn't deployed yet (no NOTIFY_FUNCTION_URL
    configured, e.g. you're just testing locally) we generate the same
    certificate text ourselves and upload it, so the feature still works
    end to end - just without the real Azure Function in the loop.
    """
    payload = {
        "scan_id": scan_record["id"],
        "gamertag": scan_record["gamertag"],
        "tournament_id": scan_record["tournament_id"],
        "verdict": scan_record["verdict"],
        "sha256": scan_record["sha256"],
        "created_at": scan_record["created_at"],
    }

    if NOTIFY_FUNCTION_URL:
        try:
            resp = requests.post(NOTIFY_FUNCTION_URL, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json().get("certificate_url")
        except requests.RequestException as exc:
            app.logger.warning("notify-function call failed, falling back to local cert generation: %s", exc)

    # Local fallback - mirrors exactly what serverless/notify-function does
    cert_text = (
        f"MATCHGUARD VERIFICATION CERTIFICATE\n"
        f"------------------------------------\n"
        f"Scan ID       : {payload['scan_id']}\n"
        f"Player        : {payload['gamertag']}\n"
        f"Tournament ID : {payload['tournament_id']}\n"
        f"Verdict       : {payload['verdict'].upper()}\n"
        f"File SHA-256  : {payload['sha256']}\n"
        f"Issued at     : {payload['created_at']}\n"
        f"Issued by     : MatchGuard Anti-Cheat Verification (serverless, local fallback mode)\n"
    )
    blob_name = f"{payload['scan_id']}.txt"
    return upload_bytes("certificates", blob_name, cert_text.encode("utf-8"), "text/plain")


@app.post("/api/scans")
def submit_scan():
    """Accepts a multipart upload: registration_id, tournament_id, gamertag,
    evidence (file). Runs the scan synchronously - fine for a project this
    size, a production system would push this to a queue instead."""
    registration_id = request.form.get("registration_id")
    tournament_id = request.form.get("tournament_id")
    gamertag = request.form.get("gamertag", "unknown")
    evidence_file = request.files.get("evidence")

    if not registration_id or not tournament_id or not evidence_file:
        return jsonify({"error": "registration_id, tournament_id and evidence file are required"}), 400

    file_bytes = evidence_file.read()
    sha256_hex = hashlib.sha256(file_bytes).hexdigest()

    # Try to decode as text for the keyword scan - if it's not a text file
    # (e.g. someone uploads a binary dump) we just skip the keyword pass and
    # rely on the hash check only.
    try:
        text_content = file_bytes.decode("utf-8", errors="ignore")
        matched = scan_text_for_keywords(text_content)
    except Exception:
        matched = []

    hash_hit = check_hash(sha256_hex)
    if hash_hit:
        matched = matched + [hash_hit]

    verdict = "flagged" if matched else "clear"

    blob_name = f"{registration_id}-{uuid.uuid4().hex[:8]}-{evidence_file.filename}"
    evidence_url = upload_bytes(EVIDENCE_CONTAINER, blob_name, file_bytes, evidence_file.content_type)

    scan_id = str(uuid.uuid4())
    created_at = now_iso()

    db = get_db()
    db.execute(
        "INSERT INTO scans (id, registration_id, tournament_id, gamertag, filename, sha256, verdict, "
        "matched_signatures, evidence_url, certificate_url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            scan_id,
            registration_id,
            tournament_id,
            gamertag,
            evidence_file.filename,
            sha256_hex,
            verdict,
            json.dumps(matched),
            evidence_url,
            None,
            created_at,
        ),
    )
    db.commit()

    record = row_to_dict(db.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone())
    certificate_url = _generate_certificate(record)
    db.execute("UPDATE scans SET certificate_url = ? WHERE id = ?", (certificate_url, scan_id))
    db.commit()

    _notify_tournament_service(registration_id, verdict)

    record["certificate_url"] = certificate_url
    return jsonify(record), 201


@app.get("/api/scans/flagged")
def flagged_scans():
    """Feeds the organizer dashboard's 'Flagged players' panel."""
    db = get_db()
    tournament_id = request.args.get("tournament_id")
    if tournament_id:
        rows = db.execute(
            "SELECT * FROM scans WHERE verdict = 'flagged' AND tournament_id = ? ORDER BY created_at DESC",
            (tournament_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM scans WHERE verdict = 'flagged' ORDER BY created_at DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/scans/tournament/<tournament_id>")
def scans_for_tournament(tournament_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM scans WHERE tournament_id = ? ORDER BY created_at DESC", (tournament_id,)
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/scans/registration/<registration_id>")
def scans_for_registration(registration_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM scans WHERE registration_id = ? ORDER BY created_at DESC", (registration_id,)
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5002)), debug=True)
