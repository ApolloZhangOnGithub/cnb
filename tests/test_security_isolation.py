"""Security tests for Issue #31 — project-level isolation.

Verifies that:
- Unregistered identities are rejected by ensure_session (fixed)
- Cross-session impersonation is still possible (known limitation, needs auth layer)
- Cross-project DB isolation exists at the SQLite level

Marked with 'security' pytest marker for selective runs.
"""

import sqlite3
from pathlib import Path

import pytest

from lib.board_db import BoardDB
from lib.board_msg import cmd_ack, cmd_inbox, cmd_send, cmd_status
from lib.board_task import cmd_task
from lib.common import ClaudesEnv

pytestmark = pytest.mark.security


def _make_project(tmp_path: Path, name: str, sessions: list[str]) -> BoardDB:
    """Create a standalone project with its own .claudes/ and board.db."""
    root = tmp_path / name
    root.mkdir()
    cd = root / ".claudes"
    cd.mkdir()
    (cd / "sessions").mkdir()
    (cd / "files").mkdir()
    (cd / "logs").mkdir()
    (cd / "cv").mkdir()

    sessions_toml = ", ".join(f'"{s}"' for s in sessions)
    (cd / "config.toml").write_text(f'claudes_home = "{root}"\nsessions = [{sessions_toml}]\nprefix = "{name}"\n')

    schema = Path(__file__).parent.parent / "schema.sql"
    conn = sqlite3.connect(str(cd / "board.db"))
    conn.executescript(schema.read_text())
    for s in sessions:
        conn.execute("INSERT INTO sessions(name) VALUES (?)", (s,))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '4')")
    conn.commit()
    conn.close()

    for s in sessions:
        (cd / "sessions" / f"{s}.md").write_text(f"# {s}\n")

    env = ClaudesEnv(
        claudes_dir=cd,
        project_root=root,
        install_home=Path(__file__).parent.parent,
        board_db=cd / "board.db",
        sessions_dir=cd / "sessions",
        cv_dir=cd / "cv",
        log_dir=cd / "logs",
        prefix=name,
        sessions=sessions,
        suspended_file=cd / "suspended",
        attendance_log=cd / "logs" / "attendance.log",
    )
    return BoardDB(env)


# ---------------------------------------------------------------------------
# Vulnerability 1: Unregistered identity auto-creation
# ---------------------------------------------------------------------------


class TestAutoRegistration:
    """ensure_session rejects unregistered identities."""

    def test_unknown_identity_rejected(self, db):
        """Unregistered names are rejected by ensure_session."""
        assert db.scalar("SELECT COUNT(*) FROM sessions WHERE name='attacker'") == 0
        with pytest.raises(SystemExit):
            db.ensure_session("attacker")
        assert db.scalar("SELECT COUNT(*) FROM sessions WHERE name='attacker'") == 0

    def test_unknown_identity_cannot_send_messages(self, db, capsys):
        """Unregistered identity is rejected when trying to send messages."""
        with pytest.raises(SystemExit):
            cmd_send(db, "intruder", ["alice", "you've been compromised"])
        msgs = db.query("SELECT sender, body FROM messages WHERE sender='intruder'")
        assert len(msgs) == 0

    def test_unknown_identity_cannot_read_inbox(self, db, capsys):
        """Unregistered identity is rejected when trying to read inbox."""
        with pytest.raises(SystemExit):
            cmd_inbox(db, "spy")
        assert db.scalar("SELECT COUNT(*) FROM sessions WHERE name='spy'") == 0


# ---------------------------------------------------------------------------
# Vulnerability 2: No access control between sessions
# ---------------------------------------------------------------------------


