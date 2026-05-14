"""board_daily — generate and save daily report with verified timestamps."""

from datetime import datetime

from lib.board_db import BoardDB
from lib.common import validate_identity
from lib.shift_report import generate_agent_report, next_shift_number


def cmd_daily(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
    name = identity.lower()

    env = db.require_env()
    dailies_dir = env.claudes_dir / "dailies"
    dailies_dir.mkdir(exist_ok=True)

    shift_number = next_shift_number(dailies_dir)
    existing = [d.name for d in dailies_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    if existing:
        current_shift = max(int(d) for d in existing)
    else:
        current_shift = shift_number

    shift_dir = dailies_dir / f"{current_shift:03d}"
    shift_dir.mkdir(parents=True, exist_ok=True)

    report_path = shift_dir / f"{name}.md"

    now = datetime.now()
    report = generate_agent_report(db, name, project_root=env.project_root)

    extra = ""
    if args:
        extra = "\n\n## 补充\n" + " ".join(args)

    content = report + extra + "\n"

    report_path.write_text(content)
    print(f"OK 日报已保存: {report_path}")
    print(f"   时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   如需补充内容，直接编辑 {report_path}")
