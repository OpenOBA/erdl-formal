# Contributing to erdl-formal

Thanks for your interest. erdl-formal is a formal verifier for the ERDL
expression kernel — it proves properties of ERDL rules using SMT (Z3).

## First Things First

1. **When in doubt, open an issue.** For any non-trivial change, start with an
   issue describing the problem and your proposed approach. Skip only for truly
   trivial fixes (typos, formatting).
2. **Only submit your own work** (or work you have the right to submit).

## Ways to Contribute

### Bug reports

Confirm against the latest `main`, then check existing issues. Include:

- a minimal reproduction (rule + schema + expected vs actual)
- version / commit
- environment (Python version, z3-solver version)

### Feature requests

Describe the feature, why it is needed, and how it should work.

### Code

1. **Open an issue first** for anything non-trivial, to avoid wasted effort.
2. Follow the developer guide (`docs/DEVELOPER-GUIDE.md`) for adding a node or
   a property.
3. Keep code, comments, and commit messages **English-only**; follow the style
   guide (`style_guide.md`).

## Development Setup

```bash
python -m pip install -e ".[dev]"   # install deps (z3-solver, pytest)
pytest                               # run the test suite (must be green)
python replay/crosscheck-vectors.py  # cross-check against erdl-vectors
```

## Review Process

All PRs go through review; expect some back-and-forth. Before submitting,
ensure the full test suite passes. For a formal verifier, correctness claims
must be backed by cross-checks against the reference engine / frozen vectors —
do not weaken or delete cross-validation assertions without a stated reason.

## Code of Conduct

See `CODE_OF_CONDUCT.md`.

## Security

Report vulnerabilities **privately** — see `SECURITY.md`. Do not open a public
issue for security findings.

## License

MIT. By contributing, you agree your contribution is licensed under Apache-2.0.
