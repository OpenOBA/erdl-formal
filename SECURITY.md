# Security Policy

## Reporting a Vulnerability

**Do NOT open a public GitHub issue** for security vulnerabilities.

Email the maintainers privately at **support@openoba.com** with the subject
`[SECURITY] <short summary>`. Include:

- affected version / commit
- a minimal reproduction (rule + schema + expected vs actual)
- potential impact

We acknowledge within 5 business days and keep you informed of progress. We
prefer coordinated disclosure: give a reasonable window before public
disclosure, and we will credit the reporter unless you ask otherwise.

## Scope

| In scope | Out of scope |
|---|---|
| The SMT encoding (`tvl.py`, `compiler.py`) | The ERDL spec itself (erdl-landing) |
| Property verification (`properties.py`, `resolution.py`) | The `erdl` engine / `erdl-vectors` repos |
| Cross-validation harness (`replay/`) | — |

## Security Model

This is a **verifier**, not a runtime guard. It proves properties of rules
against the spec's semantics; it does **not** enforce anything at runtime.

- Verification is **conditional** on schema assumptions (see
  `docs/field-contracts.md`). If a field is declared `optional=false` but is
  missing at runtime, a proven property may not hold.
- The verifier's core claim is **soundness**: it must never report `unsat`
  (property holds) when a counterexample exists. Any suspected unsoundness is
  a security issue — report it privately.

## Supported Versions

| Version | Supported |
|---|---|
| unreleased (`master`) | ✅ |
