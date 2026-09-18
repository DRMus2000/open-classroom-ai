"""Small, dependency-free approval queue for an Open WebUI review filter.

The service is intended to run on the teacher's computer.  Keep it bound to
127.0.0.1 unless a remote teacher dashboard is explicitly required.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT.parent / "data" / "review"
DB_PATH = Path(os.environ.get("REVIEW_GATE_DB", str(DATA_DIR / "review.db")))
HTML_PATH = ROOT / "review.html"
PID_PATH = Path(os.environ.get("REVIEW_GATE_PID", str(DATA_DIR / "review-service.pid")))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


@contextmanager
def db_connection():
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    with db_connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS review_requests (
                id TEXT PRIMARY KEY,
                request_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
                user_id TEXT,
                user_name TEXT,
                user_email TEXT,
                chat_id TEXT,
                message_id TEXT,
                message TEXT NOT NULL,
                edited_message TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                decided_at TEXT
            )
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenWebUIReviewGate/1.0"

    def _token_ok(self) -> bool:
        expected = self.server.review_token
        if not expected:
            return True
        supplied = self.headers.get("X-Review-Token", "")
        if supplied.startswith("Bearer "):
            supplied = supplied[7:]
        return secrets.compare_digest(supplied, expected)

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                return None
            return json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/":
            try:
                raw = HTML_PATH.read_bytes()
            except OSError:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "review.html is missing")
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if not self._token_ok():
            self._send_error(HTTPStatus.UNAUTHORIZED, "invalid review token")
            return
        if parsed.path == "/api/requests":
            statuses = parse_qs(parsed.query).get("status", ["pending"])[0]
            allowed = {"pending", "approved", "rejected", "all"}
            if statuses not in allowed:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid status")
                return
            with db_connection() as db:
                if statuses == "all":
                    rows = db.execute(
                        "SELECT * FROM review_requests ORDER BY created_at DESC LIMIT 200"
                    ).fetchall()
                else:
                    rows = db.execute(
                        "SELECT * FROM review_requests WHERE status=? ORDER BY created_at ASC LIMIT 200",
                        (statuses,),
                    ).fetchall()
            self._send_json({"requests": [row_to_dict(row) for row in rows]})
            return
        if parsed.path.startswith("/api/requests/"):
            request_id = parsed.path.rsplit("/", 1)[-1]
            with db_connection() as db:
                row = db.execute("SELECT * FROM review_requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                self._send_error(HTTPStatus.NOT_FOUND, "request not found")
                return
            self._send_json(row_to_dict(row))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if not self._token_ok():
            self._send_error(HTTPStatus.UNAUTHORIZED, "invalid review token")
            return
        parsed = urlparse(self.path)
        data = self._read_json()
        if data is None:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid JSON")
            return
        if parsed.path == "/api/requests":
            required = ["request_key", "message"]
            if any(not str(data.get(key, "")).strip() for key in required):
                self._send_error(HTTPStatus.BAD_REQUEST, "request_key and message are required")
                return
            request_key = str(data["request_key"])
            with db_connection() as db:
                existing = db.execute(
                    "SELECT * FROM review_requests WHERE request_key=?", (request_key,)
                ).fetchone()
                if existing:
                    self._send_json(row_to_dict(existing))
                    return
                request_id = uuid.uuid4().hex
                db.execute(
                    """
                    INSERT INTO review_requests
                    (id,request_key,status,user_id,user_name,user_email,chat_id,message_id,message,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        request_id,
                        request_key,
                        "pending",
                        str(data.get("user_id", "")),
                        str(data.get("user_name", "")),
                        str(data.get("user_email", "")),
                        str(data.get("chat_id", "")),
                        str(data.get("message_id", "")),
                        str(data["message"]),
                        now(),
                    ),
                )
                row = db.execute("SELECT * FROM review_requests WHERE id=?", (request_id,)).fetchone()
            self._send_json(row_to_dict(row), HTTPStatus.CREATED)
            return
        if parsed.path.startswith("/api/requests/") and parsed.path.endswith("/decision"):
            request_id = parsed.path.split("/")[3]
            decision = str(data.get("decision", "")).lower()
            if decision not in {"approve", "reject", "edit"}:
                self._send_error(HTTPStatus.BAD_REQUEST, "decision must be approve, reject, or edit")
                return
            edited = str(data.get("edited_message", ""))
            if decision == "edit" and not edited.strip():
                self._send_error(HTTPStatus.BAD_REQUEST, "edited_message is required")
                return
            status = "approved" if decision in {"approve", "edit"} else "rejected"
            with db_connection() as db:
                result = db.execute(
                    """
                    UPDATE review_requests
                    SET status=?, edited_message=?, note=?, decided_at=?
                    WHERE id=? AND status='pending'
                    """,
                    (status, edited if decision == "edit" else None, str(data.get("note", "")), now(), request_id),
                )
                row = db.execute("SELECT * FROM review_requests WHERE id=?", (request_id,)).fetchone()
            if result.rowcount != 1:
                if not row:
                    self._send_error(HTTPStatus.NOT_FOUND, "request not found")
                else:
                    self._send_error(HTTPStatus.CONFLICT, "request was already decided")
                return
            self._send_json(row_to_dict(row))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not found")

    def log_message(self, fmt: str, *args) -> None:
        print(f"[review-gate] {self.address_string()} - {fmt % args}")


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], token: str):
        super().__init__(address, Handler)
        self.review_token = token


def main() -> None:
    parser = argparse.ArgumentParser(description="Open WebUI teacher review queue")
    parser.add_argument("--host", default=os.environ.get("REVIEW_GATE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("REVIEW_GATE_PORT", "8790")))
    parser.add_argument("--token", default=os.environ.get("REVIEW_GATE_TOKEN", ""))
    args = parser.parse_args()
    init_db()
    server = ReviewServer((args.host, args.port), args.token)
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="ascii")
    print(f"Review panel: http://{args.host}:{args.port}/")
    print(f"Queue database: {DB_PATH}")
    if args.token:
        print("Review token authentication: enabled")
    else:
        print("Review token authentication: disabled (localhost-only mode recommended)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            if PID_PATH.read_text(encoding="ascii").strip() == str(os.getpid()):
                PID_PATH.unlink()
        except (FileNotFoundError, OSError):
            pass


if __name__ == "__main__":
    main()
