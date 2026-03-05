# Triage Admin User Guide

How to use the Triage Management System to manage work-item routing rules,
run evaluations, and operate the triage queue.

Last Updated: March 5, 2026

---

## Getting Started

Open the Triage UI in your browser:

```
http://localhost:3000
```

The sidebar on the left has navigation links to every page. The **Dashboard**
loads by default.

---

## 1. Dashboard

The Dashboard is your landing page. It shows:

- **API Status** — green (Healthy), amber (Degraded), or red (Offline).
- **Entity Counts** — clickable cards showing the total number of Rules, Actions,
  Triggers, and Routes. Click any card to jump to that page.
- **Validation Warnings** — the top 5 configuration warnings. Click
  **View All →** to see the full list.
- **Component Health** — per-component status cards with latency in milliseconds.

Click **↻ Refresh** to reload health data at any time.

---

## 2. Triage Queue

The Queue is where day-to-day triage work happens. It has two tabs:

| Tab | Color | What's in it |
|-----|-------|-------------|
| **🔬 Analysis** | Blue | Items needing AI analysis (Pending, Needs Info, No Match, or blank state) |
| **⚖️ Triage** | Green | Items ready for evaluation (Awaiting Approval) |

Items that have been Approved, Overridden, or Redirected are hidden from the queue.

### Dynamic Columns

The queue table columns are **loaded dynamically** from the ADO saved query
associated with each tab. Instead of a fixed set of columns, the grid adapts to
whatever fields the saved query returns. A step-by-step loading progress
indicator shows the data-load stages (Authenticating → Fetching queries →
Loading items → Processing).

All columns are **resizable** — drag the right edge of any column header to
adjust its width.

### Filtering and Sorting

- Use the **Team** dropdown to filter items by triage team.
- Click any **column header** to sort ascending; click again for descending.
- Click the **funnel icon (▼)** on any column header to open an **Excel-like
  filter dropdown**. Check or uncheck values to filter the grid. The dropdown
  shows **formatted display values** matching what you see in the grid cells
  (e.g., "Requesting Feature" not `requesting_feature`).
- A **Clear All Filters (✕)** button appears in the toolbar when any column
  filter is active. Click it to reset all column filters at once.
- The toolbar shows: total items, selected count, active filter count, and
  pagination controls.

### Running AI Analysis (Analysis Tab)

1. Select items using the checkboxes in the first column.
2. Click **🧠 Analyze Selected**.
   - The button changes to a disabled spinner **immediately** — no delay while
     the AI status is checked.
   - If the AI service is unavailable, a **toast notification** and an inline
     **warning banner** appear (non-blocking — you are never interrupted by a
     popup dialog).
3. A progress panel appears showing:
   - Overall progress bar with percentage.
   - Per-item status cards: queued → analyzing (spinner) → done / failed.
   - Completed items show category, intent, confidence, and source inline.
4. When analysis finishes, results are **merged into the existing cache** — the
   grid does not reload all items from ADO, so your scroll position and
   selection state are preserved.
5. Review the results, then click **✅ Ready for Triage** to move selected items
   to the Triage tab.

### Running Evaluations (Triage Tab)

1. Select items using the checkboxes.
2. Click **🧪 Dry Run Selected** to preview what would happen without writing to
   ADO.
3. All evaluated rows **auto-expand** to show results inline — no scrolling
   required.
4. Review the inline results for each item:
   - **Analysis State badge** — the proposed state after evaluation.
   - **Matched Trigger** and **Applied Route** tags.
   - **Rule chips** — green ✓ (passed) or red ✗ (failed) per rule. Chips show
     the **human-readable rule name** (e.g., "Retirement Match"), not the
     internal ID. Hover over a chip to see the rule ID in a tooltip.
   - **Field Changes** — table showing Field / From / To values.
5. **Click any row** with results to toggle its expansion open or closed.
6. Use the **Expand All / Collapse All** button in the summary header to toggle
   all result rows at once.
