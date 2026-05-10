import json
import sqlite3
import sys
from base64 import b64encode
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.capture_ingest import CaptureError, cmd_capture, ingest_capture, list_captures


def _init_board(cnb_dir: Path) -> None:
    schema = (Path(__file__).parent.parent / "schema.sql").read_text()
    conn = sqlite3.connect(str(cnb_dir / "board.db"))
    conn.executescript(schema)
    conn.execute("INSERT INTO sessions(name) VALUES ('lead')")
    conn.execute("INSERT INTO sessions(name) VALUES ('dispatcher')")
    conn.commit()
    conn.close()


def test_ingest_writes_capture_artifacts(tmp_path):
    cnb = tmp_path / ".cnb"
    cnb.mkdir()
    payload = {
        "source": "safari-web-extension",
        "mode": "selection",
        "title": "Example Page",
        "url": "https://example.test/doc",
        "selection_text": "hello token=secret-value world",
        "metadata": {"tab_id": 7},
    }

    result = ingest_capture(payload, project=tmp_path, notify=None)

    capture_dir = Path(result["path"])
    assert capture_dir.is_dir()
    manifest = json.loads((capture_dir / "manifest.json").read_text())
    assert manifest["mode"] == "selection"
    assert manifest["source"] == "safari-web-extension"
    assert manifest["files"]["content"] == "content.md"
    content = (capture_dir / "content.md").read_text()
    assert "Example Page" in content
    assert "token=[REDACTED]" in content
    assert "secret-value" not in content


def test_ingest_sanitizes_html_and_payload(tmp_path):
    cnb = tmp_path / ".cnb"
    cnb.mkdir()
    payload = {
        "mode": "snapshot",
        "title": "HTML",
        "html": '<html><script>alert(1)</script><input type="password" value="pw"><p>ok</p></html>',
        "metadata": {"access_token": "abc123"},
    }

    result = ingest_capture(payload, project=tmp_path, source="test", notify=None)

    capture_dir = Path(result["path"])
    html = (capture_dir / "page.sanitized.html").read_text()
    assert "<script" not in html
    assert "pw" not in html
    redacted_payload = json.loads((capture_dir / "payload.redacted.json").read_text())
    assert redacted_payload["metadata"]["access_token"] == "[REDACTED]"


def test_list_captures_returns_newest_first(tmp_path):
    (tmp_path / ".cnb").mkdir()
    first = ingest_capture({"mode": "page", "title": "First"}, project=tmp_path, notify=None)
    second = ingest_capture({"mode": "article", "title": "Second"}, project=tmp_path, notify=None)

    captures = list_captures(project=tmp_path)

    assert [item["id"] for item in captures] == [second["manifest"]["id"], first["manifest"]["id"]]


def test_global_capture_store_uses_cnb_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = ingest_capture({"mode": "page", "title": "Global"}, global_store=True, notify=None)

    capture_dir = Path(result["path"])
    assert capture_dir.is_relative_to(tmp_path / ".cnb" / "captures")
    manifest = json.loads((capture_dir / "manifest.json").read_text())
    assert manifest["scope"] == "global"
    captures = list_captures(global_store=True)
    assert captures[0]["id"] == manifest["id"]


def test_ingest_writes_screenshot_and_manifest_entry(tmp_path):
    (tmp_path / ".cnb").mkdir()
    png_bytes = b"\x89PNG\r\n\x1a\nfake"
    payload = {
        "mode": "snapshot",
        "title": "Visual",
        "screenshot_base64": b64encode(png_bytes).decode(),
    }

    result = ingest_capture(payload, project=tmp_path, notify=None)

    capture_dir = Path(result["path"])
    manifest = json.loads((capture_dir / "manifest.json").read_text())
    assert manifest["files"]["image"] == "visible.png"
    assert (capture_dir / "visible.png").read_bytes() == png_bytes


def test_invalid_screenshot_rejects_without_manifest(tmp_path):
    (tmp_path / ".cnb").mkdir()

    with pytest.raises(CaptureError):
        ingest_capture({"mode": "snapshot", "screenshot_base64": "not-valid-base64"}, project=tmp_path, notify=None)

    assert list((tmp_path / ".cnb" / "captures").glob("*/manifest.json")) == []


def test_duplicate_capture_id_gets_stable_suffix(tmp_path, monkeypatch):
    (tmp_path / ".cnb").mkdir()
    monkeypatch.setattr("lib.capture_ingest._now_iso", lambda: "2026-05-10T01:02:03Z")
    payload = {"mode": "page", "title": "Same", "url": "https://example.test/same"}

    first = ingest_capture(payload, project=tmp_path, notify=None)
    second = ingest_capture(payload, project=tmp_path, notify=None)

    assert Path(second["path"]).name == f"{Path(first['path']).name}-2"
    assert second["manifest"]["id"].endswith("-2")


def test_notify_writes_board_message_and_inbox(tmp_path):
    cnb = tmp_path / ".cnb"
    cnb.mkdir()
    _init_board(cnb)

    result = ingest_capture(
        {"mode": "article", "title": "Shared Article", "url": "https://example.test/a"},
        project=tmp_path,
        notify="lead",
        sender="dispatcher",
    )

    conn = sqlite3.connect(str(cnb / "board.db"))
    message = conn.execute("SELECT sender, recipient, body FROM messages").fetchone()
    inbox = conn.execute("SELECT session FROM inbox").fetchone()
    conn.close()
    assert message[0] == "dispatcher"
    assert message[1] == "lead"
    assert "Shared Article" in message[2]
    assert result["path"] in message[2]
    assert inbox[0] == "lead"


def test_project_argument_can_point_to_config_dir(tmp_path):
    cnb = tmp_path / ".cnb"
    cnb.mkdir()

    result = ingest_capture({"mode": "page", "title": "Config Dir"}, project=cnb, notify=None)

    capture_dir = Path(result["path"])
    assert capture_dir.is_relative_to(cnb / "captures")
    assert result["manifest"]["project_root"] == str(tmp_path.resolve())


def test_project_argument_supports_legacy_claudes_dir(tmp_path):
    legacy = tmp_path / ".claudes"
    legacy.mkdir()

    result = ingest_capture({"mode": "page", "title": "Legacy"}, project=tmp_path, notify=None)

    capture_dir = Path(result["path"])
    assert capture_dir.is_relative_to(legacy / "captures")
    assert result["manifest"]["scope"] == "project"


def test_list_captures_skips_corrupt_manifest(tmp_path):
    cnb = tmp_path / ".cnb"
    bad = cnb / "captures" / "bad"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text("{not json")
    good = ingest_capture({"mode": "page", "title": "Good"}, project=tmp_path, notify=None)

    captures = list_captures(project=tmp_path)

    assert [item["id"] for item in captures] == [good["manifest"]["id"]]


def test_cli_ingest_list_show_round_trip(tmp_path, capsys):
    (tmp_path / ".cnb").mkdir()
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps({"mode": "selection", "title": "CLI", "selection_text": "hello"}))

    cmd_capture(["ingest", "--project", str(tmp_path), "--file", str(payload_file), "--no-notify"])
    ingest_out = capsys.readouterr().out
    capture_id = next(
        line.split(":", 1)[1].strip() for line in ingest_out.splitlines() if line.strip().startswith("id:")
    )

    cmd_capture(["list", "--project", str(tmp_path), "--json"])
    listed = json.loads(capsys.readouterr().out)
    assert listed["captures"][0]["id"] == capture_id

    cmd_capture(["show", capture_id[:12], "--project", str(tmp_path)])
    shown = capsys.readouterr().out
    assert "# CLI" in shown
    assert "hello" in shown
