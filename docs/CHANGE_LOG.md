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
