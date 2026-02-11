# Triage Management API Reference

**Service**: Triage API  
**Port**: 8009  
**Base URL**: `http://localhost:8009`  
**Docs**: `http://localhost:8009/docs` (Swagger UI) | `http://localhost:8009/redoc` (ReDoc)

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [CRUD Endpoints](#crud-endpoints) (Rules, Actions, Triggers, Routes)
4. [Evaluation Endpoints](#evaluation-endpoints)
5. [ADO Integration Endpoints](#ado-integration-endpoints)
6. [Analysis Endpoints](#analysis-endpoints)
7. [Webhook Endpoint](#webhook-endpoint)
8. [Audit Endpoints](#audit-endpoints)
9. [Validation Endpoints](#validation-endpoints)
10. [Health Check](#health-check)
11. [Error Handling](#error-handling)
11. [Schemas](#schemas)

---

## Overview

The Triage API is a FastAPI application that manages the four-layer triage model (Rules → Triggers → Actions → Routes) and orchestrates evaluation of Azure DevOps work items.

All entity CRUD endpoints follow the same REST conventions:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/{entities}` | List (with optional `?status=` filter) |
| `GET` | `/api/v1/{entities}/{id}` | Get single entity |
| `POST` | `/api/v1/{entities}` | Create new entity |
| `PUT` | `/api/v1/{entities}/{id}` | Update (requires `version` for optimistic locking) |
| `DELETE` | `/api/v1/{entities}/{id}` | Soft delete (or `?hard=true` for permanent) |
| `POST` | `/api/v1/{entities}/{id}/copy` | Clone entity |
| `PUT` | `/api/v1/{entities}/{id}/status` | Change status (requires `version`) |
| `GET` | `/api/v1/{entities}/{id}/references` | Cross-references (who uses this entity?) |

---

## Authentication

The API itself does not require authentication tokens. ADO integration uses the Azure CLI credential chain:

1. `AzureCliCredential` — if the user is logged in via `az login`
2. `InteractiveBrowserCredential` — fallback browser-based login

No PAT tokens are used.

---

## CRUD Endpoints

### Rules (`/api/v1/rules`)

Rules are atomic conditions: one field + one operator + one value = True/False.

#### Create Rule

```
POST /api/v1/rules
```

**Request Body** (`RuleCreate`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable rule name |
| `description` | string | No | Purpose of this rule |
| `field` | string | Yes | Field reference — ADO (e.g., `Custom.SolutionArea`) or Analysis (e.g., `Analysis.Category`) |
| `operator` | string | Yes | Comparison operator (see [Operators](#operators)) |
| `value` | any | No | Comparison value (depends on operator) |
| `status` | string | No | `active` \| `disabled` \| `staged` (default: `active`) |

**Response** (201): Created rule document with auto-generated `id`, `version`, timestamps.

#### Update Rule

```
PUT /api/v1/rules/{rule_id}
```

**Request Body** (`RuleUpdate`): Same fields as create, all optional except:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | integer | Yes | Current version for optimistic locking |

**Response** (200): Updated rule document with incremented `version`.  
**Error** (409): Version conflict — another update occurred since you last read.

#### Operators

| Operator | Value Type | Description |
|----------|-----------|-------------|
| `equals` | string | Exact match |
| `notEquals` | string | Not equal |
| `in` | list | Value is in the list |
| `notIn` | list | Value is not in the list |
| `isNull` | — | Field is null/empty |
| `isNotNull` | — | Field has a value |
| `contains` | string | Substring match |
| `notContains` | string | No substring match |
| `startsWith` | string | Prefix match |
| `matches` | string | Regex pattern match |
| `under` | string | Hierarchical path match (e.g., Area Path) |
| `gt` | number | Greater than |
| `lt` | number | Less than |
| `gte` | number | Greater than or equal |
| `lte` | number | Less than or equal |
| `isEmpty` | — | Empty string/list |

---

### Actions (`/api/v1/actions`)

Actions are atomic field assignments: set one field to one value.

#### Create Action

```
POST /api/v1/actions
```

**Request Body** (`ActionCreate`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable action name |
| `description` | string | No | Purpose |
| `field` | string | Yes | ADO field to modify |
| `operation` | string | Yes | Operation type (see below) |
| `value` | any | No | Value to apply |
| `valueType` | string | No | Auto-derived from `operation` if omitted (set→static, copy→field_ref, template→template, set_computed→computed, append→static or template if variables used) |
| `status` | string | No | `active` \| `disabled` \| `staged` |

#### Operations

| Operation | Description | Example |
|-----------|-------------|---------|
| `set` | Set field to a static value | `"Triage"` |
| `set_computed` | Set field to a computed value | Current date |
| `copy` | Copy value from another field | `System.AreaPath` → `Custom.Region` |
| `append` | Append to existing value (supports template variables) | `"Triaged by @{SubmitterAlias}"` |
| `template` | Apply a template with variable substitution | `"@{SubmitterAlias} - Please provide Milestone ID for {Title}"` |

#### Template Variables

Available in `template` and `append` operations:

| Variable | Description |
|----------|-------------|
| `{CreatedBy}` | Work item creator (full email) |
| `{SubmitterAlias}` | Alias from email (`rojyt@microsoft.com` → `@rojyt`) |
| `{WorkItemId}` | ADO work item ID |
| `{Title}` | Work item title |
| `{today()}` | Current UTC date |
| `{currentUser()}` | Authenticated user |
| `{Analysis.Category}` | AI-classified category |
| `{Analysis.Products}` | Detected products |
| `{Analysis.Confidence}` | AI confidence score |
| `{Analysis.Intent}` | Inferred intent |
| `{Analysis.ContextSummary}` | AI-generated summary |

---

### Fields (`/api/v1/fields`)

Field schemas for autocomplete in rule and action forms.

```
GET /api/v1/fields?source=analysis&can_evaluate=true
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | string | Filter by source: `ado`, `analysis` |
| `can_evaluate` | boolean | Include only fields usable in rules |
| `can_set` | boolean | Include only fields usable in actions |
| `group` | string | Filter by display group |

Returns `{ items: [...], total: N }`.

Includes 23 ADO fields and 14 Analysis fields (from the AI pipeline).

---

### Triggers (`/api/v1/triggers`)

Triggers chain rules using AND/OR/NOT logic and map to a route when they match.

#### Create Trigger

```
POST /api/v1/triggers
```

**Request Body** (`TriggerCreate`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable trigger name |
| `description` | string | No | Purpose |
| `priority` | integer | Yes | Evaluation order (lower = higher priority) |
| `expression` | object | Yes | Nested AND/OR expression (see below) |
| `onTrue` | string | Yes | Route ID to execute when expression is True |
| `status` | string | No | `active` \| `disabled` \| `staged` |

#### Expression Format

Expressions are nested JSON objects:

```json
{
  "and": [
    "rule-abc123",
    {"or": ["rule-def456", "rule-ghi789"]},
    {"not": "rule-jkl012"}
  ]
}
```

- **String**: Rule ID reference → looks up True/False result
- **`{"and": [...]}`**: All children must be True (minimum 1 child)
- **`{"or": [...]}`**: Any child must be True (minimum 1 child)
- **`{"not": expr}`**: Inverts the child result

---

### Routes (`/api/v1/routes`)

Routes are ordered collections of actions to execute.

#### Create Route

```
POST /api/v1/routes
```

**Request Body** (`RouteCreate`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable route name |
| `description` | string | No | Purpose |
| `actions` | string[] | Yes | Ordered list of action IDs to execute |
| `status` | string | No | `active` \| `disabled` \| `staged` |

---

### Shared CRUD Operations

These work identically across all four entity types:

#### List

```
GET /api/v1/{entities}?status=active
```

Returns `{ items: [...], count: N, continuationToken: ... }`.  
Returns empty results (not 500) when Cosmos DB is unavailable.

#### Delete

```
DELETE /api/v1/{entities}/{id}?hard=false&version=3
```

- **Soft delete** (default): Sets status to `disabled`
- **Hard delete** (`?hard=true`): Permanently removes from database
- **Reference check**: Blocks deletion if other entities reference this one
- **Optimistic locking**: Optional `version` query parameter

#### Copy

```
POST /api/v1/{entities}/{id}/copy
```

**Body** (optional): `{ "newName": "Copy of My Rule" }`

Creates a clone with a new ID and version 1.

#### Cross-References

```
GET /api/v1/{entities}/{id}/references
```

Returns which other entities reference this one:
- Rule → which triggers reference it
- Action → which routes include it
- Route → which triggers point to it

---

## Evaluation Endpoints

### Evaluate Work Items

```
POST /api/v1/evaluate
```

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workItemIds` | int[] | Yes | ADO work item IDs to evaluate |
| `dryRun` | boolean | No | If true, compute without writing to ADO |

**Response**:
```json
{
  "evaluations": [
    {
      "id": "eval-12345-20260211T100000Z",
      "workItemId": 12345,
      "analysisState": "Routed",
      "matchedTrigger": "dt-abc123",
      "appliedRoute": "route-def456",
      "actionsExecuted": ["action-1", "action-2"],
      "ruleResults": {"rule-1": true, "rule-2": false},
      "fieldsChanged": {"Custom.SolutionArea": {"from": "", "to": "AMEA"}},
      "errors": [],
      "isDryRun": false,
      "summaryHtml": "<h3>Triage Summary</h3>...",
      "adoLink": "https://dev.azure.com/..."
    }
  ],
  "count": 1,
  "errors": []
}
```

### Test Evaluation (Dry Run)

```
POST /api/v1/evaluate/test
```

Same as `/evaluate` but always forces `dryRun: true`.

### Apply Evaluation to ADO

```
POST /api/v1/evaluate/apply
```

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `evaluationId` | string | Yes | Evaluation to apply |
| `workItemId` | integer | Yes | ADO work item to update |
| `revision` | integer | No | Expected revision for conflict detection |

**Response**: `{ success, workItemId, fieldsUpdated, commentPosted, newRevision }`

**Notes**:
- Dry-run evaluations cannot be applied (returns 400)
- Revision mismatch returns 409 Conflict

### Evaluation History

```
GET /api/v1/evaluations/{work_item_id}?limit=20
```

Returns past evaluations for a specific work item.

---

## ADO Integration Endpoints

### Triage Queue

```
GET /api/v1/ado/queue?state=Pending&area_path=UAT\MCAPS&max_results=100
```

Returns work item IDs from ADO pending triage.

### Triage Queue (Hydrated)

```
GET /api/v1/ado/queue/details?state=Pending&max_results=100
```

Returns full item summaries (title, state, area path, assigned to, etc.) in a single call.

### Single Work Item

```
GET /api/v1/ado/workitem/{work_item_id}
```

Returns all fields for inspection.

### ADO Connection Status

```
GET /api/v1/ado/status
```

Health check for ADO connectivity.

### Field Definitions

```
GET /api/v1/ado/fields
```

Returns metadata for all fields on the Action work item type.

---

## Analysis Endpoints

The hybrid analysis engine classifies work items using pattern matching + optional Azure OpenAI (LLM).

### Analysis Engine Status

```
GET /api/v1/analyze/status
```

Returns the current state of the analysis engine and AI availability.

**Response**:
```json
{
  "available": true,
  "aiAvailable": true,
  "mode": "AI-Powered",
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `available` | boolean | Whether the analysis engine can be initialized |
| `aiAvailable` | boolean | Whether Azure OpenAI is configured and reachable |
| `mode` | string | `"AI-Powered"` \| `"Pattern Only"` \| `"Unavailable"` |
| `error` | string? | Error message if `available` is false |

### Run Analysis

```
POST /api/v1/analyze
```

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workItemIds` | int[] | Yes | ADO work item IDs to analyze |

Fetches title/description from ADO, runs the hybrid analyzer (pattern + LLM), stores results in the `analysis-results` Cosmos container, and returns classification summaries.

### Get Analysis Detail

```
GET /api/v1/analysis/{work_item_id}
```

Returns the full stored analysis result for a single work item, including category, intent, confidence, key concepts, Azure services, technologies, technical areas, and context summary.

### Batch Analysis Lookup

```
GET /api/v1/analysis/batch?ids=12345,67890
```

Returns analysis summaries for multiple work items in a single call. Used by the QueuePage on load to populate analysis status indicators.

### Set Analysis State

```
POST /api/v1/ado/analysis-state
```

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workItemIds` | int[] | Yes | ADO work item IDs |
| `state` | string | Yes | New state (e.g., `Awaiting Approval`, `Pending`) |

Updates the `Custom.ROBAnalysisState` field on the specified ADO work items.

---

## Webhook Endpoint

```
POST /api/v1/webhook/workitem
```

Receives ADO Service Hook notifications. Automatically triggers evaluation when a work item is created or updated.

### Webhook Stats

```
GET /api/v1/webhook/stats
```

Returns processing statistics (received, evaluated, skipped counts).

---

## Audit Endpoints

### List Audit Entries

```
GET /api/v1/audit?entity_type=rule&actor=user@example.com&limit=50
```

### Entity Audit History

```
GET /api/v1/audit/{entity_type}/{entity_id}?limit=50
```

---

## Validation Endpoints

### Get Warnings

```
GET /api/v1/validation/warnings
```

Returns system-wide validation warnings:
- Orphaned rules (not referenced by any trigger)
- Orphaned actions (not referenced by any route)
- Broken references (triggers pointing to deleted rules/routes)
- Duplicate priorities (triggers with the same priority)

### Cross-Reference Lookup

```
GET /api/v1/validation/references/{entity_type}/{entity_id}
```

---

## Health Check

```
GET /health
```

Returns `{ status: "healthy"|"degraded", service: "triage-api", version: "1.0.0", database: {...} }`.

---

## Error Handling

| Status Code | Meaning |
|-------------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request / validation error / still referenced |
| 404 | Entity not found |
| 409 | Version conflict (optimistic locking) |
| 500 | Internal server error |
| 502 | ADO upstream error |
| 503 | Service unavailable (ADO connection failed) |

All errors return: `{ "detail": "Human-readable error message" }`

**Graceful degradation**: List and audit endpoints return empty results (not 500) when Cosmos DB is unavailable, so the UI can render with empty state.

---

## Schemas

Full Pydantic schema definitions are in `triage/api/schemas.py`. Interactive schema docs are available at `/docs` (Swagger UI) when the API is running.
