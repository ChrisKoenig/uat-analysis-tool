# Frontend Architecture

Overview of the React frontend for the Triage Management System.

---

## Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18+ | UI framework |
| Vite | 6.x | Build tool + dev server |
| React Router | 6.x | Client-side routing |
| CSS Modules | — | Per-page stylesheets |

No state management library — each page manages its own state via `useState`/`useEffect`.

---

## Application Structure

```
triage-ui/src/
├── App.jsx                      # Root component, routing, layout shell
├── main.jsx                     # React DOM entry point
├── index.css                    # Global styles + CSS variables
│
├── api/
│   └── triageApi.js             # Centralized API client (all HTTP calls)
│
├── pages/                       # Route-level page components
│   ├── Dashboard.jsx/.css       # System overview with entity counts
│   ├── RulesPage.jsx/.css       # Rules CRUD
│   ├── ActionsPage.jsx/.css     # Actions CRUD
│   ├── TriggersPage.jsx/.css    # Triggers CRUD + expression builder
│   ├── RoutesPage.jsx/.css      # Routes CRUD
│   ├── EvaluatePage.jsx/.css    # Run evaluations on work items
│   ├── QueuePage.jsx/.css       # ADO triage queue browser
│   ├── EvalHistoryPage.jsx/.css # Evaluation history viewer
│   ├── ValidationPage.jsx/.css  # System-wide validation warnings
│   └── AuditPage.jsx/.css       # Audit log viewer
│
├── components/
│   ├── layout/
│   │   └── AppLayout.jsx/.css   # Sidebar nav + content area shell
│   ├── common/
│   │   ├── EntityTable.jsx      # Reusable CRUD table with toggle status
│   │   ├── FieldCombobox.jsx/.css # ADO/Analysis field autocomplete dropdown
│   │   ├── StatusBadge.jsx/.css # Status pill (active/disabled/staged)
│   │   └── ViewCodeToggle.jsx/.css # JSON view toggle
│   ├── rules/
│   │   └── RuleForm.jsx         # Rule editor form
│   ├── actions/
│   │   └── ActionForm.jsx       # Action editor form
│   ├── triggers/
│   │   ├── TriggerForm.jsx      # Trigger editor form
│   │   ├── ExpressionBuilder.jsx/.css # Visual AND/OR/NOT expression editor
│   │   └── (expression tree UI)
│   └── routes/
│       └── RouteForm.jsx        # Route editor form
│
└── utils/
    ├── constants.js             # Operators, operations, template variables, nav items, API base
    └── helpers.js               # Formatting, validation helpers
```

---

## Routing

All routes are defined in `App.jsx` using React Router's lazy loading:

| Path | Page Component | Description |
|------|---------------|-------------|
| `/` | `Dashboard` | Entity counts, quick links |
| `/rules` | `RulesPage` | Rules CRUD with operator reference |
| `/actions` | `ActionsPage` | Actions CRUD with operation types |
| `/triggers` | `TriggersPage` | Triggers CRUD with expression builder |
| `/routes` | `RoutesPage` | Routes CRUD with action list management |
| `/evaluate` | `EvaluatePage` | Run evaluations against ADO items |
| `/queue` | `QueuePage` | Browse ADO triage queue |
| `/history` | `EvalHistoryPage` | View past evaluation results |
| `/validation` | `ValidationPage` | System validation warnings |
| `/audit` | `AuditPage` | Audit trail viewer |

Pages are code-split via `React.lazy()` — each page loads only when navigated to.

---

## API Client Layer

All HTTP calls go through `triageApi.js`, which provides:

