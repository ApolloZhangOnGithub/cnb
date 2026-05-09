import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.capture_ingest import ingest_capture, list_captures


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
