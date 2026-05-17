"""hint_detector — phase 2 of proactive association (#158).

Design: docs/dev/design-proactive-association.md.

When a tongxue B sends a message that overlaps with tongxue A's prior outbox,
emit a hint *from A to B* surfacing A's prior thread. Detection runs after the
message commit (post-send hook in `cmd_send`) and is non-blocking — a slow or
failing detector must not break message delivery.

Scope per design + lead's clarification: hints are sender↔recipient only —
A must have messaged B before (or B before A) for A's context to be eligible.
Cross-tongxue sourcing (A surfaces hints based on C's prior thread with B) is
deferred to a later phase.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from lib.board_db import BoardDB
from lib.board_hint import emit_hint

# ── Signal weights (see design doc table) ────────────────────────────────────
WEIGHT_ISSUE_REF = 0.5
WEIGHT_PATH_OVERLAP = 0.3
WEIGHT_KEYWORD_OVERLAP = 0.2

# Recency half-life in hours. A reference 24h old contributes half its weight.
RECENCY_HALF_LIFE_HOURS = 24.0

# Detection window — only look back this many hours when scanning sender outboxes.
DEFAULT_LOOKBACK_HOURS = 48.0

# Minimum keyword-overlap ratio to count the keyword signal.
KEYWORD_OVERLAP_MIN = 0.2

# Stopwords for keyword extraction — small English + Chinese set; the v1 detector
# is intentionally cheap. v2 (learned) replaces this with a model.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "with",
    "and",
    "or",
    "but",
    "not",
    "if",
    "this",
    "that",
    "it",
    "you",
    "i",
    "we",
    "they",
    "he",
    "she",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "will",
    "would",
    "could",
    "should",
    "can",
    "may",
    "might",
    "what",
    "which",
    "who",
    "when",
    "where",
    "why",
    "how",
    "from",
    "as",
    "by",
    "so",
    "all",
    "any",
    "some",
    "no",
    "yes",
    "ok",
    "now",
    "just",
    "more",
    "也",
    "和",
    "的",
    "了",
    "是",
    "在",
    "我",
    "你",
    "他",
    "她",
    "我们",
    "你们",
    "什么",
    "怎么",
    "为什么",
    "不",
    "没",
    "有",
    "这",
    "那",
    "这个",
    "那个",
}

_ISSUE_RE = re.compile(r"#(\d+)\b")
_PATH_RE = re.compile(r"\b([\w\-]+(?:/[\w\-.]+)+\.\w+)\b")  # e.g. lib/foo.py, docs/dev/x.md
_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def extract_issue_refs(text: str) -> set[int]:
    """Find numeric references like `#42`, `PR #221`, `issue #1234`."""
    return {int(m.group(1)) for m in _ISSUE_RE.finditer(text)}


def extract_paths(text: str) -> set[str]:
    """Find file/path tokens like `lib/foo.py`, `docs/dev/x.md`."""
    return set(_PATH_RE.findall(text))


def extract_keywords(text: str) -> set[str]:
    """Lowercase, tokenize, drop short tokens + stopwords."""
    tokens = {t.lower() for t in _WORD_RE.findall(text)}
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def recency_multiplier(message_ts: str, now: datetime) -> float:
    """Exponential decay — half life of `RECENCY_HALF_LIFE_HOURS`.

    Older messages contribute less. Future / unparseable timestamps return 1.0
    (treat as 'now' — don't drop a signal because of a clock skew).
    """
    try:
        msg_dt = datetime.strptime(message_ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            msg_dt = datetime.strptime(message_ts, "%Y-%m-%d %H:%M")
        except ValueError:
            return 1.0
    age_hours = max(0.0, (now - msg_dt).total_seconds() / 3600.0)
    return 0.5 ** (age_hours / RECENCY_HALF_LIFE_HOURS)


def compute_signals(
    prior_text: str,
    incoming_text: str,
    prior_ts: str,
    now: datetime,
) -> dict[str, float]:
    """Compute per-signal weights for a single prior message against an incoming one.

    Returns a dict of `{signal_name: weight}` — weights already multiplied by the
    recency factor. Empty dict if nothing fires.
    """
    multiplier = recency_multiplier(prior_ts, now)
    if multiplier <= 0:
        return {}

    out: dict[str, float] = {}

    issue_overlap = extract_issue_refs(prior_text) & extract_issue_refs(incoming_text)
    if issue_overlap:
        out["issue_ref"] = WEIGHT_ISSUE_REF * multiplier

    path_overlap = extract_paths(prior_text) & extract_paths(incoming_text)
    if path_overlap:
        out["path_overlap"] = WEIGHT_PATH_OVERLAP * multiplier

    kw_prior = extract_keywords(prior_text)
    kw_incoming = extract_keywords(incoming_text)
    if kw_prior and kw_incoming:
        shared = kw_prior & kw_incoming
        denom = min(len(kw_prior), len(kw_incoming))
        ratio = len(shared) / denom if denom else 0
        if ratio >= KEYWORD_OVERLAP_MIN:
            out["keyword_overlap"] = WEIGHT_KEYWORD_OVERLAP * multiplier

    return out


def compute_confidence(signals: dict[str, float]) -> float:
    """Sum signal weights, cap at 1.0."""
    return min(1.0, sum(signals.values()))


def _eligible_senders(db: BoardDB, recipient: str) -> set[str]:
    """Tongxue who have messaged the recipient before (sender↔recipient only)."""
    rows = db.query(
        "SELECT DISTINCT sender FROM messages WHERE recipient=? AND sender != ?",
        (recipient, recipient),
    )
    return {r[0] for r in rows}


def _shared_refs(prior_text: str, incoming_text: str) -> dict[str, list]:
    """Extract the overlapping refs (used for both topic-mute check and hint body)."""
    return {
        "issues": sorted(extract_issue_refs(prior_text) & extract_issue_refs(incoming_text)),
        "paths": sorted(extract_paths(prior_text) & extract_paths(incoming_text)),
    }


def _candidate_body(sender: str, refs: dict, prior_ts: str) -> str:
    """Compose the short human-readable hint body."""
    parts = []
    if refs.get("issues"):
        parts.append("issue #" + ", #".join(str(i) for i in refs["issues"]))
    if refs.get("paths"):
        parts.append(refs["paths"][0])
    if not parts:
        parts.append("先前讨论")
    return f"你提到的 {' / '.join(parts)} 跟 {sender} {prior_ts} 的对话相关。"


def detect_hints(
    db: BoardDB,
    recipient: str,
    incoming_text: str,
    *,
    now: datetime | None = None,
    lookback_hours: float = DEFAULT_LOOKBACK_HOURS,
) -> list[dict[str, Any]]:
    """Scan eligible senders' recent outbox for overlap with incoming_text.

    Returns a list of candidate hint dicts. The caller (`run_for_message`) is
    responsible for calling `emit_hint` for each. Returning structured data
    instead of side-effects keeps the function easy to unit-test.
    """
    if now is None:
        now = datetime.now()
    cutoff = (now - timedelta(hours=lookback_hours)).strftime("%Y-%m-%d %H:%M:%S")

    senders = _eligible_senders(db, recipient)
    if not senders:
        return []

    candidates: list[dict[str, Any]] = []
    for sender in sorted(senders):
        rows = db.query(
            "SELECT body, ts FROM messages WHERE sender=? AND ts > ? ORDER BY id DESC LIMIT 50",
            (sender, cutoff),
        )
        if not rows:
            continue

        # Pick the strongest prior message per sender — emit at most one hint per
        # sender to avoid flooding even before the rate cap kicks in.
        best: tuple[float, dict, dict, str, str] | None = None
        for body, prior_ts in rows:
            signals = compute_signals(body, incoming_text, prior_ts, now)
            if not signals:
                continue
            conf = compute_confidence(signals)
            if best is None or conf > best[0]:
                best = (conf, signals, _shared_refs(body, incoming_text), prior_ts, body)
        if best is None:
            continue

        conf, signals, refs, prior_ts, _prior_body = best
        candidates.append(
            {
                "sender": sender,
                "recipient": recipient,
                "body": _candidate_body(sender, refs, prior_ts),
                "signals": signals,
                "confidence": conf,
                "refs": refs,
            }
        )
    return candidates


def run_for_message(
    db: BoardDB,
    recipient: str,
    incoming_text: str,
    *,
    now: datetime | None = None,
) -> list[int]:
    """Run detection + emit hints. Returns the list of emitted hint ids.

    Designed to be called post-commit from `cmd_send`. Broad-except wrapped so
    a detector failure cannot break message delivery.
    """
    try:
        candidates = detect_hints(db, recipient, incoming_text, now=now)
    except Exception:
        return []

    emitted: list[int] = []
    for c in candidates:
        try:
            hint_id = emit_hint(
                db,
                c["sender"],
                c["recipient"],
                c["body"],
                confidence=c["confidence"],
                signals=c["signals"],
                refs=c["refs"],
            )
            emitted.append(hint_id)
        except Exception:
            # One bad emit doesn't sink the rest.
            continue
    return emitted
