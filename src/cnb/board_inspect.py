"""board_inspect — privileged read-only session inspection."""

from lib.board_db import BoardDB
from lib.board_display import print_task_queue, print_unread_inbox
from lib.common import is_privileged, parse_flags, validate_identity


def _usage() -> None:
    print("Usage: ./board --as <lead|dispatcher> inspect {inbox|tasks} <session> [--done]")


def _target_for_inspection(db: BoardDB, identity: str, raw_target: str) -> str:
    validate_identity(db, identity)
    observer = identity.lower()
    target = raw_target.lower()
    validate_identity(db, target)
    if target != observer and not is_privileged(observer):
        print("ERROR: inspect requires lead or dispatcher to read another session")
        raise SystemExit(1)
    return target


def cmd_inspect(db: BoardDB, identity: str, args: list[str]) -> None:
    if len(args) < 2:
        _usage()
        raise SystemExit(1)

    subcmd = args[0].lower()
    target = _target_for_inspection(db, identity, args[1])
    rest = args[2:]

    if subcmd in ("inbox", "messages"):
        if rest:
            _usage()
            raise SystemExit(1)
        print_unread_inbox(db, target)
        return

    if subcmd in ("task", "tasks", "queue"):
        flags, positional = parse_flags(rest, bool_flags={"done": ["--done", "--include-done"]})
        if positional:
            _usage()
            raise SystemExit(1)
        print_task_queue(db, target, include_done=bool(flags.get("done")))
        return

    _usage()
    raise SystemExit(1)
