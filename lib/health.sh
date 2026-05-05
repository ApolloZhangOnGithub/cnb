#!/usr/bin/env bash
set -euo pipefail

# session-health.sh — Session health report
# Shows restart count, idle status, uptime for each session.

_PATHS_LOADED="${_PATHS_LOADED:-}"
LOG_DIR="${PROJECT_ROOT}/.swarm-logs"
PREFIX="cc"

G='\033[0;32m'
R='\033[0;31m'
Y='\033[1;33m'
D='\033[2m'
NC='\033[0m'

now=$(date +%s)

get_sessions() {
    tmux list-sessions -F '#{session_name}' 2>/dev/null \
        | grep "^${PREFIX}-" \
        | sed "s/^${PREFIX}-//" \
        | grep -v -E "^(${DISPATCHER_SESSION:-dispatcher}|${LEAD_SESSION:-lead})$" \
        | sort
}

echo ""
echo -e "  Session\t\tStatus\t\tRestarts\tUptime\t\tAgent"
echo -e "  -------\t\t------\t\t--------\t------\t\t-----"

sessions=$(get_sessions)
total=0
alive=0
idle_count=0

for name in $sessions; do
    total=$((total + 1))
    sess="${PREFIX}-${name}"

    # Status from idle-cache
    status="offline"
    if tmux has-session -t "$sess" 2>/dev/null; then
        local_cmd=$(tmux list-panes -t "$sess" -F '#{pane_current_command}' 2>/dev/null | head -1)
        case "$local_cmd" in
            zsh|bash|sh|-zsh|-bash) status="exited" ;;
            *)
                if grep -q "^${sess} idle$" "${LOG_DIR}/idle-cache" 2>/dev/null; then
                    status="idle"
                    idle_count=$((idle_count + 1))
                else
                    status="active"
                fi
                alive=$((alive + 1))
                ;;
        esac
    fi

    # Restart count (from session-specific log)
    restarts=0
    if [ -f "${LOG_DIR}/${name}.log" ]; then
        restarts=$(wc -l < "${LOG_DIR}/${name}.log" | tr -d ' ')
    fi

    # Last start time → uptime
    uptime_str="-"
    agent="?"
    if [ -f "${LOG_DIR}/${name}.log" ]; then
        last_line=$(tail -1 "${LOG_DIR}/${name}.log")
        ts=$(echo "$last_line" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' | head -1)
        agent=$(echo "$last_line" | grep -oE 'agent: [a-z]+' | sed 's/agent: //')
        if [ -n "$ts" ]; then
            start_epoch=$(date -j -f "%Y-%m-%d %H:%M:%S" "$ts" +%s 2>/dev/null || echo 0)
            if [ "$start_epoch" -gt 0 ]; then
                elapsed=$((now - start_epoch))
                hours=$((elapsed / 3600))
                mins=$(( (elapsed % 3600) / 60 ))
                uptime_str="${hours}h${mins}m"
            fi
        fi
    fi

    # Color code status
    case "$status" in
        active)  status_col="${G}active${NC}" ;;
        idle)    status_col="${Y}idle${NC}" ;;
        exited)  status_col="${R}exited${NC}" ;;
        offline) status_col="${D}offline${NC}" ;;
    esac

    # Color code restarts (high = red)
    if [ "$restarts" -gt 5 ]; then
        restart_col="${R}${restarts}${NC}"
    elif [ "$restarts" -gt 2 ]; then
        restart_col="${Y}${restarts}${NC}"
    else
        restart_col="${G}${restarts}${NC}"
    fi

    echo -e "  ${name}\t\t${status_col}\t\t${restart_col}\t\t${uptime_str}\t\t${agent:-?}"
done

echo ""
echo -e "  Total: $total | Active: ${G}${alive}${NC} | Idle: ${Y}${idle_count}${NC} | Offline: ${D}$((total - alive))${NC}"
echo ""
