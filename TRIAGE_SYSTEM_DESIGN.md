# Triage Management System - Design Document

**Created**: February 10, 2026  
**Status**: Phase 1 - Foundation  
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

The Triage Management System automates the triage process for Azure DevOps (ADO) Actions. It analyzes incoming items, validates data quality using decision trees, applies routing rules to determine the destination team, and presents results for human review in the native ADO interface.

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
│ - Visual Design │     │ - Tree Engine   │            │
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
│   RULES     │────▶│   DECISION TREES    │────▶│   ACTIONS   │────▶│   ROUTES    │
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

### Layer 2: Decision Trees (Rule Chains)

Combine rules with AND/OR logic. Evaluated in priority order. First TRUE match wins.
Each tree points to a route to execute on TRUE. No ELSE path - if FALSE, evaluation
continues to the next tree.

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
atomic conditions that get composed into decision trees.

**Example:**
```
Action 1: Set Area Path = "UAT\MCAPS\AI"
Action 2: Set Assigned To = "@AI Apps and Agents Triage"
Action 3: Append to Discussion = "@{CreatedBy} - Missing Milestone ID..."
Action 4: Set State = "Done"
```

### Layer 4: Routes (Action Collections)

Group actions together into reusable pipelines. When a route executes, all
its actions are applied in order. The relationship mirrors Rules → Trees:
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
                                               │ 4. Walk trees│    │ 5. Update    │
                                               │    priority  │    │    ADO item   │
                                               │    order     │    │    + set state│
                                               │    1st TRUE  │    │              │
                                               │    wins      │    │              │
                                               └──────────────┘    └──────────────┘
```

### Evaluation Logic

1. **Evaluate ALL rules** against the work item → store T/F for each rule
2. **Walk decision trees** in priority order using stored results
3. **First TRUE match** → execute that tree's route
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
| **No Match** | No decision tree matched, needs manual triage | No |
| **Approved** | Human confirmed routing, no changes made | Yes |
| **Override** | Human confirmed routing with modifications | Yes |

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
| `{CreatedBy}` | Work item creator |
| `{WorkItemId}` | Work item ID |
| `{Title}` | Work item title |
| `{today()}` | Current date |
| `{currentUser()}` | Authenticated user |
| `{Analysis.Category}` | Analysis result category |
| `{Analysis.Products}` | Detected products |

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

### Container: trees

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
  "matchedTree": "dt-10",
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

### Rules API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/rules` | List all rules (filterable by status) |
| `GET` | `/rules/{id}` | Get single rule |
| `POST` | `/rules` | Create rule |
| `PUT` | `/rules/{id}` | Update rule |
| `DELETE` | `/rules/{id}` | Delete rule |
| `POST` | `/rules/{id}/copy` | Copy/clone rule |

### Actions API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/actions` | List all actions |
| `GET` | `/actions/{id}` | Get single action |
| `POST` | `/actions` | Create action |
| `PUT` | `/actions/{id}` | Update action |
| `DELETE` | `/actions/{id}` | Delete action |
| `POST` | `/actions/{id}/copy` | Copy/clone action |

### Trees API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/trees` | List all trees (sortable by priority) |
| `GET` | `/trees/{id}` | Get single tree |
| `POST` | `/trees` | Create tree |
| `PUT` | `/trees/{id}` | Update tree |
| `DELETE` | `/trees/{id}` | Delete tree |
| `POST` | `/trees/{id}/copy` | Copy/clone tree |

### Routes API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/routes` | List all routes |
| `GET` | `/routes/{id}` | Get single route |
| `POST` | `/routes` | Create route |
| `PUT` | `/routes/{id}` | Update route |
| `DELETE` | `/routes/{id}` | Delete route |
| `POST` | `/routes/{id}/copy` | Copy/clone route |

### Evaluation API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/evaluate` | Evaluate work item(s) - full pipeline |
| `POST` | `/evaluate/test` | Dry run - no ADO updates |
| `GET` | `/evaluations/{workItemId}` | Get evaluation history for item |
| `GET` | `/evaluations` | List evaluations (filterable by date, state) |

### Field Schema API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/fields` | Get all field definitions |
| `POST` | `/fields/refresh` | Re-pull from ADO API |
| `PUT` | `/fields/{id}` | Update field enrichment (operators, group) |

### Validation API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/validation/warnings` | Get all validation warnings (orphans, conflicts, etc.) |
| `GET` | `/validation/references/{type}/{id}` | Get usage references for an entity |

### Audit API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/audit` | List audit entries (filterable) |
| `GET` | `/audit/{entityType}/{entityId}` | Audit history for specific entity |

---

## Admin UI

