"""board_bug — bug tracker: report / assign / fix / list / overdue."""

import time
from datetime import datetime

from lib.board_db import BoardDB, ts
from lib.common import is_terminal_bug_status


def cmd_bug(db: BoardDB, identity: str, args: list[str]) -> None:
    subcmd = args[0] if args else "list"
    rest = args[1:] if len(args) > 1 else []
    dispatch = {
        "report": lambda: _bug_report(db, identity, rest),
        "assign": lambda: _bug_assign(db, identity, rest),
        "fix": lambda: _bug_fix(db, identity, rest),
        "list": lambda: _bug_list(db, rest),
        "overdue": lambda: _bug_overdue(db),
    }
    fn = dispatch.get(subcmd)
    if not fn:
        print("Usage: ./board --as <name> bug {report|assign|fix|list|overdue}")
        raise SystemExit(1)
    fn()


def _bug_report(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> bug report <P0|P1|P2> <description>")
        raise SystemExit(1)
    severity = args[0].upper()
    if severity not in ("P0", "P1", "P2"):
        print("ERROR: severity must be P0, P1, or P2")
        raise SystemExit(1)
    desc = " ".join(args[1:])
    sla = {"P0": "immediate", "P1": "4h", "P2": "24h"}[severity]

    now = ts()

    with db.conn() as c:
        max_id = db.scalar("SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 0) FROM bugs", c=c)
        next_id = f"BUG-{max_id + 1:03d}"
        db.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) VALUES (?, ?, ?, ?, 'OPEN', ?)",
            (next_id, severity, sla, name, desc),
            c=c,
        )
        msg_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, 'all', ?)",
            (now, name, f"[{next_id}/{severity}] {desc}"),
            c=c,
        )
        db.deliver_to_inbox(name, "all", msg_id, c=c)
    print(f"OK {next_id} ({severity}) created")


def _bug_assign(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> bug assign <BUG-NNN> <session>")
        raise SystemExit(1)
    bugid = args[0].upper()
    if not bugid.startswith("BUG-"):
        bugid = f"BUG-{bugid}"
    assignee = args[1].lower()

    exists = db.scalar("SELECT COUNT(*) FROM bugs WHERE id=?", (bugid,))
    if not exists:
        print(f"ERROR: {bugid} not found")
        raise SystemExit(1)

    now = ts()
    with db.conn() as c:
        db.execute("UPDATE bugs SET assignee=?, status='ASSIGNED' WHERE id=?", (assignee, bugid), c=c)
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, name, assignee, f"[{bugid}] assigned to you"),
            c=c,
        )
    print(f"OK {bugid} assigned to {assignee}")


def _bug_fix(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> bug fix <BUG-NNN> <evidence>")
        raise SystemExit(1)
    bugid = args[0].upper()
    if not bugid.startswith("BUG-"):
        bugid = f"BUG-{bugid}"
    evidence = " ".join(args[1:])

    row = db.query_one("SELECT status FROM bugs WHERE id=?", (bugid,))
    if not row:
        print(f"ERROR: {bugid} not found")
        raise SystemExit(1)

    if is_terminal_bug_status(row["status"]):
        print(f"Bug {bugid} is already {row['status']}.")
        return

    now = ts()
    with db.conn() as c:
        db.execute("UPDATE bugs SET status='FIXED', fixed_at=?, evidence=? WHERE id=?", (now, evidence, bugid), c=c)
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, 'all', ?)",
            (now, name, f"[{bugid}] FIXED — {evidence}"),
            c=c,
        )
    print(f"OK {bugid} marked FIXED")


def _bug_list(db: BoardDB, args: list[str]) -> None:
    filt = args[0] if args else "open"
    print("=== Bug Tracker ===")

    if filt == "open":
        rows = db.query(
            "SELECT id, severity, status, assignee, reporter, reported_at, description "
            "FROM bugs WHERE status != 'FIXED' ORDER BY reported_at"
        )
    elif filt == "all":
        rows = db.query(
            "SELECT id, severity, status, assignee, reporter, reported_at, description FROM bugs ORDER BY reported_at"
        )
    else:
        rows = db.query(
            "SELECT id, severity, status, assignee, reporter, reported_at, description "
            "FROM bugs WHERE status = ? ORDER BY reported_at",
            (filt.upper(),),
        )

    if not rows:
        print(f"  (no bugs matching filter: {filt})")
    else:
        for bid, sev, status, assignee, reporter, reported, desc in rows:
            print(f"\n  {bid} [{sev}] {status}")
            print(f"    Reporter: {reporter}  Assignee: {assignee or 'unassigned'}")
            print(f"    Reported: {reported}")
            print(f"    {desc}")
    print()


def _bug_overdue(db: BoardDB) -> None:
    now_epoch = int(time.time())
    rows = db.query("SELECT id, severity, reported_at FROM bugs WHERE status != 'FIXED'")
    found = False
    for bid, sev, reported in rows:
        try:
            dt = datetime.strptime(reported, "%Y-%m-%d %H:%M")
            rep_epoch = int(dt.timestamp())
        except (ValueError, TypeError):
            continue
        elapsed = now_epoch - rep_epoch
        limit = {"P0": 0, "P1": 14400, "P2": 86400}.get(sev, 0)
        if elapsed > limit:
            found = True
            print(f"OVERDUE: {bid} [{sev}] — {elapsed // 60}min since reported")
    if not found:
        print("No overdue bugs.")
