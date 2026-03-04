# Evaluation Pipeline Guide

How the triage evaluation pipeline works end-to-end.

---

## Overview

The evaluation pipeline answers: **"Given a work item, what should we do with it?"**

```
ADO Work Item
      │
      ▼
┌─────────────────┐
│  0. Weight      │  Load pattern weight adjustments from training-signals
│     Adjustments │  (applied during analysis, before evaluation)
└────────┬────────┘
         ▼
┌─────────────────┐
│  1. Load Data   │  Load all active rules, triggers, actions, routes
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. Rules       │  Evaluate ALL rules → {ruleId: True/False}
│     Engine      │  (16 operators, field resolution, null handling)
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. Trigger     │  Walk triggers by priority → first match wins
│     Engine      │  (AND/OR/NOT expressions over rule results)
└────────┬────────┘
         ▼
┌─────────────────┐
│  4. Routes      │  Compute field changes from route's action list
│     Engine      │  (5 operations: set, copy, append, template, computed)
└────────┬────────┘
         ▼
┌─────────────────┐
│  5. Store &     │  Save evaluation record to Cosmos DB
│     Return      │  Return results (or apply to ADO)
└─────────────────┘
```

> **Pre-requisite — Analysis Engine**: Before evaluation, work items typically pass through the **Analysis Engine** (`POST /api/v1/analyze`), which classifies items using pattern matching + optional Azure OpenAI. Analysis results populate `Analysis.*` fields that rules can reference in conditions. The analysis engine applies **learned pattern weight multipliers** from the active learning feedback loop (see below) to adjust pattern engine scores before selecting the winning category. Check engine availability via `GET /api/v1/analyze/status`. See the [API Reference](API_REFERENCE.md#analysis-endpoints) for details.

---

## Active Learning Weight Adjustments

The analysis engine incorporates feedback from human disagreement resolutions to
improve classification accuracy over time.

### How Weights Affect Analysis

During `_classify_category()`, the `intelligent_context_analyzer` loads pattern
weight adjustments (if any) from the `training-signals` Cosmos container. Each
category may have a **multiplier** that scales the pattern engine's confidence
score before comparison with the LLM engine.

For example, if `capacity` has a 1.15× multiplier and the pattern engine scores
capacity at 0.70, the adjusted score becomes 0.805 — potentially changing which
engine wins the category selection.

### Multiplier Source

Multipliers are computed by `POST /admin/tune-weights`, which aggregates all
training signals (human resolutions of LLM/Pattern disagreements) and calculates
per-category accuracy using a piecewise linear function:

| Pattern Accuracy | Multiplier | Effect |
|-----------------|------------|--------|
| 0% | 0.60× | Heavy suppression |
| 40% | 0.90× | Mild penalty |
| 70% | 1.00× | Neutral |
| 100% | 1.30× | Boost |

Categories with fewer than 3 signals are excluded. If no weight adjustments
exist, the analysis engine runs with default (1.0×) multipliers — no effect.

### Disagreement Detection

When the LLM and pattern engines produce different categories, the analysis
result includes `agreement: false` and populates both `patternCategory` and
`patternConfidence` fields. The UI surfaces a resolution prompt (see the
[Admin User Guide](TRIAGE_ADMIN_USER_GUIDE.md#9-disagreement-resolution-active-learning)).
Each resolution is stored as a **training signal** that feeds future weight tuning.

---

## Step-by-Step

### Step 1: Load Active Entities

The `EvaluationService` loads from Cosmos DB (or in-memory store):
- **Rules**: All active rules (disabled/staged excluded unless `include_staged=True`)
- **Triggers**: All active triggers, sorted by priority ascending
- **Actions**: All active actions, indexed by ID for lookup
- **Routes**: All active routes, indexed by ID for lookup

### Step 2: Rules Engine

The `RulesEngine` evaluates **every active rule** against the work item's field data.

**Input**: List of `Rule` objects + work item field dict + optional `AnalysisResult`  
**Output**: `{rule_id: True/False}` dict + list of skipped rule IDs

For each rule:
1. **Resolve field value** from the work item data (e.g., `fields["Custom.SolutionArea"]`)
2. **Apply operator** to compare field value against rule value
3. **Return True/False**

Rules that are disabled or encounter errors are added to the `skippedRules` list and treated as **False** in trigger expressions.

**Example**:
```
Rule "rule-amea": Custom.SolutionArea equals "AMEA"
Work item fields: {"Custom.SolutionArea": "AMEA"}
→ Result: True

Rule "rule-null": Custom.MilestoneID isNull
Work item fields: {"Custom.MilestoneID": null}
→ Result: True
```

### Step 3: Trigger Engine

The `TriggerEngine` walks all active triggers in priority order (lower number = higher priority).

**Input**: List of `Trigger` objects + rule results dict + skipped rules  
**Output**: `(matched_trigger_id, route_id, errors)` tuple

For each trigger:
1. **Evaluate its expression** recursively:
   - String leaf → look up rule result (True/False)
   - `{"and": [...]}` → all children True
   - `{"or": [...]}` → any child True
   - `{"not": expr}` → invert
2. **Disabled rules** in expressions evaluate as False
3. **First True match wins** — return that trigger's `onTrue` route ID

If no trigger matches, the pipeline returns `analysisState: "No Match"`.

**Example**:
```
Trigger "dt-10" (priority=10):
  expression: {"and": ["rule-amea", {"not": "rule-null"}]}
  onTrue: "route-amea"

Rule results: {"rule-amea": True, "rule-null": True}

Evaluation:
  "rule-amea" → True
  {"not": "rule-null"} → not True → False
  {"and": [True, False]} → False

→ Trigger dt-10 does NOT match, continue to next trigger...
```

### Step 4: Routes Engine

If a trigger matched, the `RoutesEngine` computes field changes from the matched route's actions.

**Input**: `Route` object + action dict + work item field data  
**Output**: List of `FieldChange(field, from_value, to_value)` objects

For each action in the route:
1. **Read current value** from work item fields
2. **Compute new value** based on operation type:
   - `set` → static value
   - `set_computed` → `today()`, `currentUser()`, etc.
   - `copy` → value from another field
   - `append` → existing value + new text
   - `template` → variable substitution with `{today}`, `{areaPath}`, etc.
3. **Record the change** as `{field, from, to}`

### Step 5: Store & Return

The evaluation result is:
1. **Persisted** to the `evaluations` container in Cosmos DB
2. **Audit logged** via the AuditService
3. **Returned** to the API caller as an `Evaluation` object

The caller (API endpoint or webhook) decides whether to auto-apply or present for review.

---

## Evaluation Modes

### Live Evaluation

```
POST /api/v1/evaluate
{"workItemIds": [12345], "dryRun": false}
```

- Stores the evaluation record
- Does NOT auto-apply to ADO
- Results can be applied later via `/api/v1/evaluate/apply`

### Dry Run / Test

```
POST /api/v1/evaluate/test
{"workItemIds": [12345]}
```

- Stores the evaluation record with `isDryRun: true`
- Cannot be applied to ADO (blocked by the apply endpoint)
- Includes staged entities in evaluation (so you can test staged rules/triggers)

### Apply to ADO

```
POST /api/v1/evaluate/apply
{"evaluationId": "eval-12345-...", "workItemId": 12345, "revision": 42}
```

- Reads stored evaluation results
- Writes computed field changes to ADO work item
- Posts summary HTML as a Discussion comment
- Returns 409 on revision conflict

---

## Staged Entity Testing

Entities with `status: "staged"` are:
- **Excluded** from live evaluations
- **Included** in dry-run/test evaluations

This lets admins preview new rules and triggers without affecting production, then promote them to `active` when ready.

---

## Error Handling

The pipeline is designed to be resilient:

| Error | Handling |
|-------|----------|
| Rule evaluation error | Rule is skipped, added to `skippedRules`, treated as False |
| Missing rule in trigger | `MissingRuleError` logged, trigger continues to next |
| Trigger expression error | Logged, trigger skipped, next trigger tried |
| No trigger matches | `analysisState: "No Match"`, no route applied |
| Route action error | Error recorded, other actions still attempted |
| ADO fetch failure | 502 returned to caller |
| Cosmos DB offline | Graceful degradation where possible |

Disabled rules referenced by active triggers generate a **warning** in the evaluation's `errors` array so admins can see which triggers may be short-circuited.

---

## Evaluation Trace

For debugging, the trace endpoint returns per-trigger evaluation details:

```
POST /api/v1/evaluate/test
```

The trace shows each trigger, its expression result, and whether it would be the "winner" — useful for understanding why a particular trigger matched (or didn't).

---

## Logging

Set `TRIAGE_LOG_LEVEL=DEBUG` to see detailed evaluation traces:

```
triage.engines.rules    - Each rule evaluation result
triage.engines.trigger  - Each trigger walk step, expression node evaluation
triage.engines.routes   - Each action execution and field change
triage.services.eval    - Pipeline orchestration summary
```
