# Black Box terminal instrumentation hook.
#
# Not sourced automatically — this project never edits your shell rc files.
# Opt in yourself by adding to ~/.zshrc:
#   source /path/to/black-box/scripts/blackbox_zsh_hook.sh
# and setting capture.terminal.enabled: true in config.yaml.
#
# Records only the command text, exit code, cwd, shell and timing — never
# stdout/stderr (this hook has no reliable way to capture a command's output
# without wrapping every command, which would be far more invasive).

BLACKBOX_EVENT_LOG="${BLACKBOX_EVENT_LOG:-$HOME/.blackbox/terminal_events.jsonl}"
mkdir -p "$(dirname "$BLACKBOX_EVENT_LOG")"

__blackbox_preexec() {
    __blackbox_cmd="$1"
    __blackbox_start=$(date +%s.%N)
}

__blackbox_precmd() {
    local exit_code=$?
    if [[ -z "$__blackbox_cmd" ]]; then
        return
    fi
    local end
    end=$(date +%s.%N)
    local duration
    duration=$(awk -v a="$__blackbox_start" -v b="$end" 'BEGIN { printf "%.3f", b - a }')
    local escaped_cmd
    escaped_cmd=$(printf '%s' "$__blackbox_cmd" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().rstrip(chr(10))))')

    printf '{"shell":"zsh","command":%s,"exit_code":%d,"cwd":"%s","duration_seconds":%s,"timestamp":"%s"}\n' \
        "$escaped_cmd" "$exit_code" "$PWD" "$duration" "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)" \
        >> "$BLACKBOX_EVENT_LOG"

    unset __blackbox_cmd
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec __blackbox_preexec
add-zsh-hook precmd __blackbox_precmd