class TestCrossSessionAccess:
    """Any identity can interact with any other session's data."""

    def test_impersonate_status_update(self, db, capsys):
        """One agent can overwrite another's status.
        EXPECTED AFTER FIX: only the agent itself should update its own status.
        """
        cmd_status(db, "alice", ["working on important task"])
        capsys.readouterr()

        # bob overwrites alice's status
        cmd_status(db, "alice", ["hacked by bob"])
        out = capsys.readouterr().out
        assert "OK" in out

        row = db.query_one("SELECT status FROM sessions WHERE name='alice'")
        # BUG: alice's status was overwritten by someone using --as alice
        assert "hacked" in row[0]

    def test_add_task_to_any_session(self, db, capsys):
        """Any identity can add tasks to any other session.
        This is by design (leads assign tasks), but combined with no auth
        it means anyone can pile work onto agents.
        """
        cmd_task(db, "nobody", ["add", "--to", "alice", "malicious task"])
        out = capsys.readouterr().out
        assert "OK" in out

        tasks = db.query("SELECT description FROM tasks WHERE session='alice'")
        assert any("malicious" in t[0] for t in tasks)

    def test_ack_clears_others_inbox(self, db, capsys):
        """An attacker using --as <victim> can clear victim's unread messages.
        EXPECTED AFTER FIX: should verify caller identity.
        """
        cmd_send(db, "bob", ["alice", "important message"])
        capsys.readouterr()

        cmd_inbox(db, "alice")
        capsys.readouterr()

        # attacker clears alice's inbox
        cmd_ack(db, "alice")
        out = capsys.readouterr().out
        assert "已清空" in out


# ---------------------------------------------------------------------------
# Vulnerability 3: Cross-project access
# ---------------------------------------------------------------------------


class TestCrossProjectAccess:
    """Access to another project's board by pointing to its .claudes/ dir."""

    def test_read_other_projects_messages(self, tmp_path, capsys):
        """Project A can read Project B's messages by accessing its DB.
        EXPECTED AFTER FIX: should reject cross-project access.
        """
        _make_project(tmp_path, "project-a", ["alice", "bob"])
        db_b = _make_project(tmp_path, "project-b", ["charlie", "dave"])

        cmd_send(db_b, "charlie", ["dave", "secret project-b data"])
        capsys.readouterr()

        # project-a user accesses project-b's database directly
        msgs = db_b.query("SELECT sender, body FROM messages")
        # BUG: full access to project-b's data from any context
        assert len(msgs) >= 1
        assert any("secret" in m[1] for m in msgs)

    def test_inject_messages_blocked_for_outsider(self, tmp_path, capsys):
        """Outsider identity is rejected when trying to inject messages."""
        db_target = _make_project(tmp_path, "target-project", ["alice", "bob"])

        with pytest.raises(SystemExit):
            cmd_send(db_target, "outsider", ["alice", "phishing message from outside"])

        msgs = db_target.query("SELECT body FROM messages WHERE sender='outsider'")
        assert len(msgs) == 0

    def test_projects_share_no_state(self, tmp_path, capsys):
        """Verify that two projects have independent databases (baseline)."""
        db_a = _make_project(tmp_path, "proj-a", ["alice"])
        db_b = _make_project(tmp_path, "proj-b", ["bob"])

        cmd_send(db_a, "alice", ["alice", "proj-a message"])
        capsys.readouterr()

        msgs_b = db_b.query("SELECT COUNT(*) FROM messages")
        # This correctly shows isolation at the DB level
        assert msgs_b[0][0] == 0


# ---------------------------------------------------------------------------
# Vulnerability 4: ensure_session creates arbitrary sessions
# ---------------------------------------------------------------------------


class TestSessionCreationAbuse:
    """ensure_session rejects names not in the configured sessions list."""

    def test_bulk_session_creation_blocked(self, db):
        """Fake session names are rejected — no table pollution."""
        count_before = db.scalar("SELECT COUNT(*) FROM sessions")
        for i in range(10):
            with pytest.raises(SystemExit):
                db.ensure_session(f"fake-agent-{i}")
        count_after = db.scalar("SELECT COUNT(*) FROM sessions")
        assert count_after == count_before

    def test_unregistered_name_rejected(self, db):
        """Names not in the sessions table are rejected."""
        with pytest.raises(SystemExit):
            db.ensure_session("normal-name")
        assert db.scalar("SELECT COUNT(*) FROM sessions WHERE name='normal-name'") == 0

    def test_registered_sessions_match_config(self, db):
        """Only sessions pre-registered in the DB are accepted."""
        config_sessions = db.env.sessions if db.env else []
        for s in config_sessions:
            db.ensure_session(s)

        with pytest.raises(SystemExit):
            db.ensure_session("not-in-config")
        assert db.scalar("SELECT COUNT(*) FROM sessions WHERE name='not-in-config'") == 0
