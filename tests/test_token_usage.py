"""Tests for lib/token_usage — JSONL token parsing and cost estimation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.token_usage import (
    _project_slug,
    aggregate_by_name,
    cmd_usage,
    estimate_cost,
    parse_session_usage,
)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    with path.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _make_assistant_msg(input_tokens: int = 10, output_tokens: int = 50, model: str = "claude-opus-4-6") -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 500,
            },
        },
    }


class TestProjectSlug:
    def test_replaces_slashes(self):
        assert _project_slug(Path("/Users/test/project")) == "-Users-test-project"

    def test_replaces_underscores(self):
        assert _project_slug(Path("/Users/test/my_project")) == "-Users-test-my-project"

    def test_both_slashes_and_underscores(self):
        assert _project_slug(Path("/a/b_c/d_e")) == "-a-b-c-d-e"


class TestParseSessionUsage:
    def test_parses_agent_name(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        _write_jsonl(jf, [{"type": "agent-name", "agentName": "alice"}, _make_assistant_msg()])
        result = parse_session_usage(jf)
        assert result["name"] == "alice"

    def test_sums_tokens(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        _write_jsonl(
            jf,
            [
                _make_assistant_msg(input_tokens=10, output_tokens=50),
                _make_assistant_msg(input_tokens=20, output_tokens=100),
            ],
        )
        result = parse_session_usage(jf)
        assert result["input"] == 30
        assert result["output"] == 150
        assert result["cache_create"] == 200
        assert result["cache_read"] == 1000
        assert result["messages"] == 2

    def test_skips_non_assistant_messages(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        _write_jsonl(
            jf,
            [
                {"type": "user", "message": {"content": "hello"}},
                {"type": "system", "message": {}},
                _make_assistant_msg(output_tokens=42),
            ],
        )
        result = parse_session_usage(jf)
        assert result["messages"] == 1
        assert result["output"] == 42

    def test_handles_malformed_json(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        jf.write_text('{bad json\n{"also broken\n' + json.dumps(_make_assistant_msg()) + "\n")
        result = parse_session_usage(jf)
        assert result["messages"] == 1

    def test_empty_file(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        jf.write_text("")
        result = parse_session_usage(jf)
        assert result["messages"] == 0
        assert result["name"] == ""

    def test_session_id_from_filename(self, tmp_path):
        jf = tmp_path / "abc123.jsonl"
        _write_jsonl(jf, [_make_assistant_msg()])
        result = parse_session_usage(jf)
        assert result["session_id"] == "abc123"

    def test_captures_model(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        _write_jsonl(jf, [_make_assistant_msg(model="claude-sonnet-4-6")])
        result = parse_session_usage(jf)
        assert result["model"] == "claude-sonnet-4-6"


class TestEstimateCost:
    def test_opus_pricing(self):
        usage = {
            "model": "claude-opus-4-6",
            "input": 1_000_000,
            "output": 1_000_000,
            "cache_read": 0,
            "cache_create": 0,
        }
        cost = estimate_cost(usage)
        assert cost == pytest.approx(90.0)

    def test_sonnet_cheaper(self):
        usage = {
            "model": "claude-sonnet-4-6",
            "input": 1_000_000,
            "output": 1_000_000,
            "cache_read": 0,
            "cache_create": 0,
        }
        cost = estimate_cost(usage)
        assert cost == pytest.approx(18.0)

    def test_cache_read_savings(self):
        usage = {"model": "claude-opus-4-6", "input": 0, "output": 0, "cache_read": 1_000_000, "cache_create": 0}
        cost = estimate_cost(usage)
        assert cost == pytest.approx(1.5)

    def test_unknown_model_uses_default(self):
        usage = {"model": "claude-unknown", "input": 1_000_000, "output": 0, "cache_read": 0, "cache_create": 0}
        cost = estimate_cost(usage)
        assert cost == pytest.approx(15.0)

    def test_zero_usage(self):
        usage = {"model": "claude-opus-4-6", "input": 0, "output": 0, "cache_read": 0, "cache_create": 0}
        assert estimate_cost(usage) == 0.0


class TestAggregateByName:
    def test_merges_same_name(self):
        sessions = [
            {
                "name": "alice",
                "model": "claude-opus-4-6",
                "session_id": "s1",
                "input": 10,
                "output": 50,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
            {
                "name": "alice",
                "model": "claude-opus-4-6",
                "session_id": "s2",
                "input": 20,
                "output": 100,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 2,
            },
        ]
        result = aggregate_by_name(sessions)
        assert len(result) == 1
        assert result[0]["name"] == "alice"
        assert result[0]["input"] == 30
        assert result[0]["output"] == 150
        assert result[0]["messages"] == 3

    def test_separate_names(self):
        sessions = [
            {
                "name": "alice",
                "model": "m",
                "session_id": "s1",
                "input": 10,
                "output": 50,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
            {
                "name": "bob",
                "model": "m",
                "session_id": "s2",
                "input": 20,
                "output": 100,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 2,
            },
        ]
        result = aggregate_by_name(sessions)
        assert len(result) == 2

    def test_sorted_by_output_descending(self):
        sessions = [
            {
                "name": "alice",
                "model": "m",
                "session_id": "s1",
                "input": 0,
                "output": 10,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
            {
                "name": "bob",
                "model": "m",
                "session_id": "s2",
                "input": 0,
                "output": 100,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
        ]
        result = aggregate_by_name(sessions)
        assert result[0]["name"] == "bob"

    def test_unnamed_uses_session_id_prefix(self):
        sessions = [
            {
                "name": "",
                "model": "m",
                "session_id": "abc12345-long-id",
                "input": 0,
                "output": 10,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
        ]
        result = aggregate_by_name(sessions)
        assert result[0]["name"] == "abc12345"


class TestCmdUsage:
    def test_no_project_dir_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit):
            cmd_usage(tmp_path / "nonexistent", [])

    def test_empty_project_dir(self, tmp_path, capsys):
        with patch("lib.token_usage._find_project_dir", return_value=tmp_path / "empty"):
            (tmp_path / "empty").mkdir()
            cmd_usage(tmp_path / "project", [])
        out = capsys.readouterr().out
        assert "无 token 用量数据" in out

    def test_summary_output(self, tmp_path, capsys):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [{"type": "agent-name", "agentName": "alice"}, _make_assistant_msg(output_tokens=100)],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            cmd_usage(tmp_path / "project", [])
        out = capsys.readouterr().out
        assert "alice" in out
        assert "合计" in out

    def test_detail_flag(self, tmp_path, capsys):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [{"type": "agent-name", "agentName": "alice"}, _make_assistant_msg()],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            cmd_usage(tmp_path / "project", ["--detail"])
        out = capsys.readouterr().out
        assert "Session" in out
        assert "s1" in out
