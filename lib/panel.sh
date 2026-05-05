#!/usr/bin/env bash
# panel.sh — clean team status panel, auto-refreshes

_self="$0"; [ -L "$_self" ] && _self="$(readlink "$_self")"; CLAUDES_HOME="$(cd "$(dirname "$_self")/.." && pwd)"
source "$CLAUDES_HOME/lib/discover.sh"

PREFIX="${PREFIX:-cc}"
INTERVAL="${1:-8}"

status_icon() {
    local name="$1"
    if ! tmux has-session -t "${PREFIX}-${name}" 2>/dev/null; then echo "  "; return; fi
    local cmd
    cmd=$(tmux list-panes -t "${PREFIX}-${name}" -F '#{pane_current_command}' 2>/dev/null | head -1)
    case "$cmd" in
        zsh|bash|sh|-zsh|-bash) echo "!!"; return ;;
    esac
    local output
    output=$(tmux capture-pane -t "${PREFIX}-${name}" -p 2>/dev/null | tail -8)
    if echo "$output" | grep -q "bypass permissions"; then
        echo ".."
    elif echo "$output" | grep -qE '^\s*(⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏|●)'; then
        echo ">>"
    else
        echo "~~"
    fi
}

render() {
    clear
    printf "\033[1m  TEAM PANEL\033[0m  %s\n\n" "$(date '+%H:%M:%S')"
    for name in "${SESSIONS[@]}"; do
        local sf="${SESSIONS_DIR}/${name}.md"
        local icon
        icon=$(status_icon "$name")

        # Status from session file
        local task="-"
        if [ -f "$sf" ]; then
            task=$(awk '/^## Status/{getline; if(NF>0) print; exit}' "$sf" 2>/dev/null)
            [ -z "$task" ] && task="-"
        fi

        # Color: >> green, .. yellow, !! red, else dim
        local color="\033[90m"
        case "$icon" in
            ">>") color="\033[32m" ;;
            "..") color="\033[33m" ;;
            "!!") color="\033[31m" ;;
        esac

        printf "  ${color}%s %-6s\033[0m %s\n" "$icon" "$name" "$task"
    done
    printf "\n  \033[90m%s 秒刷新  q 退出\033[0m\n" "$INTERVAL"
}

trap 'tput cnorm; exit' INT TERM
tput civis 2>/dev/null

while true; do
    render
    for ((i=0; i<INTERVAL*10; i++)); do
        read -rsn1 -t 0.1 key 2>/dev/null && { [ "$key" = "q" ] && { tput cnorm; exit; }; }
    done
done
