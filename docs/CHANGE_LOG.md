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
| 4 | FR-1994, FR-1999 | 2026-03-04 | `4b06cff` | **Tabbed analysis detail views + blade "No data" placeholders** — Added pill-style tabbed interface (Overview / Analysis / Decision / Evaluate) to Field Portal `AnalysisDetailPage` and Triage UI `EvaluatePage` to reduce scrolling. QueuePage blade kept as linear layout with all section headers always visible and "No data" placeholders for empty fields. |
| 5 | ENG-003 | 2026-03-05 | *pending* | **Active Learning — Full feedback loop (Steps 1-5)** — Training signals Cosmos container, corrections Cosmos migration, disagreement UI, pattern weight tuning, few-shot signal injection into LLM prompt, and dashboard agreement rate metric. All five design steps implemented. |

---

## Change Detail

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
| `field-portal/ui/src/pages/AnalysisDetailPage.jsx` | Frontend | Rewrote layout with 4-tab interface (Overview, Analysis, Decision, Evaluate); added `activeTab` state |
| `field-portal/ui/src/styles/global.css` | Frontend | Added ~90 lines of tab CSS (`.analysis-tabs`, `.analysis-tab`, `.tab-badge`, `.analysis-tab-panel`, `@keyframes fadeInPanel`, responsive breakpoint) |
| `triage-ui/src/pages/EvaluatePage.jsx` | Frontend | Added per-work-item 4-tab interface with `activeDetailTabs` state map; rewrote `renderAnalysisDetail` function |
| `triage-ui/src/pages/EvaluatePage.css` | Frontend | Added ~80 lines of tab CSS adapted for Triage UI CSS variables |
| `triage-ui/src/pages/QueuePage.jsx` | Frontend | Blade sections always render with "No data" placeholder for empty fields; removed conditional hiding |
| `triage-ui/src/pages/QueuePage.css` | Frontend | Added `.no-data` style (italic, light gray) for empty field placeholders |

#### Behavior Summary

**Field Portal AnalysisDetailPage & Triage UI EvaluatePage — Tabbed Interface:**
1. Content organized into 4 pill-style tabs: 📋 **Overview**, 🧠 **Analysis**, 🎯 **Decision**, ✅ **Evaluate**.
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

