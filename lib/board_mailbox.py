"""board_mailbox — encrypted async messaging between registered agents."""

import binascii
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag

from lib.board_db import BoardDB, ts
from lib.common import validate_identity
from lib.crypto import (
    generate_keypair,
    load_private_key,
    public_key_from_hex,
    public_key_to_hex,
    save_keypair,
    seal_b64,
    unseal_b64,
)

REGISTRY_DIR = Path(__file__).resolve().parent.parent / "registry"
PUBKEYS_FILE = REGISTRY_DIR / "pubkeys.json"
_DEFAULT_PUBKEYS_FILE = PUBKEYS_FILE


def _keys_dir(db: BoardDB) -> Path:
    assert db.env is not None
    return db.env.claudes_dir / "keys"


def _pubkeys_file(db: BoardDB | None = None, *, claudes_dir: Path | None = None) -> Path:
    override = os.environ.get("CNB_PUBKEYS_FILE")
    if override:
        return Path(override).expanduser()
    if PUBKEYS_FILE != _DEFAULT_PUBKEYS_FILE:
        return PUBKEYS_FILE
    if claudes_dir is not None:
        return claudes_dir / "pubkeys.json"
    if db is not None and db.env is not None:
        return db.env.claudes_dir / "pubkeys.json"
    return PUBKEYS_FILE


def _read_pubkeys(path: Path) -> dict[str, str]:
    if path.exists():
        data: dict[str, str] = json.loads(path.read_text())
        return data
    return {}


def _load_pubkeys(db: BoardDB | None = None, *, claudes_dir: Path | None = None) -> dict[str, str]:
    return _read_pubkeys(_pubkeys_file(db, claudes_dir=claudes_dir))


def _save_pubkeys(data: dict[str, str], db: BoardDB | None = None, *, claudes_dir: Path | None = None) -> None:
    path = _pubkeys_file(db, claudes_dir=claudes_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _find_pubkey(name: str, db: BoardDB | None = None) -> str | None:
    """Look up public_key from pubkeys.json (separate from immutable chain blocks)."""
    target = _pubkeys_file(db)
    pubkey = _read_pubkeys(target).get(name)
    if pubkey:
        return pubkey
    if target != PUBKEYS_FILE:
        return _read_pubkeys(PUBKEYS_FILE).get(name)
    return None


def cmd_keygen(db: BoardDB, identity: str) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    kd = _keys_dir(db)

    if (kd / f"{name}.pem").exists():
        print(f"ERROR: 密钥已存在 ({kd / f'{name}.pem'})，如需重新生成请先删除旧密钥")
        raise SystemExit(1)

    private, public = generate_keypair()
    save_keypair(kd, name, private, public)
    pubkey_hex = public_key_to_hex(public)

    pubkeys = _load_pubkeys(db)
    pubkeys[name] = pubkey_hex
    _save_pubkeys(pubkeys, db)
    pubkeys_file = _pubkeys_file(db)

    print("OK 密钥已生成")
    print(f"  私钥: {kd / f'{name}.pem'} (勿泄露)")
    print(f"  公钥: {pubkey_hex[:16]}...")
    print(f"  已写入 {pubkeys_file}")


def cmd_keygen_all(db: BoardDB) -> None:
    assert db.env is not None
    kd = db.env.claudes_dir / "keys"
    sessions = [r[0] for r in db.query("SELECT name FROM sessions WHERE name != 'all' ORDER BY name")]
    if not sessions:
        print("ERROR: 无注册会话")
        raise SystemExit(1)

    pubkeys = _load_pubkeys(db)
    generated = 0
    skipped = 0

    for name in sessions:
        if (kd / f"{name}.pem").exists():
            skipped += 1
            continue
        private, public = generate_keypair()
        save_keypair(kd, name, private, public)
        pubkeys[name] = public_key_to_hex(public)
        generated += 1

    if generated:
        _save_pubkeys(pubkeys, db)

    print(f"OK keygen-all: {generated} 生成, {skipped} 跳过 (已有密钥)")
    if generated:
        print(f"  密钥目录: {kd}")
        print(f"  公钥注册: {_pubkeys_file(db)}")


def cmd_seal(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> seal <recipient> <message>")
        raise SystemExit(1)

    recipient = args[0].lower()
    plaintext = " ".join(args[1:]).strip()

    if not plaintext:
        print("ERROR: 消息不能为空")
        raise SystemExit(1)

    recipient_pubkey_hex = _find_pubkey(recipient, db)
    if not recipient_pubkey_hex:
        print(f"ERROR: {recipient} 未注册公钥 (需先运行 keygen)")
        raise SystemExit(1)

    recipient_pub = public_key_from_hex(recipient_pubkey_hex)
    encrypted = seal_b64(plaintext, recipient_pub)

    now = ts()
    db.execute(
        "INSERT INTO mailbox(ts, sender, recipient, encrypted_body) VALUES (?, ?, ?, ?)",
        (now, name, recipient, encrypted),
    )
    print(f"OK 加密消息已发送给 {recipient} ({len(encrypted)} bytes)")


def cmd_unseal(db: BoardDB, identity: str) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    kd = _keys_dir(db)

    try:
        private = load_private_key(kd, name)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)

    rows = db.query(
        "SELECT id, ts, sender, encrypted_body FROM mailbox WHERE recipient=? AND read=0 ORDER BY ts",
        (name,),
    )

    if not rows:
        print("加密信箱为空")
        return

    print(f"你有 {len(rows)} 条加密消息:\n")
    decrypted_ids = []
    for msg_id, msg_ts, sender, encrypted_body in rows:
        try:
            plaintext = unseal_b64(encrypted_body, private)
            print(f"  [{msg_ts}] **{sender}**: {plaintext}")
            decrypted_ids.append(msg_id)
        except (InvalidTag, ValueError, binascii.Error, UnicodeDecodeError) as e:
            print(f"  [{msg_ts}] **{sender}**: [解密失败 — {type(e).__name__}: {e}]")

    if decrypted_ids:
        with db.conn() as c:
            for mid in decrypted_ids:
                db.execute("UPDATE mailbox SET read=1 WHERE id=?", (mid,), c=c)
        print(f"\n已标记 {len(decrypted_ids)} 条为已读")


def cmd_mailbox_log(db: BoardDB, identity: str) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    kd = _keys_dir(db)

    try:
        private = load_private_key(kd, name)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)

    rows = db.query(
        "SELECT ts, sender, encrypted_body FROM mailbox WHERE recipient=? ORDER BY ts DESC LIMIT 20",
        (name,),
    )
    if not rows:
        print("无加密消息记录")
        return

    for msg_ts, sender, encrypted_body in reversed(rows):
        try:
            plaintext = unseal_b64(encrypted_body, private)
            print(f"  [{msg_ts}] {sender}: {plaintext}")
        except (InvalidTag, ValueError, binascii.Error, UnicodeDecodeError) as e:
            print(f"  [{msg_ts}] {sender}: [无法解密 — {type(e).__name__}: {e}]")
