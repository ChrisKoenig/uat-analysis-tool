# ADO Integration Guide

How the Triage Management System integrates with Azure DevOps.

---

## Authentication

### Credential Chain

The system uses the Azure Identity library — **no PAT tokens**:

1. **`AzureCliCredential`** — if the user is logged in via `az login`
2. **`InteractiveBrowserCredential`** — opens a browser window for login

The credential is obtained once via `AzureDevOpsClient` (from `ado_integration.py`) and shared across all services.

### Setup

```bash
az login
```

The logged-in user needs **Reader** access to both ADO organizations.

---

## Dual-Organization Pattern

The system uses two separate ADO organizations for safety:

| Operation | Organization | Project | Purpose |
|-----------|-------------|---------|---------|
| **Read** | `unifiedactiontracker` | Unified Action Tracker | Production data — real Actions |
| **Write** | `unifiedactiontrackertest` | Unified Action Tracker Test | Safe for development |

This matches the existing application pattern: real Actions come from production, but all write operations target the test org to avoid accidental changes.

### Configuration

Defined in `triage/services/ado_client.py` → `TriageAdoConfig`:

```python
# Read: Production org (real data)
READ_ORGANIZATION = "unifiedactiontracker"
READ_PROJECT = "Unified Action Tracker"

# Write: Test org (safe)
WRITE_ORGANIZATION = "unifiedactiontrackertest"
WRITE_PROJECT = "Unified Action Tracker Test"
```

---

## ADO Client Architecture

The `AdoClient` is a thin adapter that wraps the existing `AzureDevOpsClient`:

```
ado_integration.py (existing)
  └── AzureDevOpsClient
        ├── Authentication chain
        ├── Credential caching
        └── Base API methods

triage/services/ado_client.py (new)
  └── AdoClient (wraps AzureDevOpsClient)
        ├── Dual-org routing (read vs write)
        ├── Triage queue WIQL query
        ├── Batch work item fetch (200-item chunks)
        ├── Comments API
        ├── 409 conflict detection
        └── Normalized response format
```

**Key principle**: Reuse, don't duplicate. Auth, credentials, and headers come from the existing client.

---

## Read Operations

All read operations target the **production** organization:

### Get Work Item

```python
result = ado_client.get_work_item(12345)
# → {"success": True, "id": 12345, "rev": 42, "fields": {...}}
```

### Triage Queue Query

```python
result = ado_client.query_triage_queue(
    state_filter="Pending",
    area_path="UAT\\MCAPS",
    max_results=100
)
# → {"success": True, "work_item_ids": [12345, 12346, ...], "count": 50}
```

Uses WIQL (Work Item Query Language) to find items by `Custom.ROBAnalysisState` and `System.AreaPath`.

### Batch Fetch

```python
result = ado_client.get_work_items_batch([12345, 12346, 12347, ...])
```

Automatically chunks requests into groups of 200 (ADO API limit).

**Error handling (`errorPolicy=Omit`)**: The batch URL includes `&errorPolicy=Omit` so that invalid or not-found work item IDs do not cause the entire batch to fail. Instead, ADO returns HTTP 200 with null placeholders in the `value` array for omitted items. The client:
1. Skips null entries (`if item is None: continue`)
2. Tracks successfully fetched IDs in a `fetched_ids` set
3. Compares requested IDs against `fetched_ids` to detect and report omitted IDs individually in `failed_ids`

This means a batch of `[713010, 731001, 712931]` where 731001 doesn't exist returns 2 successful items + `failed_ids: [731001]` instead of failing entirely.

### Field Definitions

```python
result = ado_client.get_field_definitions()
```

Returns metadata for all fields on the Action work item type.

---

## Write Operations

All write operations target the **test** organization:

### Update Work Item

```python
result = ado_client.update_work_item(
    work_item_id=12345,
    field_changes=[FieldChange("Custom.SolutionArea", old, "AMEA")],
    revision=42  # Optional: for conflict detection
)
```

Converts `FieldChange` objects to JSON Patch format for the ADO API. Returns `{"conflict": True}` on revision mismatch (409).

### Add Comment

```python
result = ado_client.add_comment(12345, "<p>Triage Summary...</p>")
```

Posts HTML to the work item's Discussion thread via the Comments API.

---

## ADO Field Catalog

Key ADO fields used by the triage system:

| Reference Name | Display Name | Type | Usage |
|---------------|-------------|------|-------|
| `Custom.ROBAnalysisState` | ROB Analysis State | String | Primary triage state field |
| `Custom.SolutionArea` | Solution Area | String | Routing destination |
| `Custom.MilestoneID` | Milestone ID | Integer | Milestone reference |
| `System.AreaPath` | Area Path | TreePath | Hierarchical team path |
| `System.AssignedTo` | Assigned To | Identity | Current assignee |
| `System.State` | State | String | Work item state |
| `System.Title` | Title | String | Item title |
| `System.WorkItemType` | Work Item Type | String | Always "Action" for triage |

### Field Resolution

Rules resolve field values from the work item's `fields` dictionary:

```python
# Direct lookup
value = work_item_data["Custom.SolutionArea"]

# Identity fields return objects or strings
assigned = fields.get("System.AssignedTo", "")
if isinstance(assigned, dict):
    display_name = assigned.get("displayName", "")
```

---

## Webhook Integration

The system can receive real-time notifications from ADO via Service Hooks.

### Setup in ADO

1. Go to **Project Settings → Service Hooks → New Subscription**
2. Service: **Web Hooks**
3. Trigger: "Work item created" or "Work item updated"
4. Filters:
   - Work Item Type = Action
   - Area Path UNDER your triage scope
5. Action URL: `https://{host}:8009/api/v1/webhook/workitem`

### Webhook Flow

```
ADO Service Hook → POST /api/v1/webhook/workitem
     │
     ▼
WebhookProcessor
     ├── Validate payload structure
     ├── Check work item type (Action only)
     ├── Determine if evaluation should trigger
     │     └── (filters, deduplication)
     └── If yes: re-fetch full work item data → run evaluation pipeline
```

The webhook endpoint returns 200 immediately (ADO expects fast responses). Evaluation runs synchronously for now.

### Webhook Stats

```
GET /api/v1/webhook/stats
```

Returns counts of received, evaluated, and skipped webhooks.

---

## API Endpoints for ADO

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ado/queue` | GET | Triage queue (work item IDs) |
| `/api/v1/ado/queue/details` | GET | Triage queue (hydrated summaries) |
| `/api/v1/ado/workitem/{id}` | GET | Single work item details |
| `/api/v1/ado/status` | GET | ADO connection health check |
| `/api/v1/ado/fields` | GET | Field definitions for Action type |
| `/api/v1/webhook/workitem` | POST | Receive Service Hook notifications |
| `/api/v1/webhook/stats` | GET | Webhook processing statistics |

---

## Connection Health

Check ADO connectivity:

```bash
curl http://localhost:8009/api/v1/ado/status
```

Returns:
```json
{
  "connected": true,
  "organization": "unifiedactiontrackertest",
  "project": "Unified Action Tracker Test",
  "message": "Connected successfully"
}
```

If ADO is unreachable, evaluation endpoints return 503; queue endpoints return 502.
