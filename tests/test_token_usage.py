"""Tests for lib/token_usage — JSONL token parsing and cost estimation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.token_usage import (
    _project_slug,
    aggregate_by_name,
    cmd_usage,
    collect_runtime_alerts,
    estimate_cost,
    load_budget_defaults,
    model_state_alerts,
    parse_session_usage,
    tongxue_token_summary,
)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    with path.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _make_assistant_msg(input_tokens: int = 10, output_tokens: int = 50, model: str = "claude-opus-4-7") -> dict:
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
        _write_jsonl(jf, [_make_assistant_msg(model="claude-sonnet-4-7")])
        result = parse_session_usage(jf)
        assert result["model"] == "claude-sonnet-4-7"
        assert result["latest_model"] == "claude-sonnet-4-7"
        assert result["models"] == ["claude-sonnet-4-7"]

    def test_captures_model_changes(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        _write_jsonl(
            jf,
            [
                _make_assistant_msg(model="claude-opus-4-7"),
                _make_assistant_msg(model="claude-sonnet-4-7"),
                _make_assistant_msg(model="claude-sonnet-4-7"),
            ],
        )
        result = parse_session_usage(jf)
        assert result["model"] == "claude-opus-4-7"
        assert result["latest_model"] == "claude-sonnet-4-7"
        assert result["models"] == ["claude-opus-4-7", "claude-sonnet-4-7"]


class TestEstimateCost:
    def test_opus_pricing(self):
        usage = {
            "model": "claude-opus-4-7",
            "input": 1_000_000,
            "output": 1_000_000,
            "cache_read": 0,
            "cache_create": 0,
        }
        cost = estimate_cost(usage)
        assert cost == pytest.approx(90.0)

    def test_sonnet_cheaper(self):
        usage = {
            "model": "claude-sonnet-4-7",
            "input": 1_000_000,
            "output": 1_000_000,
            "cache_read": 0,
            "cache_create": 0,
        }
        cost = estimate_cost(usage)
        assert cost == pytest.approx(18.0)

    def test_cache_read_savings(self):
        usage = {"model": "claude-opus-4-7", "input": 0, "output": 0, "cache_read": 1_000_000, "cache_create": 0}
        cost = estimate_cost(usage)
        assert cost == pytest.approx(1.5)

    def test_unknown_model_uses_default(self):
        usage = {"model": "claude-unknown", "input": 1_000_000, "output": 0, "cache_read": 0, "cache_create": 0}
        cost = estimate_cost(usage)
        assert cost == pytest.approx(15.0)

    def test_zero_usage(self):
        usage = {"model": "claude-opus-4-7", "input": 0, "output": 0, "cache_read": 0, "cache_create": 0}
        assert estimate_cost(usage) == 0.0

    def test_legacy_sonnet_4_6_uses_sonnet_pricing(self):
        """Historical 4-6 JSONLs must not silently re-price as opus."""
        usage = {
            "model": "claude-sonnet-4-6",
            "input": 1_000_000,
            "output": 1_000_000,
            "cache_read": 0,
            "cache_create": 0,
        }
        # Sonnet pricing: 3 + 15 = 18 per million. Opus would be 90.
        assert estimate_cost(usage) == pytest.approx(18.0)

    def test_legacy_opus_4_6_uses_opus_pricing(self):
        usage = {
            "model": "claude-opus-4-6",
            "input": 1_000_000,
            "output": 1_000_000,
            "cache_read": 0,
            "cache_create": 0,
        }
        assert estimate_cost(usage) == pytest.approx(90.0)


class TestAggregateByName:
    def test_merges_same_name(self):
        sessions = [
            {
                "name": "alice",
                "model": "claude-opus-4-7",
                "session_id": "s1",
                "input": 10,
                "output": 50,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
            {
                "name": "alice",
                "model": "claude-opus-4-7",
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

    def test_tracks_latest_model(self):
        sessions = [
            {
                "name": "alice",
                "model": "claude-opus-4-7",
                "latest_model": "claude-opus-4-7",
                "models": ["claude-opus-4-7"],
                "session_id": "s1",
                "input": 0,
                "output": 10,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
            {
                "name": "alice",
                "model": "claude-opus-4-7",
                "latest_model": "claude-sonnet-4-7",
                "models": ["claude-opus-4-7", "claude-sonnet-4-7"],
                "session_id": "s2",
                "input": 0,
                "output": 10,
                "cache_create": 0,
                "cache_read": 0,
                "messages": 1,
            },
        ]
        result = aggregate_by_name(sessions)
        assert result[0]["latest_model"] == "claude-sonnet-4-7"
        assert result[0]["models"] == ["claude-opus-4-7", "claude-sonnet-4-7"]


class TestModelStateAlerts:
    def test_reports_model_downgrade(self):
        alerts = model_state_alerts(
            [
                {
                    "name": "alice",
                    "session_id": "s1",
                    "models": ["claude-opus-4-7", "claude-sonnet-4-7"],
                }
            ]
        )
        assert alerts == ["alice: model downgraded claude-opus-4-7 -> claude-sonnet-4-7"]

    def test_ignores_upgrade(self):
        alerts = model_state_alerts(
            [
                {
                    "name": "alice",
                    "session_id": "s1",
                    "models": ["claude-sonnet-4-7", "claude-opus-4-7"],
                }
            ]
        )
        assert alerts == []

    def test_reports_codex_mini_downgrade(self):
        alerts = model_state_alerts(
            [
                {
                    "name": "codex",
                    "session_id": "s1",
                    "models": ["gpt-5.4", "gpt-5.4-mini"],
                }
            ]
        )
        assert alerts == ["codex: model downgraded gpt-5.4 -> gpt-5.4-mini"]

    def test_ignores_cross_provider_switch(self):
        """User-initiated provider switches (claude → deepseek) are not downgrades."""
        alerts = model_state_alerts(
            [
                {
                    "name": "alice",
                    "session_id": "s1",
                    "models": ["claude-opus-4-7", "deepseek-v4-pro"],
                }
            ]
        )
        assert alerts == []


class TestParseSessionUsageMeta:
    def test_custom_title_assigns_name(self, tmp_path):
        jf = tmp_path / "test.jsonl"
        _write_jsonl(jf, [{"type": "custom-title", "customTitle": "bezos"}, _make_assistant_msg()])
        result = parse_session_usage(jf)
        assert result["name"] == "bezos"

    def test_synthetic_model_is_filtered(self, tmp_path):
        """Compaction/internal '<synthetic>' entries must not register as a real model."""
        jf = tmp_path / "test.jsonl"
        _write_jsonl(
            jf,
            [
                _make_assistant_msg(model="claude-opus-4-7"),
                _make_assistant_msg(model="<synthetic>"),
                _make_assistant_msg(model="claude-opus-4-7"),
            ],
        )
        result = parse_session_usage(jf)
        assert result["models"] == ["claude-opus-4-7"]
        assert result["latest_model"] == "claude-opus-4-7"


class TestCollectRuntimeAlerts:
    def test_silent_when_all_clear(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(project_dir / "s1.jsonl", [_make_assistant_msg(model="claude-opus-4-7")])
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            assert collect_runtime_alerts(tmp_path / "project") == []

    def test_reports_downgrade(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [
                {"type": "custom-title", "customTitle": "alice"},
                _make_assistant_msg(model="claude-opus-4-7"),
                _make_assistant_msg(model="claude-sonnet-4-7"),
            ],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            alerts = collect_runtime_alerts(tmp_path / "project")
        assert alerts == ["alice: model downgraded claude-opus-4-7 -> claude-sonnet-4-7"]

    def test_reports_budget_overrun(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [
                {"type": "custom-title", "customTitle": "alice"},
                _make_assistant_msg(input_tokens=1_000_000, output_tokens=1_000_000, model="claude-opus-4-7"),
            ],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            alerts = collect_runtime_alerts(tmp_path / "project", budget=10.0, warn_pct=50.0)
        assert any("token budget usage" in a for a in alerts)
        assert any("$10.00" in a for a in alerts)

    def test_session_filter_matches(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        for name, session in [("alice", "s1"), ("bob", "s2")]:
            _write_jsonl(
                project_dir / f"{session}.jsonl",
                [
                    {"type": "custom-title", "customTitle": name},
                    _make_assistant_msg(model="claude-opus-4-7"),
                    _make_assistant_msg(model="claude-sonnet-4-7"),
                ],
            )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            alerts = collect_runtime_alerts(tmp_path / "project", session_filter="alice")
        assert len(alerts) == 1
        assert alerts[0].startswith("alice:")

    def test_recent_hours_filter_excludes_stale_jsonls(self, tmp_path):
        """JSONLs older than `recent_hours` must be skipped — they aren't the active run."""
        import os

        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        stale = project_dir / "stale.jsonl"
        _write_jsonl(
            stale,
            [
                {"type": "custom-title", "customTitle": "ghost"},
                _make_assistant_msg(model="claude-opus-4-7"),
                _make_assistant_msg(model="claude-sonnet-4-7"),
            ],
        )
        # Backdate stale.jsonl by 48 hours
        old_ts = stale.stat().st_mtime - 48 * 3600
        os.utime(stale, (old_ts, old_ts))
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            assert collect_runtime_alerts(tmp_path / "project", recent_hours=6.0) == []
            # full history should still find it
            assert collect_runtime_alerts(tmp_path / "project", recent_hours=None) != []


