# Data Model Reference

Complete reference for all data entities in the Triage Management System.

---

## Overview

The system has 8 entity types stored across 8 Cosmos DB containers (or in-memory equivalents):

| Entity | Container | Partition Key | Description |
|--------|-----------|---------------|-------------|
| Rule | `rules` | `/status` | Atomic condition (field + operator + value) |
| Action | `actions` | `/status` | Atomic field assignment (field + operation + value) |
| Trigger | `triggers` | `/status` | Chains rules with AND/OR logic, maps to a route |
| Route | `routes` | `/status` | Collection of actions to execute |
| Evaluation | `evaluations` | `/workItemId` | Per-item evaluation results |
| AnalysisResult | `analysis-results` | `/workItemId` | Structured analysis output |
| FieldSchema | `field-schema` | `/source` | ADO field definitions and metadata |
| AuditEntry | `audit-log` | `/entityType` | Change tracking records |

---

## Four-Layer Model

```
Rules → Triggers → Actions → Routes
```

- **Rules** (Layer 1): Atomic T/F conditions. Each rule tests one ADO field.
- **Triggers** (Layer 2): Chain multiple rules with AND/OR/NOT expressions. First match (by priority) wins.
- **Actions** (Layer 3): Atomic field assignments. Each action modifies one ADO field.
- **Routes** (Layer 4): Ordered collection of actions. Applied when a trigger matches.

---

## Base Entity

All managed entities (Rule, Action, Trigger, Route) inherit common fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (auto-generated: `{prefix}-{uuid8}`) |
| `name` | string | Human-readable display name |
| `description` | string | Purpose/notes |
| `status` | string | `active` \| `disabled` \| `staged` |
| `version` | integer | Optimistic locking counter (starts at 1) |
| `createdBy` | string | Email of creator |
| `createdDate` | string | ISO 8601 timestamp |
| `modifiedBy` | string | Email of last modifier |
| `modifiedDate` | string | ISO 8601 timestamp |

### Status Lifecycle

```
active ←→ disabled ←→ staged
```

- **active**: Participates in live evaluations
- **disabled**: Excluded from evaluations, preserved in database
- **staged**: Excluded from live evaluations, included in test/dry-run mode

---

## Rule

**ID prefix**: `rule-`  
**Container**: `rules`

| Field | Type | Description |
|-------|------|-------------|
| _(base fields)_ | | See Base Entity above |
| `field` | string | ADO field reference name (e.g., `Custom.SolutionArea`) |
| `operator` | string | Comparison operator (16 available) |
| `value` | any | Comparison value (type depends on operator) |

### Operators

| Category | Operators |
|----------|----------|
| String/All | `equals`, `notEquals`, `in`, `notIn`, `isNull`, `isNotNull` |
| String-specific | `contains`, `notContains`, `startsWith`, `matches` (regex) |
| Hierarchical | `under` (tree path, e.g., Area Path) |
| Numeric/Date | `gt`, `lt`, `gte`, `lte` |
| Empty check | `isEmpty` |

---

## Action

**ID prefix**: `action-`  
**Container**: `actions`

| Field | Type | Description |
|-------|------|-------------|
| _(base fields)_ | | See Base Entity above |
| `field` | string | ADO field to modify |
| `operation` | string | Operation type (5 available) |
| `value` | any | Value to apply (depends on operation) |
| `valueType` | string | `static` \| `computed` \| `field_ref` \| `template` |

### Operations

| Operation | Description | Value Example |
|-----------|-------------|---------------|
| `set` | Set field to a static value | `"AMEA"` |
| `set_computed` | Set to computed value | `"today()"`, `"currentUser()"` |
| `copy` | Copy value from another field | `"System.AreaPath"` |
| `append` | Append to existing field value | `" - Reviewed"` |
| `template` | Variable substitution | `"Routed by {currentUser} on {today}"` |

### Template Variables

Available in `template` operation:
- `{today}` — Current date
- `{currentUser}` — User who triggered the evaluation
- `{workItemId}` — ADO work item ID
- `{analysisState}` — Current analysis state
- `{areaPath}` — Area Path value

---

## Trigger

**ID prefix**: `dt-`  
**Container**: `triggers`

