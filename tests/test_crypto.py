"""Tests for lib/crypto.py — X25519 sealed-box encryption."""

import pytest
from cryptography.exceptions import InvalidTag

from lib.crypto import (
    generate_keypair,
    load_private_key,
    private_key_from_pem,
    private_key_to_pem,
    public_key_from_hex,
    public_key_to_hex,
    save_keypair,
    seal,
    seal_b64,
    unseal,
    unseal_b64,
)


class TestKeypair:
    def test_generate_returns_pair(self):
        priv, pub = generate_keypair()
        assert priv is not None
        assert pub is not None

    def test_roundtrip_pem(self):
        priv, _ = generate_keypair()
        pem = private_key_to_pem(priv)
        restored = private_key_from_pem(pem)
        assert private_key_to_pem(restored) == pem

    def test_roundtrip_hex(self):
        _, pub = generate_keypair()
        h = public_key_to_hex(pub)
        assert len(h) == 64
        restored = public_key_from_hex(h)
        assert public_key_to_hex(restored) == h

    def test_save_and_load(self, tmp_path):
        priv, pub = generate_keypair()
        save_keypair(tmp_path, "alice", priv, pub)
        assert (tmp_path / "alice.pem").exists()
        assert (tmp_path / "alice.pub").exists()
        loaded = load_private_key(tmp_path, "alice")
        assert private_key_to_pem(loaded) == private_key_to_pem(priv)

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_private_key(tmp_path, "nonexistent")


class TestSealUnseal:
    def test_roundtrip_bytes(self):
        _, sender_pub = generate_keypair()
        recv_priv, recv_pub = generate_keypair()
        plaintext = b"hello encrypted world"
        ct = seal(plaintext, recv_pub)
        result = unseal(ct, recv_priv)
        assert result == plaintext

    def test_roundtrip_b64(self):
        recv_priv, recv_pub = generate_keypair()
        msg = "这是一条加密消息"
        ct = seal_b64(msg, recv_pub)
        result = unseal_b64(ct, recv_priv)
        assert result == msg

    def test_wrong_key_fails(self):
        _, recv_pub = generate_keypair()
        wrong_priv, _ = generate_keypair()
        ct = seal(b"secret", recv_pub)
        with pytest.raises(InvalidTag):
            unseal(ct, wrong_priv)

    def test_tampered_ciphertext_fails(self):
        recv_priv, recv_pub = generate_keypair()
        ct = seal(b"secret", recv_pub)
        tampered = ct[:-1] + bytes([ct[-1] ^ 0xFF])
        with pytest.raises(InvalidTag):
            unseal(tampered, recv_priv)

    def test_short_ciphertext_fails(self):
        recv_priv, _ = generate_keypair()
        with pytest.raises(ValueError, match="too short"):
            unseal(b"tooshort", recv_priv)

    def test_each_seal_produces_different_ciphertext(self):
        recv_priv, recv_pub = generate_keypair()
        msg = b"same message"
        ct1 = seal(msg, recv_pub)
        ct2 = seal(msg, recv_pub)
        assert ct1 != ct2
        assert unseal(ct1, recv_priv) == msg
        assert unseal(ct2, recv_priv) == msg

    def test_empty_message(self):
        recv_priv, recv_pub = generate_keypair()
        ct = seal(b"", recv_pub)
        assert unseal(ct, recv_priv) == b""

    def test_large_message(self):
        recv_priv, recv_pub = generate_keypair()
        msg = b"x" * 100_000
        ct = seal(msg, recv_pub)
        assert unseal(ct, recv_priv) == msg
