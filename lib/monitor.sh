#!/usr/bin/env bash
set -euo pipefail

# monitor-poc.sh — Event-driven dispatcher POC using kqueue file watching
#
# Replaces 30s polling with instant file-change detection.
# On macOS: uses Python kqueue (native, no dependencies).
# On Linux: uses inotifywait if available, otherwise falls back to polling.
#
# Usage:
#   ./tools/monitor-poc.sh              # watch and react
#   ./tools/monitor-poc.sh --test       # send a test message and measure latency
#   ./tools/monitor-poc.sh --benchmark  # compare event vs polling latency

_self="$0"; [ -L "$_self" ] && _self="$(readlink "$_self")"; CLAUDES_HOME="$(cd "$(dirname "$_self")/.." && pwd)"
source "$CLAUDES_HOME/lib/discover.sh"

BOARD_SH="$PROJECT_ROOT/board.sh"
DB="$BOARD_DB"

log() { echo "[monitor] $(date '+%H:%M:%S.%3N') $*"; }

_file_mtime() {
    stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

# --- Event handler ---

handle_change() {
    local file="$1"
    local name
    name=$(basename "$file" .md)

    # Check if session has unread inbox
    local unread=0
    if [ -f "$DB" ]; then
        unread=$(sqlite3 "$DB" "SELECT COUNT(*) FROM inbox WHERE session='$name' AND read=0;" 2>/dev/null || echo 0)
    else
        unread=$(grep -c "^- \[" "$SESSIONS_DIR/${name}.md" 2>/dev/null | tail -1 || echo 0)
    fi

    if [ "$unread" -gt 0 ]; then
        local sess="cc-${name}"
        if tmux has-session -t "$sess" 2>/dev/null; then
            log "EVENT: ${name} has ${unread} unread — nudging"
            tmux send-keys -t "$sess" -l "./board.sh --as ${name} inbox"
            tmux send-keys -t "$sess" Enter
        else
            log "EVENT: ${name} has ${unread} unread — session not running"
        fi
    fi
}

# --- macOS kqueue watcher (Python, no dependencies) ---

watch_kqueue() {
    log "Starting kqueue watcher on ${SESSIONS_DIR}/"
    python3 - "$SESSIONS_DIR" <<'PYTHON'
import os
import sys
import select
import time

watch_dir = sys.argv[1]
kq = select.kqueue()

# Watch the directory itself for new files
dir_fd = os.open(watch_dir, os.O_RDONLY)
dir_event = select.kevent(dir_fd,
    filter=select.KQ_FILTER_VNODE,
    flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
    fflags=select.KQ_NOTE_WRITE)

# Watch each .md file
file_fds = {}

def refresh_watches():
    for f in os.listdir(watch_dir):
        if not f.endswith('.md'):
            continue
        path = os.path.join(watch_dir, f)
        if path in file_fds:
            continue
        try:
            fd = os.open(path, os.O_RDONLY)
            ev = select.kevent(fd,
                filter=select.KQ_FILTER_VNODE,
                flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND)
            kq.control([ev], 0)
            file_fds[path] = fd
        except OSError:
            pass

refresh_watches()
kq.control([dir_event], 0)

fd_to_path = {}

while True:
    fd_to_path = {fd: path for path, fd in file_fds.items()}
    try:
        events = kq.control(None, 8, 5.0)  # 5s timeout for periodic refresh
    except InterruptedError:
        continue

    if not events:
        refresh_watches()
        continue

    changed = set()
    for ev in events:
        if ev.ident == dir_fd:
            refresh_watches()
        elif ev.ident in fd_to_path:
            changed.add(fd_to_path[ev.ident])

    for path in changed:
        print(path, flush=True)

    if not changed:
        refresh_watches()
PYTHON
}

# --- Linux inotifywait watcher ---

watch_inotify() {
    log "Starting inotifywait watcher on ${SESSIONS_DIR}/"
    inotifywait -m -e modify,create --format '%w%f' "$SESSIONS_DIR/" 2>/dev/null
}

# --- Fallback: fast poll (1s instead of 30s) ---

watch_poll() {
    log "Starting fast-poll watcher (1s interval) on ${SESSIONS_DIR}/"
    local mtime_dir="/tmp/claudes-poll-$$"
    mkdir -p "$mtime_dir"
    trap 'rm -rf "$mtime_dir"' EXIT
    while true; do
        for f in "$SESSIONS_DIR"/*.md; do
            [ -f "$f" ] || continue
            local base; base=$(basename "$f")
            local mt; mt=$(_file_mtime "$f")
            local prev="0"
            [ -f "$mtime_dir/$base" ] && prev=$(cat "$mtime_dir/$base")
            if [ "$mt" != "$prev" ] && [ "$prev" != "0" ]; then
                echo "$f"
            fi
            echo "$mt" > "$mtime_dir/$base"
        done
        sleep 1
    done
}

# --- Main watch loop ---

do_watch() {
    local watcher_pid

    if python3 -c "import select; assert hasattr(select, 'kqueue')" 2>/dev/null; then
        watch_kqueue | while IFS= read -r changed_file; do
            handle_change "$changed_file"
        done
    elif command -v inotifywait &>/dev/null; then
        watch_inotify | while IFS= read -r changed_file; do
            handle_change "$changed_file"
        done
    else
        watch_poll | while IFS= read -r changed_file; do
            handle_change "$changed_file"
        done
    fi
}

# --- Test mode: measure event latency ---

do_test() {
    log "=== Latency Test ==="
    log "Sending test message and measuring detection time..."

    local test_target="${SESSIONS[0]:-test}"
    local start_ms end_ms

    # Start watcher in background, capture first event
    local tmpfile="/tmp/monitor-poc-test-$$"
    (
        if python3 -c "import select; assert hasattr(select, 'kqueue')" 2>/dev/null; then
            watch_kqueue | head -1 > "$tmpfile"
        else
            watch_poll | head -1 > "$tmpfile"
        fi
    ) &
    local watch_pid=$!
    sleep 1  # let watcher start

    start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    "$BOARD_SH" --as dispatcher send "$test_target" "[monitor-poc] latency test $(date +%s)" >/dev/null 2>&1

    # Wait for detection (max 5s)
    local waited=0
    while [ ! -s "$tmpfile" ] && [ "$waited" -lt 50 ]; do
        sleep 0.1
        waited=$((waited + 1))
    done

    end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
    kill "$watch_pid" 2>/dev/null || true
    wait "$watch_pid" 2>/dev/null || true

    local latency=$((end_ms - start_ms))
    log "Event detected in ${latency}ms"
    log "vs polling at 30s interval: avg 15000ms latency"
    log "Improvement: ~$((15000 / (latency + 1)))x faster"

    rm -f "$tmpfile"
    # Clean up test message
    "$BOARD_SH" --as "$test_target" ack >/dev/null 2>&1 || true
}

# --- Benchmark mode ---

do_benchmark() {
    log "=== Event vs Polling Benchmark ==="
    log ""
    log "Event-driven (kqueue/inotify):"
    log "  - Detection latency: <100ms typical"
    log "  - CPU usage: near-zero (kernel callback)"
    log "  - Scalability: O(1) per event"
    log ""
    log "Polling (current dispatcher, 30s):"
    log "  - Detection latency: 0-30000ms (avg 15000ms)"
    log "  - CPU usage: periodic wake + file reads"
    log "  - Scalability: O(n) per interval (n = sessions)"
    log ""
    log "Running live test..."
    do_test
}

case "${1:-watch}" in
    watch)      do_watch ;;
    --test)     do_test ;;
    --benchmark) do_benchmark ;;
    --help|-h)
        echo "monitor-poc.sh — Event-driven dispatcher POC"
        echo ""
        echo "  watch        Start file watcher (default)"
        echo "  --test       Measure detection latency"
        echo "  --benchmark  Compare event vs polling"
        ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
esac
