# Testing Guide

How to run, understand, and extend the UAT Analysis Tool test suite.

---

## Quick Start

All test configuration lives in `pyproject.toml` at the project root. A single command runs every test:

```bash
# Run all tests (uses pyproject.toml config)
python -m pytest -q

# Run with verbose output
python -m pytest -v
```

### By Location

```bash
# Root-level tests only (integration, security, unit)
python -m pytest tests/ -q

# Triage app tests only
python -m pytest apps/triage/tests/ -q
```

### By Marker

```bash
# Security compliance tests
python -m pytest -m security -v

# Integration / end-to-end tests (requires running services)
python -m pytest -m integration -v

# Skip slow tests
python -m pytest -m "not slow"
```

### Specific Targets

```bash
# A specific test file
python -m pytest apps/triage/tests/test_models.py -v

# A specific test class
python -m pytest apps/triage/tests/test_engines.py::TestTriggerEngine -v

# A specific test
python -m pytest apps/triage/tests/test_models.py::TestTrigger::test_create_simple_trigger -v

# Tests matching a keyword
python -m pytest -k "trigger"
```

---

## Test Configuration (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "apps/triage/tests"]
pythonpath = [".", "apps"]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "security: security compliance tests",
    "integration: integration / end-to-end tests",
]
```

Key points:
- **`testpaths`** — pytest discovers tests from both `tests/` and `apps/triage/tests/` by default.
- **`pythonpath`** — adds `.` (project root) and `apps/` so imports like `from triage.models.rule import Rule` and `from shared.search_service import ResourceSearchService` work.
- **`asyncio_mode = "auto"`** — async test functions run automatically via `pytest-asyncio`.
- **Markers** — use `-m security`, `-m integration`, or `-m slow` to select/deselect test subsets.

---

## Test Directory Structure

```
tests/
├── unit/                   # Unit tests for shared modules (placeholder)
│   └── __init__.py
├── integration/            # Integration / end-to-end tests
│   ├── test_end_to_end_pytest.py    # Full workflow tests across all 8 services
│   ├── test_refactoring_pytest.py   # Validates project structure after refactoring
│   └── __init__.py
└── security/               # OWASP Top 10 compliance tests
    ├── test_security_controls.py
    └── __init__.py

apps/triage/tests/
├── conftest.py             # Shared fixtures, path setup
├── test_models.py          # Data model lifecycle, validation, serialization
├── test_engines.py         # Rules, triggers, routes engine logic
├── test_api.py             # FastAPI endpoint CRUD, validation, error codes
├── test_phase2_api.py      # Phase 2: evaluation, queue, ADO integration
├── test_phase5_hardening.py # Optimistic locking, reference checks, dry-run  
├── test_ado_client.py      # ADO client adapter, dual-org config
├── test_ado_writer.py      # ADO write operations, field change formatting
├── test_webhook.py         # Webhook processing, filtering, deduplication
└── __init__.py
```

---

## Root-Level Test Suites

### Integration Tests (`tests/integration/`)

**`test_end_to_end_pytest.py`** — Full-stack workflow tests covering all 8 microservices. Requires services to be running (`start_dev.ps1`). Automatically skipped if the gateway is not reachable on `localhost:8000`.

Covers:
- Health checks for all services (ports 8000–8007)
- Intelligent UAT search (context analysis → classification → search)
- Work item evaluation workflows

```bash
python -m pytest tests/integration/test_end_to_end_pytest.py -m integration -v
```

**`test_refactoring_pytest.py`** — Structural verification that validates files, directories, and imports are correctly placed after refactoring. Tests include:
- Data files exist in `data/` and are valid JSON
- `shared.search_service` loads retirements from `data/`
- `scripts/` directory has ≥15 files
- Moved docs exist in `docs/`
- Shared modules are importable from `shared.*`
- Triage models/engines/services importable from `triage.*`

```bash
python -m pytest tests/integration/test_refactoring_pytest.py -v
```

### Security Tests (`tests/security/`)

**`test_security_controls.py`** — OWASP Top 10 compliance checks. No external dependencies required.

| Control | What It Verifies |
|---------|-----------------|
| SEC-01 | No hardcoded secrets or credentials in Python source |
| SEC-02 | NoSQL injection prevention (Cosmos DB parameterized queries) |
| SEC-03 | Input validation on API endpoints |
| SEC-04 | CORS configuration (no wildcard origins in production) |
| SEC-05 | Dependency version pinning |
| SEC-06 | Sensitive data not logged in plaintext |

```bash
python -m pytest -m security -v
```

### Unit Tests (`tests/unit/`)

Currently a placeholder for future unit tests covering `shared/` modules. See [Adding New Tests](#adding-new-tests) below.

---

## Triage App Test Suite (`apps/triage/tests/`)

**314 tests** across 8 modules, running in ~2 seconds (all in-memory, no external dependencies).

| Module | Tests | What It Covers |
|--------|-------|----------------|
| `test_models.py` | ~80 | Data model lifecycle, validation, serialization, operators |
| `test_engines.py` | ~100 | All 3 engines: rules (16 operators), triggers (AND/OR/NOT), routes (5 operations) |
| `test_api.py` | ~40 | FastAPI endpoint routing, validation, error codes, CRUD patterns |
| `test_phase2_api.py` | ~30 | Phase 2 API features: evaluation, queue, ADO integration |
| `test_phase5_hardening.py` | ~40 | Staged filtering, optimistic locking, reference checks, dry-run guards |
| `test_ado_client.py` | ~15 | ADO client adapter, dual-org config, error handling |
| `test_ado_writer.py` | ~10 | ADO write operations, field change formatting |
| `test_webhook.py` | ~10 | Webhook payload processing, filtering, deduplication |

### No External Dependencies

All triage tests run without:
- Cosmos DB (uses in-memory store)
- Azure DevOps (uses mocked ADO client)
- Azure credentials (not needed for unit tests)

### Key Patterns

**Helper factories** — Each test file has helper functions for creating test entities:

```python
def make_rule(id, field, operator, value=None, status="active"):
    return Rule(id=id, name=f"Test {id}", field=field, ...)

