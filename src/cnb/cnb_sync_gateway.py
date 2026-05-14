"""Small HTTP/SSE sync gateway for CNB companion clients.

The gateway is intentionally dependency-free so it can run on a fresh Linux
instance with only Python and SQLite available.  It stores all client-visible
state as an append-only event log; richer projections can be built later from
that log without changing the wire contract.
"""

# ruff: noqa: UP006,UP007,UP035,UP045
# Keep this module Python 3.6 compatible because Alibaba Cloud Linux 3 images
# can still ship `/usr/bin/python3` as 3.6.

import argparse
import hashlib
import hmac
import json
import os
import signal
import sqlite3
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Type, Union
from urllib.parse import parse_qs, urlparse

SCHEMA_VERSION = "1"
DEFAULT_PORT = 8765
DEFAULT_DATA_DIR = Path(os.environ.get("CNB_SYNC_DATA_DIR", "~/.cnb-sync")).expanduser()
MAX_BODY_BYTES = 1_048_576
MAX_FETCH_LIMIT = 1000
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class StoredEvent:
    def __init__(
        self,
        event_id: int,
        ts: str,
        stream: str,
        event_type: str,
        source_id: str,
        payload: Any,
        payload_sha256: str,
    ) -> None:
        self.id = event_id
        self.ts = ts
        self.stream = stream
        self.type = event_type
        self.source_id = source_id
        self.payload = payload
        self.payload_sha256 = payload_sha256

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts,
            "stream": self.stream,
            "type": self.type,
            "source_id": self.source_id,
            "payload": self.payload,
            "payload_sha256": self.payload_sha256,
        }


