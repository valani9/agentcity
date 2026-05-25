<!--
Thanks for contributing to vstack.

This repo treats every pattern as a 5-layer shipment: README, Python
lib, runnable demo on at least one framework, an eval on a public
benchmark, and a write-up essay. For non-pattern work (surfaces,
adapters, infra, docs), the bar is: tests pass, mypy --strict clean
on the touched lib, ruff clean, no new lints suppressed.

Mark sections N/A if they don't apply.
-->

## Summary
<!-- One paragraph: what changed and why. -->

## Type of change
- [ ] New OB-anchored diagnostic pattern (cite the literature)
- [ ] New invocation surface (CLI, MCP, REST, Docker, skill, adapter, browser, gen-platform)
- [ ] Bug fix
- [ ] Refactor / internal cleanup
- [ ] Docs / examples / cookbook
- [ ] CI / packaging / release plumbing
- [ ] Security / observability / performance

## Test plan
<!-- Concrete commands you ran. CI must be green; this is what
     a reviewer should rerun to convince themselves. -->
- [ ] `pytest <touched dirs>`
- [ ] `mypy <touched lib> --strict --ignore-missing-imports`
- [ ] `ruff check <touched dirs> && ruff format --check <touched dirs>`
- [ ] Manual smoke (commands + observed output):

## Public-API impact
<!-- Does this change anything in any sub-package's __all__? If yes,
     does the change follow the 0.x stability promise documented in
     vstack/__init__.py? -->

## Release notes line
<!-- One line for CHANGELOG.md if this PR ships in a release. -->

## Related issues / PRs
<!-- Closes #..., refs #..., follow-up to #... -->
