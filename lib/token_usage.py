"""token_usage — parse Claude Code JSONL logs for per-session token usage and cost estimation."""

import json
from collections import defaultdict
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

PRICING = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_create": 18.75},
    "claude-opus-4-7": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_create": 18.75},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_create": 3.75},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_create": 1.0},
}

DEFAULT_PRICING = {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_create": 18.75}


def _project_slug(project_root: Path) -> str:
    return str(project_root).replace("/", "-").replace("_", "-")


def _find_project_dir(project_root: Path) -> Path | None:
    slug = _project_slug(project_root)
    d = CLAUDE_PROJECTS_DIR / slug
    return d if d.is_dir() else None


def parse_session_usage(jsonl_path: Path) -> dict:
    name = ""
    model = ""
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0, "messages": 0}

    for line in jsonl_path.open():
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        msg_type = d.get("type", "")
        if msg_type == "agent-name":
            name = d.get("agentName", "")
        elif msg_type == "assistant":
            msg = d.get("message", {})
            if not model:
                model = msg.get("model", "")
            usage = msg.get("usage", {})
            totals["input"] += usage.get("input_tokens", 0)
            totals["output"] += usage.get("output_tokens", 0)
            totals["cache_create"] += usage.get("cache_creation_input_tokens", 0)
            totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
            totals["messages"] += 1

    return {"name": name, "model": model, "session_id": jsonl_path.stem, **totals}


def estimate_cost(usage: dict) -> float:
    prices = PRICING.get(usage.get("model", ""), DEFAULT_PRICING)
    cost = (
        usage["input"] * prices["input"]
        + usage["output"] * prices["output"]
        + usage["cache_read"] * prices["cache_read"]
        + usage["cache_create"] * prices["cache_create"]
    ) / 1_000_000
    return cost


def aggregate_by_name(sessions: list[dict]) -> list[dict]:
    by_name: dict[str, dict] = defaultdict(
        lambda: {"name": "", "model": "", "input": 0, "output": 0, "cache_create": 0, "cache_read": 0, "messages": 0}
    )
    for s in sessions:
        key = s["name"] or s["session_id"][:8]
        agg = by_name[key]
        agg["name"] = key
        if not agg["model"]:
            agg["model"] = s["model"]
        for field in ("input", "output", "cache_create", "cache_read", "messages"):
            agg[field] += s[field]
    return sorted(by_name.values(), key=lambda x: x["output"], reverse=True)


def cmd_usage(project_root: Path, args: list[str]) -> None:
    project_dir = _find_project_dir(project_root)
    if not project_dir:
        print(f"ERROR: 找不到项目 JSONL 目录: {CLAUDE_PROJECTS_DIR / _project_slug(project_root)}")
        raise SystemExit(1)

    sessions = []
    for jf in sorted(project_dir.glob("*.jsonl")):
        usage = parse_session_usage(jf)
        if usage["messages"] > 0:
            sessions.append(usage)

    if not sessions:
        print("无 token 用量数据")
        return

    show_detail = "--detail" in args or "-d" in args

    if show_detail:
        _print_detail(sessions)
    else:
        aggregated = aggregate_by_name(sessions)
        _print_summary(aggregated)


def _print_summary(sessions: list[dict]) -> None:
    total = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0, "messages": 0, "cost": 0.0}

    print(f"{'同学':<12} {'消息':>6} {'输出 tokens':>12} {'输入 tokens':>12} {'费用估算':>10}")
    print("-" * 56)

    for s in sessions:
        cost = estimate_cost(s)
        total["input"] += s["input"]
        total["output"] += s["output"]
        total["cache_create"] += s["cache_create"]
        total["cache_read"] += s["cache_read"]
        total["messages"] += s["messages"]
        total["cost"] += cost

        print(f"{s['name']:<12} {s['messages']:>6} {s['output']:>12,} {s['input']:>12,} ${cost:>8.2f}")

    print("-" * 56)
    print(f"{'合计':<12} {total['messages']:>6} {total['output']:>12,} {total['input']:>12,} ${total['cost']:>8.2f}")

    print(f"\n缓存命中: {total['cache_read']:,} tokens (节省 ${total['cache_read'] * 13.5 / 1_000_000:.2f})")


def _print_detail(sessions: list[dict]) -> None:
    print(
        f"{'Session':<12} {'Name':<10} {'Msgs':>6} {'Output':>10} {'Input':>10} {'CacheRd':>12} {'CacheWr':>12} {'Cost':>8}"
    )
    print("-" * 84)

    total_cost = 0.0
    for s in sessions:
        cost = estimate_cost(s)
        total_cost += cost
        name = s["name"] or s["session_id"][:8]
        print(
            f"{s['session_id'][:12]:<12} {name:<10} {s['messages']:>6} "
            f"{s['output']:>10,} {s['input']:>10,} {s['cache_read']:>12,} {s['cache_create']:>12,} ${cost:>7.2f}"
        )

    print("-" * 84)
    print(f"{'':>54} 总计: ${total_cost:.2f}")