class SyncEventStore:
    """SQLite-backed append-only event store."""

    def __init__(self, data_dir: Union[Path, str]) -> None:
        self.data_dir = Path(data_dir).expanduser()
        self.db_path = self.data_dir / "cnb-sync.db"
        self.attachments_dir = self.data_dir / "attachments"
        self._condition = threading.Condition()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._last_event_id = self._read_last_event_id()

    @property
    def last_event_id(self) -> int:
        return self._last_event_id

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    stream TEXT NOT NULL,
                    type TEXT NOT NULL,
                    source_id TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    created_at_unix REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_id ON events(id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_stream_id ON events(stream, id)")
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )

    def _read_last_event_id(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()
            return int(row[0] if row else 0)

    def append_events(self, incoming: Iterable[Mapping[str, Any]], *, default_source_id: str) -> List[StoredEvent]:
        rows = []  # type: List[StoredEvent]
        now = utc_now()
        with self._connect() as conn:
            for event in incoming:
                stream = str(event.get("stream") or "default")
                event_type = str(event.get("type") or event.get("event_type") or "event")
                source_id = str(event.get("source_id") or default_source_id or "")
                payload = event.get("payload", {})
                payload_json = compact_json(payload)
                payload_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
                cur = conn.execute(
                    """
                    INSERT INTO events(ts, stream, type, source_id, payload_json, payload_sha256, created_at_unix)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (now, stream, event_type, source_id, payload_json, payload_sha256, time.time()),
                )
                rows.append(
                    StoredEvent(
                        event_id=int(cur.lastrowid or 0),
                        ts=now,
                        stream=stream,
                        event_type=event_type,
                        source_id=source_id,
                        payload=payload,
                        payload_sha256=payload_sha256,
                    )
                )

        if rows:
            with self._condition:
                self._last_event_id = max(self._last_event_id, rows[-1].id)
                self._condition.notify_all()
        return rows

    def fetch_after(self, after: int = 0, *, limit: int = 100, stream: Optional[str] = None) -> List[StoredEvent]:
        limit = max(1, min(limit, MAX_FETCH_LIMIT))
        params = [max(0, after)]  # type: List[Any]
        stream_clause = ""
        if stream:
            stream_clause = "AND stream = ?"
            params.append(stream)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, ts, stream, type, source_id, payload_json, payload_sha256
                FROM events
                WHERE id > ? {stream_clause}
                ORDER BY id ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count, COALESCE(MAX(id), 0) AS last_id FROM events").fetchone()
            streams = conn.execute(
                "SELECT stream, COUNT(*) AS count, COALESCE(MAX(id), 0) AS last_id FROM events GROUP BY stream"
            ).fetchall()
        return {
            "db_path": str(self.db_path),
            "event_count": int(row["count"]),
            "last_event_id": int(row["last_id"]),
            "streams": [
                {"stream": item["stream"], "event_count": int(item["count"]), "last_event_id": int(item["last_id"])}
                for item in streams
            ],
        }

    def wait_for_events(self, after: int, *, timeout: float) -> bool:
        with self._condition:
            if self._last_event_id > after:
                return True
            self._condition.wait(timeout=timeout)
            return self._last_event_id > after

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> StoredEvent:
        return StoredEvent(
            event_id=int(row["id"]),
            ts=str(row["ts"]),
            stream=str(row["stream"]),
            event_type=str(row["type"]),
            source_id=str(row["source_id"]),
            payload=json.loads(row["payload_json"]),
            payload_sha256=str(row["payload_sha256"]),
        )


class CNBSyncHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        handler_class: Type[BaseHTTPRequestHandler],
        *,
        store: SyncEventStore,
        auth_token: str,
        cors_origin: str,
    ):
        super().__init__(server_address, handler_class)
        self.store = store
        self.auth_token = auth_token
        self.cors_origin = cors_origin


class SyncRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: CNBSyncHTTPServer

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_common_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-CNB-Device-ID")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"", "/"}:
            self._send_json(
                HTTPStatus.OK,
                {"service": "cnb-sync-gateway", "health": "/health", "events": "/v1/events", "stream": "/v1/stream"},
            )
            return
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "service": "cnb-sync-gateway", **self.server.store.stats()})
            return
        if parsed.path == "/v1/events":
            if not self._authorize():
                return
            params = parse_qs(parsed.query)
            after = self._parse_int(params.get("after", ["0"])[0], default=0)
            limit = self._parse_int(params.get("limit", ["100"])[0], default=100)
            stream = params.get("stream", [None])[0]
            events = self.server.store.fetch_after(after, limit=limit, stream=stream)
            self._send_json(
                HTTPStatus.OK,
                {"events": [event.as_dict() for event in events], "last_event_id": self.server.store.last_event_id},
            )
            return
        if parsed.path == "/v1/stream":
            if not self._authorize():
                return
            self._send_event_stream(parsed.query)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/v1/events":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorize():
            return
        try:
            body = self._read_json_body()
            incoming = self._normalize_incoming_events(body)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        source_id = self.headers.get("X-CNB-Device-ID", self.client_address[0])
        stored = self.server.store.append_events(incoming, default_source_id=source_id)
        self._send_json(
            HTTPStatus.CREATED,
            {"events": [event.as_dict() for event in stored], "last_event_id": self.server.store.last_event_id},
        )

    def _send_event_stream(self, query: str) -> None:
        params = parse_qs(query)
        after = self._parse_int(params.get("after", ["0"])[0], default=0)
        stream = params.get("stream", [None])[0]
        heartbeat = max(5, self._parse_int(params.get("heartbeat", ["15"])[0], default=15))
        self.send_response(HTTPStatus.OK)
        self._write_common_headers()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                events = self.server.store.fetch_after(after, limit=100, stream=stream)
                if events:
                    for event in events:
                        self._write_sse(event)
                        after = event.id
                    continue
                self._write_sse_comment(f"heartbeat {utc_now()}")
                self.server.store.wait_for_events(after, timeout=float(heartbeat))
        except (BrokenPipeError, ConnectionResetError):
            return

    def _write_sse(self, event: StoredEvent) -> None:
        data = compact_json(event.as_dict())
        frame = f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"
        self.wfile.write(frame.encode("utf-8"))
        self.wfile.flush()

    def _write_sse_comment(self, message: str) -> None:
        self.wfile.write(f": {message}\n\n".encode())
        self.wfile.flush()

    def _authorize(self) -> bool:
        token = self.server.auth_token
        if not token:
            return True
        expected = f"Bearer {token}"
        actual = self.headers.get("Authorization", "")
        if hmac.compare_digest(actual, expected):
            return True
        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _read_json_body(self) -> Any:
        length = self._parse_int(self.headers.get("Content-Length", "0"), default=0)
        if length <= 0:
            raise ValueError("empty_json_body")
        if length > MAX_BODY_BYTES:
            raise ValueError("json_body_too_large")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid_json") from exc

    @staticmethod
    def _normalize_incoming_events(body: Any) -> List[Mapping[str, Any]]:
        if isinstance(body, list):
            events = body
        elif isinstance(body, dict) and isinstance(body.get("events"), list):
            events = body["events"]
        elif isinstance(body, dict):
            events = [body]
        else:
            raise ValueError("expected_event_object_or_array")
        normalized = []  # type: List[Mapping[str, Any]]
        for event in events:
            if not isinstance(event, Mapping):
                raise ValueError("event_must_be_object")
            normalized.append(event)
        return normalized

    def _send_json(self, status: HTTPStatus, body: Mapping[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self._write_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _write_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", self.server.cors_origin)
        self.send_header("Access-Control-Allow-Credentials", "false")
        self.send_header("X-Content-Type-Options", "nosniff")

    @staticmethod
    def _parse_int(value: Optional[str], *, default: int) -> int:
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("CNB_SYNC_ACCESS_LOG") == "1":
            super().log_message(fmt, *args)


def build_server(
    *,
    data_dir: Union[Path, str],
    host: str,
    port: int,
    auth_token: str,
    cors_origin: str = "*",
) -> CNBSyncHTTPServer:
    store = SyncEventStore(data_dir)
    return CNBSyncHTTPServer(
        (host, port),
        SyncRequestHandler,
        store=store,
        auth_token=auth_token,
        cors_origin=cors_origin,
    )


def require_auth_for_public_bind(host: str, auth_token: str, allow_no_auth: bool) -> None:
    if allow_no_auth or auth_token:
        return
    if host in LOCAL_HOSTS:
        return
    raise SystemExit(
        "FATAL: refusing to bind without CNB_SYNC_TOKEN outside localhost. "
        "Set CNB_SYNC_TOKEN or pass --allow-no-auth for a private network test."
    )


def serve(args: argparse.Namespace) -> int:
    auth_token = args.token or os.environ.get("CNB_SYNC_TOKEN", "")
    require_auth_for_public_bind(args.host, auth_token, args.allow_no_auth)
    server = build_server(
        data_dir=args.data_dir,
        host=args.host,
        port=args.port,
        auth_token=auth_token,
        cors_origin=args.cors_origin,
    )

    stop = threading.Event()

    def _stop(_signum: int, _frame: Any) -> None:
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    print(
        f"cnb-sync-gateway listening on http://{args.host}:{args.port} "
        f"data_dir={Path(args.data_dir).expanduser()} auth={'on' if auth_token else 'off'}",
        flush=True,
    )
    server.serve_forever(poll_interval=0.5)
    stop.set()
    server.server_close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the CNB HTTP/SSE sync gateway.")
    parser.add_argument("--host", default=os.environ.get("CNB_SYNC_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CNB_SYNC_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--token", default="", help="Bearer token. Defaults to CNB_SYNC_TOKEN.")
    parser.add_argument("--cors-origin", default=os.environ.get("CNB_SYNC_CORS_ORIGIN", "*"))
    parser.add_argument("--allow-no-auth", action="store_true", help="Allow unauthenticated non-local binds.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return serve(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
