# Change Management Log

> **Environment:** Pre-Production  
> **Application:** Triage Management System  
> **Tracking Policy:** Every change deployed to Pre-Prod (or above) must be recorded here with its Change Request number, summary, date, and Git build ID.

---

## Change Log

| # | CR Number | Date | Build ID (Git) | Summary |
|---|-----------|------|-----------------|---------|
| 1 | FR-1997 | 2026-03-03 | `6abe2e1` | **Add multi-field, multi-value search to Rules** — New `containsAny` and `regexMatchAny` operators enabling rules to search across multiple ADO fields for multiple keywords or regex patterns simultaneously. Changes span backend (rule model, Pydantic schemas, rules engine evaluation with `_evaluate_contains_any` and `_evaluate_regex_match_any`) and frontend (new `MultiFieldCombobox` component, updated `RuleForm` with conditional multi-field picker and regex-specific hints, updated `RulesPage` table display). |
| 2 | FR-1993 | 2026-03-03 | `6abe2e1` | **Rules table pagination, search & expandable value cells** — Added pagination (25/50/100 page sizes), a search box to filter rules by name/field/value, and expandable value cells that truncate long lists with a "+N more" badge. |
| 3 | FR-1993 | 2026-03-03 | *pending* | **Extend pagination, search & expandable values to Triggers, Actions, Routes** — Applied the same FR-1993 UX improvements (pagination, search input, expandable value cells) to all remaining entity list pages. Extracted shared EntitySearch CSS. |
| 4 | FR-1994, FR-1999 | 2026-03-04 | `4b06cff` | **Tabbed analysis detail views + blade "No data" placeholders** — Added pill-style tabbed interface (Overview / Analysis / Decision / ServiceTree / Correct & Reanalyze) to Field Portal `AnalysisDetailPage` and Triage UI `EvaluatePage` to reduce scrolling. QueuePage blade kept as linear layout with all section headers always visible and "No data" placeholders for empty fields. |
| 5 | ENG-003 | 2026-03-05 | *pending* | **Active Learning — Full feedback loop (Steps 1-5)** — Training signals Cosmos container, corrections Cosmos migration, disagreement UI, pattern weight tuning, few-shot signal injection into LLM prompt, and dashboard agreement rate metric. All five design steps implemented. |
| 6 | B0002 | 2026-03-06 | *pending* | **Bug fix — hybrid source not recognized as LLM** — `isLLM` check in `EvaluatePage.jsx` only matched `"llm"` source. Items analyzed as `"hybrid"` (LLM primary with pattern features) appeared as pattern-only in the UI. Fixed to include `"hybrid"` in the `isLLM` check. |
| 7 | B0003 | 2026-03-06 | *pending* | **Bug fix — comparison crash on pattern-only fallback** — When LLM is unavailable and `agreement` field is `null`, the Pattern Engine Comparison section crashed because it assumed `agreement` was always `true`/`false`. Fixed: `hybrid_context_analyzer.py` now sets `agreement=None` on pattern-only fallback; `EvaluatePage.jsx` gates the comparison section on `agreement !== null && agreement !== undefined`. |
| 8 | ENG-004 | 2026-03-06 | *pending* | **LLM classifier retry logic with exponential backoff** — Added automatic retry for transient Azure OpenAI failures (429 rate limit, 500/502/503/504 server errors, network timeouts). Up to 3 retries with exponential backoff (1s base, 5s for rate limits). Jitter prevents thundering herd. |
| 9 | ENG-005 | 2026-03-06 | *pending* | **Diagnostics endpoint + inline diagnostics UI** — New `GET /api/v1/diagnostics` endpoint returning AI config, Cosmos, ADO, and cache status. Floating diagnostics icon in `AppLayout`. Inline diagnostics button in the yellow "AI Unavailable" banner on `EvaluatePage`, showing a collapsible diagnostic panel with AI status, OpenAI config, and error details. |
| 10 | ENG-006 | 2026-03-06 | *pending* | **Batch fetch resilience — errorPolicy=Omit + null-safe iteration** — ADO batch API returned HTTP 404 for entire batch when any single work item ID was invalid, causing "Batch fetch failed" for all items. Fixed by adding `errorPolicy=Omit` to the batch URL (ADO returns 200 with null placeholders for invalid IDs). Added null-safe iteration and per-ID omission tracking in `get_work_items_batch()` so valid items are returned while invalid IDs are reported individually. |
| 11 | ENG-007 | 2026-03-05 | `e0a015e` | **Environment profile config refactor + dependency refresh + docs alignment** — Added centralized `APP_ENV`-driven non-secret configuration (`config/`), environment PowerShell profiles (`config/environments/*.ps1`), and `infrastructure/scripts/show-config.ps1` for effective-value inspection. Refactored services/scripts to remove hardcoded environment values. Updated dependency lockfiles/requirements and aligned setup docs with the new environment workflow. |
| 12 | FR-1998 | 2026-03-05 | `6f3d645` | **Microsoft Graph user lookup by email** — New `graph_user_lookup.py` module with `get_user_info(email)` function that resolves a requestor email to displayName, jobTitle, and department via Microsoft Graph API. Uses shared Azure credential from `shared_auth.py`. Implements 4-strategy cascade (direct UPN, mailNickname filter, mail/UPN filter, `$search`) to handle both native and guest (#EXT#) accounts. |
| 13 | FR-2005 | 2026-03-05 | `099b45f` | **Entity export/import (Data Management)** — New Data Management page and API for exporting and importing Rules, Triggers, Routes, and Actions between environments. Auto-includes dependencies (Trigger→Rules+Route, Route→Actions). Auto-backup before import. Name-based upsert matching. Per-record selection with checkboxes. Import order: Rules→Actions→Routes→Triggers. |
| 14 | FR-2005 | 2026-03-05 | *pending* | **Data Management UX improvements** — 6 fixes from user testing: (1) loading spinners/overlay during export, import, and preview; (2) smart dependency auto-selection on export — clicking a trigger auto-selects its rules/route, clicking a route auto-selects its actions; (3) new Backups tab to list/restore pre-import snapshots; (4) "Available in Audit Log" changed from inactive text to a real navigation link; (5) export result now shows the downloaded filename; (6) new backend endpoints for listing and retrieving backups. |
| 15 | ENG-008 | 2026-03-05 | `e22e29c` | **ServiceTree routing integration — backend + UI inline edit** — Integrated ServiceTree BFF API for routing enrichment. New `servicetree_service.py` with 5-tier cache, fuzzy lookup, admin overrides. PATCH `/analysis/{id}/routing` endpoint for per-record inline corrections. `AnalysisResult` extended with 7 routing fields (serviceTreeMatch, serviceTreeOffering, solutionArea, csuDri, areaPathAdo, releaseManager, devContact). 6 admin catalog management endpoints. New `ServiceTreeRouting` React component (display/edit/compact modes) wired into QueuePage blade and EvaluatePage. `servicetree-catalog` Cosmos container. ServiceTree health dashboard component. |
| 16 | ENG-009 | 2026-03-05 | `d142975` | **Dedicated ServiceTree tab + regional_availability intent fix** — (1) Moved ServiceTree from Overview/Decision tabs into a dedicated 🗂️ ServiceTree tab with visual routing flow (horizontal chain), grouped cards (Service Match, Routing Assignment, Contacts), inline editing, empty state with "Add Routing Manually", and override audit trail. Tab bar now 5 tabs: Overview / Analysis / Decision / ServiceTree / Correct & Reanalyze. (2) Fixed "Invalid Intent: regional_availability" error by adding `regional_availability` to `VALID_INTENTS` in `llm_classifier.py` and `IntentType` enum in `intelligent_context_analyzer.py`. |
| 17 | ENG-010 | 2026-03-07 | *pending* | **Dynamic classification config — AI auto-discovery + admin review** — Replaced hardcoded classification lists in `llm_classifier.py` with Cosmos DB-backed dynamic config (`classification-config` container, partition key `/configType`). Categories, intents, and business-impact values loaded at runtime with 5-min cache (thread-safe). When the AI returns an unknown value, it is auto-recorded as "discovered" for admin review instead of raising ValueError. 3 new admin API endpoints (`GET /admin/classification-config`, `GET .../discoveries`, `PUT .../{id}`). New Classification Config page (filterable table, status badges, accept/reject/redirect workflow). Dashboard "AI Discoveries" count card with pulse animation. Seed migration script (`seed_classification_config.py`) for 40 initial documents (20 categories + 16 intents + 4 impacts). Total Cosmos containers: 13. Total API endpoints: 59. Total UI pages: 14. |
| 18 | ENG-011 | 2026-03-05 | *pending* | **Dashboard UI improvements — compact count cards, validation health card, 3-column grid** — Redesigned Dashboard layout: count metric cards condensed to compact 5-across row, validation warnings promoted from a separate page into an inline health card with severity icons, health status grid changed to responsive 3-column layout (was 2-column). Improved information density and reduced need to navigate away from Dashboard. |
| 19 | B0004 | 2026-03-05 | *pending* | **Bug fix — ServiceTree stats key mismatch (camelCase vs snake_case)** — `servicetree_service.py` `get_catalog_stats()` returned camelCase keys (`totalServices`, `totalOfferings`, etc.) but all 7 consumers in `admin_routes.py` expected snake_case (`total_services`, `total_offerings`). ServiceTree health dashboard showed 0 services despite 1439 being loaded. Fixed by changing `get_catalog_stats()` to return snake_case keys. |
| 20 | B0005 | 2026-03-05 | *pending* | **Bug fix — Classification Config Cosmos ORDER BY BadRequest** — Two Cosmos queries in `admin_routes.py` used multi-field `ORDER BY` clauses (`ORDER BY c.configType, c.value` and `ORDER BY c.discoveredCount DESC`) which require composite indexes not defined on the container. Cosmos returned `(BadRequest) One of the input values is invalid`. Fixed by removing `ORDER BY` from Cosmos queries and sorting in Python instead. |
| 21 | FR-2013 | 2026-03-05 | *pending* | **Routes page UX fixes — scrollable panels, truncated descriptions, reorder without save** — 4 fixes: (1) Routes list table scrolls at viewport height instead of pushing page infinitely. (2) RouteDesigner Available Actions and Route Actions panels cap at 420px with internal scroll. (3) Action detail text (operation/field/value) truncated with ellipsis + native tooltip on hover, action buttons pinned with `flex-shrink: 0`. (4) Critical bug: reorder (▲/▼) and remove (✕) buttons lacked `type="button"`, defaulting to `type="submit"` inside `<form>`, which triggered form submission on every click — user can now reorder freely and save explicitly. |
| 22 | FR-1998 | 2026-03-05 | *pending* | **Graph user card in analysis blade + collapsible accordion sections** — Two improvements to the Queue page analysis detail blade: (1) New `GET /api/v1/graph/user?email=` endpoint surfaces Graph user data (displayName, jobTitle, department) in a Requestor card with avatar circle, integrated into the blade header. (2) Blade body refactored from linear scroll into collapsible accordion sections (Summary, Requestor, ServiceTree Routing, AI Reasoning, Pattern & Disagreement, Domain Entities, Metadata) — Domain Entities groups 7 tag types behind a single toggle with count badge, collapsed by default. Each section independently expandable/collapsible. |
| 23 | B0006 | 2026-03-05 | *pending* | **Bug fix — SharedAuth AZ CLI not found on Windows** — `shared_auth.py` used `subprocess.run(["az", ...])` which raises `FileNotFoundError` on Windows because `az` is a `.cmd` file. Fixed by adding `shell=True` on Windows (`sys.platform == "win32"`), allowing the CLI credential path to work and preventing fallback to blocking interactive browser auth. |
| 24 | B0007 | 2026-03-06 | *pending* | **Bug fix — Requestor card always empty (wrong ADO field)** — `System.CreatedBy` was a service account ("Action 360 Platform") on all queue items, so the Requestor card always showed "No requestor data available". The actual human requestor is in `Custom.Requestors` (email string) and `Custom.Requestor` (identity object). Fixed by adding these fields to the ADO batch fetch, preserving raw emails in hidden `_requestorEmail`/`_createdByEmail` fields, and updating the frontend email extraction chain: `Custom.Requestors` → `_requestorEmail` → `_createdByEmail` → display name fallback. |
| 25 | PERF-001 | 2026-03-06 | *pending* | **Performance — Background prefetch + cache for Graph user data** — Opening the analysis blade showed a 5-second "Loading requestor info..." spinner on every click, and re-clicking the same item re-fetched. Implemented: (1) `useRef(new Map())` cache keyed by email with `{ data, loading, promise }` entries persisting across blade open/close. (2) Background prefetch IIFE fires after queue load, extracting all unique requestor emails and calling `getGraphUser()` with 80 ms stagger. (3) Cache-first blade open logic: cache hit → instant display, prefetch in-flight → await existing promise, cache miss → on-demand fetch + cache. Total API endpoints: 60. |

---

## Change Detail

### PERF-001 — Background Prefetch + Cache for Graph User Data

**Date:** 2026-03-06  
**Build ID:** *pending*  
**Requested By:** User feedback — 5-second latency on every blade open  
**Status:** Built, awaiting deployment

#### Problem

Every time a user clicked an analysis blade on the Queue page, the frontend called `GET /api/v1/graph/user?email=` and waited ~5 seconds for the Microsoft Graph API response. Closing and re-opening the same item repeated the fetch. With 30+ items in the queue, this created a poor user experience.

#### Solution — Three-Part Fix

1. **`useRef(new Map())` cache** — A `graphCacheRef` stores email → `{ data, loading, promise }` entries. The cache lives in a ref (not state) so it persists across renders and blade open/close cycles without triggering re-renders.

2. **Background prefetch after queue load** — After items are loaded into the queue, an IIFE extracts all unique requestor emails using the priority chain (`Custom.Requestors` → `_requestorEmail` → `_createdByEmail` → `Custom.Requestor` → `System.CreatedBy`). For each unique email not already cached, it fires `api.getGraphUser(email)` with 80 ms stagger between requests to avoid hammering the API.

3. **Cache-first blade open** — `handleAnalysisClick` checks the cache before fetching:
   - **Cache hit** (data exists): instantly `setGraphUser(cached.data)`, no spinner
   - **Prefetch in-flight** (promise exists): `setGraphUserLoading(true)`, awaits the existing promise
   - **Cache miss**: creates a new entry, calls the API, caches the result

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | Replaced `useState(null)` for graphUser with `useRef(new Map())` cache; added prefetch IIFE in queue load effect; replaced `handleAnalysisClick` Graph fetch with 3-path cache-first logic |

---

### B0007 — Requestor Card Always Empty (Wrong ADO Field)

**Date:** 2026-03-06  
**Build ID:** *pending*  
**Requested By:** Bug — blade showed "No requestor data available" on all items  
**Status:** Fixed

#### Symptom

The Requestor card in the analysis blade always showed "No requestor data available" on every queue item, despite Graph user lookup working correctly when tested with a known email.

#### Root Cause

`System.CreatedBy` — the field used to extract the requestor email — was a service account ("Action 360 Platform") on all queue items, not a human user. The actual human requestor is stored in ADO custom fields:
- `Custom.Requestors` — email string (e.g., `sujaypillai@microsoft.com`)
- `Custom.Requestor` — identity object with `displayName`, `uniqueName`, `imageUrl`

Neither field was included in the ADO batch fetch `fields` parameter.

#### Fix — Two Parts

1. **Backend** (`triage/services/ado_client.py`): Added `Custom.Requestor`, `Custom.Requestors`, and `System.CreatedBy` to the batch fetch `fields` list. After normalizing identity fields to displayName strings for table display, preserved raw emails in hidden fields: `_requestorEmail` (from `Custom.Requestor.uniqueName`) and `_createdByEmail` (from `System.CreatedBy.uniqueName`).

2. **Frontend** (`QueuePage.jsx`): Updated email extraction to use a priority chain: `Custom.Requestors` → `_requestorEmail` → `_createdByEmail` → `Custom.Requestor` → `System.CreatedBy` display name fallback.

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/services/ado_client.py` | Backend | Added `Custom.Requestor`, `Custom.Requestors`, `System.CreatedBy` to fetch fields; preserved `_requestorEmail` and `_createdByEmail` hidden fields |
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | Updated requestor email extraction chain for blade + prefetch |

---

### FR-2013 — Routes Page UX Fixes

**Date:** 2026-03-05  
**Build ID:** *pending*  
**Requested By:** Feature Request 2013 — user testing feedback  
**Status:** Built, awaiting deployment

#### Issues Addressed

| # | Issue | Fix |
|---|-------|-----|
| 1 | Routes list grows infinitely when many routes exist, pushing page content down | Added `max-height: calc(100vh - 200px)` + `overflow-y: auto` to `.routes-list .card` |
| 2 | Available Actions list in RouteDesigner overflows below the panel when many actions exist | Both Available Actions and Route Actions panels capped at `max-height: 420px` with `overflow-y: auto` on the list |
| 3 | Long action descriptions (value text) push reorder/remove buttons off-screen to the right | Action detail text constrained to `max-width: 220px` with `text-overflow: ellipsis`; native `title` tooltip shows full text on hover; action buttons set to `flex-shrink: 0` |
| 4 | Clicking reorder arrows (▲/▼) or remove (✕) immediately saves and closes the edit panel | Added `type="button"` to all interactive buttons in RouteDesigner — they previously defaulted to `type="submit"` inside the `<form>`, triggering form submission on every click |

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage-ui/src/components/routes/RouteDesigner.jsx` | Frontend | Added `type="button"` to Add, Move Up, Move Down, and Remove buttons; added `title` attribute to detail span for tooltip |
| `triage-ui/src/components/routes/RouteDesigner.css` | Frontend | Added `max-height: 420px` + flex column layout to panels; `overflow-y: auto` on lists; `max-width: 220px` on detail text; `flex-shrink: 0` on action buttons |
| `triage-ui/src/pages/RoutesPage.css` | Frontend | Added `max-height: calc(100vh - 200px)` + `overflow-y: auto` to `.routes-list .card` |

---

### FR-1998 — Graph User Card in Analysis Blade + Collapsible Sections

**Date:** 2026-03-05  
**Build ID:** *pending*  
**Requested By:** Feature Request 1998 — blade usability + requestor context  
**Status:** Built, awaiting deployment

#### Summary

Two improvements to the Queue page analysis detail blade:

1. **Requestor card** — When the blade opens, the frontend calls the new `GET /api/v1/graph/user?email=` endpoint (which delegates to `graph_user_lookup.get_user_info`). The returned display name, job title, and department render in a card with an avatar circle (blue gradient, first-initial). The endpoint normalises ADO identity strings (`"Display Name <email>"` → email via regex).

2. **Collapsible accordion sections** — The blade body, previously a long linear scroll, is now organized into independently collapsible sections:
   - **Summary** (always visible) — Confidence ring + classification grid
   - **Requestor** (open by default) — Graph user card
   - **ServiceTree Routing** (open by default) — Existing `<ServiceTreeRouting>` component
   - **AI Reasoning** (open by default) — Reasoning text
   - **Pattern & Disagreement** (open when present) — Pattern comparison + ENG-003 disagreement UI
   - **Domain Entities** (collapsed by default) — Groups 7 tag types (keyConcepts, azureServices, technologies, technicalAreas, regions, complianceFrameworks, detectedProducts) behind a single toggle with total count badge
   - **Metadata** (always visible footer)

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/api/routes.py` | Backend | New `GET /api/v1/graph/user?email=` endpoint — normalises ADO identity strings, calls `graph_user_lookup.get_user_info`, returns `{displayName, jobTitle, department, email}` or 404 |
| `triage-ui/src/api/triageApi.js` | Frontend | New `getGraphUser(email)` function in Graph User Lookup section |
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | Added `graphUser`/`graphUserLoading`/`collapsedSections` state + `toggleSection` helper; modified `handleAnalysisClick` to fetch Graph user; replaced entire blade body with collapsible accordion structure |
| `triage-ui/src/pages/QueuePage.css` | Frontend | ~140 lines: `.blade-accordion` toggle/chevron/badge/body, `.requestor-card`/avatar/info, `.blade-entities-grid`, dark-mode variants |

---

### B0006 — SharedAuth AZ CLI Not Found on Windows

**Date:** 2026-03-05  
**Build ID:** *pending*  
**Requested By:** Bug — server hung on startup  
**Status:** Fixed

#### Root Cause

`shared_auth.py` used `subprocess.run(["az", "account", "show"])` to probe Azure CLI availability. On Windows, `az` is a `.cmd` batch file (`az.cmd`), not an executable. Without `shell=True`, Python's `subprocess` raises `FileNotFoundError` (`[WinError 2]`). The code caught this as a non-fatal skip, falling through to `InteractiveBrowserCredential` which blocks the event loop waiting for browser interaction — hanging the single uvicorn worker and making all HTTP requests time out indefinitely.

#### Fix

Added `shell=(sys.platform == "win32")` to the `subprocess.run()` call so Windows resolves `az.cmd` through the shell. Azure CLI credential now works on Windows, avoiding the blocking browser fallback.

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `shared_auth.py` | Backend | Added `shell=True` on Windows for `az` subprocess call |

---

### ENG-010 — Dynamic Classification Config

**Date:** 2026-03-07  
**Build ID:** *pending*  
**Requested By:** System design — hardcoded lists prevented AI from growing  
**Status:** Built, awaiting deployment + seed migration

#### Problem

`llm_classifier.py` had hardcoded `VALID_CATEGORIES`, `VALID_INTENTS`, and `VALID_BUSINESS_IMPACTS` lists. When GPT-4o returned a value not in these lists (e.g., `regional_availability`), a `ValueError` was raised and analysis failed. Adding new values required a code change and redeployment.

#### Solution

Dynamic classification config stored in Cosmos DB. The system loads categories/intents/impacts at runtime with a 5-minute cache. Unknown AI values are automatically recorded as "discovered" items for admin review, rather than blocking analysis.

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/config/cosmos_config.py` | Modified | Added `classification-config` container definition (13 total) |
| `llm_classifier.py` | Modified | Major refactor — dynamic loading, 5-min cache, AI auto-discovery, no more ValueError |
| `triage/api/admin_routes.py` | Modified | 3 new endpoints: list config, list discoveries, update config item |
| `seed_classification_config.py` | New | One-time seed migration (40 docs: 20 cats + 16 intents + 4 impacts) |
| `triage-ui/src/pages/ClassificationConfigPage.jsx` | New | Full management page with filters, badges, accept/reject/redirect |
| `triage-ui/src/pages/ClassificationConfigPage.css` | New | Styles for classification config page |
| `triage-ui/src/pages/Dashboard.jsx` | Modified | AI Discoveries count card with pulse animation |
| `triage-ui/src/pages/Dashboard.css` | Modified | `.dashboard-count-highlight` + `disco-pulse` keyframe |
| `triage-ui/src/api/triageApi.js` | Modified | 3 new API functions for classification config |
| `triage-ui/src/App.jsx` | Modified | Lazy import + route for `/classification` |
| `triage-ui/src/utils/constants.js` | Modified | 🧠 Classification nav item |

#### Deployment Steps

1. Deploy updated Triage API (backend changes)
2. Run seed migration: `python seed_classification_config.py` (creates `classification-config` container + 40 docs)
3. Deploy updated Triage UI (frontend changes)
4. Verify: Dashboard shows "AI Discoveries: 0", Classification Config page lists 40 official items

---

### FR-2005 (UX) — Data Management UX Improvements

**Date:** 2026-03-05  
**Build ID:** *pending*  
**Requested By:** User testing feedback  
**Status:** Built, awaiting deployment

#### Issues Addressed

| # | Issue | Fix |
|---|-------|-----|
| 1 | No loading indicator during export/import — user thinks system is broken | Added spinner overlay with animation during all async operations |
| 2 | Clicking a trigger in export doesn't auto-select its dependencies | Smart bidirectional dependency graph: selecting a trigger auto-selects referenced rules + route + route's actions |
| 3 | Import button gives no visual feedback while processing | Same spinner overlay as export |
| 4 | No way to view or restore backups without doing a full import/export | New "Backups" tab listing all pre-import snapshots with one-click restore |
| 5 | "Available in Audit Log" text looks like a link but does nothing | Changed to a real `<Link to="/audit">` navigation element |
| 6 | Export Complete shows no filename or download location | Export result card now displays the downloaded filename |

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/services/data_management_service.py` | Backend | Backups persisted as audit entries; new `list_backups()` method; fixed `get_backup_for_audit()` JSON parsing |
| `triage/api/data_management_routes.py` | Backend | New `GET /backups` and `GET /backups/{audit_id}` endpoints |
| `triage-ui/src/pages/DataManagementPage.jsx` | Frontend | Spinner overlay, dependency graph auto-selection, Backups tab, filename display, audit link |
| `triage-ui/src/pages/DataManagementPage.css` | Frontend | Spinner animation, overlay styles, backup card styles, link styles |
| `triage-ui/src/api/triageApi.js` | Frontend | New `listBackups()` and `getBackup()` API functions |

---

### ENG-008 — ServiceTree Routing Integration (Backend + UI Inline Edit)

**Date:** 2026-03-05  
**Build ID:** `e22e29c`  
**Requested By:** Triage operations (automated routing enrichment)  
**Status:** Built, awaiting deployment

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `servicetree_service.py` | Backend (new) | Core ServiceTree service — BFF API fetch, 5-tier cache, fuzzy lookup (exact→substring→fuzzy), admin overrides, singleton |
| `triage/api/routes.py` | Backend | Added `_RoutingPatch` Pydantic model + `PATCH /analysis/{id}/routing` endpoint; ServiceTree enrichment in `_map_hybrid_to_analysis_result()` |
| `triage/api/admin_routes.py` | Backend | 6 new ServiceTree admin endpoints: catalog summary, search, list services, refresh, apply/remove overrides; ServiceTree health component + diagnostics |
| `triage/models/analysis_result.py` | Backend | 7 new ServiceTree fields: serviceTreeMatch, serviceTreeOffering, solutionArea, csuDri, areaPathAdo, releaseManager, devContact |
| `triage/config/cosmos_config.py` | Backend | Added `servicetree-catalog` container (partition key `/solutionArea`) |
| `triage-ui/src/components/ServiceTreeRouting.jsx` | Frontend (new) | Reusable component with display/edit/compact modes, override badge, 3-column grid |
| `triage-ui/src/components/ServiceTreeRouting.css` | Frontend (new) | Styles for routing section, edit grid, override badge, compact variant |
| `triage-ui/src/api/triageApi.js` | Frontend | Added `patchAnalysisRouting()` API function |
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | ServiceTree routing section in analysis detail blade |
| `triage-ui/src/pages/EvaluatePage.jsx` | Frontend | ServiceTree removed from Overview/Decision; dedicated ServiceTree tab added |
| `triage-ui/src/components/ServiceTreeTab.jsx` | Frontend (new) | Dedicated ServiceTree tab with visual routing flow, grouped cards, inline editing, empty state, override audit |
| `triage-ui/src/components/ServiceTreeTab.css` | Frontend (new) | Styles for routing flow, grouped cards, buttons, responsive layout |

#### Behavior Summary

1. **Automatic Enrichment**: During analysis, detected products/Azure services are matched against the ServiceTree catalog using exact → substring → fuzzy matching. The best match populates 7 routing fields on the `AnalysisResult`.
2. **Inline Display**: ServiceTree routing fields are shown in a 3-column grid on the QueuePage analysis blade and in a dedicated **ServiceTree** tab on EvaluatePage with visual routing flow and grouped cards.
3. **Inline Edit**: Admins can click "Edit Routing" on the **ServiceTree** tab of EvaluatePage (or QueuePage blade) to correct any routing field. Changes are saved via `PATCH /analysis/{id}/routing` and stamped with `routingOverrideBy` / `routingOverrideAt`.
4. **Catalog Management**: 6 admin endpoints for searching, refreshing, and overriding the cached ServiceTree catalog. Cache refreshes from the BFF API every 7 days.
5. **ServiceTree BFF**: Proxied through `tf-servicetree-api.azurewebsites.net` (Express.js → `F051-PRD-Automation` Function App), authenticated via corp tenant AAD.

---

### FR-2005 — Entity Export/Import (Data Management)

**Date:** 2026-03-05  
**Build ID:** `099b45f`  
**Requested By:** Operations (environment portability and backup)  
**Status:** Built, awaiting deployment

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/services/data_management_service.py` | Backend (new) | Core export/import service — dependency resolution, name-based upsert, auto-backup, ID remapping |
| `triage/api/data_management_routes.py` | Backend (new) | FastAPI router with 3 POST endpoints (export, import/preview, import/execute) |
| `triage/api/routes.py` | Backend | Mounted data management router |
| `triage-ui/src/pages/DataManagementPage.jsx` | Frontend (new) | Tabbed Export/Import page with per-record checkboxes and dependency display |
| `triage-ui/src/pages/DataManagementPage.css` | Frontend (new) | Styles matching existing design system |
| `triage-ui/src/api/triageApi.js` | Frontend | Added 3 API functions: exportEntities, previewImport, executeImport |
| `triage-ui/src/utils/constants.js` | Frontend | Added "Data Mgmt" nav item with 📦 icon |
| `triage-ui/src/App.jsx` | Frontend | Added lazy import and route for /data-management |

#### Behavior Summary

1. **Export**: Select entity types and individual records → auto-includes dependencies → downloads JSON bundle.
2. **Import Preview**: Upload JSON bundle → shows per-record create/update actions before committing.
3. **Import Execute**: Auto-backs up current state → imports in dependency order (Rules→Actions→Routes→Triggers) → name-based upsert with ID remapping.
4. **Dependency Resolution**: Triggers auto-include their referenced Rules and Route; Routes auto-include their Actions.
5. **Cross-Environment**: Matches by name (natural key), not UUID — safe for transfers between environments with different IDs.

---

### ENG-007 — Environment Profiles, Config Centralization, and Documentation Alignment

**Date:** 2026-03-05  
**Build ID:** `e0a015e`  
**Requested By:** Engineering (platform maintainability)  
**Status:** Built, awaiting deployment

#### Files Modified (Representative)

| File | Type | Description |
|------|------|-------------|
| `config/__init__.py` | Backend config | Added `AppConfig` with `APP_ENV` profile loading and env-var override support |
| `config/dev.py`, `config/preprod.py`, `config/prod.py` | Backend config | Added environment-specific non-secret defaults and required prod env guards |
| `config/environments/dev.ps1`, `config/environments/preprod.ps1`, `config/environments/prod.ps1` | Deployment ops | Added shared PowerShell profile files for script parameterization |
| `infrastructure/scripts/show-config.ps1` | Deployment ops (new) | Added script to print effective settings by environment profile |
| `keyvault_config.py`, `shared_auth.py`, `ado_integration.py`, `enhanced_matching.py`, `launcher.py` | Backend | Replaced hardcoded environment values with centralized config lookups |
| `api_gateway.py`, `api/search_api.py`, `field-portal/api/config.py`, `admin_service.py` | Backend/API | Switched runtime behavior to environment-driven values and safer defaults |
| `containers/deploy.ps1`, `infrastructure/deploy/*.ps1`, `configure_keyvault_security.ps1`, `ensure_cosmos_firewall_ip.ps1`, `add_ip_to_keyvault.ps1` | Deployment ops | Updated scripts to load shared environment profile values instead of inline literals |
| `README.md`, `docs/DEVELOPER_SETUP.md` | Documentation | Added `APP_ENV` workflow and profile inspection guidance |

#### Behavior Summary

1. Developers can switch environments by setting `APP_ENV` (`dev`, `preprod`, `prod`).
2. Runtime services and deployment scripts now resolve non-secret values from centralized profile files.
3. Manual hardcoded local values (ports/endpoints/resource names) are significantly reduced.
4. `show-config.ps1` gives a quick audit of effective values and shell-level overrides.
5. Documentation now reflects the updated configuration model and setup flow.

### FR-1998 — Microsoft Graph User Lookup by Email

**Date:** 2026-03-05  
**Build ID:** `6f3d645`  
**Requested By:** Feature Request 1998  
**Status:** Built, awaiting integration

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `graph_user_lookup.py` | Backend (new) | Microsoft Graph user lookup — `get_user_info(email)` returns displayName, jobTitle, department |

#### Behavior Summary

1. Call `get_user_info("user@domain.com")` with a requestor email address.
2. The function acquires a Graph API token via the shared credential from `shared_auth.py` (no extra auth prompt).
3. Four lookup strategies execute in sequence until a match is found:
   - **Strategy 1:** Direct UPN lookup (`/users/{email}`)
   - **Strategy 2:** Filter by `mailNickname eq '{alias}'`
   - **Strategy 3:** Filter by `mail eq '{email}' or userPrincipalName eq '{email}'`
   - **Strategy 4:** `$search` on `mailNickname:{alias}` (catches guest/external `#EXT#` accounts)
4. Returns a `GraphUserInfo` dataclass with `display_name`, `job_title`, `department` — or `None` if not found.
5. Can be run standalone for testing: `python graph_user_lookup.py bprice@microsoft.com`

### FR-1997 — Multi-Field Search Operators (containsAny + regexMatchAny)

**Date:** 2026-03-03  
**Build ID:** `6abe2e1`  
**Requested By:** Feature Request 1997  
**Status:** Deployed to Pre-Prod

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/models/rule.py` | Backend | Added `containsAny` and `regexMatchAny` to `VALID_OPERATORS`, added `fields: List[str]` attribute, validation, display string |
| `triage/api/schemas.py` | Backend | Added `fields: Optional[List[str]]` to `RuleCreate` and `RuleUpdate` |
| `triage/engines/rules_engine.py` | Backend | Added `_evaluate_contains_any()` and `_evaluate_regex_match_any()` multi-field evaluation methods + operator dispatch |
| `triage-ui/src/utils/constants.js` | Frontend | Added `containsAny` and `regexMatchAny` operators; `MULTI_FIELD_OPERATORS` constant |
| `triage-ui/src/components/common/MultiFieldCombobox.jsx` | Frontend (new) | Chip-based multi-select ADO field picker |
| `triage-ui/src/components/common/MultiFieldCombobox.css` | Frontend (new) | Styling for multi-field combobox |
| `triage-ui/src/components/rules/RuleForm.jsx` | Frontend | Conditional multi-field / keyword UI when `containsAny` selected; regex-specific labels, placeholders, and hints when `regexMatchAny` selected |
| `triage-ui/src/pages/RulesPage.jsx` | Frontend | Table field column renders multi-field rules as chips |

#### Behavior Summary

**containsAny:**
1. User selects **"Contains Any (multi-field)"** operator in the rule form.
2. Field input switches to a multi-select chip picker for choosing multiple ADO/Analysis fields.
3. Value input becomes a keyword textarea (comma-separated).
4. At evaluation time, the engine checks if **any keyword** appears in **any selected field** (case-insensitive substring match), returning `true` on the first hit.

**regexMatchAny:**
1. User selects **"Regex Match Any (multi-field)"** operator in the rule form.
2. Same multi-field chip picker as containsAny.
3. Value input shows regex-specific placeholder (e.g., `SR\d+, ICM\d+`) and hint text.
4. At evaluation time, the engine runs `re.search(pattern, text, re.IGNORECASE)` for each pattern × field combination, returning `true` on the first hit. Invalid regex patterns are logged and skipped.

---

### ENG-003 — Active Learning: Disagreement-Driven Training Signals

**Date:** 2026-03-05  
**Build ID:** *pending*  
**Requested By:** Engineering (ENG-003 Design Doc)  
**Status:** Built, awaiting deployment

#### Files Modified (Steps 1-2: Disagreement UI + Training Signals)

| File | Type | Description |
|------|------|-------------|
| `triage/config/cosmos_config.py` | Backend | Added `training-signals` container definition (PK: `/workItemId`) |
| `triage/api/admin_routes.py` | Backend | Migrated corrections CRUD from JSON file to Cosmos with auto-seed and fallback. Added `TrainingSignalCreate`/`TrainingSignalItem` models. New `POST /admin/training-signals` and `GET /admin/training-signals` endpoints. Corrections now use document IDs instead of array indices. |
| `hybrid_context_analyzer.py` | Backend | `_load_corrections()` now tries Cosmos first, falls back to `corrections.json` |
| `triage-ui/src/api/triageApi.js` | Frontend | Added `submitTrainingSignal()` and `listTrainingSignals()`. Updated `updateCorrection()`/`deleteCorrection()` to use document IDs. |
| `triage-ui/src/pages/EvaluatePage.jsx` | Frontend | Added disagreement resolution UI (LLM / Pattern / Neither) in Analysis tab after Pattern Engine Comparison section. State: `disagreementStates` map per work item. |
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | Added disagreement resolution UI in blade after Pattern Engine Comparison section. State: `bladeDisagreement` map. |
| `triage-ui/src/pages/CorrectionsPage.jsx` | Frontend | Updated to use document ID-based CRUD instead of index-based. |

#### Files Modified (Step 3: Pattern Weight Tuning)

| File | Type | Description |
|------|------|-------------|
| `weight_tuner.py` | Backend (new) | `PatternWeightTuner` class — reads training signals from Cosmos, aggregates by category, computes per-category multipliers (0.6–1.3), stores as a single document in the `training-signals` container. |
| `intelligent_context_analyzer.py` | Backend | `_load_weight_adjustments()` reads multipliers from Cosmos via `PatternWeightTuner`. `_classify_category()` applies multipliers to `category_scores` before selecting the winning category. |
| `triage/api/admin_routes.py` | Backend | Added `POST /admin/tune-weights` (run batch) and `GET /admin/pattern-weights` (view adjustments) endpoints with `WeightTuningResponse` model. |
| `triage-ui/src/api/triageApi.js` | Frontend | Added `tunePatternWeights()` and `getPatternWeights()` API functions. |

#### Behavior Summary

**Steps 1-2 (Disagreement UI + Training Signals):**
1. When LLM and Pattern Engine disagree on classification, a **"Resolve Disagreement"** prompt appears in both the EvaluatePage Analysis tab and the QueuePage blade.
2. Users select one of three options: **🧠 LLM is correct**, **📊 Pattern is correct**, or **❌ Neither is correct**.
3. If "Neither" is selected, category/intent inputs appear for manual specification.
4. Optional notes field available for all choices.
5. On submit, a training signal is stored in the Cosmos `training-signals` container.
6. Corrections data migrated from `corrections.json` flat file to Cosmos `corrections` container with automatic one-time seed. JSON fallback preserved for environments without Cosmos.

**Step 3 (Pattern Weight Tuning):**
7. `POST /admin/tune-weights` reads all training signals, aggregates human choices by pattern category, and computes a score multiplier per category (0.6× penalty to 1.3× boost).
8. Categories need ≥ 3 signals before adjustments are applied; below threshold they stay at 1.0×.
9. The pattern engine loads these multipliers at startup and applies them to `category_scores` in `_classify_category()` before selecting the winning category.
10. `GET /admin/pattern-weights` returns the current adjustments with per-category accuracy, signal counts, and status (boosted/penalized/neutral).

#### Files Modified (Step 4: Few-Shot Injection from Training Signals)

| File | Type | Description |
|------|------|-------------|
| `hybrid_context_analyzer.py` | Backend | Added `_load_training_signals()` — queries Cosmos `training-signals` container (max 50, excludes `_system` docs). Added `_find_relevant_training_signals()` — scores signals by category relevance, 'neither' bonus, keyword overlap, returns top 5. Signals loaded in `__init__()` and injected in `analyze()` via `pattern_features["relevant_training_signals"]`. |
| `llm_classifier.py` | Backend | Extended `_build_user_prompt()` with third injection block: "Classification Examples from Human Feedback" — formats each relevant training signal showing LLM/Pattern categories, human choice, resolved category, and notes. |

#### Files Modified (Step 5: Dashboard Agreement Rate Metric)

| File | Type | Description |
|------|------|-------------|
| `triage/api/admin_routes.py` | Backend | Added `GET /admin/agreement-rate` endpoint with `AgreementRateResponse` / `PeriodStats` models. Queries `analysis-results` for agreement field, counts `training-signals` (excluding `_system`), computes overall + per-period (7/30/90 day) agreement rates. |
| `triage-ui/src/api/triageApi.js` | Frontend | Added `getAgreementRate()` API function. |
| `triage-ui/src/pages/Dashboard.jsx` | Frontend | Added `agreementRate` state, parallel fetch in `useEffect`, and agreement rate card in status row showing percentage, total analyses, signal count, and color-coded indicator (green >= 80%, orange >= 60%, red < 60%). |

#### Behavior Summary (Steps 4-5)

**Step 4 (Few-Shot Signal Injection):**
11. Training signals are loaded from Cosmos at startup (max 50 most recent, excluding system documents).
12. When analyzing a work item, the system finds the top 5 most relevant training signals by scoring category relevance (±3.0 match/mismatch), 'neither' override bonus (+1.5), and keyword overlap in notes.
13. Relevant signals are injected into the LLM prompt as "Classification Examples from Human Feedback" — each shows what LLM/Pattern said, what the human chose, and the resolved category.
14. This provides few-shot learning: the LLM sees how humans resolved similar disagreements and adjusts accordingly.

**Step 5 (Agreement Rate Metric):**
15. `GET /admin/agreement-rate` queries all analysis results with an `agreement` field and computes the overall agreement rate plus breakdowns for the last 7, 30, and 90 days.
16. The Dashboard shows a new "LLM / Pattern Agreement" status card alongside the existing API status card.
17. Color-coded: green (>= 80%), orange (>= 60%), red (< 60%). Displays total analysis count and training signal count.

---

### FR-1993 — Rules Table Pagination & Expandable Value Cells

**Date:** 2026-03-03  
**Build ID:** `6abe2e1`  
**Requested By:** Feature Request 1993  
**Status:** Deployed to Pre-Prod

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage-ui/src/components/common/Pagination.jsx` | Frontend (new) | Reusable pagination control with page numbers, prev/next, and page-size selector |
| `triage-ui/src/components/common/Pagination.css` | Frontend (new) | Pagination styling |
| `triage-ui/src/components/common/ExpandableValue.jsx` | Frontend (new) | Truncates long comma-separated lists, shows "+N more" badge with expand/collapse |
| `triage-ui/src/components/common/ExpandableValue.css` | Frontend (new) | ExpandableValue styling |
| `triage-ui/src/pages/RulesPage.jsx` | Frontend | Integrated Pagination, ExpandableValue, and search; added page/pageSize/searchTerm state; switched table to filtered + paginated slice |
| `triage-ui/src/pages/RulesPage.css` | Frontend | Added search input styling |

#### Behavior Summary

1. Rules table defaults to **25 rows per page** with options for 50 or 100.
2. Page navigation shows first/prev/page numbers/next/last with ellipsis for large page counts.
3. Changing filters resets to page 1.
4. A **search box** in the page header filters rules instantly by name, field, or value (case-insensitive). A clear button appears when text is entered.
5. Search integrates with pagination — results reset to page 1, and the paginated count reflects filtered results.
6. Value column shows the first **3 items** of a comma-separated list; remaining items are hidden behind a **"+N more"** pill badge.
7. Clicking the badge expands to show all items; a **"show less"** link collapses back.

---

### FR-1993 (cont.) — Pagination, Search & Expandable Values for Triggers, Actions, Routes

**Date:** 2026-03-03  
**Build ID:** *pending*  
**Requested By:** Feature Request 1993  
**Status:** Deployed to Pre-Prod

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage-ui/src/components/common/EntitySearch.css` | Frontend (new) | Shared search-input styles (`.entity-search`, `.entity-search-input`, `.entity-search-clear`) extracted from RulesPage |
| `triage-ui/src/pages/TriggersPage.jsx` | Frontend | Added pagination, search (by name/expression/route), filteredTriggers/paginatedTriggers memos |
| `triage-ui/src/pages/ActionsPage.jsx` | Frontend | Added pagination, search (by name/field/operation/value), ExpandableValue for Value column |
| `triage-ui/src/pages/RoutesPage.jsx` | Frontend | Added pagination, search (by name/action names), ExpandableValue for Actions column |
| `triage-ui/src/pages/RulesPage.jsx` | Frontend | Migrated search CSS class names from `.rules-search-*` to shared `.entity-search-*` |
| `triage-ui/src/pages/RulesPage.css` | Frontend | Removed page-specific search styles (now in EntitySearch.css) |

#### Behavior Summary

All three additional entity pages now have the same UX as Rules:

1. **Pagination** — 25/50/100 per page with full page-number navigation.
2. **Search** — Real-time case-insensitive filtering:
   - **Triggers:** name, expression DSL, route name
   - **Actions:** name, target field, operation label, value
   - **Routes:** name, action names
3. **Expandable values** — Actions value column and Routes action-list column use `ExpandableValue` to truncate long lists with "+N more" expand/collapse.
4. Filter count displays updated total with search/filter context.

---

### FR-1994, FR-1999 — Tabbed Analysis Detail Views + Blade "No Data" Placeholders

**Date:** 2026-03-04  
**Build ID:** `4b06cff`  
**Requested By:** Feature Requests 1994, 1999  
**Status:** Deployed to Pre-Prod

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `field-portal/ui/src/pages/AnalysisDetailPage.jsx` | Frontend | Rewrote layout with 5-tab interface (Overview, Analysis, Decision, ServiceTree, Correct & Reanalyze); added `activeTab` state |
| `field-portal/ui/src/styles/global.css` | Frontend | Added ~90 lines of tab CSS (`.analysis-tabs`, `.analysis-tab`, `.tab-badge`, `.analysis-tab-panel`, `@keyframes fadeInPanel`, responsive breakpoint) |
| `triage-ui/src/pages/EvaluatePage.jsx` | Frontend | Added per-work-item 5-tab interface with `activeDetailTabs` state map; rewrote `renderAnalysisDetail` function |
| `triage-ui/src/pages/EvaluatePage.css` | Frontend | Added ~80 lines of tab CSS adapted for Triage UI CSS variables |
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | Blade sections always render with "No data" placeholder for empty fields; removed conditional hiding |
| `triage-ui/src/pages/QueuePage.css` | Frontend | Added `.no-data` style (italic, light gray) for empty field placeholders |

#### Behavior Summary

**Field Portal AnalysisDetailPage & Triage UI EvaluatePage — Tabbed Interface:**
1. Content organized into 5 pill-style tabs: 📋 **Overview**, 🧠 **Analysis**, 🎯 **Decision**, 🗂️ **ServiceTree**, 🔄 **Correct & Reanalyze**.
2. Status banner remains above tabs (always visible regardless of active tab).
3. Decision tab displays entity count badge (e.g., "12") from domain entities.
4. Tab panels animate in with `fadeInPanel` CSS keyframes.
5. Responsive: tabs stack vertically below 700px viewport width.
6. EvaluatePage maintains independent tab state per work item via `activeDetailTabs` map keyed by work item ID.

**QueuePage Blade — Linear Layout with "No Data" Placeholders:**
1. Blade uses linear scrolling layout (tabs were tested but reverted per user feedback).
2. All section headers always display regardless of data availability.
3. Empty fields show `<span className="no-data">No data</span>` in italic light gray.
4. Consistent layout across items — LLM-analyzed items show richer entity data while pattern-match items show "No data" for unpopulated sections.

---

## Engineering Design Changes

> These are internal engineering improvements and architectural changes that are not tied to a specific Feature Request. They improve reliability, observability, and system intelligence.

### ENG-001 — Fix Empty Analysis Tab (reasoning === contextSummary)

**Date:** 2026-03-04  
**Build ID:** *pending*  
**Identified By:** Engineering (internal testing)  
**Status:** Ready for deploy

#### Problem

The Analysis tab on both the Triage UI EvaluatePage and Field Portal AnalysisDetailPage was rendering empty when the analysis was performed by LLM. The guard condition `reasoning && reasoning !== contextSummary` always evaluated to `false` for LLM results because `hybrid_context_analyzer.py` (line 565) sets both fields to the same `llm_result.reasoning` value.

#### Root Cause

In `hybrid_context_analyzer.py`, when LLM is the primary source:
```python
ctx_summary = llm_result.reasoning if llm_result.reasoning else ...
```
This means `reasoning === contextSummary` for all LLM-analyzed items, causing the frontend condition to suppress the entire reasoning block.

#### Fix

- **`triage-ui/src/pages/EvaluatePage.jsx`** — Removed the `!== detail.contextSummary` guard. Added object-type handling for dict-style reasoning. Enriched Analysis tab with Pattern Engine Comparison (pattern category, pattern confidence, agreement badge) and Category Score Breakdown (sorted badges from `categoryScores`).
- **`field-portal/ui/src/pages/AnalysisDetailPage.jsx`** — Same guard removal so reasoning always renders.
- **`triage-ui/src/pages/QueuePage.jsx`** — Replaced "AI Analysis Summary" section (which showed `contextSummary`) with dedicated "AI Classification Reasoning" section and new "Pattern Engine Comparison" section in the blade.

---

### ENG-002 — Resolve Entity IDs to Human-Readable Names

**Date:** 2026-03-04  
**Build ID:** *pending*  
**Identified By:** Engineering (internal testing)  
**Status:** Ready for deploy

#### Problem

Evaluation results and entity cross-reference ("Used In") sections displayed raw Cosmos DB document IDs (e.g., `dt-b2323785`, `route-1cd48eef`, `action-db6bc19d`) instead of human-readable entity names.

#### Fix

- **`triage/api/routes.py`** — Evaluate endpoint now builds 4 name lookup maps (`ruleNames`, `triggerNames`, `routeNames`, `actionNames`) from Cosmos `SELECT c.id, c.name`. References endpoint returns `referenceNames` map alongside IDs.
- **`triage-ui/src/pages/EvaluatePage.jsx`** — Trigger/route badges and actions list use name maps with raw ID fallback and ID-in-tooltip.
- **`triage-ui/src/pages/QueuePage.jsx`** — Same trigger/route name resolution.
- **`triage-ui/src/pages/RulesPage.jsx`**, **`RoutesPage.jsx`**, **`ActionsPage.jsx`** — "Used In" sections resolve IDs via `referenceNames` map.

---

### ENG-003 — Active Learning: Disagreement-Driven Classification Feedback Loop (Design)

**Date:** 2026-03-04  
**Status:** Design / Proposed

#### Motivation

When the LLM and pattern engine disagree on classification (e.g., LLM says "troubleshooting" at 95% confidence, pattern says "technical_support" at 40%), users currently see this as informational only. There is no mechanism to capture which answer was correct and feed that back into the system.

#### Proposed Design

1. **Disagreement Prompt UI** — When `agreement === false`, surface an inline "Which classification is correct?" prompt on the Analysis tab and QueuePage blade. Three options:
   - **LLM is correct** — accept the LLM classification (single click)
   - **Pattern is correct** — accept the pattern engine classification (single click)
   - **Neither is correct** — expands a category dropdown + optional notes field so the user can supply the right answer manually

   Prioritize low friction (< 2 seconds for LLM/Pattern; < 10 seconds for Neither). The Neither path captures net-new training data the system has never seen.

2. **Training Signal Storage** — Store each resolution in a `training-signals` Cosmos container:
   ```json
   {
     "id": "ts-{workItemId}-{timestamp}",
     "workItemId": 713300,
     "llmCategory": "troubleshooting",
     "patternCategory": "technical_support",
     "humanChoice": "business_desk",
     "resolution": "neither",
     "correctionNotes": "This is a funding request — Business Desk",
     "resolvedBy": "bprice@microsoft.com",
     "timestamp": "2026-03-04T..."
   }
   ```
   `resolution` field values: `"llm"` | `"pattern"` | `"neither"`.
   When `resolution` is `"llm"` or `"pattern"`, `humanChoice` is auto-populated.
   When `resolution` is `"neither"`, `humanChoice` is the user-selected category from the dropdown and `correctionNotes` captures the explanation.

3. **Pattern Engine Weight Tuning** — Batch process accumulated corrections to adjust keyword weights and category scoring rules in the pattern engine. If EDR-related items are consistently resolved in favor of the LLM, boost the pattern engine's scoring for those keyword clusters.

4. **LLM Prompt Enrichment** — Inject top-N corrections as few-shot examples in the LLM system prompt to refine classification without retraining.

5. **Agreement Rate Metric** — Track LLM/pattern agreement rate over time on the Dashboard as a system health indicator. Upward trend = system is learning.

#### Relationship to Existing Corrections System

The project already has a **Corrections** system (Phase 1 — Corrective Learning) that is actively wired end-to-end:

| Layer | How it works today |
|-------|-------------------|
| **Storage** | `corrections.json` flat file at project root (not Cosmos yet). CRUD via `/admin/corrections` API. |
| **UI — CorrectionsPage** | Dedicated page (`/corrections`) for viewing, adding, editing, and deleting corrections. |
| **UI — EvaluatePage** | "Approve" and "Request Corrections" buttons call `addCorrection()`, writing to corrections.json. "Re-Analyze" also saves a correction before re-running the analyzer with hint text appended. |
| **Analyzer ingestion** | `HybridContextAnalyzer.__init__()` loads corrections.json at startup. On each analysis, `_find_relevant_corrections()` does keyword overlap matching (≥ 20% word similarity) and returns the top 3. |
| **LLM prompt injection** | `LLMClassifier._build_prompt()` appends matched corrections as "Learn from Previous Corrections" examples in the prompt. |
| **Re-analysis endpoint** | `/analyze/reanalyze` appends `[CORRECTION: ...]` hints to the work item description, re-runs the analyzer, and upserts the result in Cosmos. |
| **Cosmos container** | `corrections` container is defined in `cosmos_config.py` (partition key `/workItemId`) but is **not yet used** — data lives in the JSON file. |
| **Analysis result model** | `AnalysisResult.relevantCorrections` stores matched correction references in each analysis output. |

**Key gap:** The existing system captures corrections *reactively* (user must open EvaluatePage, mark "incorrect", fill in the right category, and submit). The proposed Active Learning design captures corrections *proactively* at the point of disagreement, with lower friction and richer signal (`resolution` type + both engine outputs preserved).

**Migration path:** Corrections move to Cosmos in Step 2 alongside the new training-signals container, so all feedback data is Cosmos-backed from day one. The existing corrections.json entries are migrated into the `corrections` Cosmos container, admin CRUD endpoints switch to Cosmos reads/writes, and the analyzer loads corrections from Cosmos instead of the flat file. Training signals and corrections share a unified Cosmos-backed store from the start — no temporary coexistence of file + database.

#### Priority Sequence

| Step | Deliverable | Complexity |
|------|-------------|------------|
| 1 | Disagreement prompt UI — 3-option (LLM / Pattern / Neither) on Analysis tab + blade | Medium |
| 2 | Training signals Cosmos container + API **+ migrate corrections.json → Cosmos `corrections` container** (all feedback Cosmos-backed from day one) | Medium |
| 3 | Pattern engine weight adjustment (batch) | Medium |
| 4 | Few-shot injection from training signals (extend existing corrections injection) | Low |
| 5 | Dashboard agreement rate metric | Low |


---

## Bugs Found During Testing

| # | Bug ID | Date | Related CR | Build ID (Git) | Summary |
|---|--------|------|------------|-----------------|---------|
| 1 | B0001 | 2026-03-04 | ENG-003 | *pending* | **False disagreement — enum vs string comparison** — Agreement check always returned `False` because pattern engine returns an `IssueCategory` enum (e.g., `IssueCategory.SUPPORT_ESCALATION`) while the LLM classifier returns a plain string (`"support_escalation"`). Python `==` between enum and string is always `False`. Also, original check required both category AND intent to match, but only category matters for triage routing. |
| 2 | B0002 | 2026-03-06 | ENG-003 | *pending* | **Hybrid source not recognized as LLM** — `isLLM` check in `EvaluatePage.jsx` only matched `"llm"`, so `"hybrid"` source items appeared as pattern-only. Fixed to include `"hybrid"`. |
| 3 | B0003 | 2026-03-06 | ENG-003 | *pending* | **Comparison crash on pattern-only fallback** — When LLM unavailable, `agreement` is `null`. UI assumed boolean, crashing on Pattern Engine Comparison. Fixed in both backend (`agreement=None`) and frontend (null guard). |
| 4 | B0004 | 2026-03-05 | ENG-008 | *pending* | **ServiceTree stats key mismatch (camelCase vs snake_case)** — `get_catalog_stats()` returned camelCase keys but 7 consumers expected snake_case. Dashboard showed 0 services despite 1439 loaded. Fixed to return snake_case. |
| 5 | B0005 | 2026-03-05 | ENG-010 | *pending* | **Classification Config Cosmos ORDER BY BadRequest** — Multi-field `ORDER BY` clauses in Cosmos queries required undefined composite indexes. Cosmos returned BadRequest. Fixed by removing ORDER BY and sorting in Python. |

### B0001 — False Disagreement: Enum vs String Category Comparison

**Date:** 2026-03-04  
**Related CR:** ENG-003 (Active Learning)  
**Found During:** Manual testing of Step 1 (Disagreement UI)  
**Severity:** High — every analysis showed a false disagreement, defeating the active learning feedback loop  
**Status:** Fixed

#### Symptom

The Analysis tab showed "Disagreement" and offered the "Help Resolve This Disagreement" prompt even when LLM and Pattern Engine both classified the item as **Support Escalation**. The UI text literally read: *"The LLM classified this as Support Escalation but the pattern engine says Support Escalation."*

#### Root Cause

Two issues in `hybrid_context_analyzer.py`:

1. **Type mismatch** — `pattern_category` was assigned directly from `pattern_result.category`, which is an `IssueCategory` enum. The LLM classifier returns a plain string. Comparing `"support_escalation" == IssueCategory.SUPPORT_ESCALATION` evaluates to `False` in Python.
2. **Over-strict check** — The agreement logic originally required both `category` AND `intent` to match. Intent differences within the same category are not meaningful disagreements for triage routing.

#### Fix

- Normalize `pattern_category` and `pattern_intent` to their `.value` strings before comparison.
- Changed agreement check to compare **category only**.

#### Files Modified

| File | Description |
|------|-------------|
| `hybrid_context_analyzer.py` | Added `hasattr(x, 'value')` → `x.value` normalization for `pattern_category` and `pattern_intent`. Simplified agreement check to category-only comparison. |

---

### B0002 — Hybrid Source Not Recognized as LLM

**Date:** 2026-03-06  
**Related CR:** ENG-003 (Active Learning)  
**Found During:** Manual testing of batch analysis  
**Severity:** Medium — LLM-analyzed items appeared as pattern-only in UI, hiding LLM features  
**Status:** Fixed

#### Root Cause

`EvaluatePage.jsx` used `source === "llm"` to determine LLM-specific rendering. The hybrid analyzer returns `source: "hybrid"` when the LLM is primary but pattern features are included. These items lost all LLM-specific UI (reasoning, confidence, comparison).

#### Fix

Changed `isLLM` check to `source === "llm" || source === "hybrid"`.

#### Files Modified

| File | Description |
|------|-------------|
| `triage-ui/src/pages/EvaluatePage.jsx` | `isLLM` now matches both `"llm"` and `"hybrid"` source values |

---

### B0003 — Comparison Crash on Pattern-Only Fallback

**Date:** 2026-03-06  
**Related CR:** ENG-003 (Active Learning)  
**Found During:** Testing with Azure OpenAI unavailable  
**Severity:** Medium — Pattern Engine Comparison section crashed when LLM was down  
**Status:** Fixed

#### Root Cause

When the LLM is unavailable, `hybrid_context_analyzer.py` produced results without an `agreement` field (it was never set). The frontend `EvaluatePage.jsx` rendered the Pattern Engine Comparison section unconditionally, referencing `agreement` as if it were always a boolean, causing undefined property access.

#### Fix

Two-part fix:
1. **Backend** (`hybrid_context_analyzer.py`): Set `agreement=None` explicitly in pattern-only fallback path.
2. **Frontend** (`EvaluatePage.jsx`): Guard the comparison section with `agreement !== null && agreement !== undefined`.

#### Files Modified

| File | Description |
|------|-------------|
| `hybrid_context_analyzer.py` | Added `agreement=None` in pattern-only fallback result |
| `triage-ui/src/pages/EvaluatePage.jsx` | Gated Pattern Engine Comparison on non-null `agreement` |

---

### B0004 — ServiceTree Stats Key Mismatch (camelCase vs snake_case)

**Date:** 2026-03-05  
**Related CR:** ENG-008 (ServiceTree Routing Integration)  
**Found During:** ServiceTree catalog refresh testing  
**Severity:** Medium — Dashboard showed 0 services despite 1439 being loaded, ServiceTree health appeared degraded  
**Status:** Fixed

#### Symptom

After refreshing the ServiceTree catalog (which successfully loaded 1439 services across 123 offerings from the BFF API), the admin dashboard health components showed `total_services: 0` and `total_offerings: 0`. The ServiceTree section appeared empty despite data being present in Cosmos.

#### Root Cause

`servicetree_service.py` `get_catalog_stats()` returned camelCase keys (`totalServices`, `totalOfferings`, `solutionAreas`, `areaPaths`, `cacheAge`, `cacheFile`), but all 7 consumers in `admin_routes.py` accessed them using snake_case (`total_services`, `total_offerings`, `solution_areas`, `area_paths`, `cache_age`, `cache_file`). Python `dict.get()` returned `0`/`None` for all lookups.

#### Fix

Changed `get_catalog_stats()` to return snake_case keys matching the consumer expectations.

#### Files Modified

| File | Description |
|------|-------------|
| `servicetree_service.py` | `get_catalog_stats()` return dict keys changed from camelCase to snake_case |

---

### B0005 — Classification Config Cosmos ORDER BY BadRequest

**Date:** 2026-03-05  
**Related CR:** ENG-010 (Dynamic Classification Config)  
**Found During:** Classification Config page testing  
**Severity:** High — Entire Classification Config page returned 500 error, no config data visible  
**Status:** Fixed

#### Symptom

Navigating to the Classification Config page showed a BadRequest error. The API returned HTTP 500 with Cosmos error: `(BadRequest) One of the input values is invalid`.

#### Root Cause

Two Cosmos queries in `admin_routes.py` used `ORDER BY` clauses that require composite indexes:
1. `SELECT * FROM c WHERE ... ORDER BY c.configType, c.value` — multi-field ORDER BY requires a composite index on `(configType ASC, value ASC)`
2. `SELECT * FROM c WHERE c.status = 'discovered' ORDER BY c.discoveredCount DESC` — ORDER BY on a non-partition-key field requires a range index in the correct direction

Neither composite index was defined on the `classification-config` container.

#### Fix

Removed `ORDER BY` from both Cosmos queries and replaced with Python-side sorting:
1. Query 1: `raw.sort(key=lambda d: (d.get("configType", ""), d.get("value", "")))`
2. Query 2: `raw.sort(key=lambda d: d.get("discoveredCount", 0), reverse=True)`

#### Files Modified

| File | Description |
|------|-------------|
| `triage/api/admin_routes.py` | Removed ORDER BY from 2 Cosmos queries; added Python `list.sort()` after query execution |

---

### ENG-011 — Dashboard UI Improvements (Compact Cards + Health Grid)

**Date:** 2026-03-05  
**Build ID:** *pending*  
**Requested By:** User feedback (information density)  
**Status:** Built, awaiting deployment

#### Problem

The Dashboard count metric cards occupied too much vertical space (one per row). Validation warnings required navigating to a separate page. The health status grid was 2-column, leaving wasted horizontal space.

#### Solution

1. **Compact count cards**: Metric cards (Total Analyses, Rules, Triggers, Routes, Actions, AI Discoveries) condensed into a 5-across compact row.
2. **Validation warnings as health card**: Top 5 validation warnings promoted from the Validation page into an inline health card on the Dashboard with severity icons (⚠️ warning, ℹ️ info).
3. **3-column health grid**: Health status cards arranged in a responsive 3-column grid layout.

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage-ui/src/pages/Dashboard.jsx` | Frontend | Compact count card layout, validation warnings health card, 3-column grid structure |
| `triage-ui/src/pages/Dashboard.css` | Frontend | `.dashboard-count-row` compact layout, `.dashboard-health-grid` 3-column responsive grid, validation card styles |

---

### ENG-004 — LLM Classifier Retry Logic with Exponential Backoff

**Date:** 2026-03-06  
**Build ID:** *pending*  
**Requested By:** Engineering (reliability improvement)  
**Status:** Built, awaiting deployment

#### Problem

Transient Azure OpenAI failures (429 rate limit, 500/502/503/504 server errors, network timeouts) caused immediate classification failure with no retry. Single transient errors resulted in full fallback to pattern-only analysis.

#### Solution

Added automatic retry with exponential backoff to `LLMClassifier.classify()`:
- **Max retries**: 3 attempts
- **Base backoff**: 1.0 seconds (doubles each retry)
- **Rate limit backoff**: 5.0 seconds (for 429 responses)
- **Jitter**: Random 0-50% added to backoff to prevent thundering herd
- **Retryable errors**: 429, 500, 502, 503, 504 status codes + `APIConnectionError` + `APITimeoutError`

#### Files Modified

| File | Description |
|------|-------------|
| `llm_classifier.py` | Added `MAX_RETRIES`, `BASE_BACKOFF_SECONDS`, `RATE_LIMIT_BACKOFF` constants. `classify()` method wrapped in retry loop with `_is_retryable()` helper. Logs retry attempts with backoff duration. |

---

### ENG-005 — Diagnostics Endpoint + Inline Diagnostics UI

**Date:** 2026-03-06  
**Build ID:** *pending*  
**Requested By:** Engineering (observability)  
**Status:** Built, awaiting deployment

#### Problem

When AI classification was unavailable, the yellow "AI Unavailable" banner gave no actionable diagnostic information. Users had to check server logs or ask engineering for help troubleshooting.

#### Solution

1. **Backend**: New `GET /api/v1/diagnostics` endpoint returning comprehensive system status (AI config, Cosmos DB, ADO, cache).
2. **Floating icon**: `DiagnosticsPanel` component accessible from `AppLayout` for global system health view.
3. **Inline diagnostics**: When the "AI Unavailable" banner shows on `EvaluatePage`, an "Show Diagnostics" button appears, expanding a collapsible panel with AI status, OpenAI configuration, and error details.

#### Files Modified

| File | Type | Description |
|------|------|-------------|
| `triage/api/routes.py` | Backend | Added `GET /api/v1/diagnostics` endpoint with AI, Cosmos, ADO, and cache status |
| `triage-ui/src/api/triageApi.js` | Frontend | Added `getDiagnostics()` API function |
| `triage-ui/src/components/common/DiagnosticsPanel.jsx` | Frontend (new) | Floating diagnostics panel component |
| `triage-ui/src/components/common/DiagnosticsPanel.css` | Frontend (new) | Diagnostics panel styling |
| `triage-ui/src/components/layout/AppLayout.jsx` | Frontend | Imported and rendered `DiagnosticsPanel` |
| `triage-ui/src/pages/EvaluatePage.jsx` | Frontend | Added inline diagnostics button + collapsible panel in AI Unavailable banner |
| `triage-ui/src/pages/EvaluatePage.css` | Frontend | Added ~120 lines of inline diagnostics CSS |

---

### ENG-006 — Batch Fetch Resilience: errorPolicy=Omit + Null-Safe Iteration

**Date:** 2026-03-06  
**Build ID:** *pending*  
**Requested By:** Engineering (batch analysis bug fix)  
**Status:** Fixed and verified

#### Problem

When analyzing multiple work items, if even one ID in the batch was invalid (e.g., didn't exist in ADO), the ADO REST API returned HTTP 404 for the **entire batch**. This caused "Batch fetch failed" errors for all items, even the valid ones.

**Example**: Batch of `[713010, 731001, 712931, 712918]` where 731001 doesn't exist → 404 → all 4 items fail.

#### Root Cause

The ADO REST API `GET /_apis/wit/workitems?ids=...` endpoint defaults to `errorPolicy=Fail`, which returns a 404 for the entire response when any single item is not found.

#### Solution — Two-Part Fix

**Part 1: errorPolicy=Omit** (`_read_batch_url()`)
- Added `&errorPolicy=Omit` to the batch URL query parameters
- ADO now returns HTTP 200 with a `value` array that contains null placeholders for invalid/not-found items instead of failing the entire request

**Part 2: Null-safe iteration** (`get_work_items_batch()`)
- `errorPolicy=Omit` returns `[{valid}, null, {valid}, {valid}]` — null entries for omitted items
- Added `if item is None: continue` to skip null entries
- Added `fetched_ids` set to track which IDs were successfully returned
- After processing, compares requested chunk IDs against `fetched_ids` to identify and report individually which IDs were omitted

#### Verified Result

Batch `[713010, 731001, 712931, 712918]`:
- 3 valid items analyzed successfully (713010, 712931, 712918)
- 1 invalid item (731001) reported as `"Failed to fetch #731001"` — non-fatal error
- No disruption to valid items

#### Files Modified

| File | Description |
|------|-------------|
| `triage/services/ado_client.py` | `_read_batch_url()`: Added `&errorPolicy=Omit` to batch URL. `get_work_items_batch()`: Added null filtering, `fetched_ids` tracking set, per-ID omission detection. |