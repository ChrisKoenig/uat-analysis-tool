# Tests

This directory contains project-wide tests organized by category:

| Directory | Purpose | Marker |
|-----------|---------|--------|
| `unit/` | Unit tests for `shared/` modules | — |
| `integration/` | End-to-end workflows across all services | `@pytest.mark.integration` |
| `security/` | OWASP Top 10 compliance checks | `@pytest.mark.security` |

App-specific tests live in `apps/triage/tests/` (314 tests, all in-memory).

## Running

```bash
# All tests (both locations configured in pyproject.toml)
python -m pytest -q

# Only root-level tests
python -m pytest tests/ -q

# By marker
python -m pytest -m security -v
```

See [docs/TESTING_GUIDE.md](../docs/TESTING_GUIDE.md) for full documentation on test architecture, patterns, and how to add new tests.
