# Bash completion for the vstack CLI family.
# Install:
#   sudo cp completions/vstack.bash /etc/bash_completion.d/vstack
#   or: source <path>/vstack.bash

_vstack_mcp_completions() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "serve list-tools list-resources config-snippet" -- "$cur") )
        return 0
    fi
    if [[ "$prev" == "config-snippet" ]]; then
        COMPREPLY=( $(compgen -W "claude-desktop cursor cline continue generic" -- "$cur") )
        return 0
    fi
}

_vstack_api_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "serve routes openapi" -- "$cur") )
        return 0
    fi
}

_vstack_config_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "get set list unset path keys install-skills gen-platform" -- "$cur") )
        return 0
    fi
    if [[ "$prev" == "path" ]]; then
        COMPREPLY=( $(compgen -W "home baselines sessions analytics config" -- "$cur") )
        return 0
    fi
    if [[ "$prev" == "gen-platform" ]]; then
        COMPREPLY=( $(compgen -W "claude-desktop cursor cline continue roo-code windsurf zed aider goose kiro openclaw codex-cli opencode docker-compose" -- "$cur") )
        return 0
    fi
    if [[ "$prev" == "get" || "$prev" == "set" || "$prev" == "unset" ]]; then
        COMPREPLY=( $(compgen -W "default_mode default_model telemetry log_level preferred_llm api_host api_port skills_install_path" -- "$cur") )
        return 0
    fi
}

_vstack_learn_completions() {
    local cur prev
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "record recall outcome outcomes path clear" -- "$cur") )
        return 0
    fi
}

_vstack_analytics_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "summary top-costs cost path raw" -- "$cur") )
        return 0
    fi
}

_vstack_browser_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "scrape screenshot tools" -- "$cur") )
        return 0
    fi
}

_vstack_gbrain_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "status sync search corpus" -- "$cur") )
        return 0
    fi
}

_vstack_bench_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "list run compare" -- "$cur") )
        return 0
    fi
}

_vstack_doctor_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=( $(compgen -W "--json --skip-network --only-errors --help" -- "$cur") )
}

complete -F _vstack_mcp_completions vstack-mcp
complete -F _vstack_api_completions vstack-api
complete -F _vstack_config_completions vstack-config
complete -F _vstack_learn_completions vstack-learn
complete -F _vstack_analytics_completions vstack-analytics
complete -F _vstack_browser_completions vstack-browser
complete -F _vstack_gbrain_completions vstack-gbrain
complete -F _vstack_bench_completions vstack-bench
complete -F _vstack_doctor_completions vstack-doctor
