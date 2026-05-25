# Upgrade workflow

`vstack-upgrade` checks PyPI for newer releases of `valanistack`, prints the install command, and shows the relevant CHANGELOG sections as migration notes. Never execs `pip` itself — different package managers (pip / pipx / uv / system) behave differently and the user runs the command themselves.

```bash
vstack-upgrade                       # human-readable
vstack-upgrade --json                # machine-readable
vstack-upgrade --quiet               # silent if up-to-date (exit 0)
vstack-upgrade --allow-prereleases   # consider rc / dev versions
```

## Exit codes

- `0` — up to date
- `1` — upgrade available
- `2` — PyPI lookup failed

Useful in CI to fail a build if a critical bump is available:

```bash
vstack-upgrade --quiet || echo "vstack upgrade available — see CHANGELOG"
```

## What the install command looks like

```
$ vstack-upgrade
valanistack upgrade available: 0.4.0 -> 0.5.0
Install command:
  pip install --upgrade 'valanistack==0.5.0'

Migration notes:

## [0.5.0] -- 2026-05-25
- Added vstack.browser ...
- Added vstack.gbrain ...
...
```
