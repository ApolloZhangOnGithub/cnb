import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from lib.cnb_sync_gateway import SyncEventStore, build_server, require_auth_for_public_bind


def request_json(
    method: str,
    url: str,
    *,
    body: Any | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = None
    merged_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=merged_headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


@contextmanager
def running_server(data_dir: Path, *, token: str = "") -> Iterator[str]:
    server = build_server(data_dir=data_dir, host="127.0.0.1", port=0, auth_token=token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]  # type: ignore[misc]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_store_appends_and_fetches_events(tmp_path):
    store = SyncEventStore(tmp_path)

    stored = store.append_events(
        [{"stream": "chat", "type": "message.created", "payload": {"text": "hello"}}],
        default_source_id="mac-local",
    )

    assert stored[0].id == 1
    assert stored[0].payload_sha256
    fetched = store.fetch_after(0)
    assert fetched[0].as_dict()["payload"] == {"text": "hello"}
    assert store.fetch_after(1) == []
    assert store.stats()["event_count"] == 1


def test_http_requires_bearer_token_when_configured(tmp_path):
    with running_server(tmp_path, token="secret") as base_url:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            request_json(
                "POST",
                f"{base_url}/v1/events",
                body={"stream": "chat", "type": "message.created", "payload": {"text": "blocked"}},
            )
        assert exc_info.value.code == 401

        status, body = request_json(
            "POST",
            f"{base_url}/v1/events",
            body={"stream": "chat", "type": "message.created", "payload": {"text": "allowed"}},
            headers={"Authorization": "Bearer secret", "X-CNB-Device-ID": "test-client"},
        )
        assert status == 201
        assert body["events"][0]["source_id"] == "test-client"

        status, body = request_json(
            "GET",
            f"{base_url}/v1/events?after=0",
            headers={"Authorization": "Bearer secret"},
        )
        assert status == 200
        assert body["events"][0]["payload"] == {"text": "allowed"}


def test_sse_stream_returns_backlog_event(tmp_path):
    with running_server(tmp_path) as base_url:
        request_json(
            "POST",
            f"{base_url}/v1/events",
            body={"stream": "chat", "type": "message.delta", "payload": {"text": "partial"}},
        )

        with urllib.request.urlopen(f"{base_url}/v1/stream?after=0&heartbeat=5", timeout=5) as resp:
            lines = [resp.readline().decode("utf-8").strip() for _ in range(3)]

        assert lines[0] == "id: 1"
        assert lines[1] == "event: message.delta"
        assert lines[2].startswith("data: ")
        assert json.loads(lines[2][len("data: ") :])["payload"] == {"text": "partial"}


def test_public_bind_requires_auth_token():
    with pytest.raises(SystemExit):
        require_auth_for_public_bind("0.0.0.0", "", allow_no_auth=False)

    require_auth_for_public_bind("0.0.0.0", "token", allow_no_auth=False)
    require_auth_for_public_bind("127.0.0.1", "", allow_no_auth=False)
