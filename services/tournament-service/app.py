"""
MatchGuard - Tournament Service
--------------------------------
Owns everything related to tournaments, anti-cheat packages and purchases.
This is one of the two Flask microservices in the MatchGuard platform - it
does NOT know anything about how scanning/evidence works, that lives in the
scan-service. The two talk to each other only through REST, same as we did
in the "monolithic -> microservice" lab.

Author: Elias
Course: Cloud Computing - Final Project (Aug 2026)

Quick and dirty note to self: keeping this on plain sqlite3 instead of
pulling in SQLAlchemy, we don't need an ORM for a project this size and it
keeps the Docker image small.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request, send_from_directory

try:
    from flask_cors import CORS
    HAS_FLASK_CORS = True
except ImportError:  # pragma: no cover - falls back to the manual handler below
    HAS_FLASK_CORS = False

from blob_utils import upload_bytes, is_blob_configured, LOCAL_FALLBACK_DIR

DB_PATH = os.environ.get("TOURNAMENT_DB_PATH", os.path.join(os.path.dirname(__file__), "tournaments.db"))
BANNER_CONTAINER = os.environ.get("BANNER_CONTAINER_NAME", "tournament-banners")

app = Flask(__name__)

if HAS_FLASK_CORS:
    CORS(app)  # frontend is served from a different origin/container, needs this
else:
    # Minimal hand-rolled fallback so this still works on a box where
    # flask-cors hasn't been installed (same headers flask-cors would add).
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
        return response

# ---------------------------------------------------------------------------
# Anti-cheat service packages. In a "real" business these would live in a
# billing table, but for the scope of this project a hardcoded catalogue is
# plenty - the important part is that a package purchase drives what level
# of scanning the scan-service is allowed to run for that tournament.
# ---------------------------------------------------------------------------
PACKAGES = [
    {
        "id": "bronze",
        "name": "Bronze",
        "price_usd": 49,
        "max_players": 16,
        "tagline": "For small LAN parties and community cups",
        "features": [
            "Known cheat-signature hash scan",
            "Up to 16 registered players",
            "Digital verification certificate",
        ],
    },
    {
        "id": "silver",
        "name": "Silver",
        "price_usd": 149,
        "max_players": 64,
        "tagline": "For weekly online ladders and regional LANs",
        "features": [
            "Everything in Bronze",
            "Process/log keyword scanning (aimbot, wallhack, injector signatures)",
            "Up to 64 registered players",
            "Flagged-player dashboard for organizers",
        ],
    },
    {
        "id": "gold",
        "name": "Gold",
        "price_usd": 399,
        "max_players": None,  # unlimited
        "tagline": "For major online tournaments and LAN finals",
        "features": [
            "Everything in Silver",
            "Unlimited registered players",
            "Manual review escalation queue",
            "On-site LAN check-in kiosk mode",
        ],
    },
]
PACKAGES_BY_ID = {p["id"]: p for p in PACKAGES}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
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
        CREATE TABLE IF NOT EXISTS tournaments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            game TEXT NOT NULL,
            format TEXT NOT NULL,          -- 'online' or 'lan'
            organizer_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            package_id TEXT NOT NULL,
            banner_url TEXT,
            status TEXT NOT NULL DEFAULT 'pending_payment',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS purchases (
            id TEXT PRIMARY KEY,
            tournament_id TEXT NOT NULL,
            package_id TEXT NOT NULL,
            amount_usd INTEGER NOT NULL,
            payment_ref TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id TEXT PRIMARY KEY,
            tournament_id TEXT NOT NULL,
            gamertag TEXT NOT NULL,
            email TEXT NOT NULL,
            scan_status TEXT NOT NULL DEFAULT 'not_submitted',
            created_at TEXT NOT NULL,
            FOREIGN KEY (tournament_id) REFERENCES tournaments(id)
        );
        """
    )
    db.commit()
    db.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------------
# Health check - Kubernetes readiness/liveness probes hit this
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify({"service": "tournament-service", "status": "ok", "time": now_iso()})


@app.get("/local-blob/<container>/<path:blob_name>")
def serve_local_blob(container, blob_name):
    """Only used when AZURE_STORAGE_CONNECTION_STRING isn't configured -
    lets banner images still render in the browser during local dev."""
    return send_from_directory(os.path.join(LOCAL_FALLBACK_DIR, container), blob_name)


# ---------------------------------------------------------------------------
# Packages catalogue
# ---------------------------------------------------------------------------
@app.get("/api/packages")
def list_packages():
    return jsonify(PACKAGES)


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------
@app.get("/api/tournaments")
def list_tournaments():
    db = get_db()
    rows = db.execute("SELECT * FROM tournaments ORDER BY created_at DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/tournaments")
