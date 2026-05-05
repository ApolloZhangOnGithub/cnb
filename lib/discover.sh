#!/usr/bin/env bash
# Shared: find .claudes/ in current or parent directories
_find_claudes_dir() {
    local dir="$PWD"
    while [ "$dir" != "/" ]; do
        if [ -d "$dir/.claudes" ]; then echo "$dir/.claudes"; return 0; fi
        dir="$(dirname "$dir")"
    done
    echo "ERROR: .claudes/ not found. Run: claudes-code init <session-names>" >&2
    return 1
}
CLAUDES_DIR="$(_find_claudes_dir)" || exit 1
PROJECT_ROOT="$(dirname "$CLAUDES_DIR")"
BOARD_DIR="$CLAUDES_DIR"
SESSIONS_DIR="$CLAUDES_DIR/sessions"
DB="$CLAUDES_DIR/board.db"
BOARD_DB="$DB"
[ -f "$CLAUDES_DIR/config.sh" ] && source "$CLAUDES_DIR/config.sh"
PREFIX="${PREFIX:-cc}"
