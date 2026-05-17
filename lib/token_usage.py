"""token_usage — parse Claude Code JSONL logs for per-session token usage and cost estimation."""

import json
import time as _time
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# JSONLs older than this window are excluded from "live" runtime alerts. Full history
# (cmd_usage) ignores this filter.
DEFAULT_RECENT_HOURS = 6.0

# Synthetic placeholders Claude Code writes during compaction / internal flows. They are
# not real model assignments, so they should never count toward downgrade detection.
SYNTHETIC_MODELS = frozenset({"<synthetic>"})

_OPUS_PRICING = {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_create": 18.75}
_SONNET_PRICING = {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_create": 3.75}
_HAIKU_PRICING = {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_create": 1.0}

# Legacy 4-6 keys kept as aliases — historical JSONLs on disk reference them and
# would otherwise fall through to the default opus pricing (3-5x over-estimate
# for sonnet sessions).
PRICING = {
    "claude-opus-4-6": _OPUS_PRICING,
    "claude-opus-4-7": _OPUS_PRICING,
    "claude-sonnet-4-6": _SONNET_PRICING,
    "claude-sonnet-4-7": _SONNET_PRICING,
    "claude-haiku-4-5-20251001": _HAIKU_PRICING,
}

DEFAULT_PRICING = {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_create": 18.75}
DEFAULT_BUDGET_WARN_PCT = 80.0


def _project_slug(project_root: Path) -> str:
    return str(project_root).replace("/", "-").replace("_", "-")


def _find_project_dir(project_root: Path) -> Path | None:
    slug = _project_slug(project_root)
    d = CLAUDE_PROJECTS_DIR / slug
    return d if d.is_dir() else None


def _model_tier(model: str) -> int:
    lowered = model.lower()
    if "mini" in lowered or "haiku" in lowered:
        return 1
    if "opus" in lowered or "gpt-5.5" in lowered:
        return 3
    if "sonnet" in lowered or "gpt-5.4" in lowered or "gpt-5.3" in lowered:
        return 2
    return 0


def parse_session_usage(jsonl_path: Path) -> dict:
    name = ""
    model = ""
    latest_model = ""
    models: list[str] = []
    totals = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0, "messages": 0}

    for line in jsonl_path.open():
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        msg_type = d.get("type", "")
        if msg_type == "agent-name":
            name = d.get("agentName", "")
        elif msg_type == "custom-title":
            # JSONLs may identify their owner via either 'agent-name' or 'custom-title'.
            name = name or d.get("customTitle", "")
        elif msg_type == "assistant":
            msg = d.get("message", {})
            current_model = msg.get("model", "")
            if current_model in SYNTHETIC_MODELS:
                current_model = ""
            if not model:
                model = current_model
            if current_model:
                latest_model = current_model
                if not models or models[-1] != current_model:
                    models.append(current_model)
            usage = msg.get("usage", {})
            totals["input"] += usage.get("input_tokens", 0)
            totals["output"] += usage.get("output_tokens", 0)
            totals["cache_create"] += usage.get("cache_creation_input_tokens", 0)
            totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
            totals["messages"] += 1

    return {
        "name": name,
        "model": model,
        "latest_model": latest_model or model,
        "models": models,
        "session_id": jsonl_path.stem,
        **totals,
    }


def estimate_cost(usage: dict) -> float:
    prices = PRICING.get(usage.get("model", ""), DEFAULT_PRICING)
    cost = (
        usage["input"] * prices["input"]
        + usage["output"] * prices["output"]
        + usage["cache_read"] * prices["cache_read"]
        + usage["cache_create"] * prices["cache_create"]
    ) / 1_000_000
    return float(cost)


def aggregate_by_name(sessions: list[dict]) -> list[dict]:
    by_name: dict[str, dict] = defaultdict(
        lambda: {
            "name": "",
            "model": "",
            "latest_model": "",
            "models": [],
            "input": 0,
            "output": 0,
            "cache_create": 0,
            "cache_read": 0,
            "messages": 0,
        }
    )
    for s in sessions:
        key = s["name"] or s["session_id"][:8]
        agg = by_name[key]
        agg["name"] = key
        if not agg["model"]:
            agg["model"] = s["model"]
        if s.get("latest_model"):
            agg["latest_model"] = s["latest_model"]
        for model in s.get("models", []):
            if model not in agg["models"]:
                agg["models"].append(model)
        for field in ("input", "output", "cache_create", "cache_read", "messages"):
            agg[field] += s[field]
    return sorted(by_name.values(), key=lambda x: x["output"], reverse=True)


def model_state_alerts(sessions: list[dict]) -> list[str]:
    """Detect intra-family model downgrades (e.g. opus → sonnet).

    Cross-provider switches (claude → deepseek) are user-initiated via `cnb model use` and
    should not raise alerts. We require both first and latest models to be in known tiers
    (>0) before comparing.
    """
    alerts: list[str] = []
    for s in sessions:
        models = [model for model in s.get("models", []) if model]
        if len(models) < 2:
            continue
        first = models[0]
        latest = models[-1]
        first_tier = _model_tier(first)
        latest_tier = _model_tier(latest)
        if first_tier == 0 or latest_tier == 0:
            continue
        if latest_tier < first_tier:
            name = s.get("name") or str(s.get("session_id", ""))[:8]
            alerts.append(f"{name}: model downgraded {first} -> {latest}")
    return alerts


def _parse_usage_args(args: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {"detail": False, "budget": 0.0, "warn_pct": DEFAULT_BUDGET_WARN_PCT}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--detail", "-d"):
            parsed["detail"] = True
            i += 1
        elif arg in ("--budget", "--budget-usd") and i + 1 < len(args):
            parsed["budget"] = _float_arg(arg, args[i + 1])
            i += 2
        elif arg == "--warn-pct" and i + 1 < len(args):
            parsed["warn_pct"] = _float_arg(arg, args[i + 1])
            i += 2
        else:
            print(f"WARNING: unknown usage option ignored: {arg}")
            i += 1
    return parsed


def _float_arg(flag: str, value: str) -> float:
    try:
        return float(value)
    except ValueError:
        print(f"WARNING: {flag} expects a number, got {value!r}")
        return 0.0


def cmd_usage(project_root: Path, args: list[str]) -> None:
    parsed_args = _parse_usage_args(args)
    project_dir = _find_project_dir(project_root)
    if not project_dir:
        print(f"ERROR: 找不到项目 JSONL 目录: {CLAUDE_PROJECTS_DIR / _project_slug(project_root)}")
        raise SystemExit(1)

    sessions = _load_project_sessions(project_root, recent_hours=None)

    if not sessions:
        print("无 token 用量数据")
        return

    if parsed_args["detail"]:
        _print_detail(sessions)
    else:
        aggregated = aggregate_by_name(sessions)
        _print_summary(aggregated)
    _print_runtime_state(sessions, budget=float(parsed_args["budget"]), warn_pct=float(parsed_args["warn_pct"]))


def _print_summary(sessions: list[dict]) -> None:
    total = {"input": 0, "output": 0, "cache_create": 0, "cache_read": 0, "messages": 0, "cost": 0.0}

    print(f"{'同学':<12} {'消息':>6} {'当前模型':<22} {'输出 tokens':>12} {'输入 tokens':>12} {'费用估算':>10}")
    print("-" * 80)

    for s in sessions:
        cost = estimate_cost(s)
        total["input"] += s["input"]
        total["output"] += s["output"]
        total["cache_create"] += s["cache_create"]
        total["cache_read"] += s["cache_read"]
        total["messages"] += s["messages"]
        total["cost"] += cost

        model = s.get("latest_model") or s.get("model", "")
        print(f"{s['name']:<12} {s['messages']:>6} {model[:22]:<22} {s['output']:>12,} {s['input']:>12,} ${cost:>8.2f}")

    print("-" * 80)
    print(
        f"{'合计':<12} {total['messages']:>6} {'':<22} {total['output']:>12,} {total['input']:>12,} ${total['cost']:>8.2f}"
    )

    print(f"\n缓存命中: {total['cache_read']:,} tokens (节省 ${total['cache_read'] * 13.5 / 1_000_000:.2f})")


def _print_runtime_state(sessions: list[dict], *, budget: float, warn_pct: float) -> None:
    alerts = model_state_alerts(sessions)
    if alerts:
        print("\n模型状态:")
        for alert in alerts:
            print(f"WARNING: {alert}")
    if budget <= 0:
        return
    total_cost = sum(estimate_cost(s) for s in sessions)
    pct = (total_cost / budget) * 100 if budget else 0
    remaining = max(0.0, budget - total_cost)
    print(f"\n预算: ${budget:.2f}；已用 ${total_cost:.2f} ({pct:.1f}%)；剩余 ${remaining:.2f}")
    if pct >= warn_pct:
        print(f"WARNING: token budget usage {pct:.1f}% >= {warn_pct:.1f}% threshold")


def _load_project_sessions(project_root: Path, *, recent_hours: float | None = None) -> list[dict]:
    """Parse all session JSONLs. If `recent_hours` is set, skip files older than that window.

    Tradeoff on mtime: a long-running session whose JSONL hasn't been written to in
    `recent_hours` is excluded — its model state is treated as stale. This is the right
    default for live alerts (we want recent runtime signals) but cmd_usage opts into
    full history (`recent_hours=None`) for the historical breakdown.
    """
    project_dir = _find_project_dir(project_root)
    if not project_dir:
        return []
    cutoff = None
    if recent_hours is not None:
        cutoff = _time.time() - recent_hours * 3600
    sessions = []
    for jf in sorted(project_dir.glob("*.jsonl")):
        if cutoff is not None and jf.stat().st_mtime < cutoff:
            continue
        u = parse_session_usage(jf)
        if u["messages"] > 0:
            sessions.append(u)
    return sessions


def load_budget_defaults(claudes_dir: Path) -> tuple[float, float]:
    """Read [budget] from .cnb/config.toml. Returns (usd, warn_pct).

    Defaults: usd=0.0 (disabled), warn_pct=DEFAULT_BUDGET_WARN_PCT. Malformed values
    (typo'd strings like "50usd") fall back to defaults rather than raising — the
    runtime alert hook must never break a board call because of a config typo.
    """
    toml_file = claudes_dir / "config.toml"
    if not toml_file.exists():
        return 0.0, DEFAULT_BUDGET_WARN_PCT
    try:
        cfg = tomllib.loads(toml_file.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return 0.0, DEFAULT_BUDGET_WARN_PCT
    section = cfg.get("budget", {})
    try:
        usd = float(section.get("usd", 0) or 0)
    except (TypeError, ValueError):
        usd = 0.0
    try:
        warn_pct = float(section.get("warn_pct", DEFAULT_BUDGET_WARN_PCT))
    except (TypeError, ValueError):
        warn_pct = DEFAULT_BUDGET_WARN_PCT
    return usd, warn_pct


def collect_runtime_alerts(
    project_root: Path,
    *,
    budget: float = 0.0,
    warn_pct: float = DEFAULT_BUDGET_WARN_PCT,
    session_filter: str | None = None,
    recent_hours: float | None = DEFAULT_RECENT_HOURS,
) -> list[str]:
    """Return runtime alert strings (model downgrade + over-budget). Empty if all clear.

    `session_filter` restricts to a single tongxue name (case-insensitive); useful for
    per-session views where only the caller's own state should surface.
    `recent_hours` limits scanning to JSONLs touched within that window — the default
    keeps live commands snappy. Pass `None` for full history (cmd_usage).
    """
    sessions = _load_project_sessions(project_root, recent_hours=recent_hours)
    if session_filter:
        needle = session_filter.lower()
        sessions = [s for s in sessions if (s.get("name") or "").lower() == needle]
    if not sessions:
        return []

    aggregated = aggregate_by_name(sessions)
    alerts: list[str] = list(model_state_alerts(aggregated))

    if budget > 0:
        total_cost = sum(estimate_cost(s) for s in sessions)
        pct = (total_cost / budget) * 100
        if pct >= warn_pct:
            alerts.append(
                f"token budget usage {pct:.1f}% >= {warn_pct:.1f}% threshold (${total_cost:.2f} / ${budget:.2f})"
            )
    return alerts


def cmd_board_usage(db: Any, args: list[str]) -> None:
    """Board command adapter — dispatch to cmd_usage with config-default budget."""
    assert db.env is not None
    if not any(a in ("--budget", "--budget-usd") for a in args):
        budget, warn_pct = load_budget_defaults(db.env.claudes_dir)
        if budget > 0:
            args = [*args, "--budget", str(budget), "--warn-pct", str(warn_pct)]
    cmd_usage(db.env.project_root, args)


def _print_detail(sessions: list[dict]) -> None:
    print(
        f"{'Session':<12} {'Name':<10} {'Model':<22} {'Msgs':>6} {'Output':>10} {'Input':>10} {'CacheRd':>12} {'CacheWr':>12} {'Cost':>8}"
    )
    print("-" * 108)

    total_cost = 0.0
    for s in sessions:
        cost = estimate_cost(s)
        total_cost += cost
        name = s["name"] or s["session_id"][:8]
        print(
            f"{s['session_id'][:12]:<12} {name:<10} {(s.get('latest_model') or s.get('model', ''))[:22]:<22} "
            f"{s['messages']:>6} "
            f"{s['output']:>10,} {s['input']:>10,} {s['cache_read']:>12,} {s['cache_create']:>12,} ${cost:>7.2f}"
        )

    print("-" * 108)
    print(f"{'':>78} 总计: ${total_cost:.2f}")