7. When satisfied, click **⚡ Evaluate Selected** to apply changes to ADO.
8. Use **↩️ Return to Analysis** to send items back for re-analysis if needed.

### Viewing Analysis Details

Each work item that has analysis data shows a **green dot** in the row. Click it
to open the Analysis Detail slide-out panel, which displays:

- **Confidence score ring** — green (≥80%), orange (≥50%), red (<50%).
- **Classification** — category, intent, business impact, technical complexity,
  urgency.
- **AI Analysis Summary** — context description from the AI.
- **Tag sections** — Key Concepts (blue), Azure Services (green), Technologies
  (purple), Technical Areas (orange), Products (red).
- **Metadata** — timestamp and analysis ID.

Items without analysis show a gray dot.

### Column Reference

The queue table columns are **dynamic** — they come from the ADO saved query for
the active tab. Common columns include:

| Column | Description |
|--------|-------------|
| ID | Clickable link to the work item in Azure DevOps |
| Title | Work item title |
| Analysis State | Colored badge showing where the item is in the pipeline |
| Category / Intent | AI-assigned classification |
| Commitment | Committed, Uncommitted, or Best Case |
| MS Status | On Track, Blocked, At Risk, or Completed |
| Requesting Feature | The associated TFT feature |
| 💬 | Comment count |

Additional columns appear if the ADO saved query includes them. All columns
support sorting, filtering, and resizing.

### Analysis State Reference

| State | Color | Meaning |
|-------|-------|---------|
| Pending | Blue | Waiting for analysis |
| Needs Info | Amber | Could not classify — more detail needed |
| No Match | Gray | No trigger matched this item |
| Awaiting Approval | Purple | Ready for triage evaluation |
| Approved | Green | Triage complete |
| Override | Teal | Manually overridden |
| Redirected | Orange | Routed to another team |

---

## 3. Evaluate (Ad-Hoc)

Use the Evaluate page for one-off evaluations or AI analysis of specific work
items by ID.

### Evaluate Mode

1. Enter one or more work item IDs (comma-separated) in the text field.
2. Check **Dry Run** (on by default) to preview without writing to ADO.
3. Click **⚡ Evaluate**.
4. Review the results for each work item:
   - Matched Trigger and Applied Route.
   - Rule Results — green ✓ (passed) or red ✗ (failed) per rule.
   - Field Changes — table showing Field, From, and To values.
5. To apply changes, uncheck Dry Run and click **⚡ Evaluate** again, then
   click **Apply to ADO** on each result card.

### Analyze Mode

1. Toggle to the **🔬 Analyze** tab.
2. Enter work item IDs and click **🔬 Analyze**.
3. Review the AI classification for each item:
   - Category, Intent, Business Impact, Confidence %.
   - Context Summary and Reasoning.
   - Key Concepts, Azure Services, Technologies, Products.
4. Under **Your Evaluation**:
   - Select **"✔ Yes, this analysis is correct"** → click **✔ Approve Analysis**.
   - Or select **"✗ No, this analysis needs correction"** → choose the correct
     Category, Intent, and/or Business Impact from the dropdowns → optionally
     add feedback → click **🔄 Reanalyze with Corrections** or
     **💾 Save Corrections Only**.

### Correction Dropdowns

**Category** (22 options in 6 groups):

| Group | Options |
|-------|---------|
| Core | Technical Support, Feature Request, Bug Report, Service Issue |
| Service | Compliance/Regulatory, Security/Governance, Service Availability |
| Capacity | AOAI Capacity, General Capacity |
| Business | Business Desk, Account Management, Licensing/Billing |
| Support | Customer Escalation, Partner Support, Internal Request |
| Specialized | Data Sovereignty, Architecture Review, Migration Assistance, Performance Optimization, Integration Support |

**Intent** (15 options in 4 groups):

| Group | Options |
|-------|---------|
| Support | Seeking Guidance, Reporting Issue, Requesting Information |
| Requests | Requesting Feature, Capacity Request, Access Request |
| Business | Compliance Support, Business Process, Account Request |
| Specialized | Architecture Consultation, Migration Support, Performance Tuning |

