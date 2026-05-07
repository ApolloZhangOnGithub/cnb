"""board_mail — persistent mail with CC and threading."""

import json

from lib.board_db import BoardDB, ts
from lib.common import parse_flags


def cmd_mail(db: BoardDB, identity: str, args: list[str]) -> None:
    subcmd = args[0] if args else "list"
    rest = args[1:] if len(args) > 1 else []

    if subcmd == "send":
        _mail_send(db, identity, rest)
    elif subcmd == "list":
        _mail_list(db, identity, rest)
    elif subcmd == "read":
        _mail_read(db, identity, rest)
    elif subcmd == "reply":
        _mail_reply(db, identity, rest)
    else:
        print("Usage: ./board --as <name> mail {send|list|read|reply}")
        raise SystemExit(1)


def _parse_recipient_list(raw: str) -> list[str]:
    return [r.strip().lower() for r in raw.split(",") if r.strip()]


def _mail_send(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    flags, positional = parse_flags(
        args,
        value_flags={
            "to": ["--to"],
            "cc": ["--cc"],
            "subject": ["--subject", "-s"],
            "body": ["--body", "-b"],
        },
    )

    to_raw = str(flags.get("to", ""))
    cc_raw = str(flags.get("cc", ""))
    subject = str(flags.get("subject", ""))
    body = str(flags.get("body", ""))

    if not body and positional:
        body = " ".join(positional)

    if not to_raw or not subject or not body:
        print("Usage: ./board --as <name> mail send --to <recipients> --subject <subj> --body <body> [--cc <cc>]")
        raise SystemExit(1)

    recipients = _parse_recipient_list(to_raw)
    cc = _parse_recipient_list(cc_raw) if cc_raw else []

    if not recipients:
        print("ERROR: 至少需要一个收件人")
        raise SystemExit(1)

    now = ts()
    mail_id = db.execute(
        "INSERT INTO mail(sender, recipients, cc, subject, body, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (name, json.dumps(recipients), json.dumps(cc), subject, body, now),
    )

    all_targets = set(recipients + cc) - {name}
    for target in all_targets:
        db.ensure_session(target)

    print(f"OK mail #{mail_id} sent")
    print(f"  To: {', '.join(recipients)}")
    if cc:
        print(f"  CC: {', '.join(cc)}")
    print(f"  Subject: {subject}")


def _mail_list(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    flags, _ = parse_flags(args, bool_flags={"unread": ["--unread", "-u"], "all": ["--all", "-a"]})
    unread_only = bool(flags.get("unread"))
    show_all = bool(flags.get("all"))

    if show_all:
        rows = db.query("SELECT id, thread_id, sender, recipients, cc, subject, ts, read_by FROM mail ORDER BY ts DESC")
    else:
        rows = db.query(
            "SELECT id, thread_id, sender, recipients, cc, subject, ts, read_by FROM mail "
            "WHERE recipients LIKE ? OR cc LIKE ? OR sender=? ORDER BY ts DESC",
            (f'%"{name}"%', f'%"{name}"%', name),
        )

    if not rows:
        print("邮箱为空")
        return

    if unread_only:
        rows = [r for r in rows if name not in json.loads(r[7])]

    if not rows:
        print("无未读邮件")
        return

    print("=== 邮箱 ===\n")
    for row in rows:
        mid, thread_id, sender, recipients_json, _cc_json, subject, mail_ts, read_by_json = row
        read_by = json.loads(read_by_json)
        is_read = name in read_by
        marker = " " if is_read else "●"
        thread_marker = f" ↩{thread_id}" if thread_id else ""
        recipients = json.loads(recipients_json)
        to_str = ", ".join(recipients)
        print(f"  {marker} #{mid}{thread_marker} [{mail_ts}] {sender} → {to_str}: {subject}")

    unread_count = sum(1 for r in rows if name not in json.loads(r[7]))
    if unread_count:
        print(f"\n  {unread_count} 封未读")


def _mail_read(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if not args:
        print("Usage: ./board --as <name> mail read <#id>")
        raise SystemExit(1)

    try:
        mail_id = int(args[0].lstrip("#"))
    except ValueError:
        print("Usage: ./board --as <name> mail read <#id>")
        raise SystemExit(1)

    row = db.query_one(
        "SELECT id, thread_id, sender, recipients, cc, subject, body, ts, read_by FROM mail WHERE id=?",
        (mail_id,),
    )
    if not row:
        print(f"ERROR: 邮件 #{mail_id} 不存在")
        raise SystemExit(1)

    mid, thread_id, sender, recipients_json, cc_json, subject, body, mail_ts, read_by_json = row
    recipients = json.loads(recipients_json)
    cc = json.loads(cc_json)
    read_by = json.loads(read_by_json)

    print(f"Mail #{mid}")
    if thread_id:
        print(f"  Re: #{thread_id}")
    print(f"  From: {sender}")
    print(f"  To: {', '.join(recipients)}")
    if cc:
        print(f"  CC: {', '.join(cc)}")
    print(f"  Subject: {subject}")
    print(f"  Date: {mail_ts}")
    print(f"\n{body}")

    thread_replies = db.query(
        "SELECT id, sender, body, ts FROM mail WHERE thread_id=? ORDER BY ts",
        (mid,),
    )
    if thread_replies:
        print(f"\n--- {len(thread_replies)} 条回复 ---")
        for rid, rsender, rbody, rts in thread_replies:
            print(f"\n  #{rid} [{rts}] {rsender}:")
            print(f"  {rbody}")

    if name not in read_by:
        read_by.append(name)
        db.execute("UPDATE mail SET read_by=? WHERE id=?", (json.dumps(read_by), mid))


def _mail_reply(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> mail reply <#id> <body>")
        raise SystemExit(1)

    try:
        parent_id = int(args[0].lstrip("#"))
    except ValueError:
        print("Usage: ./board --as <name> mail reply <#id> <body>")
        raise SystemExit(1)

    body = " ".join(args[1:])

    parent = db.query_one(
        "SELECT id, thread_id, sender, recipients, cc, subject FROM mail WHERE id=?",
        (parent_id,),
    )
    if not parent:
        print(f"ERROR: 邮件 #{parent_id} 不存在")
        raise SystemExit(1)

    _, parent_thread_id, parent_sender, recipients_json, cc_json, subject = parent
    thread_root = parent_thread_id if parent_thread_id else parent_id

    original_recipients = json.loads(recipients_json)
    original_cc = json.loads(cc_json)
    all_involved = set(original_recipients + original_cc + [parent_sender]) - {name}
    reply_recipients = list(all_involved)

    reply_subject = subject if subject.startswith("Re: ") else f"Re: {subject}"

    now = ts()
    reply_id = db.execute(
        "INSERT INTO mail(thread_id, sender, recipients, cc, subject, body, ts, read_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (thread_root, name, json.dumps(reply_recipients), "[]", reply_subject, body, now, json.dumps([name])),
    )

    print(f"OK mail #{reply_id} reply sent")
    print(f"  To: {', '.join(reply_recipients)}")
    print(f"  Subject: {reply_subject}")
