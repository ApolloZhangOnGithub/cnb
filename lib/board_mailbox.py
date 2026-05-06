"""board_mailbox — encrypted async messaging between registered agents."""

import json
from pathlib import Path

from lib.board_db import BoardDB, ts
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


def _keys_dir(db: BoardDB) -> Path:
    return db.env.claudes_dir / "keys"


def _find_pubkey(name: str) -> str | None:
    """Look up public_key from registry entry."""
    for f in REGISTRY_DIR.glob("*.json"):
        entry = json.loads(f.read_text())
        if entry.get("name") == name and entry.get("type") != "project":
            return entry.get("public_key")
    return None


def _update_registry_pubkey(name: str, pubkey_hex: str) -> bool:
    """Write public_key into the agent's registry JSON."""
    for f in REGISTRY_DIR.glob("*.json"):
        entry = json.loads(f.read_text())
        if entry.get("name") == name and entry.get("type") != "project":
            entry["public_key"] = pubkey_hex
            f.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")
            return True
    return False


def cmd_keygen(db: BoardDB, identity: str) -> None:
    name = identity.lower()
    kd = _keys_dir(db)

    if (kd / f"{name}.pem").exists():
        print(f"ERROR: 密钥已存在 ({kd / f'{name}.pem'})，如需重新生成请先删除旧密钥")
        raise SystemExit(1)

    private, public = generate_keypair()
    save_keypair(kd, name, private, public)
    pubkey_hex = public_key_to_hex(public)

    updated = _update_registry_pubkey(name, pubkey_hex)
    if updated:
        print("OK 密钥已生成")
        print(f"  私钥: {kd / f'{name}.pem'} (勿泄露)")
        print(f"  公钥: {pubkey_hex[:16]}...")
        print("  已写入 registry")
    else:
        print("OK 密钥已生成")
        print(f"  私钥: {kd / f'{name}.pem'}")
        print(f"  公钥: {pubkey_hex[:16]}...")
        print(f"  WARNING: 未在 registry 中找到 {name}，公钥未自动注册")
        print(f"  手动注册: registry register {name} 后再运行 keygen")


def cmd_seal(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> seal <recipient> <message>")
        raise SystemExit(1)

    recipient = args[0].lower()
    plaintext = " ".join(args[1:])

    recipient_pubkey_hex = _find_pubkey(recipient)
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
        except Exception:
            print(f"  [{msg_ts}] **{sender}**: [解密失败 — 密钥不匹配或消息损坏]")

    if decrypted_ids:
        placeholders = ",".join("?" * len(decrypted_ids))
        db.execute(f"UPDATE mailbox SET read=1 WHERE id IN ({placeholders})", tuple(decrypted_ids))
        print(f"\n已标记 {len(decrypted_ids)} 条为已读")


def cmd_mailbox_log(db: BoardDB, identity: str) -> None:
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
        except Exception:
            print(f"  [{msg_ts}] {sender}: [无法解密]")
