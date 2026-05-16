"""crypto — X25519 sealed-box encryption for inter-agent messaging."""

import base64
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

_HKDF_INFO = b"claudes-mailbox-v1"


def generate_keypair() -> tuple[X25519PrivateKey, X25519PublicKey]:
    private = X25519PrivateKey.generate()
    return private, private.public_key()


def private_key_to_pem(key: X25519PrivateKey) -> bytes:
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())


def private_key_from_pem(data: bytes) -> X25519PrivateKey:
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    k = load_pem_private_key(data, password=None)
    if not isinstance(k, X25519PrivateKey):
        raise ValueError("not an X25519 private key")
    return k


def public_key_to_hex(key: X25519PublicKey) -> str:
    return key.public_bytes_raw().hex()


def public_key_from_hex(h: str) -> X25519PublicKey:
    return X25519PublicKey.from_public_bytes(bytes.fromhex(h))


def project_key_namespace(project_root: Path) -> str:
    resolved = str(project_root.expanduser().resolve())
    return "p" + hashlib.sha256(resolved.encode()).hexdigest()[:12]


def key_storage_name(name: str, project_root: Path | None = None) -> str:
    safe_name = name.replace("/", "_").replace("\\", "_").replace("\0", "").lower()
    if project_root is None:
        return safe_name
    return f"{project_key_namespace(project_root)}-{safe_name}"


def _derive_key(shared_secret: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(shared_secret)


def seal(plaintext: bytes, recipient_pub: X25519PublicKey) -> bytes:
    """Encrypt with ephemeral X25519 + AESGCM. Returns ephemeral_pub(32) + nonce(12) + ciphertext."""
    eph_priv, eph_pub = generate_keypair()
    shared = eph_priv.exchange(recipient_pub)
    aes_key = _derive_key(shared)
    nonce = os.urandom(12)
    ct = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    return eph_pub.public_bytes_raw() + nonce + ct


def unseal(blob: bytes, recipient_priv: X25519PrivateKey) -> bytes:
    """Decrypt a sealed message. Raises on tamper or wrong key."""
    if len(blob) < 44:
        raise ValueError("ciphertext too short")
    eph_pub_bytes = blob[:32]
    nonce = blob[32:44]
    ct = blob[44:]
    eph_pub = X25519PublicKey.from_public_bytes(eph_pub_bytes)
    shared = recipient_priv.exchange(eph_pub)
    aes_key = _derive_key(shared)
    return AESGCM(aes_key).decrypt(nonce, ct, None)


def seal_b64(plaintext: str, recipient_pub: X25519PublicKey) -> str:
    return base64.b64encode(seal(plaintext.encode(), recipient_pub)).decode()


def unseal_b64(encoded: str, recipient_priv: X25519PrivateKey) -> str:
    return unseal(base64.b64decode(encoded), recipient_priv).decode()


def save_keypair(
    keys_dir: Path, name: str, private: X25519PrivateKey, public: X25519PublicKey, project_root: Path | None = None
) -> None:
    keys_dir.mkdir(parents=True, exist_ok=True)
    storage_name = key_storage_name(name, project_root)
    (keys_dir / f"{storage_name}.pem").write_bytes(private_key_to_pem(private))
    (keys_dir / f"{storage_name}.pem").chmod(0o600)
    (keys_dir / f"{storage_name}.pub").write_text(public_key_to_hex(public) + "\n")


def load_private_key(keys_dir: Path, name: str, project_root: Path | None = None) -> X25519PrivateKey:
    pem_path = keys_dir / f"{key_storage_name(name, project_root)}.pem"
    legacy_path = keys_dir / f"{key_storage_name(name)}.pem"
    if not pem_path.exists() and project_root is not None and legacy_path.exists():
        pem_path = legacy_path
    if not pem_path.exists():
        raise FileNotFoundError(f"私钥不存在: {pem_path} (先运行 keygen)")
    return private_key_from_pem(pem_path.read_bytes())
