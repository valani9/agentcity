# Shell completions for vstack CLIs

This directory ships completion scripts for the vstack CLI family. Install the one matching your shell:

## Bash

```bash
# Linux / macOS Homebrew
sudo cp completions/vstack.bash /etc/bash_completion.d/vstack
# Or in your home directory
cp completions/vstack.bash ~/.bash_completion.d/vstack
# Make sure ~/.bashrc sources ~/.bash_completion.d/*
```

## Zsh

```bash
# Drop into any directory on your $fpath
mkdir -p ~/.zsh/completions
cp completions/_vstack ~/.zsh/completions/
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -U compinit && compinit' >> ~/.zshrc
```

## Fish

```bash
mkdir -p ~/.config/fish/completions
cp completions/vstack.fish ~/.config/fish/completions/
```

After install, your shell will complete:

- The 10 top-level CLIs: `vstack`, `vstack-mcp`, `vstack-api`, `vstack-config`, `vstack-upgrade`, `vstack-learn`, `vstack-analytics`, `vstack-browser`, `vstack-gbrain`, `vstack-bench`, `vstack-doctor`
- The 34 per-pattern CLIs: `vstack-lewin`, `vstack-aar`, `vstack-schein-culture`, etc.
- Subcommands for each (e.g. `vstack-mcp <Tab>` shows `serve`, `list-tools`, `list-resources`, `config-snippet`)
- Pattern names where applicable (e.g. `vstack-config gen-platform <Tab>` shows `cursor`, `cline`, etc.)

Reload your shell after install (`exec $SHELL`) or open a fresh terminal.
