# Testing Guide

How to run, understand, and extend the Triage Management System test suite.

---

## Quick Start

```bash
# Run all tests
python -m pytest triage/tests/ -q

# Run with verbose output
python -m pytest triage/tests/ -v

# Run a specific test file
python -m pytest triage/tests/test_models.py -v

# Run a specific test class
python -m pytest triage/tests/test_engines.py::TestTriggerEngine -v

# Run a specific test
python -m pytest triage/tests/test_models.py::TestTrigger::test_create_simple_trigger -v
```

---

## Test Suite Overview

**313 tests** across 8 modules, running in ~2 seconds (all in-memory, no external dependencies).

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

---

## Test Architecture

### No External Dependencies

All tests run without:
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

## Test Categories

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
- `append`: Append to existing
- `template`: Variable substitution

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

### For a New Rule Operator

Add to `test_engines.py` → `TestRulesEngine`:

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

Add to `test_api.py` or create a new test file:

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

Add to `test_models.py`:

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

---

## Test Configuration

### conftest.py

The `triage/tests/conftest.py` file contains shared fixtures. Tests don't require any special setup — all storage is in-memory by default.

### Running Subsets

```bash
# Only model tests
python -m pytest triage/tests/test_models.py

# Only engine tests, with debug output
python -m pytest triage/tests/test_engines.py -v -s

# Tests matching a keyword
python -m pytest triage/tests/ -k "trigger"

# Stop on first failure
python -m pytest triage/tests/ -x

# Show slowest tests
python -m pytest triage/tests/ --durations=10
```

---

## Frontend Build Verification

While there are no frontend unit tests yet, verify the build as a smoke test:

```bash
cd triage-ui
npx vite build
```

Expected: `76 modules transformed` with no errors.
