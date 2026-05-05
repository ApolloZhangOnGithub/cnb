#!/usr/bin/env bash
set -euo pipefail

# build-queue.sh — Serialize builds to prevent CPU saturation
# Only one session can build at a time. Others wait or skip.
#
# Uses mkdir-based locking for atomicity: mkdir is atomic on all POSIX
# systems, so two concurrent callers cannot both succeed. Metadata
# (session, timestamp, target) is stored inside the lock directory.
#
# Usage:
#   ./build-queue.sh acquire <session> <target>  # Try to get build lock
#   ./build-queue.sh release <session>            # Release build lock
#   ./build-queue.sh status                       # Show current lock holder
#   ./build-queue.sh wrap <session> <command...>  # Run command under lock
#
# Integration example (in session scripts):
#   ./tools/build-queue.sh wrap <session> <build-cmd>
#   # Automatically acquires lock, runs build, releases on exit

LOCK_DIR="$BOARD_DIR/build.lock.d"
LOCK_INFO="$LOCK_DIR/info"
BOARD="$TOOLS_SWARM/board.sh"
MAX_WAIT=300  # seconds to wait before giving up

# read_lock_info — parse the info file inside the lock directory
# Sets: holder, locked_at, lock_target
read_lock_info() {
    if [ -f "$LOCK_INFO" ]; then
        holder=$(head -1 "$LOCK_INFO" | cut -d'|' -f1)
        locked_at=$(head -1 "$LOCK_INFO" | cut -d'|' -f2)
        lock_target=$(head -1 "$LOCK_INFO" | cut -d'|' -f3)
    else
        holder="unknown"
        locked_at="0"
        lock_target="unknown"
    fi
}

# force_release_stale — remove a stale lock if older than 10 minutes
# Returns 0 if the lock was stale and removed, 1 otherwise
force_release_stale() {
    read_lock_info
    now=$(date +%s)
    if [ -n "$locked_at" ] && [ "$locked_at" -gt 0 ] && [ $((now - locked_at)) -gt 600 ]; then
        echo "Stale lock from $holder (>10min), forcing release"
        rm -rf "$LOCK_DIR"
        return 0
    fi
    return 1
}

cmd="${1:-status}"
shift || true

case "$cmd" in
    acquire)
        session="${1:?Usage: build-queue.sh acquire <session> <target>}"
        target="${2:-unknown}"

        # Atomic lock acquisition via mkdir
        if ! mkdir "$LOCK_DIR" 2>/dev/null; then
            # Lock directory already exists — check for staleness
            if force_release_stale; then
                # Stale lock was removed, retry the mkdir
                if ! mkdir "$LOCK_DIR" 2>/dev/null; then
                    # Another session grabbed it between our rm and mkdir
                    read_lock_info
                    echo "BUSY|$holder|$lock_target"
                    exit 1
                fi
            else
                read_lock_info
                echo "BUSY|$holder|$lock_target"
                exit 1
            fi
        fi

        # Write metadata into the lock directory
        echo "${session}|$(date +%s)|${target}" > "$LOCK_INFO"
        echo "OK|${session}|${target}"
        ;;

    release)
        session="${1:?Usage: build-queue.sh release <session>}"

        if [ -d "$LOCK_DIR" ]; then
            read_lock_info
            if [ "$holder" = "$session" ]; then
                rm -rf "$LOCK_DIR"
                echo "OK released"
            else
                echo "ERR: lock held by $holder, not $session"
                exit 1
            fi
        else
            echo "OK (no lock)"
        fi
        ;;

    status)
        if [ -d "$LOCK_DIR" ]; then
            read_lock_info
            now=$(date +%s)
            elapsed=$((now - locked_at))
            echo "LOCKED by $holder ($lock_target) for ${elapsed}s"
        else
            echo "FREE"
        fi
        ;;

    wrap)
        session="${1:?Usage: build-queue.sh wrap <session> <command...>}"
        shift
        [ $# -eq 0 ] && { echo "Usage: build-queue.sh wrap <session> <command...>"; exit 1; }
        target="$1"

        # Wait for lock
        waited=0
        while ! mkdir "$LOCK_DIR" 2>/dev/null; do
            # Lock exists — check for staleness
            if [ -d "$LOCK_DIR" ]; then
                read_lock_info
                now=$(date +%s)

                # Stale lock check
                if [ "$locked_at" -gt 0 ] && [ $((now - locked_at)) -gt 600 ]; then
                    echo "[build-queue] Stale lock from $holder, forcing release"
                    rm -rf "$LOCK_DIR"
                    continue  # retry mkdir at top of loop
                fi

                if [ $waited -ge $MAX_WAIT ]; then
                    echo "[build-queue] Timeout waiting for lock (held by $holder)"
                    exit 1
                fi

                if [ $((waited % 30)) -eq 0 ]; then
                    echo "[build-queue] Waiting for $holder to finish building... (${waited}s)"
                fi
            fi

            sleep 5
            waited=$((waited + 5))
        done

        # We hold the lock directory — write metadata
        echo "${session}|$(date +%s)|${target}" > "$LOCK_INFO"

        # Release lock on exit (success or failure)
        trap 'rm -rf "$LOCK_DIR"' EXIT
        echo "[build-queue] $session acquired lock, running: $*"
        "$@"
        exit_code=$?
        echo "[build-queue] Build finished (exit $exit_code)"
        exit $exit_code
        ;;

    *)
        echo "Usage: build-queue.sh {acquire|release|status|wrap} [args...]"
        exit 1
        ;;
esac