### Tech Stack
- **React** with blade-style layout (Azure portal pattern)
- **Flask/FastAPI** backend API (port 8009)

### Layout

Left navigation:
- Evaluate Triage
- Analytics (future)
- Rules
- Trees
- Actions
- Routes
- Users

> **Design note:** The nav order follows the compositional hierarchy —
> Rules are atomic conditions composed into Trees; Actions are atomic
> operations composed into Routes.

### Features

- **CRUD** for all four layers (rules, trees, actions, routes — in compositional order)
- **Expression builder** for decision trees (nested AND/OR groups)
- **Visual route designer** for composing actions into routes
- **Status management**: Active / Disabled / Staged per item
- **Copy/Clone** any item
- **"Used in" references**: Rule shows which trees reference it
- **Execution preview**: Full chain display when clicking any item
- **View Code toggle**: DSL view for power users
- **Validation warnings**: Inline alerts for conflicts, orphans, duplicates
- **Import/Export**: Bulk operations for initial setup
- **Test mode**: Enter work item ID → dry run without updating ADO

---

## Triage UI

### Features

- **Queue view**: Items from ADO triage query with status indicators
- **Select & evaluate**: Choose 1, n, or all items, click "Evaluate"
- **Results display**: Per-item analysis summary, rules fired, route applied
- **ADO deep link**: Click to open item in ADO for review/approval

---

## Build Phases

### Phase 1: Foundation
Backend infrastructure, data layer, core engine logic.
- Cosmos DB setup (8 containers)
- Data models for all entities
- Rules Engine (evaluate atomic rules → T/F)
- Decision Tree Engine (walk trees, find first TRUE match)
- Routes Engine (execute action collections)
- CRUD APIs for rules, actions, trees, routes
- Audit logging
- ADO field schema integration
- Analysis results storage

### Phase 2: ADO Integration
Connect the engine to real ADO data.
- Fetch work items from triage queue
- Analysis engine → Cosmos DB → rules engine pipeline
- ADO write-back with 409 conflict handling
- Analysis.State management (Custom.ROBAnalysisState)
- HTML summary generation (Custom.pChallengeDetails)
- Discussion comment posting (@ping for Needs Info)
- Evaluation logging

### Phase 3: React UI - Admin
Admin can manage rules, trees, actions, routes.
- React project setup with blade-style layout
- Rules, Actions, Trees, Routes management pages
- Expression builder for trees
- Visual route designer
- Validation warnings
- Status management (Active/Disabled/Staged)
- Execution preview and View Code toggle

### Phase 4: React UI - Triage
Triage person can evaluate queue and review results.
- Queue view from ADO query
- Select & evaluate functionality
- Results review per item
- ADO deep links

### Phase 5: Test Mode & Hardening
Safe testing, edge cases, production readiness.
- Dry run test mode
- Staged rules (test-only visibility)
- Optimistic locking for concurrent edits
- Error handling for missing references
- Disabled rule behavior in trees

### Phase 6: Analytics & Fine Tuning (Future)
Deferred - build first, analyze later.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration method | Service Hooks (webhooks) | ADO extensions blocked by MS security policy |
| Human review location | Native ADO interface | Business processes require ADO |
| Route application | Before human review | System applies, human reviews/approves |
| Storage | Cosmos DB | Flexible schema, audit, analytics, Azure-native |
| Frontend | React | Complex interactive UI (expression builders, visual designers) |
| Backend | Flask/FastAPI (single service) | Consistent with existing Python stack, right scale |
| Rule evaluation | All rules first, then walk trees | Analytics value from knowing all rule results |
| Tree matching | First TRUE by priority | Deterministic, predictable routing |
| Disabled rules in AND trees | Tree evaluates as FALSE | Safe - prevents incorrect routing |
| State management | Active/Disabled/Staged per entity | Safe testing and gradual rollout |
| Conflict handling | Optimistic locking (version field) | Low concurrency, simple and effective |
| Override tracking | Hybrid (DB flag + ADO history) | Fast analytics + detailed audit when needed |
| Analysis storage | Cosmos DB (structured) + ADO (HTML summary) | Analytics/fine-tuning from DB, human readable in ADO |
| Audit logging | Cosmos DB audit-log container | Consistent with existing app, TRIP-compliant |

---

## Quick Reference

### Start Services
```powershell
# Start triage API
python triage_service.py  # port 8009

# Start React UI (development)
cd triage-ui
npm start               # port 3000
```

### Test Commands
```powershell
# Evaluate a single work item (dry run)
curl -X POST http://localhost:8009/api/v1/evaluate/test -d '{"workItemIds": [12345]}'

# List all active rules
curl http://localhost:8009/api/v1/rules?status=active
```
