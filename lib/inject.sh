#!/usr/bin/env bash
set -euo pipefail

# say.sh — Force-inject a message into another Claude Code session
# Auto-detects tmux or screen. Override with SWARM_MODE=tmux|screen.

_PATHS_LOADED="${_PATHS_LOADED:-}"
# sessions loaded from config
PREFIX="cc"

if [ $# -lt 2 ]; then
    cat <<'EOF'
Usage: ./say.sh <target> <message>

  target: session name (<session-name>) or 'all'

Examples:
  ./inject.sh alice "what's blocking P0?"
  ./say.sh all "everyone check inbox"
EOF
    exit 1
fi

TARGET="$1"; shift
MSG="$*"

# Auto-detect mode
detect_mode() {
    if [ -n "${SWARM_MODE:-}" ]; then echo "$SWARM_MODE"; return; fi
    # Check if any tmux sessions exist with our prefix
    if tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -q "^${PREFIX}-"; then
        echo "tmux"; return
    fi
    # Check if any screen sessions exist with our prefix
    if (screen -list 2>/dev/null || true) | grep -q "\.${PREFIX}-"; then
        echo "screen"; return
    fi
    # Default to tmux if available
    if command -v tmux &>/dev/null; then echo "tmux"
    elif command -v screen &>/dev/null; then echo "screen"
    else echo "none"; fi
}

MODE=$(detect_mode)

send_tmux() {
    local name="$1" message="$2"
    local sess="${PREFIX}-${name}"
    if ! tmux has-session -t "$sess" 2>/dev/null; then
        echo "  $name: not running"
        return 1
    fi
    local oneline; oneline=$(echo "$message" | tr '\n' ' ')
    tmux send-keys -t "$sess" -l "$oneline"
    tmux send-keys -t "$sess" Enter
    echo "  $name: injected (tmux)"
}

send_screen() {
    local name="$1" message="$2"
    local sess="${PREFIX}-${name}"
    if ! (screen -list 2>/dev/null || true) | grep -q "\.${sess}[[:space:]]"; then
        echo "  $name: not running"
        return 1
    fi
    local oneline; oneline=$(echo "$message" | tr '\n' ' ')
    screen -S "$sess" -p 0 -X stuff "$oneline"
    sleep 0.3
    screen -S "$sess" -p 0 -X stuff "$(printf '\015')"
    echo "  $name: injected (screen)"
}

if [ "$MODE" = "none" ]; then
    echo "ERROR: neither tmux nor screen found" >&2; exit 1
fi

TARGET_LOWER=$(echo "$TARGET" | tr '[:upper:]' '[:lower:]')

if [ "$TARGET_LOWER" = "all" ]; then
    echo "Injecting to all ($MODE):"
    for name in "${SESSIONS[@]}"; do
        send_${MODE} "$name" "$MSG" || true
    done
else
    send_${MODE} "$TARGET_LOWER" "$MSG"
fi