**Business Impact**: Low, Medium, High, Critical.

---

## 4. Rules

Rules are individual field-matching conditions. They compare a work-item field
against a value using an operator.

### Creating a Rule

1. Click **+ New Rule** in the header.
2. Fill in:
   - **Name** — descriptive name (required).
   - **Field** — the ADO or Analysis field to evaluate. Use the searchable
     combobox to find the field.
   - **Operator** — how to compare (see table below).
   - **Value** — the value to compare against. Hidden for Is Null / Is Not Null.
     For In / Not In, enter a comma-separated list.
   - **Status** — Active, Disabled, or Staged.
   - **Triage Team** — scopes the rule to a specific team (optional).
3. Click **Save**.

### Operators

| Group | Operator | Description |
|-------|----------|-------------|
| String / All | Equals | Exact match |
| | Not Equals | Does not match |
| | In (list) | Matches any value in a comma-separated list |
| | Not In (list) | Matches none of the listed values |
| | Is Null | Field is empty |
| | Is Not Null | Field has a value |
| String | Contains | Field contains the substring |
| | Not Contains | Field does not contain the substring |
| | Starts With | Field starts with the value |
| | Matches (Regex) | Field matches a regular expression |
| Hierarchical | Under (Tree Path) | Field is under a tree path (e.g., area path) |
| Numeric / Date | Greater Than, Less Than, Greater or Equal, Less or Equal | Numeric or date comparison |

### Editing and Managing Rules

- **Edit**: Click any row to open the detail panel → modify fields → **Save**.
- **Clone**: Click the copy icon on a row → a duplicate is created with "(copy)"
  appended to the name.
- **Toggle Status**: Click the toggle icon → confirm in the dialog to
  enable/disable the rule.
- **Cross-references**: The detail panel shows which triggers reference this rule.

---

## 5. Actions

Actions define what happens to a work item's fields when a route runs. Each
action targets one field and applies one operation.

### Creating an Action

1. Click **+ New Action** in the header.
2. Fill in:
   - **Name** — descriptive name (required).
   - **Target Field** — the field to modify (searchable combobox).
   - **Operation** — how to modify the field (see table below).
   - **Value** — depends on the operation.
   - **Status** and **Triage Team** — same as rules.
3. Click **Save**.

### Operations

| Operation | Value Input | What it does |
|-----------|-------------|-------------|
| **Set** | Text input | Sets the field to a fixed value |
| **Set Computed** | Dropdown: `today()` or `currentUser()` | Sets the field to a computed value |
| **Copy** | Field reference (combobox) | Copies the value from another field |
| **Append** | Text input | Appends text to the existing field value |
| **Template** | Template string | Composes a value from template variables |

### Template Variables

When using Template or Append operations, you can insert variables by clicking
the chips below the text area:

| Variable | Value |
|----------|-------|
| `{CreatedBy}` | Work item creator |
| `{SubmitterAlias}` | Alias extracted from email (for @-mentions) |
| `{WorkItemId}` | Work item ID |
| `{Title}` | Work item title |
| `{today()}` | Current date |
| `{currentUser()}` | Signed-in user |
| `{Analysis.Category}` | AI-assigned category |
| `{Analysis.Products}` | Detected products |
| `{Analysis.Confidence}` | AI confidence score |
| `{Analysis.Intent}` | AI-assigned intent |
| `{Analysis.ContextSummary}` | AI context summary |

**Example**: `Triaged by {currentUser()} on {today()} — {Analysis.Category}`

### Managing Actions

- **Edit**: Click a row → modify → **Save**.
- **Clone**: Copy icon on the row.
- **Delete**: Delete icon → confirm in dialog.
- **Cross-references**: Detail panel shows which routes include this action.

---

## 6. Triggers

Triggers are boolean expressions that determine which route applies to a work
item. They are evaluated in **priority order** (lowest number first) and the
**first TRUE match wins**.

### Creating a Trigger

