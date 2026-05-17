"""board_hint — phase 1 plumbing for proactive association (#158).

Design: docs/dev/design-proactive-association.md.

Phase 1 scope is intentionally narrow — schema migration + CLI skeleton + opt-in
flag wiring + emit/list/clear/mute/unmute. Detection (signal computation,
confidence math) and surface UI (yellow block in `board view`) are phases 2/3.
"""

from __future__ import annotations

import json
import tomllib
from datetime import datetime, timedelta
from typing import Any

from lib.board_db import BoardDB
from lib.common import parse_flags

DEFAULT_TTL_DAYS = 7
DEFAULT_RATE_LIMIT_PER_HOUR = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

# Status values for hints — keep aligned with the design doc table.
STATUS_PENDING = "pending"
STATUS_SURFACED = "surfaced"
STATUS_EXPIRED = "expired"
STATUS_MUTED = "muted"
STATUS_DROPPED_RATE = "dropped_rate"
STATUSES = frozenset({STATUS_PENDING, STATUS_SURFACED, STATUS_EXPIRED, STATUS_MUTED, STATUS_DROPPED_RATE})

# Mute scopes.
SCOPE_SENDER = "sender"
SCOPE_TOPIC = "topic"
SCOPES = frozenset({SCOPE_SENDER, SCOPE_TOPIC})