class TestLoadBudgetDefaults:
    def test_missing_config_returns_disabled(self, tmp_path):
        budget, warn_pct = load_budget_defaults(tmp_path)
        assert budget == 0.0
        assert warn_pct == 80.0

    def test_reads_usd_and_warn_pct(self, tmp_path):
        (tmp_path / "config.toml").write_text("[budget]\nusd = 50.0\nwarn_pct = 60\n")
        budget, warn_pct = load_budget_defaults(tmp_path)
        assert budget == 50.0
        assert warn_pct == 60.0

    def test_malformed_toml_returns_disabled(self, tmp_path):
        (tmp_path / "config.toml").write_text("not = valid = toml = at = all = =")
        budget, warn_pct = load_budget_defaults(tmp_path)
        assert budget == 0.0
        assert warn_pct == 80.0

    def test_unparseable_usd_falls_back(self, tmp_path):
        """A typo'd string like '50usd' must not raise — fall back to disabled."""
        (tmp_path / "config.toml").write_text('[budget]\nusd = "50usd"\nwarn_pct = 60\n')
        budget, warn_pct = load_budget_defaults(tmp_path)
        assert budget == 0.0
        assert warn_pct == 60.0

    def test_unparseable_warn_pct_falls_back(self, tmp_path):
        (tmp_path / "config.toml").write_text('[budget]\nusd = 50.0\nwarn_pct = "high"\n')
        budget, warn_pct = load_budget_defaults(tmp_path)
        assert budget == 50.0
        assert warn_pct == 80.0


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
        assert "claude-opus-4-7" in out

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

    def test_budget_and_model_state_output(self, tmp_path, capsys):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [
                {"type": "agent-name", "agentName": "alice"},
                _make_assistant_msg(input_tokens=1_000_000, output_tokens=1_000_000, model="claude-opus-4-7"),
                _make_assistant_msg(input_tokens=1_000_000, output_tokens=1_000_000, model="claude-sonnet-4-7"),
            ],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            cmd_usage(tmp_path / "project", ["--budget", "100", "--warn-pct", "50"])
        out = capsys.readouterr().out
        assert "WARNING: alice: model downgraded claude-opus-4-7 -> claude-sonnet-4-7" in out
        assert "预算: $100.00" in out
        assert "WARNING: token budget usage" in out