- **Centralized fetch wrapper** with standard error handling
- **`ApiError` class** with `status`, `message`, and `detail` fields
- **CRUD functions for each entity type**: `listRules()`, `getRule(id)`, `createRule(data)`, `updateRule(id, data)`, `deleteRule(id, opts)`, `copyRule(id)`, `getRuleReferences(id)`, `updateRuleStatus(id, status, version)` — and equivalents for actions, triggers, routes
- **Evaluation functions**: `evaluateWorkItems(ids, dryRun)`, `evaluateTest(ids)`, `applyEvaluation(evalId, wiId, rev)`, `getEvaluationHistory(wiId)`
- **ADO functions**: `getTriageQueue(filters)`, `getTriageQueueDetails(filters)`, `getWorkItem(id)`, `getAdoStatus()`, `getAdoFields()`
- **Other**: `getValidationWarnings()`, `getAuditLog(filters)`, `getEntityAudit(type, id)`, `healthCheck()`

In development, Vite proxies `/api` requests to `http://localhost:8009`.

---

## Layout & Navigation

The `AppLayout` component provides:
- **Left sidebar** with navigation items defined in `constants.js`:
  - Dashboard, Evaluate, Queue, Rules, Actions, Triggers, Routes, Validation, Audit, History
- **Content area** where the active page renders
- **Responsive** bladestyle layout

---

## UI Patterns

### CRUD Pages

All four entity pages (Rules, Actions, Triggers, Routes) follow the same pattern:

1. **List view** — table showing all entities with status badges
2. **Create/Edit form** — slide-in panel with entity-specific fields
3. **Status management** — toggle active/disabled/staged with version locking
4. **Delete** — with confirmation dialog and reference check warnings
5. **Copy** — clone an entity as starting point for a new one
6. **Cross-references** — "Used by" display showing which entities reference this one

### Expression Builder

The Triggers page includes a visual expression builder (`ExpressionBuilder.jsx`) that lets admins compose AND/OR/NOT logic trees without writing JSON. Features:
- Nested AND/OR groups with depth-coded left borders
- **NOT** button always visible in red accent on every rule and group
- Single-condition AND/OR groups allowed (for wrapping a single rule)
- Add rules from a dropdown of available active rules

### FieldCombobox

Reusable searchable dropdown (`FieldCombobox.jsx`) for selecting ADO and Analysis field reference names. Used in:
- **RuleForm** — evaluable fields (`canEvaluate: true`)
- **ActionForm** — settable fields for Target Field (`canSet: true`), evaluable fields for Copy source

Features:
- **Clear-on-focus**: clicking the field clears search text to show all options
- **Dropdown chevron** (▼/▲) indicates it's a dropdown
- **Flat list** sorted by display name, no group headers
- **Selected item** highlighted with blue left border accent
- **Custom values**: press Enter to use a typed reference name not in the list
- Falls back to plain text input if the field list API is unavailable

### ActionForm

- **Operation selection** adapts the value input (text → dropdown → textarea → field picker)
- **Value Type auto-derived**: no dropdown — set→static, copy→field_ref, template→template, set_computed→computed, append→static (or template if variables used)
- **Template variable buttons** shown for both Template and Append operations
- **{SubmitterAlias}** extracts alias from email for @-mentions in comments

### Evaluation Flow

1. User enters work item IDs on the Evaluate page
2. Clicks "Evaluate" or "Test (Dry Run)"
3. Results show matched trigger, applied route, rule results, and field changes
4. For live evaluations, "Apply to ADO" writes changes back

### Data Display

- `StatusBadge` — colored pill showing active (green), disabled (gray), staged (blue)
- `ViewCodeToggle` — switch between formatted view and raw JSON
- `EntityTable` — reusable table with sorting, filtering, and action buttons

---

## Styling

- **Global styles** in `index.css` with CSS custom properties (variables)
- **Per-page CSS** files adjacent to each page component
- No CSS-in-JS — standard CSS files
- Dark theme by default with consistent color variables

---

## Build & Development

```bash
# Development (with hot reload)
cd triage-ui
npm run dev

# Production build
npx vite build

# Preview production build
npx vite preview
```

Build output goes to `triage-ui/dist/` (76 modules, ~180KB gzipped).
