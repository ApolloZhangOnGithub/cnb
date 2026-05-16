"""Tests for lib/board_mailbox.py — encrypted async messaging.

Covers: keygen, seal (encrypt+send), unseal (decrypt+read), mailbox_log,
error paths (missing keys, empty messages, duplicate keygen).
"""

import json
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_mailbox import _private_key_path, cmd_keygen, cmd_keygen_all, cmd_mailbox_log, cmd_seal, cmd_unseal


def _mock_registry(pubkeys_file):
    """ExitStack helper to patch PUBKEYS_FILE and REGISTRY_DIR together."""
    stack = ExitStack()
    stack.enter_context(patch("lib.board_mailbox.PUBKEYS_FILE", pubkeys_file))
    stack.enter_context(patch("lib.board_mailbox.REGISTRY_DIR", pubkeys_file.parent))
    return stack


@pytest.fixture
def mailbox_db(db):
    """BoardDB with keys dir."""
    keys_dir = db.env.claudes_dir / "keys"
    keys_dir.mkdir(exist_ok=True)
    return db


@pytest.fixture
def pubkeys_file(tmp_path):
    """Temporary pubkeys.json inside a registry dir."""
    registry = tmp_path / "registry"
    registry.mkdir()
    f = registry / "pubkeys.json"
    f.write_text("{}")
    return f


@pytest.fixture
def keyed_pair(mailbox_db, pubkeys_file):
    """Two sessions (alice, bob) with generated keypairs."""
    with _mock_registry(pubkeys_file):
        cmd_keygen(mailbox_db, "alice")
        cmd_keygen(mailbox_db, "bob")
    return mailbox_db, pubkeys_file


class TestKeygen:
    def test_generates_keypair(self, mailbox_db, pubkeys_file, capsys):
        with _mock_registry(pubkeys_file):
            cmd_keygen(mailbox_db, "alice")
        output = capsys.readouterr().out
        assert "OK" in output
        assert _private_key_path(mailbox_db, "alice").exists()
        assert not (mailbox_db.env.claudes_dir / "keys" / "alice.pem").exists()

    def test_key_filename_is_namespaced_by_project(self, mailbox_db, pubkeys_file):
        with _mock_registry(pubkeys_file):
            cmd_keygen(mailbox_db, "alice")
        path = _private_key_path(mailbox_db, "alice")
        assert path.name.startswith("p")
        assert path.name.endswith("-alice.pem")

    def test_registers_pubkey(self, mailbox_db, pubkeys_file):
        with _mock_registry(pubkeys_file):
            cmd_keygen(mailbox_db, "alice")
        data = json.loads(pubkeys_file.read_text())
        assert "alice" in data
        assert len(data["alice"]) > 10

    def test_duplicate_keygen_exits(self, mailbox_db, pubkeys_file):
        with _mock_registry(pubkeys_file):
            cmd_keygen(mailbox_db, "alice")
            with pytest.raises(SystemExit):
                cmd_keygen(mailbox_db, "alice")


class TestKeygenAll:
    def test_generates_keys_for_all_sessions(self, mailbox_db, pubkeys_file, capsys):
        with _mock_registry(pubkeys_file):
            cmd_keygen_all(mailbox_db)
        output = capsys.readouterr().out
        assert "OK keygen-all" in output
        sessions = [r[0] for r in mailbox_db.query("SELECT name FROM sessions WHERE name != 'all'")]
        for s in sessions:
            assert _private_key_path(mailbox_db, s).exists(), f"Missing key for {s}"
        data = json.loads(pubkeys_file.read_text())
        for s in sessions:
            assert s in data

    def test_skips_existing_keys(self, mailbox_db, pubkeys_file, capsys):
        with _mock_registry(pubkeys_file):
            cmd_keygen(mailbox_db, "alice")
            capsys.readouterr()
            cmd_keygen_all(mailbox_db)
        output = capsys.readouterr().out
        assert "跳过" in output

    def test_idempotent(self, mailbox_db, pubkeys_file, capsys):
        with _mock_registry(pubkeys_file):
            cmd_keygen_all(mailbox_db)
            capsys.readouterr()
            cmd_keygen_all(mailbox_db)
        output = capsys.readouterr().out
        assert "0 生成" in output

    def test_generated_keys_work_for_seal_unseal(self, mailbox_db, pubkeys_file, capsys):
        with _mock_registry(pubkeys_file):
            cmd_keygen_all(mailbox_db)
            capsys.readouterr()
            cmd_seal(mailbox_db, "alice", ["bob", "auto-keygen test"])
            capsys.readouterr()
        cmd_unseal(mailbox_db, "bob")
        output = capsys.readouterr().out
        assert "auto-keygen test" in output

    def test_unseal_can_read_legacy_private_key(self, mailbox_db, pubkeys_file, capsys):
        with _mock_registry(pubkeys_file):
            cmd_keygen(mailbox_db, "bob")
            namespaced = _private_key_path(mailbox_db, "bob")
            legacy = namespaced.parent / "bob.pem"
            namespaced.rename(legacy)
            cmd_keygen(mailbox_db, "alice")
            capsys.readouterr()
            cmd_seal(mailbox_db, "alice", ["bob", "legacy-key works"])
            capsys.readouterr()

        cmd_unseal(mailbox_db, "bob")

        output = capsys.readouterr().out
        assert "legacy-key works" in output