1. Click **+ New Trigger** in the header.
2. Fill in:
   - **Name** — descriptive name (required).
   - **Priority** — a number. Lower = higher priority. The first true match wins.
   - **Expression** — build using the visual editor (see below).
   - **Target Route** — the route to fire when this trigger matches.
   - **Status** and **Triage Team**.
3. Click **Save**.

### Building an Expression

The expression builder is a visual drag-free editor for composing AND/OR/NOT
logic trees:

1. Start by clicking **"Start with AND group"** or **"Start with OR group"**.
2. Inside the group:
   - Click **+ Add Rule** to pick from active rules.
   - Click **+ AND Group** or **+ OR Group** to nest a sub-group.
3. For each item:
   - Click **NOT** to negate it (wraps/unwraps).
   - Click **✕** to remove it.
4. Click the group header (AND / OR) to toggle the operator.

Groups are color-coded by nesting depth. The resulting expression is previewed
in text form, such as: `rule-A AND (rule-B OR NOT rule-C)`.

### How Evaluation Works

When the system evaluates a work item:

1. All active triggers are sorted by priority (lowest first).
2. For each trigger, its expression is evaluated against the work item.
3. The first trigger whose expression evaluates to TRUE fires its target route.
4. Remaining triggers are skipped.

---

## 7. Routes

Routes are ordered sequences of actions that execute when a trigger fires.

### Creating a Route

1. Click **+ New Route** in the header.
2. Enter a **Name**.
3. Use the **Route Designer** to compose the action sequence:
   - **Left panel** — "Available Actions": lists all active actions not in the
     route. Click **+ Add** to move one to the route.
   - **Right panel** — "Route Actions": the ordered list of actions in the route.
     Use **▲ Move Up**, **▼ Move Down**, and **✕ Remove** to arrange them.
4. Set **Status** and **Triage Team**.
5. Click **Save**.

Actions execute in the order shown (top to bottom).

---

## 8. Corrections

The Corrections page tracks AI classification errors to improve future analysis
accuracy. Corrections are stored in Cosmos DB (container: `corrections`,
partition key: `/workItemId`) and are managed via the Admin API.

### Adding a Correction

1. Click **+ New Correction**.
2. Fill in:
   - **Misclassified Text** — describe the misclassified item.
   - **Original Category** — what the AI assigned (grouped dropdown).
   - **Corrected Category** — what it should have been (grouped dropdown).
   - **Original Intent** and **Corrected Intent** — same pattern.
   - **Notes** — explain why the correction is needed.
3. Click **Add Correction**.

Corrections can also be submitted directly from the **Evaluate > Analyze** page
when reviewing AI results (see Section 3, Analyze Mode).

### Editing and Deleting

- Click any row to open the detail panel → modify → **Save Changes**.
- Click **Delete** → confirm in the dialog.
- Each correction is identified by its Cosmos document ID.

---

## 9. Disagreement Resolution (Active Learning)

When the LLM engine and the Pattern engine **disagree** on an item's category,
the system surfaces a resolution prompt so a human can arbitrate. This is the
primary input to the active learning feedback loop.

### Where Disagreements Appear

- **Evaluate Page (Analyze Mode)** — after analyzing a work item, if the two
  engines disagree, a **"Classification Disagreement"** panel appears showing:
  - LLM's category and confidence.
  - Pattern engine's category and confidence.
  - Three resolution buttons: **Use LLM**, **Use Pattern**, **Neither**.
- **Queue Page** — items in the Analysis or Triage tab that have disagreements
  show a disagreement indicator. Clicking it opens the same resolution UI.

### Resolving a Disagreement

1. Review both classifications and their confidence scores.
2. Choose one of:
   - **Use LLM** — accept the LLM's category.
   - **Use Pattern** — accept the Pattern engine's category.
   - **Neither** — enter the correct category manually.
3. Optionally add **correction notes** explaining your choice.
4. Click **Submit**.

The resolution is saved as a **Training Signal** in Cosmos DB (`training-signals`
container). Over time, these signals are aggregated to tune pattern weights
automatically (see Section 10).