def create_tournament():
    # Accept either multipart/form-data (with an optional banner image file)
    # or plain JSON, so the frontend has flexibility depending on the form.
    if request.content_type and "multipart/form-data" in request.content_type:
        form = request.form
        name = form.get("name")
        game = form.get("game")
        fmt = form.get("format", "online")
        organizer_name = form.get("organizer_name")
        start_date = form.get("start_date")
        package_id = form.get("package_id")
        banner_file = request.files.get("banner")
    else:
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        game = data.get("game")
        fmt = data.get("format", "online")
        organizer_name = data.get("organizer_name")
        start_date = data.get("start_date")
        package_id = data.get("package_id")
        banner_file = None

    if not all([name, game, organizer_name, start_date, package_id]):
        return jsonify({"error": "name, game, organizer_name, start_date and package_id are required"}), 400

    if package_id not in PACKAGES_BY_ID:
        return jsonify({"error": f"unknown package_id '{package_id}'"}), 400

    banner_url = None
    if banner_file and banner_file.filename:
        blob_name = f"{uuid.uuid4()}-{banner_file.filename}"
        banner_url = upload_bytes(BANNER_CONTAINER, blob_name, banner_file.read(), banner_file.content_type)

    tid = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO tournaments (id, name, game, format, organizer_name, start_date, package_id, banner_url, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment', ?)",
        (tid, name, game, fmt, organizer_name, start_date, package_id, banner_url, now_iso()),
    )
    db.commit()

    row = db.execute("SELECT * FROM tournaments WHERE id = ?", (tid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.get("/api/tournaments/<tournament_id>")
def get_tournament(tournament_id):
    db = get_db()
    row = db.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,)).fetchone()
    if row is None:
        return jsonify({"error": "tournament not found"}), 404
    result = row_to_dict(row)
    result["package"] = PACKAGES_BY_ID.get(result["package_id"])
    return jsonify(result)


@app.post("/api/tournaments/<tournament_id>/purchase")
def purchase_package(tournament_id):
    """Simulates paying for the anti-cheat package tied to a tournament.

    We are not integrating a real payment gateway (Stripe etc.) - that is out
    of scope for this module - so this just flips the tournament to 'active'
    and records a purchase row with a fake payment reference, which is
    exactly the kind of thing a real checkout webhook would do.
    """
    db = get_db()
    row = db.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,)).fetchone()
    if row is None:
        return jsonify({"error": "tournament not found"}), 404

    package = PACKAGES_BY_ID[row["package_id"]]
    purchase_id = str(uuid.uuid4())
    payment_ref = f"MG-{purchase_id[:8].upper()}"

    db.execute(
        "INSERT INTO purchases (id, tournament_id, package_id, amount_usd, payment_ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (purchase_id, tournament_id, package["id"], package["price_usd"], payment_ref, now_iso()),
    )
    db.execute("UPDATE tournaments SET status = 'active' WHERE id = ?", (tournament_id,))
    db.commit()

    return jsonify({
        "purchase_id": purchase_id,
        "payment_ref": payment_ref,
        "amount_usd": package["price_usd"],
        "tournament_id": tournament_id,
        "status": "active",
    }), 201


# ---------------------------------------------------------------------------
# Player registrations (the scan-service links evidence uploads back to
# these by registration id)
# ---------------------------------------------------------------------------
@app.get("/api/tournaments/<tournament_id>/registrations")
def list_registrations(tournament_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM registrations WHERE tournament_id = ? ORDER BY created_at DESC", (tournament_id,)
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.post("/api/tournaments/<tournament_id>/registrations")
def register_player(tournament_id):
    data = request.get_json(silent=True) or {}
    gamertag = data.get("gamertag")
    email = data.get("email")

    if not gamertag or not email:
        return jsonify({"error": "gamertag and email are required"}), 400

    db = get_db()
    tournament = db.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,)).fetchone()
    if tournament is None:
        return jsonify({"error": "tournament not found"}), 404

    package = PACKAGES_BY_ID[tournament["package_id"]]
    if package["max_players"] is not None:
        current_count = db.execute(
            "SELECT COUNT(*) AS c FROM registrations WHERE tournament_id = ?", (tournament_id,)
        ).fetchone()["c"]
        if current_count >= package["max_players"]:
            return jsonify({"error": f"registration cap reached for the {package['name']} package"}), 409

    rid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO registrations (id, tournament_id, gamertag, email, scan_status, created_at) "
        "VALUES (?, ?, ?, ?, 'not_submitted', ?)",
        (rid, tournament_id, gamertag, email, now_iso()),
    )
    db.commit()

    row = db.execute("SELECT * FROM registrations WHERE id = ?", (rid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.patch("/api/registrations/<registration_id>/scan-status")
def update_scan_status(registration_id):
    """Internal endpoint the scan-service calls back once it has a verdict.

    Not exposed to the public frontend nav - the scan-service is the only
    caller. Kept simple (no auth) since this is a student project running
    inside a private cluster network, but in production this would sit
    behind a service-to-service auth token.
    """
    data = request.get_json(silent=True) or {}
    scan_status = data.get("scan_status")
    if scan_status not in ("clear", "flagged", "pending"):
        return jsonify({"error": "scan_status must be one of clear|flagged|pending"}), 400

    db = get_db()
    cur = db.execute("UPDATE registrations SET scan_status = ? WHERE id = ?", (scan_status, registration_id))
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "registration not found"}), 404
    return jsonify({"ok": True})


@app.get("/api/registrations/<registration_id>")
def get_registration(registration_id):
    db = get_db()
    row = db.execute("SELECT * FROM registrations WHERE id = ?", (registration_id,)).fetchone()
    if row is None:
        return jsonify({"error": "registration not found"}), 404
    return jsonify(row_to_dict(row))


init_db()

if __name__ == "__main__":
    # Debug=True locally only, gunicorn is used in the container (see Dockerfile)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)