def _hints_config(db: BoardDB) -> dict[str, Any]:
    """Read `[hints]` from .cnb/notifications.toml. Defaults when missing.

    Defaults keep the feature OFF — opt-in per recipient via the config flag.
    """
    cfg = {
        "enabled": False,
        "threshold": DEFAULT_CONFIDENCE_THRESHOLD,
        "rate_limit_per_hour": DEFAULT_RATE_LIMIT_PER_HOUR,
        "ttl_days": DEFAULT_TTL_DAYS,
    }
    env = db.env
    if env is None:
        return cfg
    toml_path = env.claudes_dir / "notifications.toml"
    if not toml_path.is_file():
        return cfg
    try:
        data = tomllib.loads(toml_path.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return cfg
    section = data.get("hints", {})
    for key in ("enabled", "threshold", "rate_limit_per_hour", "ttl_days"):
        if key in section:
            cfg[key] = section[key]
    return cfg


def _log_event(db: BoardDB, hint_id: int, event: str, meta: dict | None = None) -> None:
    db.execute(
        "INSERT INTO hint_events(hint_id, event, meta) VALUES (?, ?, ?)",
        (hint_id, event, json.dumps(meta) if meta else None),
    )


def _is_muted(db: BoardDB, recipient: str, sender: str, refs: dict) -> bool:
    """Check whether recipient has muted this sender or any of the hint's topics."""
    rows = db.query(
        "SELECT scope, value FROM hint_mutes WHERE recipient=?",
        (recipient,),
    )
    for scope, value in rows:
        if scope == SCOPE_SENDER and value == sender:
            return True
        # value format matches the topic key, e.g. "issue:42" or "path:lib/x.py"
        if scope == SCOPE_TOPIC and ":" in value:
            topic_kind, topic_val = value.split(":", 1)
            topic_kind = topic_kind.strip()
            topic_val = topic_val.strip()
            if topic_kind == "issue" and int(topic_val) in (refs.get("issues") or []):
                return True
            if topic_kind == "path" and topic_val in (refs.get("paths") or []):
                return True
    return False


def _rate_capped(db: BoardDB, sender: str, recipient: str, rate_per_hour: int) -> bool:
    """True if the (sender, recipient) pair has already accumulated rate_per_hour hints in last 1h.

    Per-pair semantics: rate is scoped to the *pair*, not the sender alone. The same sender
    emitting to multiple distinct recipients does not draw against each other's budget.
    Mirrors how mute is per-(recipient, sender) — both guardrails share the same granularity.
    """
    cutoff = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    count = db.scalar(
        "SELECT COUNT(*) FROM hints WHERE sender=? AND recipient=? AND ts > ? AND status != ?",
        (sender, recipient, cutoff, STATUS_DROPPED_RATE),
    )
    return (count or 0) >= rate_per_hour


def emit_hint(
    db: BoardDB,
    sender: str,
    recipient: str,
    body: str,
    *,
    confidence: float = 0.0,
    signals: dict | None = None,
    refs: dict | None = None,
) -> int:
    """Insert a hint. Returns the new hint id. Applies status based on guardrails."""
    cfg = _hints_config(db)
    refs = refs or {}
    signals = signals or {}
    ttl_days = int(cfg["ttl_days"])
    expires_at = (datetime.now() + timedelta(days=ttl_days)).strftime("%Y-%m-%d %H:%M:%S")

    # Mute check applies first — muted hints still get recorded for telemetry.
    if _is_muted(db, recipient, sender, refs):
        status = STATUS_MUTED
    elif _rate_capped(db, sender, recipient, int(cfg["rate_limit_per_hour"])):
        status = STATUS_DROPPED_RATE
    elif confidence < float(cfg["threshold"]):
        # Below threshold: enter pending; surface step will not pick it up.
        status = STATUS_PENDING
    else:
        status = STATUS_PENDING  # eligible to surface; phase 3 will surface it

    assert status in STATUSES, f"emit_hint: status {status!r} not in STATUSES — typo or stale code"
    hint_id = db.execute(
        "INSERT INTO hints(sender, recipient, body, signals, confidence, refs, expires_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (sender, recipient, body, json.dumps(signals), confidence, json.dumps(refs), expires_at, status),
    )
    _log_event(db, hint_id, "emit", {"status": status, "confidence": confidence})
    return hint_id


def list_hints(
    db: BoardDB,
    *,
    recipient: str | None = None,
    sender: str | None = None,
    include_expired: bool = False,
) -> list[dict]:
    """Return hints filtered by recipient/sender. Excludes expired by default."""
    where: list[str] = []
    params: list[Any] = []
    if recipient:
        where.append("recipient=?")
        params.append(recipient)
    if sender:
        where.append("sender=?")
        params.append(sender)
    if not include_expired:
        where.append("status != ?")
        params.append(STATUS_EXPIRED)
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.query(
        f"SELECT id, sender, recipient, body, confidence, refs, ts, status FROM hints {where_clause} ORDER BY id DESC",
        tuple(params),
    )
    out = []
    for row in rows:
        out.append(
            {
                "id": row[0],
                "sender": row[1],
                "recipient": row[2],
                "body": row[3],
                "confidence": row[4],
                "refs": json.loads(row[5]) if row[5] else {},
                "ts": row[6],
                "status": row[7],
            }
        )
    return out


def clear_hints(db: BoardDB, recipient: str) -> int:
    """Mark recipient's pending/surfaced hints as ignored (logged for telemetry).

    Returns count cleared. Does NOT touch messages/inbox — hints are independent.
    """
    surfaced = db.query(
        "SELECT id FROM hints WHERE recipient=? AND status IN (?, ?)",
        (recipient, STATUS_PENDING, STATUS_SURFACED),
    )
    for (hid,) in surfaced:
        _log_event(db, hid, "ignore", {"reason": "user_clear"})
    db.execute(
        "UPDATE hints SET status=? WHERE recipient=? AND status IN (?, ?)",
        (STATUS_EXPIRED, recipient, STATUS_PENDING, STATUS_SURFACED),
    )
    return len(surfaced)


def mute(db: BoardDB, recipient: str, *, sender: str | None = None, topic: str | None = None) -> None:
    """Add a mute. Exactly one of sender / topic must be provided."""
    if (sender is None) == (topic is None):
        print("ERROR: hint mute requires exactly one of <sender> or --topic <issue:N|path:P>")
        raise SystemExit(1)
    scope = SCOPE_SENDER if sender else SCOPE_TOPIC
    value = sender if sender else topic
    db.execute(
        "INSERT OR IGNORE INTO hint_mutes(recipient, scope, value) VALUES (?, ?, ?)",
        (recipient, scope, value),
    )


def unmute(db: BoardDB, recipient: str, *, sender: str | None = None, topic: str | None = None) -> int:
    """Remove a mute. Returns rows affected."""
    if (sender is None) == (topic is None):
        print("ERROR: hint unmute requires exactly one of <sender> or --topic <issue:N|path:P>")
        raise SystemExit(1)
    scope = SCOPE_SENDER if sender else SCOPE_TOPIC
    value = sender if sender else topic
    return db.execute_changes(
        "DELETE FROM hint_mutes WHERE recipient=? AND scope=? AND value=?",
        (recipient, scope, value),
    )


def cmd_hint(db: BoardDB, identity: str, args: list[str]) -> None:
    """Board command — `board --as <name> hint <subcmd> [args]`."""
    if not args:
        print("Usage: board --as <name> hint {emit|list|clear|mute|unmute} ...")
        raise SystemExit(1)

    sub = args[0]
    rest = args[1:]

    if sub == "emit":
        flags, positional = parse_flags(rest, value_flags={"refs": ["--refs"], "confidence": ["--confidence"]})
        if len(positional) < 2:
            print("Usage: board --as <name> hint emit <recipient> <body> [--refs ...] [--confidence N]")
            raise SystemExit(1)
        recipient = positional[0]
        body = " ".join(positional[1:])
        confidence = float(flags["confidence"]) if "confidence" in flags else 0.0
        refs = _parse_refs(str(flags["refs"])) if "refs" in flags else {}
        hint_id = emit_hint(db, identity, recipient, body, confidence=confidence, refs=refs)
        print(f"OK hint #{hint_id} emitted to {recipient}")
        return

    if sub == "list":
        flags, _positional = parse_flags(rest, value_flags={"for": ["--for"], "from": ["--from"]})
        include_expired = "--all" in rest
        hints = list_hints(
            db,
            recipient=str(flags["for"]) if "for" in flags else identity,
            sender=str(flags["from"]) if "from" in flags else None,
            include_expired=include_expired,
        )
        if not hints:
            print("(没有 hint)")
            return
        for h in hints:
            print(
                f"  #{h['id']:>3} [{h['status']:<13}] from {h['sender']:<10} conf={h['confidence']:.2f} "
                f"{h['ts']}  {h['body'][:80]}"
            )
        return

    if sub == "clear":
        flags, _positional = parse_flags(rest, value_flags={"for": ["--for"]})
        target = str(flags["for"]) if "for" in flags else identity
        n = clear_hints(db, target)
        print(f"OK 清空 {n} 条 hint (recipient={target})")
        return

    if sub == "mute":
        flags, positional = parse_flags(rest, value_flags={"topic": ["--topic"]})
        if "topic" in flags:
            mute(db, identity, topic=str(flags["topic"]))
            print(f"OK muted topic '{flags['topic']}' for {identity}")
            return
        if not positional:
            print("Usage: board --as <name> hint mute <sender>   OR   --topic <issue:N|path:P>")
            raise SystemExit(1)
        mute(db, identity, sender=positional[0])
        print(f"OK muted sender '{positional[0]}' for {identity}")
        return

    if sub == "unmute":
        flags, positional = parse_flags(rest, value_flags={"topic": ["--topic"]})
        if "topic" in flags:
            n = unmute(db, identity, topic=str(flags["topic"]))
            print(f"OK unmuted topic '{flags['topic']}' ({n} row)")
            return
        if not positional:
            print("Usage: board --as <name> hint unmute <sender>   OR   --topic <issue:N|path:P>")
            raise SystemExit(1)
        n = unmute(db, identity, sender=positional[0])
        print(f"OK unmuted sender '{positional[0]}' ({n} row)")
        return

    print(f"ERROR: unknown hint subcommand '{sub}'. Try: emit list clear mute unmute")
    raise SystemExit(1)


def _parse_refs(spec: str) -> dict:
    """Parse `--refs issues:42,paths:lib/x.py` into a dict.

    Format: comma-separated `kind:value` pairs. Same `kind` collects into a list.
    """
    out: dict[str, list] = {"issues": [], "paths": []}
    for token in spec.split(","):
        token = token.strip()
        if ":" not in token:
            continue
        kind, value = token.split(":", 1)
        kind = kind.strip()
        value = value.strip()
        if not value:
            continue
        if kind == "issues":
            try:
                out["issues"].append(int(value))
            except ValueError:
                pass
        elif kind == "paths":
            out["paths"].append(value)
    return out
