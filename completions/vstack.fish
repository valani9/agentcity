# Fish completion for the vstack CLI family.
# Install: cp completions/vstack.fish ~/.config/fish/completions/

# vstack-mcp
complete -c vstack-mcp -f -n "__fish_use_subcommand" -a "serve list-tools list-resources config-snippet"
complete -c vstack-mcp -f -n "__fish_seen_subcommand_from config-snippet" \
    -a "claude-desktop cursor cline continue generic"

# vstack-api
complete -c vstack-api -f -n "__fish_use_subcommand" -a "serve routes openapi"

# vstack-config
complete -c vstack-config -f -n "__fish_use_subcommand" \
    -a "get set list unset path keys install-skills gen-platform"
complete -c vstack-config -f -n "__fish_seen_subcommand_from path" \
    -a "home baselines sessions analytics config"
complete -c vstack-config -f -n "__fish_seen_subcommand_from gen-platform" \
    -a "claude-desktop cursor cline continue roo-code windsurf zed aider goose kiro openclaw codex-cli opencode docker-compose"
complete -c vstack-config -f -n "__fish_seen_subcommand_from get set unset" \
    -a "default_mode default_model telemetry log_level preferred_llm api_host api_port skills_install_path"

# vstack-learn
complete -c vstack-learn -f -n "__fish_use_subcommand" \
    -a "record recall outcome outcomes path clear"

# vstack-analytics
complete -c vstack-analytics -f -n "__fish_use_subcommand" \
    -a "summary top-costs cost path raw"

# vstack-browser
complete -c vstack-browser -f -n "__fish_use_subcommand" -a "scrape screenshot tools"

# vstack-gbrain
complete -c vstack-gbrain -f -n "__fish_use_subcommand" -a "status sync search corpus"

# vstack-bench
complete -c vstack-bench -f -n "__fish_use_subcommand" -a "list run compare"

# vstack-doctor
complete -c vstack-doctor -l json -d "Emit JSON instead of pretty text"
complete -c vstack-doctor -l skip-network -d "Skip the PyPI upgrade check"
complete -c vstack-doctor -l only-errors -d "Print only ERROR-level findings"

# vstack-hello
complete -c vstack-hello -l offline -d "Skip LLM resolution; always show canned sample"
complete -c vstack-hello -l json -d "Emit a JSON envelope instead of pretty text"
complete -c vstack-hello -l no-banner -d "Skip the ASCII banner and footer"

# vstack (top-level AAR CLI)
complete -c vstack -f -n "__fish_use_subcommand" -a "aar bench version"