class TestTongxueTokenSummary:
    def test_returns_none_when_no_jsonls(self, tmp_path):
        project_dir = tmp_path / "empty"
        project_dir.mkdir()
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            assert tongxue_token_summary(tmp_path / "project", "alice") is None

    def test_returns_none_when_name_not_found(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [{"type": "custom-title", "customTitle": "bob"}, _make_assistant_msg()],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            assert tongxue_token_summary(tmp_path / "project", "alice") is None

    def test_returns_aggregated_data(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [
                {"type": "custom-title", "customTitle": "alice"},
                _make_assistant_msg(input_tokens=100, output_tokens=200, model="claude-opus-4-7"),
            ],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            result = tongxue_token_summary(tmp_path / "project", "alice")
        assert result is not None
        assert result["name"] == "alice"
        assert result["input"] == 100
        assert result["output"] == 200
        assert result["latest_model"] == "claude-opus-4-7"
        assert result["messages"] == 1

    def test_name_match_is_case_insensitive(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [{"type": "custom-title", "customTitle": "Alice"}, _make_assistant_msg()],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            result = tongxue_token_summary(tmp_path / "project", "ALICE")
        assert result is not None
        assert result["name"] == "Alice"

    def test_merges_multiple_jsonls(self, tmp_path):
        project_dir = tmp_path / "jsonls"
        project_dir.mkdir()
        _write_jsonl(
            project_dir / "s1.jsonl",
            [
                {"type": "custom-title", "customTitle": "alice"},
                _make_assistant_msg(input_tokens=10, output_tokens=50),
            ],
        )
        _write_jsonl(
            project_dir / "s2.jsonl",
            [
                {"type": "custom-title", "customTitle": "alice"},
                _make_assistant_msg(input_tokens=20, output_tokens=100),
            ],
        )
        with patch("lib.token_usage._find_project_dir", return_value=project_dir):
            result = tongxue_token_summary(tmp_path / "project", "alice")
        assert result["input"] == 30
        assert result["output"] == 150
        assert result["messages"] == 2
