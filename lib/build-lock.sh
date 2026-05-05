#!/usr/bin/env bash
set -euo pipefail

# build-queue.sh — Serialize builds to prevent CPU saturation
# Only one session can build at a time. Others wait or skip.
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

LOCK_FILE="$BOARD_DIR/build.lock"
BOARD="$TOOLS_SWARM/board.sh"
MAX_WAIT=300  # seconds to wait before giving up

cmd="${1:-status}"
shift || true

case "$cmd" in
    acquire)
        session="${1:?Usage: build-queue.sh acquire <session> <target>}"
        target="${2:-unknown}"

        # Check if lock exists and is still valid
        if [ -f "$LOCK_FILE" ]; then
            holder=$(head -1 "$LOCK_FILE" | cut -d'|' -f1)
            locked_at=$(head -1 "$LOCK_FILE" | cut -d'|' -f2)
            lock_target=$(head -1 "$LOCK_FILE" | cut -d'|' -f3)

            # Stale lock detection: if locked > 10 minutes, force release
            now=$(date +%s)
            if [ -n "$locked_at" ] && [ $((now - locked_at)) -gt 600 ]; then
                echo "Stale lock from $holder (>10min), forcing release"
                rm -f "$LOCK_FILE"
            else
                echo "BUSY|$holder|$lock_target"
                exit 1
            fi
        fi

        # Acquire
        echo "${session}|$(date +%s)|${target}" > "$LOCK_FILE"
        echo "OK|${session}|${target}"
        ;;

    release)
        session="${1:?Usage: build-queue.sh release <session>}"

        if [ -f "$LOCK_FILE" ]; then
            holder=$(head -1 "$LOCK_FILE" | cut -d'|' -f1)
            if [ "$holder" = "$session" ]; then
                rm -f "$LOCK_FILE"
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
        if [ -f "$LOCK_FILE" ]; then
            holder=$(head -1 "$LOCK_FILE" | cut -d'|' -f1)
            locked_at=$(head -1 "$LOCK_FILE" | cut -d'|' -f2)
            lock_target=$(head -1 "$LOCK_FILE" | cut -d'|' -f3)
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
        while [ -f "$LOCK_FILE" ]; do
            holder=$(head -1 "$LOCK_FILE" | cut -d'|' -f1)
            locked_at=$(head -1 "$LOCK_FILE" | cut -d'|' -f2)
            now=$(date +%s)

            # Stale lock check
            if [ $((now - locked_at)) -gt 600 ]; then
                echo "[build-queue] Stale lock from $holder, forcing release"
                rm -f "$LOCK_FILE"
                break
            fi

            if [ $waited -ge $MAX_WAIT ]; then
                echo "[build-queue] Timeout waiting for lock (held by $holder)"
                exit 1
            fi

            if [ $((waited % 30)) -eq 0 ]; then
                echo "[build-queue] Waiting for $holder to finish building... (${waited}s)"
            fi
            sleep 5
            waited=$((waited + 5))
        done

        # Acquire lock
        echo "${session}|$(date +%s)|${target}" > "$LOCK_FILE"

        # Run command, release lock on exit (success or failure)
        trap 'rm -f "$LOCK_FILE"' EXIT
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