def make_trigger(id, priority, expression, onTrue, status="active"):
    return Trigger(id=id, name=f"Test {id}", priority=priority, ...)

def make_action(id, field, operation, value=None, status="active"):
    return Action(id=id, name=f"Test {id}", field=field, ...)
```

**FastAPI TestClient** — API tests use `fastapi.testclient.TestClient`:

```python
from fastapi.testclient import TestClient
from triage.api.routes import app

client = TestClient(app)

def test_list_rules():
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
```

**Mocking** — External services (ADO client, Cosmos DB) are mocked with `unittest.mock`:

```python
@patch("triage.api.routes.get_ado")
@patch("triage.api.routes.get_eval")
def test_evaluate(self, mock_get_eval, mock_get_ado):
    mock_ado = MagicMock()
    mock_ado.get_work_item.return_value = {"success": True, ...}
    mock_get_ado.return_value = mock_ado
```

---

## Triage Test Categories

### 1. Model Tests (`test_models.py`)

Tests for all data model classes:
- Default creation and field validation
- Status lifecycle (`active` → `disabled` → `staged`)
- Version tracking for optimistic locking
- Serialization (`to_dict()` / `from_dict()`)
- Entity-specific validation (operators, operations, expressions)
- Referenced IDs extraction (rules from triggers, actions from routes)

### 2. Engine Tests (`test_engines.py`)

**RulesEngine** — All 16 operators:
- String: `equals`, `notEquals`, `contains`, `notContains`, `startsWith`, `matches`
- List: `in`, `notIn`
- Null: `isNull`, `isNotNull`, `isEmpty`
- Hierarchical: `under`
- Numeric: `gt`, `lt`, `gte`, `lte`
- Edge cases: null fields, missing fields, type coercion

**TriggerEngine** — Expression evaluation:
- Simple rule reference
- AND/OR/NOT combinations
- Nested expressions (AND inside OR, etc.)
- Priority ordering (first match wins)
- Disabled/skipped rules (treated as False)
- Missing rules (MissingRuleError)
- Staged trigger filtering

**RoutesEngine** — All 5 operations:
- `set`: Static value assignment
- `set_computed`: Computed values
- `copy`: Field-to-field copy
- `append`: Append to existing (with template variable resolution via shared `_resolve_variables()`)
- `template`: Variable substitution (uses shared `_resolve_variables()` helper)

### 3. API Tests (`test_api.py`, `test_phase2_api.py`)

- All CRUD endpoints (create, read, update, delete, list, copy, status)
- Optimistic locking (409 on version conflict)
- Reference checking (400 on delete of referenced entity)
- Evaluation endpoint (post, dry-run, apply)
- Error responses (404, 400, 409, 500)
- Graceful degradation (empty results when Cosmos offline)

### 4. Hardening Tests (`test_phase5_hardening.py`)

- Staged entity filtering with `include_staged` flag
- Optimistic locking enforcement
- Pre-delete reference check blocking
- Dry-run guard (cannot apply dry-run evaluations)
- Broken reference validation warnings
- Disabled rule warnings in evaluations

---

## Adding New Tests

### Where to Put New Tests

| Test Type | Location | When to Use |
|-----------|----------|-------------|
| Shared module unit test | `tests/unit/` | Testing `shared/*.py` modules in isolation |
| Integration / workflow test | `tests/integration/` | End-to-end tests requiring multiple services |
| Security compliance test | `tests/security/` | OWASP or compliance-related validations |
| Triage model/engine/API test | `apps/triage/tests/` | Triage-specific business logic |

### For a New Shared Module

Add a test file to `tests/unit/`:

```python
# tests/unit/test_cache_manager.py
import pytest
from shared.cache_manager import CacheManager

class TestCacheManager:
    def test_get_returns_none_when_empty(self):
        cm = CacheManager()
        assert cm.get("nonexistent") is None

    def test_set_and_get(self):
        cm = CacheManager()
        cm.set("key", "value")
        assert cm.get("key") == "value"
```

### For a New Rule Operator

Add to `apps/triage/tests/test_engines.py` → `TestRulesEngine`:

```python
def test_new_operator(self):
    """newOperator evaluates correctly"""
    rule = make_rule("r1", "System.Title", "newOperator", "expected")
    engine = RulesEngine()
    results, skipped = engine.evaluate_all(
        [rule],
        {"System.Title": "test value"},
        analysis=None,
    )
    assert results["r1"] is True  # or False
```

### For a New API Endpoint

Add to `apps/triage/tests/test_api.py` or create a new test file:

```python
class TestNewEndpoint:
    def test_happy_path(self):
        response = client.get("/api/v1/new-endpoint")
        assert response.status_code == 200
        data = response.json()
        assert "expected_key" in data
    
    def test_not_found(self):
        response = client.get("/api/v1/new-endpoint/bogus-id")
        assert response.status_code == 404
```

### For a New Model

Add to `apps/triage/tests/test_models.py`:

```python
class TestNewModel:
    def test_create_default(self):
        entity = NewModel()
        assert entity.id == ""
        assert entity.status == EntityStatus.ACTIVE
    
    def test_to_dict_round_trip(self):
        entity = NewModel(id="test-1", name="Test")
        data = entity.to_dict()
        restored = NewModel.from_dict(data)
        assert restored.id == entity.id
```

### For a New Security Control

Add to `tests/security/test_security_controls.py`:

```python
class TestNewSecurityControl:
    """SEC-XX — Description of what's being validated."""

    def test_control_passes(self):
        # Scan source files or config for the violation
        violations = []
        for filepath in _python_files():
            text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
            # ... check for violations ...
        assert violations == [], f"Violations found:\n" + "\n".join(violations)
```

---

## Test Configuration

### conftest.py

`apps/triage/tests/conftest.py` sets up the Python path so `triage.*` imports work. Tests don't require any special setup — all storage is in-memory by default.

### Running Subsets

```bash
# Only model tests
python -m pytest apps/triage/tests/test_models.py

# Only engine tests, with debug output
python -m pytest apps/triage/tests/test_engines.py -v -s

# Tests matching a keyword
python -m pytest -k "trigger"

# Stop on first failure
python -m pytest -x

# Show slowest tests
python -m pytest --durations=10

# Run with coverage (if pytest-cov installed)
python -m pytest --cov=triage --cov=shared --cov-report=term-missing
```

---

## Frontend Build Verification

While there are no frontend unit tests yet, verify the build as a smoke test:

```bash
cd apps/triage/ui
npx vite build
```

Expected: `76 modules transformed` with no errors.