### Why This Matters

Every disagreement resolution teaches the system which engine to trust more for
specific categories. After enough signals accumulate (minimum 3 per category),
running weight tuning adjusts the pattern engine's influence accordingly.

---

## 10. Pattern Weight Tuning

Pattern weight tuning is a batch process that adjusts the pattern engine's
influence per category based on accumulated training signals.

### How It Works

1. The system collects all training signals (disagreement resolutions).
2. For each category, it calculates how often the pattern engine agreed with
   the human's final choice (accuracy).
3. A **multiplier** is computed using a piecewise linear function:

   | Pattern Accuracy | Multiplier | Effect |
   |-----------------|------------|--------|
   | 0% | 0.60× | Heavy suppression |
   | 40% | 0.90× | Mild penalty |
   | 70% | 1.00× | Neutral — no change |
   | 100% | 1.30× | Boost — pattern is reliable |

4. Categories with fewer than 3 signals are skipped (insufficient data).
5. The multipliers are stored as a system document in the `training-signals`
   container.

### Running Weight Tuning

Weight tuning is triggered via the Admin API:

```
POST /admin/tune-weights
```

The response shows: total signals processed, per-category accuracy, computed
multipliers, and any categories skipped due to insufficient data.

### Viewing Current Weights

```
GET /admin/pattern-weights
```

Returns the current multiplier for each category and the timestamp of the last
tune operation.

### Effect on Analysis

During AI analysis, the `intelligent_context_analyzer` loads the current weight
adjustments and applies them to pattern engine scores before selecting the
winning category. For example, if `capacity` has a 1.15× multiplier, the
pattern engine's confidence for capacity is multiplied by 1.15 before comparison.

---

## 11. Data Management (Export / Import)

The **Data Management** page (📦 in sidebar) allows you to export and import
Rules, Triggers, Routes, and Actions. Use this for:

- **Backup** – snapshot your current configuration before making changes
- **Environment transfer** – move entities from dev → pre-prod → prod
- **Restore** – re-import a previously exported bundle

### Export Tab

1. Check the entity types you want to export (Rules, Triggers, Routes, Actions).
2. Click **Load Records** — individual records appear with checkboxes.
3. Select/deselect individual records, or use **Select All / Deselect All**.
4. Click **Export Selected** — a JSON file downloads to your machine.

> **Auto-Dependencies:** When you export Triggers, the system automatically
> includes any Rules and Routes they reference. When you export Routes, the
> system automatically includes their Actions. Dependencies are listed in the
> export summary.

### Import Tab

1. Click **Choose File** (or drag-and-drop) to upload a `.json` export bundle.
2. The system shows an **import preview** with each entity marked as
   **create** (new) or **update** (name already exists).
3. Select which entities to import using the checkboxes.
4. Click **Import Selected** — the system:
   - Creates an **auto-backup** of all affected entity types first
   - Imports in dependency order: Rules → Actions → Routes → Triggers
   - Matches by **name** (not UUID) — safe across environments
   - Remaps internal ID references automatically
5. A result summary shows created / updated / failed counts.

### Important Notes

- **Name-based matching**: if an entity with the same name exists, it is
  updated (overwritten). If the name is new, a new entity is created.
- **Auto-backup**: before any import, the system exports all affected entity
  types as a snapshot. This appears in the Audit Log.
- **Import order**: Rules → Actions → Routes → Triggers ensures that
  references point to already-imported entities.

---

## 12. Validation

The Validation page runs integrity checks across all rules, actions, triggers,
and routes. It detects broken references, orphaned entities, and configuration
errors.

### Warning Types

| Type | Severity | Meaning |
|------|----------|---------|
| Orphaned Rule | ⚠ Warning | Rule is not referenced by any trigger |
| Orphaned Action | ⚠ Warning | Action is not included in any route |
| Missing Reference | 🔴 Error | A trigger/route references a deleted rule/action |
| Duplicate Priority | 🔴 Error | Two triggers share the same priority number |
| Invalid Expression | 🔴 Error | Trigger expression is malformed |
| Empty Route | ℹ Info | Route has zero actions |

