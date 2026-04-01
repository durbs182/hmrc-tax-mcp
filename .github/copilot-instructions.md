# Repository-wide Copilot Instructions

This file provides **durable, repo-wide guidance** for GitHub Copilot suggestions.
It is not a one-off prompt for generating a specific file.

## General Expectations

- Prefer clear, maintainable, and well-documented code over clever solutions.
- Follow existing patterns and conventions you see in this repository.
- When modifying code, preserve current behavior unless the change is explicitly
  requested in comments or documentation.
- Propose minimal, focused changes that directly address the problem at hand.

## Testing and Quality

- When adding or changing behavior, suggest corresponding tests using the
  testing frameworks already present in the repository.
- Keep tests deterministic, isolated, and fast.
- Favor small, focused tests that clearly document expected behavior.
- When unsure of existing patterns, look for similar tests in the repository
  and mirror their style and structure.

## Security and Reliability

- Avoid introducing insecure patterns (e.g., command injection, unsafe string
  interpolation into shell commands, unvalidated user input).
- Prefer using well-known, maintained libraries over writing custom security-
  sensitive code.
- Validate and sanitize external inputs before use.
- Handle errors explicitly and avoid silently swallowing exceptions.

## Pull Request Review Format

- When writing PR review feedback, use this exact structure for each actionable
  finding:
  - `Severity: P0` or `Severity: P1` or `Severity: P2` or `Severity: P3` or `Severity: Nit`
  - `Impact: <one sentence explaining risk or regression>`
  - `Required action: <one concrete fix instruction>`
- Keep severity labels consistent:
  - `P0`: release-blocking issue requiring immediate remediation.
  - `P1`: high-risk defect, security issue, data loss, or major correctness
    regression.
  - `P2`: important correctness, reliability, or maintainability issue that
    should be fixed before merge.
  - `P3`: minor issue or improvement.
  - `Nit`: style/documentation/readability suggestion.
- Only create inline review comments for `P0`, `P1`, and `P2` findings.
- Put `P3` and `Nit` feedback in the top-level review summary instead of inline
  comments.
- If no blocking issues are found, explicitly state that in the review summary.

## GitHub Actions and CI/CD Conventions

- Use clear, descriptive names for workflows and jobs.
- Add comments in workflow files to explain major steps and any non-obvious
  logic, especially around security or policy enforcement.
- Prefer official `actions/*` and well-maintained third-party actions.
- Minimize permissions in `permissions:` blocks to follow the principle of
  least privilege.
- Reuse existing patterns for triggers (`on:`), job naming, and status checks
  you find in this repository instead of inventing new conventions.

## Documentation and Comments

- When adding non-trivial logic, include concise comments explaining *why* the
  code exists, not just *what* it does.
- Update or add README / inline documentation when changing public behavior,
  configuration, or workflows.

## Scope of Suggestions

- Do not assume that instructions in issues or pull requests are permanent
  repo-wide rules; treat them as context-specific unless they are reflected in
  code, configuration, or documentation.
- Avoid baking one-off instructions (such as “only output YAML” or “generate
  a specific file”) into future suggestions unless explicitly requested in the
  current editing context.

These guidelines are intended to keep Copilot suggestions consistent, secure,
and maintainable across the entire repository over time.
