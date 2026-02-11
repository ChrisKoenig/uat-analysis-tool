# Triage Management System - Design Document

**Created**: February 10, 2026  
**Updated**: February 11, 2026  
**Status**: Phases 1–5 Complete (Foundation through Hardening)  
**Author**: GitHub Copilot + Brad Price

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Four-Layer Model](#four-layer-model)
4. [Data Flow](#data-flow)
5. [Analysis State Machine](#analysis-state-machine)
6. [ADO Field Catalog](#ado-field-catalog)
7. [Operators & Comparisons](#operators--comparisons)
8. [Route Actions](#route-actions)
9. [Cosmos DB Schema](#cosmos-db-schema)
10. [API Design](#api-design)
11. [Admin UI](#admin-ui)
12. [Triage UI](#triage-ui)
13. [Build Phases](#build-phases)
14. [Key Design Decisions](#key-design-decisions)

---

## System Overview

The Triage Management System automates the triage process for Azure DevOps (ADO) Actions. It analyzes incoming items, validates data quality using triggers, applies routing rules to determine the destination team, and presents results for human review in the native ADO interface.

### Goals

- **Reduce manual effort**: Automate analysis, rule evaluation, and routing
- **Improve consistency**: Rules-based routing eliminates subjective decisions
- **Enable evolution**: Start with human confirmation, move to full automation as confidence grows
- **Provide traceability**: Every evaluation logged and auditable
- **Support extensibility**: Admins manage rules/routes through UI without code changes

---

## Architecture

### System Components

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│ React Frontend  │────▶│ Triage API      │────▶│ Cosmos DB    │
│ (port 3000)     │     │ (port 8009)     │     │              │
│                 │     │                 │     │ 8 containers │
│ - Admin UI      │     │ - CRUD APIs     │     │              │
│ - Triage UI     │     │ - Rules Engine  │     └──────────────┘
│ - Visual Design │     │ - Trigger Engine│            │
│ - Test mode     │     │ - Routes Engine │     ┌──────────────┐
└─────────────────┘     │ - ADO Integration│───▶│ Azure DevOps │
                        │ - Audit Logging │     │              │
                        └─────────────────┘     └──────────────┘
                               │
                        ┌──────────────┐
                        │ Analysis     │
                        │ Engine       │
                        │ (existing)   │
                        └──────────────┘
```

### Integration with Existing Application

The triage system is a **new standalone service** alongside the existing microservices:

| Service | Port | Purpose |
|---------|------|---------|
| Main Web App | 5003 | Existing analysis UI |
| API Gateway | 8000 | Existing routing |
| Context Analyzer | 8001 | Existing |
| Search Service | 8002 | Existing |
| Enhanced Matching | 8003 | Existing |
| UAT Management | 8004 | Existing |
| LLM Classifier | 8005 | Existing |
| Embedding Service | 8006 | Existing |
| Vector Search | 8007 | Existing |
| Admin Portal | 8008 | Existing |
| **Triage API** | **8009** | **NEW - Rules/Routes/Evaluation** |
| **React UI** | **3000** | **NEW - Admin & Triage Interface** |

---

## Four-Layer Model

The system uses four composable building blocks. Each layer is independently
managed and reusable across the system.

```
┌─────────────┐     ┌─────────────────────┐     ┌─────────────┐     ┌─────────────┐
│   RULES     │────▶│      TRIGGERS       │────▶│   ACTIONS   │────▶│   ROUTES    │
│  (atomic)   │     │  (chain rules)      │     │  (atomic)   │     │ (group      │
│             │     │                     │     │             │     │  actions)   │
│ Single      │     │ AND/OR combos       │     │ Single      │     │ Collection  │
│ condition   │     │ of rules            │     │ field set   │     │ of actions  │
│ = T/F       │     │ Priority ordered    │     │             │     │ to execute  │
│             │     │ First TRUE wins     │     │             │     │             │
└─────────────┘     └─────────────────────┘     └─────────────┘     └─────────────┘
   Reusable            Reusable                    Reusable            Reusable
```

### Layer 1: Rules (Atomic Conditions)

Each rule evaluates a single condition against a work item's data, producing True or False.

**Example:**
```
Rule 1: Milestone ID is Null
Rule 2: Milestone Status = "Blocked"
Rule 3: Analysis Category = "Feature Request"
Rule 4: Analysis Product contains "Route Server"
Rule 9: Solution Area = "AMEA"
```

### Layer 2: Triggers (Rule Chains)

Combine rules with AND/OR logic. Evaluated in priority order. First TRUE match wins.
Each trigger points to a route to execute on TRUE. No ELSE path - if FALSE, evaluation
continues to the next trigger.

**Example:**
```
Priority 10: IF Rule 1 AND Rule 3                               → Route 1
Priority 20: IF Rule 2 AND (Rule 3 OR Rule 7)                   → Route 3
Priority 30: IF Rule 3 AND (Rule 4 OR Rule 5 OR Rule 6) AND Rule 7 → Route 2
Priority 40: IF ((Rule 5 OR Rule 6 OR Rule 7) AND NOT Rule 2) OR Rule 9 → Route 15
```

### Layer 3: Actions (Atomic Field Changes)

Each action defines a single field assignment or operation. Actions are the
atomic building blocks that get composed into routes — just as rules are the
atomic conditions that get composed into triggers.

**Example:**
```
Action 1: Set Area Path = "UAT\MCAPS\AI"
Action 2: Set Assigned To = "@AI Apps and Agents Triage"
Action 3: Append to Discussion = "@{CreatedBy} - Missing Milestone ID..."
Action 4: Set State = "Done"
```

### Layer 4: Routes (Action Collections)

Group actions together into reusable pipelines. When a route executes, all
its actions are applied in order. The relationship mirrors Rules → Triggers:
Actions are composed into Routes.

**Example:**
```
Route 1 (AI Triage):     Action 1, Action 2
Route 5 (Needs Info):    Action 3, set Analysis.State = "Needs Info"
Route 8 (Self-Service):  Action 3 (instructions), Action 4 (close)
```

---

## Data Flow

### Processing Pipeline

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────┐     ┌──────────────┐
│  ADO Item    │────▶│ 1. Quality Check  │────▶│ 2. Evaluate  │────▶│ 3. Execute   │
│  (from queue)│     │    (analysis)     │     │    ALL rules  │     │    winning   │
│              │     │                   │     │    → T/F each │     │    route     │
└──────────────┘     └───────────────────┘     └──────┬───────┘     └──────┬───────┘
                                                      │                    │
                                                      ▼                    ▼
                                               ┌──────────────┐    ┌──────────────┐
                                               │ 4. Walk      │    │ 5. Update    │
                                               │    priority  │    │    ADO item   │
                                               │    order     │    │    + set state│
                                               │    1st TRUE  │    │              │
                                               │    wins      │    │              │
                                               └──────────────┘    └──────────────┘
```

### Evaluation Logic

1. **Evaluate ALL rules** against the work item → store T/F for each rule
2. **Walk triggers** in priority order using stored results
3. **First TRUE match** → execute that trigger's route
4. **If no match** → Analysis.State = "No Match" (flag for manual triage)
5. **Log everything** → evaluations container in Cosmos DB

### Human Review (in ADO)

After processing, the triage person:
1. Opens items from "Awaiting Approval" query in ADO
2. Sees fields already set by the system + Analysis Summary
3. Reviews and either:
   - Sets Analysis.State = "Approved" (no changes needed)
   - Makes adjustments, sets Analysis.State = "Override"
4. Item drops out of the approvals query. Done.

### Trigger Model

- **Phase 1**: Manual - triage person clicks "Evaluate" in the React UI
- **Future**: Automatic via ADO Service Hooks (webhooks)

---

## Analysis State Machine

```
(new item) → Pending → Processing...
                          │
              ┌───────────┼───────────────┐
              ▼           ▼               ▼
           MATCH     INCOMPLETE       NO MATCH
              │           │               │
              ▼           ▼               ▼
      Awaiting       Needs Info       No Match
      Approval      (ping submitter)  (manual triage)
              │           │
              │           │ (data arrives,
              │           │  next eval cycle)
      ┌───────┴───┐      │
      ▼           ▼      ▼
  Approved    Override   Re-evaluate...
```

### Analysis.State Values

| Value | Meaning | Terminal? |
|-------|---------|-----------|
| **Pending** | Received, not yet processed | No |
| **Awaiting Approval** | Route matched and applied, ready for human review | No |
| **Needs Info** | Missing data, submitter pinged via Discussion comments | No |
| **Redirected** | Out of scope, instructions posted, item being closed | No |
| **No Match** | No trigger matched, needs manual triage | No |
| **Error** | Pipeline error during evaluation | No |
| **Approved** | Human confirmed routing, no changes made | Yes |
| **Override** | Human confirmed routing with modifications | Yes |

Re-triggerable states (allow re-evaluation): Pending, Needs Info, No Match, Error.

### ADO Fields for State Management

| Field | Purpose |
|-------|---------|
| `Custom.ROBAnalysisState` | Analysis State lifecycle tracking |
| `Custom.pChallengeDetails` | HTML summary (Quality Score, Analysis, Reasoning, Rules Applied, Route Selected) |

---

## ADO Field Catalog

### Fields Evaluated (Read) - 27 fields

| Field | Display Name | Notes |
|-------|-------------|-------|
| `System.Id` | ID | Work item identifier |
| `System.AssignedTo` | Assigned To | Current owner |
| `System.AreaPath` | Area Path | Hierarchical, supports "under" operator |
| `Custom.StatusUpdate` | Status Update | |
| `Title` | Title | |
| `Description` | Description | Rich text |
| `Custom.CustomerScenarioandDesiredOutcome` | Customer Scenario | Key for analysis |
| `Custom.CustomerImpactData` | Customer Impact Data | |
| `Custom.AssignToCorp` | Assign To Corp | Flag for corp assistance needed |
| `Custom.Requestors` | Requestors | |
| `Custom.Account` | Account | Customer account |
| `Custom.AzurePreferredRegion` | Azure Preferred Region | |
| `Custom.TranslatedAccountName` | Translated Account Name | |
| `Custom.TPID` | TPID | Top Parent ID |
| `Custom.AreaField` | Area Field | |
| `Custom.EOU` | EOU | |
| `Custom.Segment` | Segment | |
| `Custom.Opportunity_ID` | Opportunity ID | |
| `Custom.SalesPlay` | Sales Play | |
| `Custom.SolutionArea` | Solution Area | Key for routing |
| `Custom.MilestoneID` | Milestone ID | |
| `Custom.MilestoneStatus` | Milestone Status | |
| `Custom.MilestoneReason` | Milestone Reason | |
| `Custom.MilestoneWorkload` | Milestone Workload | |
| `Custom.NoNAI_RequestType` | NoNAI Request Type | |
| `Custom.NoNAI_SR` | NoNAI SR | |
| `Custom.33714421-65d5-488a-b6d9-4e0997d84b74` | Ref ID | |
| `Discussion` | Discussion | Comments thread |
| `Custom.ROBAnalysisState` | Analysis State | Also set |

### Fields Set (Write) - 17 fields

| Field | Display Name | Notes |
|-------|-------------|-------|
| `State` | State | ADO workflow state |
| `Custom.SubState` | Sub-State | |
| `System.AreaPath` | Area Path | Also evaluated |
| `System.AssignedTo` | Assigned To | Primary routing target |
| `Custom.ClosureStatement` | Closure Statement | |
| `Custom.AssignToCorp` | Assign To Corp | Also evaluated |
| `Custom.ActionPriorityField` | Action Priority | |
| `Custom.Contributor1` | Contributor 1 | |
| `Custom.Contributor2` | Contributor 2 | |
| `Custom.pTriageType` | Triage Type | Destination analysis |
| `Custom.Cloud_Impacted` | Cloud Impacted | |
| `Custom.NoNAI_RequestType` | NoNAI Request Type | Also evaluated |
| `Custom.NoNAI_SR` | NoNAI SR | Also evaluated |
| `Custom.33714421-65d5-488a-b6d9-4e0997d84b74` | Ref ID | Also evaluated |
| `Discussion` | Discussion | @ping comments, also evaluated |
| `Custom.ROBAnalysisState` | Analysis State | Also evaluated |
| `Custom.pChallengeDetails` | Challenge Details | HTML analysis summary |

### Field Schema Source

Field metadata (types, allowed values, required flags) pulled dynamically from ADO REST API:
```
GET .../_apis/wit/workitemtypes/{type}/fields?$expand=All&api-version=7.1
```

Enriched with custom metadata: valid operators per field, display grouping, source designation.

---

## Operators & Comparisons

| Operator | Description | Applicable Types | Example |
|----------|-------------|-----------------|---------|
| `equals` | Exact match | All | `Service = "Azure ML"` |
| `notEquals` | Not equal | All | `Status != "Closed"` |
| `in` | Value in list | String, Number | `Service IN ["Azure ML", "OpenAI"]` |
| `notIn` | Value not in list | String, Number | `Service NOT IN [list]` |
| `contains` | Substring match | String | `Title contains "urgent"` |
| `notContains` | Substring not found | String | `Title not contains "test"` |
| `startsWith` | Prefix match | String | `AreaPath startsWith "UAT\\"` |
| `under` | Hierarchical path match | TreePath | `AreaPath under "UAT\\MCAPS"` |
| `matches` | Regex pattern | String | `Description matches "regex"` |
| `isNull` | Field is empty | All | `Milestone is null` |
| `isNotNull` | Field has value | All | `Milestone is not null` |
| `gt` | Greater than | Number, Date | `Priority > 2` |
| `lt` | Less than | Number, Date | `Priority < 3` |
| `gte` | Greater than or equal | Number, Date | `Priority >= 2` |
| `lte` | Less than or equal | Number, Date | `Priority <= 3` |

---

## Route Actions

| Operation | Description | Example |
|-----------|-------------|---------|
| `set` | Set static value | `AssignedTo = "@Analytics Triage"` |
| `set_computed` | Set computed value | `TriagedDate = today()` |
| `copy` | Copy from another field | `AssignedTo = copyFrom("CreatedBy")` |
| `append` | Append to existing value | `Tags = append("Triaged")` |
| `template` | Set with variable substitution | `Discussion = "@{CreatedBy} - Please provide..."` |

### Template Variables

| Variable | Resolves To |
|----------|-------------|
| `{CreatedBy}` | Work item creator (`System.CreatedBy`) |
| `{WorkItemId}` | Work item ID (`System.Id`) |
| `{Title}` | Work item title |
| `{today()}` | Current date (UTC, YYYY-MM-DD) |
| `{currentUser()}` | Authenticated user |
| `{Analysis.Category}` | Analysis result category |
| `{Analysis.Products}` | Detected products (comma-separated) |
| `{Analysis.Confidence}` | Analysis confidence score |
| `{Analysis.Intent}` | Detected intent |
| `{Analysis.ContextSummary}` | Analysis context summary |

> `Analysis.*` variables resolve only when analysis data is available.
> Unresolved variables are left as-is with a warning logged.

---

## Cosmos DB Schema

**Database**: `triage-management`

### Container: rules

**Partition Key**: `/status`

```json
{
  "id": "rule-1",
  "name": "Milestone ID is Null",
  "description": "Checks if the Milestone ID field is empty",
  "status": "active",
  "field": "Custom.MilestoneID",
  "operator": "isNull",
  "value": null,
  "version": 1,
  "createdBy": "brad.price@microsoft.com",
  "createdDate": "2026-02-10T09:00:00Z",
  "modifiedBy": "brad.price@microsoft.com",
  "modifiedDate": "2026-02-10T09:00:00Z"
}
```

### Container: actions

**Partition Key**: `/status`

```json
{
  "id": "action-1",
  "name": "Set Area Path to AI",
  "description": "Routes to the AI Apps and Agents team area",
  "status": "active",
  "field": "System.AreaPath",
  "operation": "set",
  "value": "UAT\\MCAPS\\AI",
  "valueType": "static",
  "version": 1,
  "createdBy": "brad.price@microsoft.com",
  "createdDate": "2026-02-10T09:00:00Z",
  "modifiedBy": "brad.price@microsoft.com",
  "modifiedDate": "2026-02-10T09:00:00Z"
}
```

### Container: triggers

**Partition Key**: `/status`

```json
{
  "id": "dt-10",
  "name": "No Milestone Feature Request",
  "description": "Routes feature requests without milestones to AI Triage",
  "status": "active",
  "priority": 10,
  "expression": {
    "and": ["rule-1", "rule-3"]
  },
  "onTrue": "route-1",
  "version": 1,
  "createdBy": "brad.price@microsoft.com",
  "createdDate": "2026-02-10T09:00:00Z",
  "modifiedBy": "brad.price@microsoft.com",
  "modifiedDate": "2026-02-10T09:00:00Z"
}
```

### Container: routes

**Partition Key**: `/status`

```json
{
  "id": "route-1",
  "name": "AI Triage Team",
  "description": "Routes to AI Apps and Agents Triage team",
  "status": "active",
  "actions": ["action-1", "action-2"],
  "version": 1,
  "createdBy": "brad.price@microsoft.com",
  "createdDate": "2026-02-10T09:00:00Z",
  "modifiedBy": "brad.price@microsoft.com",
  "modifiedDate": "2026-02-10T09:00:00Z"
}
```

### Container: evaluations

**Partition Key**: `/workItemId`

```json
{
  "id": "eval-12345-20260210-093000",
  "workItemId": 12345,
  "date": "2026-02-10T09:30:00Z",
  "evaluatedBy": "system",
  "ruleResults": {
    "rule-1": true,
    "rule-2": false,
    "rule-3": true,
    "rule-5": true
  },
  "skippedRules": ["rule-4"],
  "matchedTrigger": "dt-10",
  "appliedRoute": "route-1",
  "actionsExecuted": ["action-1", "action-2"],
  "analysisState": "Awaiting Approval",
  "summaryHtml": "<html>...</html>",
  "fieldsChanged": {
    "System.AssignedTo": { "from": null, "to": "@AI Triage" },
    "System.AreaPath": { "from": "UAT\\Triage", "to": "UAT\\MCAPS\\AI" }
  }
}
```

### Container: analysis-results

**Partition Key**: `/workItemId`

```json
{
  "id": "analysis-12345-20260210",
  "workItemId": 12345,
  "timestamp": "2026-02-10T09:30:00Z",
  "originalTitle": "Need GPU capacity for ML training",
  "originalDescription": "We need additional GPU...",
  "category": "feature_request",
  "intent": "requesting_feature",
  "confidence": 0.94,
  "source": "hybrid",
  "agreement": true,
  "businessImpact": "high",
  "technicalComplexity": "medium",
  "urgencyLevel": "high",
  "detectedProducts": ["Azure Machine Learning"],
  "azureServices": ["machine learning"],
  "complianceFrameworks": [],
  "technologies": ["GPU"],
  "regions": ["West US"],
  "businessDomains": [],
  "technicalAreas": ["compute"],
  "keyConcepts": ["GPU capacity", "ML training"],
  "semanticKeywords": ["azure ml", "gpu", "capacity"],
  "contextSummary": "Customer needs GPU capacity...",
  "reasoning": "Request mentions GPU capacity...",
  "patternCategory": "feature_request",
  "patternConfidence": 0.88,
  "categoryScores": { "feature_request": 0.88, "capacity": 0.45 },
  "detectedProducts": ["Azure Machine Learning"],
  "technicalIndicators": [],
  "relevantCorrections": [],
  "similarIssues": [],
  "aiAvailable": true,
  "aiError": null
}
```

### Container: field-schema

**Partition Key**: `/source`

```json
{
  "id": "System.AreaPath",
  "displayName": "Area Path",
  "type": "treePath",
  "source": "ado",
  "canEvaluate": true,
  "canSet": true,
  "operators": ["equals", "under", "startsWith"],
  "allowedValues": [],
  "required": false,
  "group": "Standard"
}
```

### Container: audit-log

**Partition Key**: `/entityType`

```json
{
  "id": "audit-20260210-093000-abc123",
  "timestamp": "2026-02-10T09:30:00Z",
  "action": "rule.update",
  "actor": "brad.price@microsoft.com",
  "entityType": "rule",
  "entityId": "rule-1",
  "changes": {
    "status": { "from": "active", "to": "disabled" }
  },
  "correlationId": "abc-123"
}
```

---

## API Design

### Base URL: `http://localhost:8009/api/v1`

### Entity CRUD APIs (Rules, Actions, Triggers, Routes)

All four entity types share the same 8-endpoint pattern:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/{entities}` | List all (filterable by `?status=`) |
| `GET` | `/{entities}/{id}` | Get single entity |
| `POST` | `/{entities}` | Create entity |
| `PUT` | `/{entities}/{id}` | Update entity (optimistic locking via `version`) |
| `DELETE` | `/{entities}/{id}` | Soft delete (`?hard=true` for permanent) |
| `POST` | `/{entities}/{id}/copy` | Clone entity |
| `PUT` | `/{entities}/{id}/status` | Change status (active/disabled/staged) |
| `GET` | `/{entities}/{id}/references` | Cross-references (which triggers use this rule, etc.) |

Where `{entities}` is one of: `rules`, `actions`, `triggers`, `routes` (32 endpoints total).

Delete is blocked if the entity is still referenced by other entities.

### Evaluation API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/evaluate` | Evaluate work item(s) — full pipeline |
| `POST` | `/evaluate/test` | Dry run — no ADO updates, results stored |
| `POST` | `/evaluate/apply` | Apply a stored evaluation to ADO |
| `GET` | `/evaluations/{workItemId}` | Get evaluation history for a work item |

### ADO Integration API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/ado/queue` | Fetch triage queue work item IDs |
| `GET` | `/ado/queue/details` | Fetch queue with hydrated fields |
| `GET` | `/ado/workitem/{id}` | Fetch a single work item from ADO |
| `GET` | `/ado/status` | ADO connection health check |
| `GET` | `/ado/fields` | ADO field definitions for the Action work item type |

### Webhook API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook/workitem` | Receive ADO Service Hook notifications |
| `GET` | `/webhook/stats` | Webhook processing statistics |

### Validation API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/validation/warnings` | System-wide validation (orphans, broken refs, dup priorities) |
| `GET` | `/validation/references/{type}/{id}` | Entity reference lookup |

### Audit API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/audit` | List audit entries (filterable by entity_type, actor) |
| `GET` | `/audit/{entityType}/{entityId}` | Audit history for specific entity |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health + Cosmos DB status |

**Total: 48 endpoints** (32 CRUD + 16 specialized)

---

## Admin UI

### Tech Stack
- **React** (Vite) with blade-style layout (Azure portal pattern)
- **FastAPI** backend API (port 8009)

### Layout

Left navigation (sidebar):

| Section | Items |
|---------|-------|
| Operations | Dashboard, Queue, Evaluate |
| Configuration | Rules, Triggers, Actions, Routes |
| System | Validation, Audit Log, Eval History |

> **Design note:** The configuration nav order follows the compositional
> hierarchy — Rules are atomic conditions composed into Triggers; Actions are
> atomic operations composed into Routes.

### Features (Implemented)

- **CRUD** for all four layers (rules, triggers, actions, routes — in compositional order)
- **Expression builder** for triggers (nested AND/OR groups)
- **Visual route designer** for composing actions into routes
- **Status management**: Active / Disabled / Staged per item
- **Copy/Clone** any item
- **"Used in" references**: Rule shows which triggers reference it
- **View Code toggle**: JSON view for power users
- **Validation warnings**: Inline alerts for conflicts, orphans, duplicates
- **Confirm dialogs**: Safe delete with reference checking
- **Status filter**: Filter entity lists by active/disabled/staged
- **Test mode**: Enter work item ID → dry run without updating ADO

### Features (Planned)

- **Import/Export**: Bulk operations for initial setup
- **Execution preview**: Full chain display when clicking any item
- **Analytics dashboard**: Rule hit rates, route frequency, triage throughput
- **User management**: Admin roles and permissions

---

## Triage UI

### Features

- **Queue view**: Items from ADO triage query with status indicators
- **Select & evaluate**: Choose 1, n, or all items, click "Evaluate"
- **Results display**: Per-item analysis summary, rules fired, route applied
- **ADO deep link**: Click to open item in ADO for review/approval

---

## Build Phases

### Phase 1: Foundation ✅
Backend infrastructure, data layer, core engine logic.
- Cosmos DB setup (8 containers) with in-memory fallback for local dev
- Data models for all entities (BaseEntity + Rule, Action, Trigger, Route, Evaluation, AnalysisResult, AuditEntry, FieldSchema)
- Rules Engine (15 operators, evaluate atomic rules → T/F)
- Trigger Engine (AND/OR/NOT expressions, priority-ordered, first TRUE wins)
- Routes Engine (5 operations: set, set_computed, copy, append, template)
- CRUD APIs for rules, actions, triggers, routes (8 endpoints each, 32 total)
- Audit logging service
- ADO field schema integration
- Analysis results storage
- Centralized logging (`triage.*` namespace, `TRIAGE_LOG_LEVEL` env var)

### Phase 2: ADO Integration ✅
Connect the engine to real ADO data.
- Fetch work items from triage queue (WIQL-based)
- Full evaluation pipeline (rules → triggers → route → state → HTML → store)
- ADO write-back with 409 conflict handling (revision-aware)
- Analysis.State management (Custom.ROBAnalysisState)
- HTML summary generation (Custom.pChallengeDetails)
- Discussion comment posting (@ping for Needs Info)
- Evaluation logging with full trace
- Webhook receiver (ADO Service Hooks) with HMAC verification
- Batch evaluation support
- Dual-org pattern (read from production, write to test)

### Phase 3: React UI - Admin ✅
Admin can manage rules, triggers, actions, routes.
- React + Vite project with blade-style layout (76 modules)
- Rules, Actions, Triggers, Routes CRUD pages with EntityTable
- Expression builder for triggers (nested AND/OR/NOT groups)
- Visual route designer (action sequencer)
- Validation page (orphans, broken refs, dup priorities)
- Status management (Active/Disabled/Staged) with StatusBadge
- View Code toggle (JSON view)
- Confirm dialogs for safe delete
- Status filter dropdowns

### Phase 4: React UI - Triage ✅
Triage person can evaluate queue and review results.
- Queue page from ADO query with hydrated fields
- Evaluate page — select items, run pipeline
- Dashboard — system overview
- Eval History page — past evaluations
- Audit Log page — change history
- ADO deep links

### Phase 5: Test Mode & Hardening ✅
Safe testing, edge cases, production readiness.
- Dry run test mode (results stored, no ADO writes)
- Staged rules/actions/triggers/routes (test-only visibility via `include_staged`)
- Optimistic locking for concurrent edits (all entity types)
- Referential integrity on delete (blocked if still referenced)
- Broken reference validation (triggers→rules, triggers→routes, routes→actions)
- Error state in evaluation pipeline
- 313 automated tests across 8 test modules

### Phase 6: Analytics & Fine Tuning (Future)
Deferred — build first, analyze later.
- Rule hit-rate analytics
- Route frequency tracking
- Triage throughput metrics
- Import/Export for bulk operations
- User management and roles

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ADO authentication | Azure AD interactive login | AzureCliCredential → InteractiveBrowserCredential chain; no PAT tokens |
| Integration method | Service Hooks (webhooks) | ADO extensions blocked by MS security policy |
| Human review location | Native ADO interface | Business processes require ADO |
| Route application | Before human review | System applies, human reviews/approves |
| Storage | Cosmos DB | Flexible schema, audit, analytics, Azure-native |
| Frontend | React | Complex interactive UI (expression builders, visual designers) |
| Backend | FastAPI (single service) | Consistent with existing Python stack, async-capable, auto-docs |
| Rule evaluation | All rules first, then walk triggers | Analytics value from knowing all rule results |
| Trigger matching | First TRUE by priority | Deterministic, predictable routing |
| Disabled rules in AND triggers | Trigger evaluates as FALSE | Safe - prevents incorrect routing |
| State management | Active/Disabled/Staged per entity | Safe testing and gradual rollout |
| Conflict handling | Optimistic locking (version field) | Low concurrency, simple and effective |
| Override tracking | Hybrid (DB flag + ADO history) | Fast analytics + detailed audit when needed |
| Analysis storage | Cosmos DB (structured) + ADO (HTML summary) | Analytics/fine-tuning from DB, human readable in ADO |
| Audit logging | Cosmos DB audit-log container | Consistent with existing app, TRIP-compliant |

---

## Quick Reference

### Start Services
```powershell
# Start triage API (from project root)
python -m triage.triage_service          # port 8009
# — or use the launcher script —
.\start_triage.ps1

# Start React UI (development)
cd triage-ui
npm run dev              # port 3000
```

### API Documentation (auto-generated)
- Swagger UI: http://localhost:8009/docs
- ReDoc: http://localhost:8009/redoc

### Test Commands
```powershell
# Run all 313 automated tests
python -m pytest triage/tests/ -v

# Evaluate a single work item (dry run)
curl -X POST http://localhost:8009/api/v1/evaluate/test -H "Content-Type: application/json" -d '{"workItemIds": [12345]}'

# List all active rules
curl http://localhost:8009/api/v1/rules?status=active

# Check service health
curl http://localhost:8009/health
```
