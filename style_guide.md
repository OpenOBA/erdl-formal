# Style Guide

- **English-only** for code, comments, docstrings, and commit messages.
- **Python**: follow [PEP 8](https://peps.python.org/pep-0008/). Docstrings use
  Google style with a one-line summary.
- **Tests**: files named `test_*.py`, functions named `test_<behavior>`; cover
  normal / boundary / missing-field / error cases.
- **SMT encodings**: cite the spec section they implement, e.g.
  `spec v2.0 §10.2 E11` (leaf collapse).
- **Cross-validation**: correctness claims must reference a cross-check against
  the reference engine / frozen vectors; do not add unverified expectations.
- No third-party identifiers or internal process labels in code.
