"""board_vote — governance: vote / tally."""

from lib.board_db import BoardDB, ts
from lib.common import PRIVILEGED_ROLES


def cmd_vote(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if name in PRIVILEGED_ROLES:
        print("ERROR: privileged roles have no voting rights (charter §二)")
        raise SystemExit(1)
    if len(args) < 3:
        print("Usage: ./board --as <name> vote <number> <SUPPORT|OBJECT> <reason>")
        raise SystemExit(1)

    num = args[0]
    decision = args[1].upper()
    reason = " ".join(args[2:])
    if decision not in ("SUPPORT", "OBJECT"):
        print("ERROR: must be SUPPORT or OBJECT")
        raise SystemExit(1)

    padded = f"{int(num):03d}" if num.isdigit() else num
    prop_id = db.scalar(
        "SELECT id FROM proposals WHERE number=? OR number=? LIMIT 1",
        (padded, num),
    )
    if not prop_id:
        print(f"ERROR: proposal {num} not found")
        raise SystemExit(1)

    prop_status = db.scalar("SELECT status FROM proposals WHERE id=?", (prop_id,))
    if prop_status != "OPEN":
        print(f"ERROR: proposal {num} already decided ({prop_status})")
        raise SystemExit(1)

    now = ts()
    db.execute(
        "INSERT OR REPLACE INTO votes(proposal_id, voter, decision, reason, ts) VALUES (?, ?, ?, ?, ?)",
        (prop_id, name, decision, reason, now),
    )
    print(f"OK voted {decision}\n\nTally:")

    for (line,) in db.query(
        "SELECT voter || ': ' || decision || ' — ' || reason FROM votes WHERE proposal_id=?",
        (prop_id,),
    ):
        print(f"  {line}")

    s = db.scalar(
        "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='SUPPORT'",
        (prop_id,),
    )
    o = db.scalar(
        "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='OBJECT'",
        (prop_id,),
    )

    prop_type = db.scalar("SELECT type FROM proposals WHERE id=?", (prop_id,))
    eligible = (
        db.scalar("SELECT COUNT(*) FROM sessions WHERE name != (SELECT value FROM meta WHERE key='dispatcher_session')")
        or 0
    )
    threshold = (eligible * 2 + 2) // 3 if prop_type == "S" else eligible // 2 + 1

    print(f"\n  SUPPORT={s} OBJECT={o} | type={prop_type} threshold={threshold}/{eligible}")

    if s >= threshold:
        db.execute(
            "UPDATE proposals SET status='PASSED', decided_at=? WHERE id=?",
            (now, prop_id),
        )
        print(f"\n>>> PASSED ({prop_type}级, {s}/{eligible} >= {threshold}) <<<")
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'SYSTEM', 'All', ?)",
            (now, f"[VOTE] Proposal {padded} PASSED ({s}S/{o}O, threshold {threshold})"),
        )
    elif o > (eligible - threshold):
        db.execute(
            "UPDATE proposals SET status='FAILED', decided_at=? WHERE id=?",
            (now, prop_id),
        )
        print(f"\n>>> FAILED (无法达到 {threshold} 票) <<<")
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'SYSTEM', 'All', ?)",
            (now, f"[VOTE] Proposal {padded} FAILED ({s}S/{o}O, threshold {threshold})"),
        )
    else:
        print(f"  (待定，还需 {threshold - s} 票 SUPPORT 通过)")


def cmd_tally(db: BoardDB, args: list[str]) -> None:
    if not args:
        print("Usage: ./board tally <number>")
        raise SystemExit(1)
    num = args[0]
    padded = f"{int(num):03d}" if num.isdigit() else num
    prop_id = db.scalar(
        "SELECT id FROM proposals WHERE number=? OR number=? LIMIT 1",
        (padded, num),
    )
    if not prop_id:
        print(f"ERROR: proposal {num} not found")
        raise SystemExit(1)

    prop_status = db.scalar("SELECT status FROM proposals WHERE id=?", (prop_id,))
    if prop_status != "OPEN":
        decided_at = db.scalar("SELECT decided_at FROM proposals WHERE id=?", (prop_id,))
        print(f"Already {prop_status}: {decided_at}")
        return

    for (line,) in db.query(
        "SELECT voter || ': ' || decision || ' — ' || reason FROM votes WHERE proposal_id=?",
        (prop_id,),
    ):
        print(f"  {line}")

    s = db.scalar(
        "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='SUPPORT'",
        (prop_id,),
    )
    o = db.scalar(
        "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='OBJECT'",
        (prop_id,),
    )
    prop_type = db.scalar("SELECT type FROM proposals WHERE id=?", (prop_id,))
    eligible = (
        db.scalar("SELECT COUNT(*) FROM sessions WHERE name != (SELECT value FROM meta WHERE key='dispatcher_session')")
        or 0
    )
    threshold = (eligible * 2 + 2) // 3 if prop_type == "S" else eligible // 2 + 1
    print(f"  SUPPORT={s} OBJECT={o} | type={prop_type} threshold={threshold}/{eligible}")