| Field | Type | Description |
|-------|------|-------------|
| _(base fields)_ | | See Base Entity above |
| `priority` | integer | Evaluation order (lower = evaluated first) |
| `expression` | object | Nested AND/OR/NOT expression referencing rule IDs |
| `onTrue` | string | Route ID to execute when expression evaluates to True |

### Expression Format

```json
{
  "and": [
    "rule-abc123",
    {"or": ["rule-def456", "rule-ghi789"]},
    {"not": "rule-jkl012"}
  ]
}
```

- **String**: Rule ID → looks up True/False from rule evaluation results
- **`{"and": [...]}`**: All children must be True
- **`{"or": [...]}`**: Any child must be True
- **`{"not": expr}`**: Inverts the child result
- Disabled/skipped rules evaluate as **False**
- Missing rules raise **MissingRuleError**

### Priority

Triggers are evaluated in ascending priority order. **First match wins** — when a trigger's expression evaluates to True, its route is applied and no further triggers are evaluated.

---

## Route

**ID prefix**: `route-`  
**Container**: `routes`

| Field | Type | Description |
|-------|------|-------------|
| _(base fields)_ | | See Base Entity above |
| `actions` | string[] | Ordered list of action IDs to execute |

Actions are executed in order. Each action's field change is computed and collected into the evaluation result.

---

## Evaluation

**Container**: `evaluations`  
**Partition key**: `workItemId`  
**Not a managed entity** — evaluations are immutable records.

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `eval-{workItemId}-{timestamp}` |
| `workItemId` | integer | ADO work item ID |
| `date` | string | Evaluation timestamp |
| `evaluatedBy` | string | `"system"` or user email |
| `ruleResults` | object | `{ruleId: true/false, ...}` |
| `skippedRules` | string[] | Rule IDs that were skipped |
| `matchedTrigger` | string \| null | Trigger ID that matched |
| `appliedRoute` | string \| null | Route ID that was executed |
| `actionsExecuted` | string[] | Action IDs that were applied |
| `analysisState` | string | Resulting state (see below) |
| `summaryHtml` | string | HTML summary for ADO field |
| `fieldsChanged` | object | `{field: {from, to}, ...}` |
| `errors` | string[] | Errors encountered |
| `isDryRun` | boolean | Whether this was a test run |

### Analysis States

| State | Meaning |
|-------|---------|
| `Pending` | Not yet evaluated |
| `Routed` | Trigger matched, route applied |
| `No Match` | No trigger matched |
| `Awaiting Approval` | Changes computed, pending human review |
| `Approved` | Human approved and applied changes |
| `Error` | Evaluation encountered errors |

---

## AuditEntry

**Container**: `audit-log`  
**Partition key**: `entityType`

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `audit-{timestamp}-{uuid8}` |
| `timestamp` | string | When the change occurred |
| `action` | string | `create` \| `update` \| `delete` \| `disable` \| `enable` \| `evaluate` |
| `entityType` | string | `rule` \| `action` \| `trigger` \| `route` \| `evaluation` |
| `entityId` | string | ID of the changed entity |
| `actor` | string | User email or `"system"` |
| `changes` | object | `{field: {from, to}, ...}` |
| `details` | string | Human-readable description |

---

## Entity Relationships

```
Rule ──referenced by──▶ Trigger (via expression)
Trigger ──points to──▶ Route (via onTrue)
Action ──referenced by──▶ Route (via actions list)
```

### Cross-Reference Rules

- **Rule deletion** blocked if any trigger references it in an expression
- **Action deletion** blocked if any route includes it in the actions list
- **Route deletion** blocked if any trigger points to it via `onTrue`

---

## Cosmos DB Configuration

**Database**: `triage-management`

| Container | Partition Key | Purpose |
|-----------|---------------|---------|
| `rules` | `/status` | Optimized for listing by status |
| `actions` | `/status` | Optimized for listing by status |
| `triggers` | `/status` | Optimized for listing by status |
| `routes` | `/status` | Optimized for listing by status |
| `evaluations` | `/workItemId` | Optimized for per-item history |
| `analysis-results` | `/workItemId` | Optimized for per-item lookup |
| `field-schema` | `/source` | Grouped by data source |
| `audit-log` | `/entityType` | Grouped by entity type for filtering |

All containers are auto-created on first startup.
