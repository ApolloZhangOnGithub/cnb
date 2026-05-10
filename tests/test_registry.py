"""Tests for bin/registry — agent identity blockchain.

Covers: _content_hash, _load_chain, _next_block, _find_agent (pure functions),
cmd_register, cmd_verify, cmd_verify_chain, cmd_list, cmd_rank, cmd_whois,
_sync_readme, main dispatch, and all error paths.
All filesystem/git operations mocked per project convention.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
import types

registry_path = str(Path(__file__).parent.parent / "bin" / "registry")
loader = importlib.machinery.SourceFileLoader("registry", registry_path)
spec = importlib.util.spec_from_loader("registry", loader, origin=registry_path)
reg = types.ModuleType(spec.name)
reg.__spec__ = spec
reg.__file__ = registry_path
loader.exec_module(reg)

GENESIS = {
    "block": 0,
    "name": "test-project",
    "type": "project",
    "created": "2026-01-01",
    "description": "Genesis block.",
    "chain": None,
    "content_hash": None,
}
GENESIS["content_hash"] = reg._content_hash(GENESIS)

AGENT_1 = {
    "block": 1,
    "name": "alice",
    "display_name": "Claude Alice",
    "type": "agent",
    "role": "dev",
    "description": "Developer",
    "created": "2026-01-02",
    "prev": GENESIS["content_hash"],
    "chain": "abc1234",
    "content_hash": None,
}
AGENT_1["content_hash"] = reg._content_hash(AGENT_1)

AGENT_2 = {
    "block": 2,
    "name": "bob",
    "display_name": "Claude Bob",
    "type": "agent",
    "role": "tester",
    "description": "Tester",
    "created": "2026-01-03",
    "prev": AGENT_1["content_hash"],
    "chain": "def5678",
    "content_hash": None,
}
AGENT_2["content_hash"] = reg._content_hash(AGENT_2)


def _write_chain(tmp_path, entries):
    """Write a list of entries as JSON files in a registry dir."""
    registry = tmp_path / "registry"
    registry.mkdir(exist_ok=True)
    for entry in entries:
        if entry.get("type") == "project":
            fname = "GENESIS.json"
        else:
            fname = f"{entry['block']:04d}-{entry['name']}.json"
        (registry / fname).write_text(json.dumps(entry, indent=2) + "\n")
    return registry


# ---------------------------------------------------------------------------
# _content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_deterministic(self):
        entry = {"block": 0, "name": "x", "chain": "abc"}
        h1 = reg._content_hash(entry)
        h2 = reg._content_hash(entry)
        assert h1 == h2

    def test_excludes_content_hash_field(self):
        entry = {"block": 0, "name": "x", "chain": "abc"}
        entry_with_hash = {**entry, "content_hash": "whatever"}
        assert reg._content_hash(entry) == reg._content_hash(entry_with_hash)

    def test_different_data_different_hash(self):
        a = {"block": 0, "name": "x"}
        b = {"block": 0, "name": "y"}
        assert reg._content_hash(a) != reg._content_hash(b)

    def test_returns_16_char_hex(self):
        h = reg._content_hash({"block": 0})
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_key_order_irrelevant(self):
        a = {"block": 0, "name": "x", "type": "agent"}
        b = {"type": "agent", "name": "x", "block": 0}
        assert reg._content_hash(a) == reg._content_hash(b)

    def test_accepts_legacy_utf8_hash(self):
        entry = {
            "block": 4,
            "name": "legacy",
            "type": "agent",
            "description": "中文说明",
            "chain": None,
            "content_hash": None,
        }
        legacy_hash = reg._legacy_content_hash(entry)
        assert legacy_hash != reg._content_hash(entry)
        assert reg._content_hash_matches(entry, legacy_hash)


# ---------------------------------------------------------------------------
# _load_chain
# ---------------------------------------------------------------------------


class TestLoadChain:
    def test_loads_sorted_by_block(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_2, AGENT_1])
        with patch.object(reg, "REGISTRY_DIR", registry):
            chain = reg._load_chain()
        assert [e["block"] for e in chain] == [0, 1, 2]

    def test_empty_dir(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        with patch.object(reg, "REGISTRY_DIR", registry):
            assert reg._load_chain() == []

    def test_ignores_files_without_block(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS])
        (registry / "pubkeys.json").write_text('{"keys": []}')
        with patch.object(reg, "REGISTRY_DIR", registry):
            chain = reg._load_chain()
        assert len(chain) == 1


# ---------------------------------------------------------------------------
# _next_block
# ---------------------------------------------------------------------------


class TestNextBlock:
    def test_empty_chain_returns_zero(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        with patch.object(reg, "REGISTRY_DIR", registry):
            assert reg._next_block() == 0

    def test_returns_max_plus_one(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1, AGENT_2])
        with patch.object(reg, "REGISTRY_DIR", registry):
            assert reg._next_block() == 3


# ---------------------------------------------------------------------------
# _find_agent
# ---------------------------------------------------------------------------


class TestFindAgent:
    def test_finds_existing_agent(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        with patch.object(reg, "REGISTRY_DIR", registry):
            result = reg._find_agent("alice")
        assert result is not None
        assert result["name"] == "alice"

    def test_returns_none_for_missing(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        with patch.object(reg, "REGISTRY_DIR", registry):
            assert reg._find_agent("nobody") is None

    def test_skips_project_type(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS])
        with patch.object(reg, "REGISTRY_DIR", registry):
            assert reg._find_agent("test-project") is None


# ---------------------------------------------------------------------------
# cmd_register
# ---------------------------------------------------------------------------


class TestCmdRegister:
    def test_no_args_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            reg.cmd_register([])

    def test_already_registered_exits(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        with patch.object(reg, "REGISTRY_DIR", registry), pytest.raises(SystemExit):
            reg.cmd_register(["alice"])
        out = capsys.readouterr().out
        assert "已注册" in out

    def test_register_new_agent(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS])
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="new1234\n"))

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", mock_run),
        ):
            reg.cmd_register(["newagent", "--role", "dev", "--description", "A new agent"])

        out = capsys.readouterr().out
        assert "OK" in out
        assert "Claude Newagent" in out
        assert "Block #1" in out

        written = list(registry.glob("0001-newagent.json"))
        assert len(written) == 1
        data = json.loads(written[0].read_text())
        assert data["role"] == "dev"
        assert data["description"] == "A new agent"
        assert data["prev"] == GENESIS["content_hash"]
        assert data["content_hash"] is not None

    def test_register_parses_role_and_description(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS])
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="hash123\n"))

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", mock_run),
        ):
            reg.cmd_register(["agent", "--role", "lead", "--description", "the leader"])

        data = json.loads((registry / "0001-agent.json").read_text())
        assert data["role"] == "lead"
        assert data["description"] == "the leader"


# ---------------------------------------------------------------------------
# cmd_verify
# ---------------------------------------------------------------------------


class TestCmdVerify:
    def test_no_args_exits(self):
        with pytest.raises(SystemExit):
            reg.cmd_verify([])

    def test_not_registered_exits(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS])
        with patch.object(reg, "REGISTRY_DIR", registry), pytest.raises(SystemExit):
            reg.cmd_verify(["nobody"])
        out = capsys.readouterr().out
        assert "未注册" in out

    def test_valid_agent_passes(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        git_log_output = "abc1234 Register alice — Block #1\n"
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=git_log_output))

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", mock_run),
        ):
            reg.cmd_verify(["alice"])

        out = capsys.readouterr().out
        assert "OK" in out
        assert "内容完整" in out

    def test_tampered_content_fails(self, tmp_path, capsys):
        tampered = {**AGENT_1, "role": "hacker"}
        registry = _write_chain(tmp_path, [GENESIS, tampered])

        with patch.object(reg, "REGISTRY_DIR", registry), pytest.raises(SystemExit):
            reg.cmd_verify(["alice"])
        out = capsys.readouterr().out
        assert "篡改" in out

    def test_chain_not_found_warns(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=""))

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", mock_run),
        ):
            reg.cmd_verify(["alice"])

        out = capsys.readouterr().out
        assert "WARN" in out
        assert "未找到" in out


# ---------------------------------------------------------------------------
# cmd_verify_chain
# ---------------------------------------------------------------------------


class TestCmdVerifyChain:
    def test_valid_chain(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1, AGENT_2])
        with patch.object(reg, "REGISTRY_DIR", registry):
            reg.cmd_verify_chain([])
        out = capsys.readouterr().out
        assert "OK" in out
        assert "3 blocks" in out

    def test_legacy_utf8_hash_keeps_existing_chain_valid(self, tmp_path, capsys):
        legacy = {
            "block": 2,
            "name": "legacy",
            "display_name": "Claude Legacy",
            "type": "agent",
            "role": "dev",
            "description": "中文说明",
            "created": "2026-01-03",
            "prev": AGENT_1["content_hash"],
            "chain": "legacy1",
            "content_hash": None,
        }
        legacy["content_hash"] = reg._legacy_content_hash(legacy)
        next_agent = {
            "block": 3,
            "name": "carol",
            "display_name": "Claude Carol",
            "type": "agent",
            "role": "reviewer",
            "description": "Reviewer",
            "created": "2026-01-04",
            "prev": legacy["content_hash"],
            "chain": "ghi9012",
            "content_hash": None,
        }
        next_agent["content_hash"] = reg._content_hash(next_agent)
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1, legacy, next_agent])

        with patch.object(reg, "REGISTRY_DIR", registry):
            reg.cmd_verify_chain([])
        out = capsys.readouterr().out
        assert "OK" in out
        assert "4 blocks" in out

    def test_broken_prev_link(self, tmp_path, capsys):
        broken = {**AGENT_2, "prev": "wrong_hash"}
        broken["content_hash"] = reg._content_hash(broken)
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1, broken])

        with patch.object(reg, "REGISTRY_DIR", registry), pytest.raises(SystemExit):
            reg.cmd_verify_chain([])
        out = capsys.readouterr().out
        assert "断裂" in out

    def test_tampered_content_detected(self, tmp_path, capsys):
        tampered = {**AGENT_1, "role": "hacker"}
        registry = _write_chain(tmp_path, [GENESIS, tampered])

        with patch.object(reg, "REGISTRY_DIR", registry), pytest.raises(SystemExit):
            reg.cmd_verify_chain([])
        out = capsys.readouterr().out
        assert "篡改" in out

    def test_empty_chain_passes(self, tmp_path, capsys):
        registry = tmp_path / "registry"
        registry.mkdir()
        with patch.object(reg, "REGISTRY_DIR", registry):
            reg.cmd_verify_chain([])
        out = capsys.readouterr().out
        assert "OK" in out
        assert "0 blocks" in out


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_lists_all_entries(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1, AGENT_2])
        with patch.object(reg, "REGISTRY_DIR", registry):
            reg.cmd_list([])
        out = capsys.readouterr().out
        assert "Claude Alice" in out
        assert "Claude Bob" in out
        assert "#0" in out
        assert "#1" in out
        assert "#2" in out

    def test_empty_chain(self, tmp_path, capsys):
        registry = tmp_path / "registry"
        registry.mkdir()
        with patch.object(reg, "REGISTRY_DIR", registry):
            reg.cmd_list([])
        out = capsys.readouterr().out
        assert "Block" in out
        assert "Name" in out


# ---------------------------------------------------------------------------
# cmd_rank
# ---------------------------------------------------------------------------


class TestCmdRank:
    def test_ranks_by_commits_desc(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1, AGENT_2])

        def fake_run(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            if "--author" in cmd or "--grep" in cmd:
                if "alice" in str(cmd):
                    r.stdout = "commit1\ncommit2\ncommit3\n"
                elif "bob" in str(cmd):
                    r.stdout = "commit1\n"
                else:
                    r.stdout = ""
            else:
                r.stdout = ""
            return r

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", side_effect=fake_run),
        ):
            reg.cmd_rank([])

        out = capsys.readouterr().out
        assert "Claude Alice" in out
        assert "Claude Bob" in out

    def test_skips_project_entries(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS])
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=""))

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", mock_run),
        ):
            reg.cmd_rank([])

        out = capsys.readouterr().out
        assert "test-project" not in out


# ---------------------------------------------------------------------------
# cmd_whois
# ---------------------------------------------------------------------------


class TestCmdWhois:
    def test_no_args_exits(self):
        with pytest.raises(SystemExit):
            reg.cmd_whois([])

    def test_not_found_exits(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS])
        with patch.object(reg, "REGISTRY_DIR", registry), pytest.raises(SystemExit):
            reg.cmd_whois(["ghost"])
        out = capsys.readouterr().out
        assert "未注册" in out

    def test_shows_agent_info(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=""))

        with (
            patch.object(reg, "REGISTRY_DIR", registry),
            patch("subprocess.run", mock_run),
        ):
            reg.cmd_whois(["alice"])

        out = capsys.readouterr().out
        assert "Claude Alice" in out
        assert "#1" in out
        assert "dev" in out
        assert "abc1234" in out


# ---------------------------------------------------------------------------
# _sync_readme
# ---------------------------------------------------------------------------


class TestSyncReadme:
    def test_creates_readme_with_table(self, tmp_path):
        registry = _write_chain(tmp_path, [GENESIS, AGENT_1])
        with patch.object(reg, "REGISTRY_DIR", registry):
            reg._sync_readme()

        readme = registry / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "# Registry Chain" in content
        assert "Claude Alice" in content
        assert "`abc1234`" in content

    def test_empty_chain_writes_header_only(self, tmp_path):
        registry = tmp_path / "registry"
        registry.mkdir()
        with patch.object(reg, "REGISTRY_DIR", registry):
            reg._sync_readme()

        content = (registry / "README.md").read_text()
        assert "# Registry Chain" in content
        assert "Block" in content


# ---------------------------------------------------------------------------
# main dispatch
# ---------------------------------------------------------------------------


class TestMain:
    def test_no_args_exits(self):
        with patch.object(sys, "argv", ["registry"]), pytest.raises(SystemExit):
            reg.main()

    def test_unknown_command_exits(self, capsys):
        with patch.object(sys, "argv", ["registry", "badcmd"]), pytest.raises(SystemExit):
            reg.main()
        out = capsys.readouterr().out
        assert "Unknown command" in out

    def test_dispatches_list(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS])
        with (
            patch.object(sys, "argv", ["registry", "list"]),
            patch.object(reg, "REGISTRY_DIR", registry),
        ):
            reg.main()
        out = capsys.readouterr().out
        assert "Block" in out

    def test_dispatches_sync_readme(self, tmp_path, capsys):
        registry = _write_chain(tmp_path, [GENESIS])
        with (
            patch.object(sys, "argv", ["registry", "sync-readme"]),
            patch.object(reg, "REGISTRY_DIR", registry),
        ):
            reg.main()
        out = capsys.readouterr().out
        assert "OK" in out
        assert (registry / "README.md").exists()