### Resolving Warnings

1. Open the Validation page.
2. Use the **Group By** dropdown to group by Type or Severity.
3. For each warning, click **"Go to →"** to navigate directly to the offending
   entity (it will be highlighted).
4. Fix the issue (add a reference, delete the orphan, correct the priority, etc.).
5. Click **🔄 Refresh** to verify the warning is gone.

---

## 13. Audit Log

The Audit Log records every create, update, delete, status-change, copy, and
evaluate operation in the system.

### Viewing the Log

1. Set filters:
   - **Entity Type**: All, Rule, Action, Trigger, Route.
   - **Action**: All, Created, Updated, Deleted, Activated, Disabled, Copied, Evaluated.
   - **Limit**: 25, 50, 100, or 200 entries.
2. Click **🔄 Refresh**.
3. Entries appear in a timeline (newest first), each showing:
   - Action badge (color-coded).
   - Entity type, ID, and name.
   - Timestamp and actor.
4. Expand any entry to see a **Changes** table with Field / Before / After
   columns showing exactly what changed.

### Action Badge Colors

| Action | Color |
|--------|-------|
| Created | Green |
| Updated | Blue |
| Deleted | Red |
| Activated / Disabled | Amber |
| Copied | Purple |
| Evaluated | Teal |

---

## 14. Evaluation History

Look up past evaluation runs for a specific work item.

1. Enter a **Work Item ID** and select a limit (Last 10/20/50/100).
2. Click **Search** (or use a bookmarkable URL: `/history?id=12345`).
3. Results appear as a timeline (newest first). Each card shows:
   - Date/time, Analysis State, Matched Trigger, Applied Route, Evaluated By.
   - **DRY RUN** badge if applicable.
4. Expand a card for full details:
   - Rule Results (✓/✗ per rule).
   - Field Changes (Field / From / To).
   - Actions Executed.
   - Skipped Rules and Errors (if any).

---

## Concepts Reference

### Entity Hierarchy

```
Rules  →  combined into →  Trigger Expressions  →  point to →  Routes  →  contain →  Actions
```

- **Rules** test individual field conditions.
- **Triggers** combine rules into boolean expressions and assign a route.
- **Routes** are ordered lists of actions that execute on the work item.
- **Actions** modify individual fields on the work item.

### Status Badges

| Status | Color | Meaning |
|--------|-------|---------|
| Active | Green | Entity is live and participates in evaluation |
| Disabled | Gray | Entity is skipped during evaluation |
| Staged | Yellow | Entity is saved but not yet active |

### Evaluation Pipeline

1. AI analysis classifies the work item (category, intent, confidence).
   - Pattern engine scores are adjusted by **learned weight multipliers** from
     active learning (see Section 10).
   - If LLM and Pattern engines **disagree**, the disagreement is flagged for
     human resolution (see Section 9).
2. Triggers are evaluated in priority order against the work item + analysis.
3. The first matching trigger fires its route.
4. The route's actions execute in sequence, modifying ADO fields.
5. Results are recorded in the audit log and evaluation history.
6. Disagreement resolutions feed back as **training signals**, which are
   periodically aggregated to tune pattern weights.

---

## Tips

- **Always dry-run first.** Use Dry Run to preview changes before writing to ADO.
- **Check Validation regularly.** Orphaned rules and missing references cause
  silent failures during evaluation.
- **Use the Analysis Detail panel.** The green dot in the queue shows AI
  confidence and reasoning — use it to verify classifications before triage.
- **Corrections improve the AI.** When you see a misclassification, record it
  on the Corrections page or via the Evaluate page's correction flow.
- **Resolve disagreements promptly.** The more training signals you provide,
  the better the pattern weight tuning becomes.
- **Run weight tuning periodically.** After accumulating new training signals,
  call `POST /admin/tune-weights` to update pattern multipliers.
- **Bookmark history URLs.** `/history?id=12345` gives you a direct link to a
  work item's evaluation history.
