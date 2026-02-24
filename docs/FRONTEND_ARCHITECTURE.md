# Frontend Architecture

Overview of the React frontends for the Triage Management System and Field Portal.

Last Updated: February 23, 2026

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
│   ├── CorrectionsPage.jsx/.css # Corrections review + edit
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
| `/queue` | `QueuePage` | ADO triage queue — Analysis + Triage dual-tab view |
| `/history` | `EvalHistoryPage` | View past evaluation results |
| `/validation` | `ValidationPage` | System validation warnings |
| `/corrections` | `CorrectionsPage` | Review and edit analysis corrections |
| `/audit` | `AuditPage` | Audit trail viewer |

11 pages total, code-split via `React.lazy()` — each page loads only when navigated to.

---

## API Client Layer

All HTTP calls go through `triageApi.js`, which provides:

- **Centralized fetch wrapper** with standard error handling
- **`ApiError` class** with `status`, `message`, and `detail` fields
- **CRUD functions for each entity type**: `listRules()`, `getRule(id)`, `createRule(data)`, `updateRule(id, data)`, `deleteRule(id, opts)`, `copyRule(id)`, `getRuleReferences(id)`, `updateRuleStatus(id, status, version)` — and equivalents for actions, triggers, routes
- **Evaluation functions**: `evaluateWorkItems(ids, dryRun)`, `evaluateTest(ids)`, `applyEvaluation(evalId, wiId, rev)`, `getEvaluationHistory(wiId)`
- **ADO functions**: `getTriageQueue(filters)`, `getTriageQueueDetails(filters)`, `getSavedQueryResults(queryId, max)`, `getWorkItem(id)`, `getAdoStatus()`, `getAdoFields()`
- **Analysis functions**: `getAnalysisEngineStatus()`, `runAnalysis(ids)`, `getAnalysisBatch(ids)`, `getAnalysisDetail(id)`, `setAnalysisState(ids, state)`
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

### QueuePage (Triage Queue)

The Queue page combines **analysis** and **triage** workflows into a dual-tab interface.

#### Tab Layout

| Tab | Color | Contents |
|-----|-------|----------|
| **Analysis** | Blue (#1565c0) | Items needing analysis (Pending / Needs Info / No Match / blank state) |
| **Triage** | Green (#2e7d32) | Items ready for triage (Awaiting Approval) |

A **toolbar row** sits above the tabs with action buttons (Refresh, Analyze/Evaluate). Action buttons use neutral gray styling (`btn-toolbar`) to visually separate them from the colored tab navigation.

#### AI Availability Check

Before running analysis, the UI calls `getAnalysisEngineStatus()`. If the AI engine is unavailable (`aiAvailable: false`), a confirmation dialog warns the user that analysis will use pattern-only mode. The user can proceed or cancel.

#### Analysis Progress Panel

While analysis is running, a centered modal panel shows:
- Animated striped progress bar with percentage
- Per-item status cards: queued → analyzing (spinner) → done / failed
- Done items show category, intent, confidence, and source inline
- Panel stays visible after completion with a Done button

#### Analysis Detail Panel (slide-out)

Clicking a work item's analysis indicator opens a slide-out panel with:
- **Quality Score ring** — circular display with color-coded confidence (green ≥80%, orange ≥50%, red <50%)
- **AI warning banner** — yellow alert when `aiAvailable` was false, indicating pattern-only results
- **Classification** — category, intent, business impact, technical complexity, urgency
- **AI Analysis Summary** — left-bordered block with context summary
- **Color-coded tag sections**:
  - Key Concepts (blue), Azure Services (green), Technologies (purple), Technical Areas (orange), Products (red)
- **Metadata footer** — timestamp and analysis ID

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

---

## Field Portal UI

The Field Portal is a separate React SPA under `field-portal/ui/`.

### Tech Stack

Same as Triage UI — React 18+, Vite, React Router, CSS Modules.
Adds **MSAL** (`@azure/msal-browser` / `@azure/msal-react`) for Azure AD authentication.

### Architecture

```
field-portal/ui/src/
├── App.jsx                  # Root component, MSAL provider, routing
├── main.jsx                 # React DOM entry
├── pages/                   # 9-step wizard pages
├── components/              # Shared UI components
├── api/                     # API client (calls port 8010)
└── auth/                    # MSAL configuration + auth helpers
```

### Key Features

- **9-step assessment wizard** for field engineers to submit structured assessments
- **MSAL authentication** — users sign in via Azure AD; tokens sent to API
- **Cosmos DB persistence** — assessments stored in dedicated containers
- Vite proxies `/api` to `http://localhost:8010` in development

### Build & Run

```bash
cd field-portal/ui
npm run dev      # Development — port 3001
npx vite build   # Production build
```
