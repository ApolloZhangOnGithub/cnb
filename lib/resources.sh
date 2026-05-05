#!/usr/bin/env bash
set -euo pipefail

# resource-monitor.sh — Unified resource monitoring (battery + memory + CPU)
# Detects anomalies and notifies via board.sh.
#
# Usage:
#   ./resource-monitor.sh              # One-shot status check
#   ./resource-monitor.sh --watch      # Continuous monitoring (30s interval)
#   ./resource-monitor.sh --json       # Machine-readable output

_self="$0"; [ -L "$_self" ] && _self="$(readlink "$_self")"; CLAUDES_HOME="$(cd "$(dirname "$_self")/.." && pwd)"
[ -z "${CLAUDES_DIR:-}" ] && source "$CLAUDES_HOME/lib/discover.sh"

BOARD="${PROJECT_ROOT:-$(pwd)}/board"
STATE_FILE="${CLAUDES_DIR:-/tmp}/resource-monitor-state"

# Thresholds
BATTERY_LOW=30
BATTERY_CRITICAL=15
MEMORY_WARN_PCT=80
CPU_SATURATED=90
CPU_SUSTAIN_CHECKS=2  # consecutive checks at saturation before alert

MODE="status"
while [ $# -gt 0 ]; do
    case "$1" in
        --watch) MODE="watch"; shift ;;
        --json) MODE="json"; shift ;;
        *) shift ;;
    esac
done

# ─── Battery Detection ──────────────────────────────────────────────────────

check_battery() {
    local on_battery=false
    local pct=100
    local remaining="—"
    local status="OK"

    if command -v pmset &>/dev/null; then
        local batt_info
        batt_info=$(pmset -g batt 2>/dev/null || true)

        if echo "$batt_info" | grep -q "Battery Power"; then
            on_battery=true
        fi

        pct=$(echo "$batt_info" | grep -oE '[0-9]+%' | head -1 | tr -d '%' || echo "100")
        remaining=$(echo "$batt_info" | grep -oE '[0-9]+:[0-9]+ remaining' | head -1 || echo "—")

        if [ "$on_battery" = true ]; then
            if [ "${pct:-100}" -lt "$BATTERY_CRITICAL" ]; then
                status="CRITICAL"
            elif [ "${pct:-100}" -lt "$BATTERY_LOW" ]; then
                status="LOW"
            else
                status="ON_BATTERY"
            fi
        else
            status="AC"
        fi
    else
        status="N/A"
    fi

    echo "$status|$pct|$on_battery|$remaining"
}

# ─── Memory Detection ───────────────────────────────────────────────────────

check_memory() {
    local status="OK"
    local used_pct=0
    local pressure="normal"

    if command -v memory_pressure &>/dev/null; then
        local mp_output
        mp_output=$(memory_pressure 2>/dev/null | tail -1 || echo "")
        if echo "$mp_output" | grep -qi "critical"; then
            pressure="critical"
            status="CRITICAL"
        elif echo "$mp_output" | grep -qi "warn"; then
            pressure="warn"
            status="WARNING"
        else
            pressure="normal"
        fi
    fi

    # Get memory usage percentage via vm_stat
    if command -v vm_stat &>/dev/null; then
        local page_size
        page_size=$(vm_stat | head -1 | grep -oE '[0-9]+' || echo "4096")
        local pages_free pages_active pages_wired pages_speculative
        pages_free=$(vm_stat | awk '/Pages free/{print $3}' | tr -d '.')
        pages_active=$(vm_stat | awk '/Pages active/{print $3}' | tr -d '.')
        pages_wired=$(vm_stat | awk '/Pages wired/{print $4}' | tr -d '.')
        pages_speculative=$(vm_stat | awk '/Pages speculative/{print $3}' | tr -d '.' || echo "0")

        local total_pages
        total_pages=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
        if [ "$total_pages" -gt 0 ] && [ -n "$pages_free" ]; then
            local total_mb=$((total_pages / 1024 / 1024))
            local free_pages=$((${pages_free:-0} + ${pages_speculative:-0}))
            local free_mb=$((free_pages * ${page_size:-4096} / 1024 / 1024))
            if [ "$total_mb" -gt 0 ]; then
                used_pct=$(( (total_mb - free_mb) * 100 / total_mb ))
            fi
        fi

        # On macOS, high used% is normal (file cache fills all RAM).
        # Only rely on memory_pressure for status; used_pct is informational.
    fi

    echo "$status|$used_pct|$pressure"
}

# ─── CPU Detection ──────────────────────────────────────────────────────────

check_cpu() {
    local status="OK"
    local usage=0

    if command -v top &>/dev/null; then
        # macOS top: get idle percentage, compute usage
        local idle
        idle=$(top -l 1 -n 0 2>/dev/null | awk '/CPU usage/{for(i=1;i<=NF;i++) if($i ~ /idle/) print $(i-1)}' | tr -d '%' || echo "50")
        if [ -n "$idle" ]; then
            usage=$(echo "$idle" | awk '{printf "%.0f", 100 - $1}')
        fi
    fi

    if [ "${usage:-0}" -ge "$CPU_SATURATED" ]; then
        status="SATURATED"
    fi

    echo "$status|$usage"
}

# ─── Notification Logic ─────────────────────────────────────────────────────

# Track state to avoid spam (only notify on state transitions)
load_prev_state() {
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo "AC|normal|OK"
    fi
}

save_state() {
    echo "$1" > "$STATE_FILE"
}