class TestSeal:
    def test_seal_stores_encrypted_message(self, keyed_pair):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file):
            cmd_seal(db, "alice", ["bob", "secret", "message"])
        count = db.scalar("SELECT COUNT(*) FROM mailbox WHERE sender='alice' AND recipient='bob'")
        assert count == 1

    def test_seal_body_is_encrypted(self, keyed_pair):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file):
            cmd_seal(db, "alice", ["bob", "hello world"])
        body = db.scalar("SELECT encrypted_body FROM mailbox WHERE sender='alice'")
        assert body != "hello world"
        assert len(body) > 20

    def test_seal_no_recipient_key_exits(self, keyed_pair):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file), pytest.raises(SystemExit):
            cmd_seal(db, "alice", ["charlie", "no key for charlie"])

    def test_seal_empty_message_exits(self, keyed_pair):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file), pytest.raises(SystemExit):
            cmd_seal(db, "alice", ["bob", ""])

    def test_seal_too_few_args_exits(self, keyed_pair):
        db, _pubkeys_file = keyed_pair
        with pytest.raises(SystemExit):
            cmd_seal(db, "alice", ["bob"])


class TestUnseal:
    def test_unseal_decrypts_message(self, keyed_pair, capsys):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file):
            cmd_seal(db, "alice", ["bob", "top secret"])
        capsys.readouterr()

        cmd_unseal(db, "bob")
        output = capsys.readouterr().out
        assert "top secret" in output

    def test_unseal_marks_as_read(self, keyed_pair, capsys):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file):
            cmd_seal(db, "alice", ["bob", "read me"])
        capsys.readouterr()

        cmd_unseal(db, "bob")
        unread = db.scalar("SELECT COUNT(*) FROM mailbox WHERE recipient='bob' AND read=0")
        assert unread == 0

    def test_unseal_empty_mailbox(self, keyed_pair, capsys):
        db, _ = keyed_pair
        cmd_unseal(db, "bob")
        output = capsys.readouterr().out
        assert "加密信箱为空" in output

    def test_unseal_no_private_key_exits(self, mailbox_db):
        with pytest.raises(SystemExit):
            cmd_unseal(mailbox_db, "nokeys")

    def test_unseal_multiple_messages(self, keyed_pair, capsys):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file):
            cmd_seal(db, "alice", ["bob", "first"])
            cmd_seal(db, "alice", ["bob", "second"])
        capsys.readouterr()

        cmd_unseal(db, "bob")
        output = capsys.readouterr().out
        assert "first" in output
        assert "second" in output
        assert "2 条" in output


class TestMailboxLog:
    def test_log_shows_decrypted_history(self, keyed_pair, capsys):
        db, pubkeys_file = keyed_pair
        with _mock_registry(pubkeys_file):
            cmd_seal(db, "alice", ["bob", "logged msg"])
        capsys.readouterr()

        cmd_mailbox_log(db, "bob")
        output = capsys.readouterr().out
        assert "logged msg" in output

    def test_log_empty(self, keyed_pair, capsys):
        db, _ = keyed_pair
        cmd_mailbox_log(db, "bob")
        output = capsys.readouterr().out
        assert "无加密消息记录" in output

    def test_log_no_key_exits(self, mailbox_db):
        with pytest.raises(SystemExit):
            cmd_mailbox_log(mailbox_db, "nokeys")
