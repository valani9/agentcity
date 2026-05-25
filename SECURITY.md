# Security Policy

## Supported Versions

vstack is in active development. Security fixes are issued for the
latest minor release on the `0.x` series. Once the project reaches
`1.0.0`, the supported window will extend to the prior minor as well.

| Version  | Supported |
| -------- | --------- |
| `0.1.x`  | yes       |
| `< 0.1`  | no        |

## Reporting a Vulnerability

If you find a security issue in vstack — anything that allows an
attacker to bypass intended diagnostic boundaries, exfiltrate prompts,
poison telemetry, or execute untrusted code via library APIs — please
report it privately rather than opening a public GitHub issue.

**Preferred channel**: GitHub Security Advisories.

  1. Go to <https://github.com/valani9/vstack/security/advisories>.
  2. Click **Report a vulnerability**.
  3. Describe the issue with enough detail to reproduce
     (commit hash, code snippet, expected vs observed behavior).

**Fallback**: email `valani@bu.edu` with the subject line
`vstack Security: <short description>`.

You should receive an acknowledgement within 72 hours.

## Disclosure Timeline

After a report is received and validated, the timeline is:

  1. **Acknowledgement** — within 72 hours.
  2. **Triage** — within 7 days. Severity is graded against the
     [CVSS v3.1 calculator](https://www.first.org/cvss/calculator/3.1).
  3. **Fix** — within 14 days for critical and high severity issues.
     Medium and low severity may take longer; you will receive a
     time estimate during triage.
  4. **Coordinated disclosure** — a patched release is published to
     PyPI, the advisory is published on GitHub, and (if the reporter
     consents) credit is given by name in the advisory and changelog.

If a fix is materially delayed, the reporter is informed in writing
before any deadline passes.

## What is in scope

  - Code execution via library APIs that should never execute code.
  - Prompt-injection paths through `vstack.aar._guards` that bypass
    the documented sanitization promises.
  - Authentication / token leakage from any of the shipped LLM client
    adapters.
  - Telemetry sinks leaking data they were not configured to receive.
  - Build / release pipeline issues that allow malicious package
    publishing.

## What is out of scope

  - The LLM provider's own behavior. vstack does not control the
    upstream provider's safety or refusal policies; report those to
    the provider directly.
  - Denial of service by sending oversized inputs to your own
    deployment of the library. Set request size limits at your
    application boundary.
  - Social-engineering attacks against the maintainer.
  - Issues in dependencies — please report those upstream first; if
    vstack exposes a vulnerable transitive dependency in a way
    that the upstream library cannot mitigate, that *is* in scope.

## Hardening Notes

Production deployments should:

  - Apply `sanitize_for_prompt` to any free-text field originating
    outside the application boundary before passing it to a pattern
    generator.
  - Log `detect_injection` hits at WARNING with the originating
    request ID for forensic review.
  - Set explicit timeouts (`timeout=` constructor argument) on every
    LLM client; the default of 120s is a sane upper bound but
    application-specific values may be lower.
  - Pin `vstack` to a specific minor version in production
    requirements files until 1.0.0.
  - Verify the wheel signature (PyPI trusted publisher provenance)
    before deploying.
