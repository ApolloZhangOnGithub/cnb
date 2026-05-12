"""board_pending — pending actions queue: add / list / verify / retry / resolve."""

import shlex
import subprocess

from lib import fmt
from lib.board_db import BoardDB, ts
from lib.common import parse_flags, validate_identity

VALID_TYPES = ("auth", "approve", "confirm")
PENDING_STATUSES = ("pending", "reminded")


def cmd_pending(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
    subcmd = args[0] if args else "list"
    rest = args[1:] if len(args) > 1 else []

    if subcmd == "add":
        _pending_add(db, identity, rest)
    elif subcmd == "list":
        _pending_list(db, identity, rest)
    elif subcmd == "verify":
        _pending_verify(db, identity, rest)
    elif subcmd == "retry":
        _pending_retry(db, identity, rest)
    elif subcmd == "resolve":
        _pending_resolve(db, identity, rest)
    else:
        print("Usage: ./board --as <name> pending {add|list|verify|retry|resolve}")
        raise SystemExit(1)


def _pending_add(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    flags, _positional = parse_flags(
        args,
        value_flags={
            "type": ["--type", "-t"],
            "command": ["--command", "-c"],
            "reason": ["--reason", "-r"],
            "verify": ["--verify", "-v"],
            "retry": ["--retry"],
        },
    )

    action_type = str(flags.get("type", "")).lower()
    command = str(flags.get("command", ""))
    reason = str(flags.get("reason", ""))
    verify_cmd = str(flags.get("verify", "")) or None
    retry_cmd = str(flags.get("retry", "")) or None

    if not action_type or not command or not reason:
        print(
            "Usage: ./board --as <name> pending add --type <auth|approve|confirm> --command <cmd> --reason <why> [--verify <cmd>] [--retry <cmd>]"
        )
        raise SystemExit(1)

    if action_type not in VALID_TYPES:
        valid = ", ".join(VALID_TYPES)
        print(fmt.err(f"类型必须是 {valid} 之一"))
        raise SystemExit(1)

    now = ts()
    action_id = db.execute(
        "INSERT INTO pending_actions(type, command, reason, verify_command, retry_command, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (action_type, command, reason, verify_cmd, retry_cmd, name, now),
    )
    print(fmt.ok(f"pending #{action_id} added ({action_type})"))
    print(f"  用户需执行: {fmt.bold(command)}")
    print(f"  原因: {reason}")


def _pending_list(db: BoardDB, identity: str, args: list[str]) -> None:
    flags, _ = parse_flags(args, bool_flags={"all": ["--all", "-a"]})
    show_all = bool(flags.get("all"))

    if show_all:
        rows = db.query(
            "SELECT id, type, command, reason, verify_command, retry_command, status, created_by, created_at, resolved_at "
            "FROM pending_actions ORDER BY id"
        )
    else:
        rows = db.query(
            "SELECT id, type, command, reason, verify_command, retry_command, status, created_by, created_at, resolved_at "
            "FROM pending_actions WHERE status IN ('pending', 'reminded') ORDER BY id"
        )

    if not rows:
        print(fmt.dim("无待处理操作" if not show_all else "无操作记录"))
        return

    title = "=== 待处理操作 ===" if not show_all else "=== 所有操作 ==="
    print(fmt.header(title))
    print()
    for row in rows:
        aid, atype, cmd, reason, verify, retry, status, creator, _created, resolved = row
        status_icon = {"pending": "⏳", "reminded": "🔔", "done": "✓", "retried": "✓✓", "failed": "✗"}.get(status, "?")
        color_fn = {
            "pending": fmt.yellow,
            "reminded": fmt.yellow,
            "done": fmt.green,
            "retried": fmt.green,
            "failed": fmt.red,
        }.get(status, fmt.dim)
        print(f"  {fmt.bold(f'#{aid}')} [{status_icon} {color_fn(status)}] ({atype}) by {fmt.sender_name(creator)}")
        print(f"    用户需执行: {fmt.bold(f'! {cmd}')}")
        print(f"    原因: {reason}")
        if verify:
            print(f"    验证命令: {fmt.dim(verify)}")
        if retry:
            print(f"    重试命令: {fmt.dim(retry)}")
        if resolved:
            print(f"    完成于: {fmt.dim(resolved)}")
        print()


def _command_output(result: subprocess.CompletedProcess[str]) -> str:
    stderr = result.stderr.strip() if isinstance(result.stderr, str) else ""
    stdout = result.stdout.strip() if isinstance(result.stdout, str) else ""
    return stderr or stdout or f"exit {result.returncode}"


def _run_command(command: str, timeout: int) -> tuple[bool, str | None]:
    try:
        result = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "超时"
    except (OSError, ValueError) as e:
        return False, f"出错: {e}"

    if result.returncode == 0:
        return True, None
    return False, _command_output(result)


def _run_retry_command(db: BoardDB, action_id: int, retry_cmd: str) -> bool:
    succeeded, detail = _run_command(retry_cmd, timeout=60)
    if succeeded:
        db.execute("UPDATE pending_actions SET status='retried' WHERE id=?", (action_id,))
        print(f"  #{action_id}: {fmt.green('重试成功 ✓')}")
        return True

    db.execute("UPDATE pending_actions SET status='failed' WHERE id=?", (action_id,))
    if detail == "超时":
        print(f"  #{action_id}: {fmt.red('重试超时')}")
    else:
        print(f"  #{action_id}: {fmt.red('重试失败')} — {detail}")
    return False


def _pending_verify(db: BoardDB, identity: str, args: list[str]) -> None:
    flags, positional = parse_flags(args, bool_flags={"retry": ["--retry"]})
    auto_retry = bool(flags.get("retry"))

    specific_id = None
    if positional:
        if len(positional) > 1:
            print("Usage: ./board --as <name> pending verify [#id] [--retry]")
            raise SystemExit(1)
        try:
            specific_id = int(positional[0].lstrip("#"))
        except ValueError:
            print("Usage: ./board --as <name> pending verify [#id] [--retry]")
            raise SystemExit(1)

    if specific_id:
        rows = db.query(
            "SELECT id, verify_command, command, retry_command FROM pending_actions "
            "WHERE id=? AND status IN ('pending', 'reminded')",
            (specific_id,),
        )
    else:
        rows = db.query(
            "SELECT id, verify_command, command, retry_command FROM pending_actions "
            "WHERE status IN ('pending', 'reminded') AND verify_command IS NOT NULL ORDER BY id"
        )

    if not rows:
        print(fmt.dim("无可验证的操作"))
        return

    verified = 0
    failed = 0
    retried = 0
    retry_failed = 0
    retry_skipped = 0
    for aid, verify_cmd, cmd, retry_cmd in rows:
        if not verify_cmd:
            print(f"  #{aid}: {fmt.dim('无验证命令')}")
            failed += 1
            continue

        succeeded, detail = _run_command(verify_cmd, timeout=30)
        if succeeded:
            now = ts()
            db.execute(
                "UPDATE pending_actions SET status='done', resolved_at=? WHERE id=?",
                (now, aid),
            )
            print(f"  #{aid}: {fmt.green('验证通过 ✓')}")
            verified += 1

            if auto_retry:
                if retry_cmd:
                    if _run_retry_command(db, aid, retry_cmd):
                        retried += 1
                    else:
                        retry_failed += 1
                else:
                    print(f"  #{aid}: {fmt.dim('无重试命令，跳过 retry')}")
                    retry_skipped += 1
        else:
            db.execute("UPDATE pending_actions SET status='reminded' WHERE id=?", (aid,))
            if detail == "超时":
                print(f"  #{aid}: {fmt.yellow('验证超时')}")
            else:
                print(f"  #{aid}: {fmt.red('验证失败')} — {detail}; 用户仍需执行: {fmt.bold(f'! {cmd}')}")
            failed += 1

    print(f"\n验证结果: {fmt.green(str(verified))} 通过, {fmt.red(str(failed))} 未通过")
    if auto_retry:
        print(
            f"重试结果: {fmt.green(str(retried))} 成功, {fmt.red(str(retry_failed))} 失败, {fmt.dim(str(retry_skipped))} 跳过"
        )


def _pending_retry(db: BoardDB, identity: str, args: list[str]) -> None:
    specific_id = None
    if args:
        try:
            specific_id = int(args[0].lstrip("#"))
        except ValueError:
            print("Usage: ./board --as <name> pending retry [#id]")
            raise SystemExit(1)

    if specific_id:
        rows = db.query(
            "SELECT id, retry_command FROM pending_actions WHERE id=? AND status IN ('done', 'failed')",
            (specific_id,),
        )
    else:
        rows = db.query(
            "SELECT id, retry_command FROM pending_actions "
            "WHERE status IN ('done', 'failed') AND retry_command IS NOT NULL ORDER BY id"
        )

    if not rows:
        print(fmt.dim("无可重试的操作（需先通过验证）"))
        return

    retried = 0
    failed = 0
    for aid, retry_cmd in rows:
        if not retry_cmd:
            print(f"  #{aid}: {fmt.dim('无重试命令')}")
            continue

        if _run_retry_command(db, aid, retry_cmd):
            retried += 1
        else:
            failed += 1

    print(f"\n重试结果: {fmt.green(str(retried))} 成功, {fmt.red(str(failed))} 失败")


def _pending_resolve(db: BoardDB, identity: str, args: list[str]) -> None:
    if not args:
        print("Usage: ./board --as <name> pending resolve <#id>")
        raise SystemExit(1)

    try:
        action_id = int(args[0].lstrip("#"))
    except ValueError:
        print("Usage: ./board --as <name> pending resolve <#id>")
        raise SystemExit(1)

    row = db.query_one("SELECT status FROM pending_actions WHERE id=?", (action_id,))
    if not row:
        print(fmt.err(f"pending #{action_id} 不存在"))
        raise SystemExit(1)

    if row[0] not in PENDING_STATUSES:
        print(f"pending #{action_id} 已是 {row[0]} 状态")
        return

    now = ts()
    db.execute(
        "UPDATE pending_actions SET status='done', resolved_at=? WHERE id=?",
        (now, action_id),
    )
    print(fmt.ok(f"pending #{action_id} 已手动标记为完成"))