notify_if_changed() {
    local battery_status="$1"
    local memory_status="$2"
    local cpu_status="$3"
    local battery_pct="$4"

    local current_state="${battery_status}|${memory_status}|${cpu_status}"
    local prev_state
    prev_state=$(load_prev_state)

    if [ "$current_state" = "$prev_state" ]; then
        return
    fi

    save_state "$current_state"

    # Battery transitions
    if [ "$battery_status" = "CRITICAL" ]; then
        "$BOARD" --as monitor send All "[BATTERY CRITICAL] ${battery_pct}% remaining. Suspending non-essential sessions recommended." 2>/dev/null || true
    elif [ "$battery_status" = "LOW" ]; then
        "$BOARD" --as monitor send All "[BATTERY LOW] ${battery_pct}%. Consider reducing active sessions." 2>/dev/null || true
    elif [ "$battery_status" = "ON_BATTERY" ] && echo "$prev_state" | grep -q "^AC"; then
        "$BOARD" --as monitor send All "[BATTERY] Switched to battery power (${battery_pct}%)." 2>/dev/null || true
    fi

    # Memory transitions
    if [ "$memory_status" = "CRITICAL" ] && ! echo "$prev_state" | grep -q "CRITICAL"; then
        "$BOARD" --as monitor send All "[MEMORY CRITICAL] System under memory pressure. Save state + reduce sessions." 2>/dev/null || true
    elif [ "$memory_status" = "WARNING" ] && echo "$prev_state" | grep -q "normal\|OK"; then
        "$BOARD" --as monitor send All "[MEMORY WARNING] Memory pressure rising. Monitor closely." 2>/dev/null || true
    fi

    # CPU transitions
    if [ "$cpu_status" = "SATURATED" ] && ! echo "$prev_state" | grep -q "SATURATED"; then
        "$BOARD" --as monitor send All "[CPU SATURATED] CPU > ${CPU_SATURATED}%. Avoid concurrent builds." 2>/dev/null || true
    fi
}

# ─── Output Formatters ──────────────────────────────────────────────────────

print_status() {
    local batt_result mem_result cpu_result
    batt_result=$(check_battery)
    mem_result=$(check_memory)
    cpu_result=$(check_cpu)

    local batt_status batt_pct batt_on_battery batt_remaining
    IFS='|' read -r batt_status batt_pct batt_on_battery batt_remaining <<< "$batt_result"

    local mem_status mem_pct mem_pressure
    IFS='|' read -r mem_status mem_pct mem_pressure <<< "$mem_result"

    local cpu_status cpu_usage
    IFS='|' read -r cpu_status cpu_usage <<< "$cpu_result"

    if [ "$MODE" = "json" ]; then
        cat <<JSON
{"battery":{"status":"$batt_status","pct":$batt_pct,"on_battery":$batt_on_battery,"remaining":"$batt_remaining"},"memory":{"status":"$mem_status","used_pct":$mem_pct,"pressure":"$mem_pressure"},"cpu":{"status":"$cpu_status","usage":$cpu_usage}}
JSON
        return
    fi

    echo "Resource Monitor"
    echo "================"
    echo ""
    printf "Battery:  %s" "$batt_status"
    if [ "$batt_status" != "N/A" ]; then
        printf " (%s%%)" "$batt_pct"
        [ "$batt_remaining" != "—" ] && printf " %s" "$batt_remaining"
    fi
    echo ""
    printf "Memory:   %s (%s%% used, pressure: %s)\n" "$mem_status" "$mem_pct" "$mem_pressure"
    printf "CPU:      %s (%s%% usage)\n" "$cpu_status" "$cpu_usage"
    echo ""

    # Recommendations
    local has_issue=false
    if [ "$batt_status" = "CRITICAL" ]; then
        echo "! CRITICAL: Suspend all non-essential sessions NOW."
        has_issue=true
    elif [ "$batt_status" = "LOW" ]; then
        echo "! Battery low: reduce to 2-3 sessions."
        has_issue=true
    elif [ "$batt_status" = "ON_BATTERY" ]; then
        echo "* Running on battery. Monitor usage."
        has_issue=true
    fi

    if [ "$mem_status" = "CRITICAL" ]; then
        echo "! CRITICAL: Memory pressure critical. Restart largest session."
        has_issue=true
    elif [ "$mem_status" = "WARNING" ]; then
        echo "! Memory pressure elevated. Consider suspending idle sessions."
        has_issue=true
    fi

    if [ "$cpu_status" = "SATURATED" ]; then
        echo "! CPU saturated. Avoid concurrent builds."
        has_issue=true
    fi

    if [ "$has_issue" = false ]; then
        echo "All resources nominal."
    fi
}

# ─── Main ───────────────────────────────────────────────────────────────────

case "$MODE" in
    status|json)
        print_status
        ;;
    watch)
        echo "Resource monitor started (interval: 30s)"
        while true; do
            batt_result=$(check_battery)
            mem_result=$(check_memory)
            cpu_result=$(check_cpu)

            IFS='|' read -r batt_status batt_pct batt_on_battery batt_remaining <<< "$batt_result"
            IFS='|' read -r mem_status mem_pct mem_pressure <<< "$mem_result"
            IFS='|' read -r cpu_status cpu_usage <<< "$cpu_result"

            notify_if_changed "$batt_status" "$mem_status" "$cpu_status" "$batt_pct"

            sleep 30
        done
        ;;
esac
