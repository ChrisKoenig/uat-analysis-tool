# Project Status - Intelligent Context Analysis System
**Last Updated**: February 20, 2026
**Status**: ✅ All systems operational — Triage Management + Field Submission Portal + Cosmos DB (shared evaluations & corrections) + AI classification

---

## ⚠️ CRITICAL CONTEXT FOR NEW SESSIONS — READ FIRST

### Two Completely Different Audiences — Two Separate UIs

This platform serves **two distinct personas** that must NEVER be combined into one UI:

| | **Field Personnel** (submit issues) | **Corporate Triage Team** (review & route) |
|---|---|---|
| **Who** | Field CSMs, account managers, support engineers | Central triage/operations team |
| **Purpose** | Enter issues they need help with, get AI guidance | Review incoming items, apply rules, route to teams |
| **Current UI** | Flask app `:5003` (`app.py`, 2369 lines) | React SPA `:3000` (`triage-ui/`) |
| **Future UI** | New React SPA (separate URL/project) | Current React SPA (`:3000`) |
| **API Backend** | Microservices via API Gateway `:8000` | FastAPI Triage API `:8009` |

**The Flask app is NOT "legacy to replace"** — it is the active field submission portal. The React triage UI is a separate system for the corporate triage team. They share the Analysis Engine but nothing else.

### Field Submission Flow (9-Step Process — DO NOT BREAK)

This flow was refined over several weeks and works correctly. The correction step (Step 4) is **integrated into the submission journey**, not a separate admin page:

```
Step 1: Issue Submission (/)
  └─ Title + Description/Customer Scenario + Business Impact form
  └─ Template: issue_submission.html

Step 2: Quality Review (/submit)
  └─ AI completeness scoring (score < 50 blocks, < 80 warns)
  └─ Options: Update Input (back to Step 1), Continue to Analysis, Cancel
  └─ Template: input_quality_review.html

Step 3: Context Analysis (/start_processing → /context_summary)
  └─ HybridContextAnalyzer runs: pattern matching + GPT-4o + vectors + corrections
  └─ Shows: Category, Intent, Confidence%, Business Impact, Technical Complexity
  └─ AI reasoning displayed to user
  └─ Template: context_summary.html

Step 4: User Review & Correction (/context_summary or /evaluate_context)
  └─ "Looks Good - Continue" → proceed to Step 5
  └─ "Modify Classification" → /evaluate_context (detailed view)
      └─ Correction form: correct_category, correct_intent, correct_business_impact
      └─ "Reanalyze with Corrections" → re-runs analysis with hints → back to summary
      └─ "Save Corrections Only" → saves to corrections.json for learning
  *** CORRECTION IS PART OF THE USER JOURNEY, NOT A SEPARATE ADMIN FUNCTION ***
  └─ Template: context_evaluation.html (885 lines)

Step 5: Resource Search (/search_resources → /perform_search → /search_results)
  └─ Searches: Microsoft Learn, similar products, regional availability
  └─ Retirement info, capacity guidance
  └─ TFT Features (for feature_request category — checkbox selection)
  └─ Category-specific guidance:
      - technical_support → CSS Compass/Escalation links
      - cost_billing → Out of scope, redirect to GetHelp
      - aoai_capacity → aka.ms/aicapacityhub
      - capacity → AI vs Non-AI capacity instructions
  └─ Template: search_results.html

Step 6: UAT Input (/uat_input)
  └─ Opportunity ID + Milestone ID (recommended, not required)
  └─ Template: uat_input.html

Step 7: Similar UAT Search (/select_related_uats)
  └─ Searches ADO for similar UATs from last 180 days
  └─ Sorted by similarity score (highest first)
  └─ Template: select_related_uats.html

Step 8: UAT Selection
  └─ Checkboxes (max 5), saved via AJAX POST /save_selected_uat
  └─ Template: select_related_uats.html (same page)

Step 9: UAT Created (/create_uat)
  └─ Creates work item in ADO (unifiedactiontrackertest org)
  └─ Fields: Title, Description, Impact, Category, Intent, Reasoning
  └─ Custom fields: AssigntoCorp=True, StatusUpdate=WizardAuto
  └─ Links selected TFT Features and related UATs
  └─ Template: uat_created.html
```

### Key Code Files for Field Submission Flow
| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 2369 | Flask app — all 20+ routes for the field submission flow |
| `enhanced_matching.py` | 2646 | EnhancedMatcher, AzureDevOpsSearcher, analyze_context_for_evaluation() |
| `microservices_client.py` | 396 | HTTP client wrappers for calling microservices via API Gateway |
| `ado_integration.py` | 1088 | ADO client — create_work_item_from_issue(), search_tft_features() |
| `hybrid_context_analyzer.py` | ~730 | Orchestrator: pattern + LLM + vectors + corrective learning |
| `intelligent_context_analyzer.py` | ~1800 | IssueCategory/IntentType enums, pattern rules, product detection |
| `templates/` | 21 files | Jinja2 templates for entire field flow |

### Templates (Field Submission Flow Order)
```
issue_submission.html → input_quality_review.html → context_summary.html →
context_evaluation.html → searching_resources.html → search_results.html →
uat_input.html → searching_uats.html → select_related_uats.html → uat_created.html
```

### What Was Built Feb 11 (Triage UI — Separate from Field Flow)
These are triage team tools, NOT field submission replacements:
- `triage/api/classify_routes.py` — Standalone classify API (POST /api/v1/classify, /classify/batch)
- `triage/api/admin_routes.py` — Corrections CRUD + health dashboard API
- `triage-ui/src/pages/ClassifyPage.jsx` — Triage team can test classifications
- `triage-ui/src/pages/CorrectionsPage.jsx` — Admin CRUD for corrections.json (NOT field correction flow)
- `triage-ui/src/pages/HealthPage.jsx` — Component-level health dashboard

---

## System Overview

The project has two major subsystems with **different audiences**:

1. **Field Portal** — React SPA + FastAPI orchestrator (ports 3001/8010) where field personnel submit issues through a 9-step wizard: submit → quality review → AI analysis → correction → resource search → TFT features → UAT input → related UATs → UAT creation. **Now stores evaluations and corrections to Cosmos DB** for triage dedup and fine-tuning.
2. **Triage Management System** — FastAPI + React SPA (ports 3000/8009) for the corporate triage team to review queued work items, apply rules/triggers/routes, and route to teams
3. **Legacy Input System** — Flask web UI (port 5003) — original field submission portal, still operational

All share the Hybrid Analysis Engine (API Gateway :8000 → Agents :8001-8007), Cosmos DB (`triage-management` database), and authentication infrastructure (Key Vault, Azure AD).

---

## Current Architecture

### Triage Management System (PRIMARY — active development)
- **Backend API**: FastAPI on port 8009 (uvicorn, `triage/api/routes.py`)
- **Frontend**: React + Vite on port 3000 (`triage-ui/`)
- **Database**: Azure Cosmos DB (`cosmos-gcs-dev`, serverless, North Central US)
- **Analysis Engine**: Hybrid pattern matching + LLM classification
- **Startup**: `python launcher.py` (GUI launcher) OR manual start

### Field Portal (NEW — Feb 12, actively improved through Feb 19)
- **Backend API**: FastAPI on port 8010 (uvicorn, `field-portal/api/main.py`)
- **Frontend**: React 18 + Vite on port 3001 (`field-portal/ui/`)
- **Pattern**: Calls analysis engines DIRECTLY (no gateway/microservice dependency). Gateway is fallback only.
  - Quality scoring: `AIAnalyzer.analyze_completeness()` called directly from `enhanced_matching.py`
  - Context analysis: `HybridContextAnalyzer.analyze()` called directly from `hybrid_context_analyzer.py`
  - This means the field portal works independently — no need to start the old system or microservices
- **Auth**: AzureCliCredential-first with cached singletons across all 4 key files (no repeated auth prompts)
- **OpenAPI**: Full Swagger docs at http://localhost:8010/docs (Copilot-plugin ready)
- **Startup**: `python launcher.py` → "Field Portal" card, or manual start

### Input/Analysis System (legacy — still operational)
- **Web UI**: http://localhost:5003
- **Teams Bot**: http://localhost:3978/api/messages
- **Startup Script**: `.\start_app.ps1`

### Admin Portal
- **Admin Service**: port 8008 (`admin_service.py`)

### Microservices (All ports working)
- API Gateway: 8000
- Context Analyzer: 8001
- Search Service: 8002
- Enhanced Matching: 8003
- UAT Management: 8004
- LLM Classifier: 8005
- Embedding Service: 8006
- Vector Search: 8007

---

## Desktop Launcher (`launcher.py`)

A tkinter GUI that starts/stops all three service groups with one click:

| Card | What it starts | Port(s) |
|------|---------------|---------|
| Input Process | `app.py` (Flask) | 5003 |
| Admin Process | `admin_service.py` | 8008 |
| Triage Process | uvicorn + `npm.cmd run dev` | 8009 + 3000 |
| Field Portal | uvicorn + `npm.cmd run dev` | 8010 + 3001 |

**Features**:
- Key Vault access check on startup
- `wait_for_http()` before opening browser (no premature browser opens)
- `PYTHONIOENCODING=utf-8` for emoji characters in console output
- Double-click guard (`_starting` set)
- Port-already-in-use detection (shows "Running (external)" status)
- Persistent token cache (`TokenCachePersistenceOptions(name="gcs-cosmos-auth")` — no repeated auth prompts)
- Triage env vars injected: `COSMOS_ENDPOINT`, `COSMOS_USE_AAD=true`, `COSMOS_TENANT_ID`

**To start**: `python launcher.py`

---

## Cosmos DB Configuration

### Account Details
- **Account**: `cosmos-gcs-dev`
- **Type**: Serverless (no provisioned RUs)
- **Region**: North Central US
- **Resource Group**: `rg-gcs-dev`
- **Subscription**: `13267e8e-b8f0-41c3-ba3e-569b3b7c8482`
- **Database**: `triage-management` (created manually in portal — RBAC doesn't allow `create_database_if_not_exists`)

### Authentication
- **Local auth (keys)**: DISABLED by Azure Policy — cannot be enabled
- **Auth method**: AAD only (cross-tenant)
- **Cosmos Tenant**: `16b3c013-d300-468d-ac64-7eda0820b6d3` (Microsoft Non-Production / fdpo.onmicrosoft.com)
- **User Tenant**: `72f988bf-86f1-41af-91ab-2d7cd011db47` (Microsoft Corp — different!)
- **RBAC Role**: Cosmos DB Built-in Data Contributor (`00000000-0000-0000-0000-000000000002`)
- **RBAC Principal**: `f1a846d2-dca1-4402-b526-e5b3e5643bb7` (Brad.Price@microsoft.com)
- **Managed Identity**: `mi-gcs-dev` (client: `7846e03e-9279-4057-bdcd-4a2f7f8ebe85`) — for Azure deployment only

### Cross-Tenant Credential Chain (`cosmos_config.py`)
Because the user's corporate tenant differs from the Cosmos DB resource tenant, a custom credential chain is used:
```python
ChainedTokenCredential(
    SharedTokenCacheCredential(tenant_id=COSMOS_TENANT_ID, ...),
    InteractiveBrowserCredential(tenant_id=COSMOS_TENANT_ID, ...)
)
```
Both use `TokenCachePersistenceOptions(name="gcs-cosmos-auth")` for persistent disk cache — only prompts once.

### Environment Variables Required for Triage API
```
COSMOS_ENDPOINT=https://cosmos-gcs-dev.documents.azure.com:443/
COSMOS_USE_AAD=true
COSMOS_TENANT_ID=16b3c013-d300-468d-ac64-7eda0820b6d3
```
These are injected automatically by `launcher.py` or must be set manually.

### Containers (9 total, auto-created)
`rules`, `actions`, `triggers`, `routes`, `evaluations`, `analysis-results`, `field-schema`, `audit-log`, `corrections`

**Shared containers:**
- `evaluations` — Written by both triage (`source: "triage"`) and field portal (`source: "field-portal"`); partition key `/workItemId`
- `corrections` — Written by field portal at Step 4; consumed by fine-tuning engine; partition key `/workItemId`

### Key Limitation
- Azure CLI login fails locally (Conditional Access policy error 53003) — use Cloud Shell for `az` commands
- Database/container creation requires portal or Cloud Shell (RBAC data-plane role doesn't cover control-plane)

---

## Recent Changes (Feb 20, 2026) — Cosmos DB Integration for Field Portal

### Feb 20: Field Portal → Cosmos DB Evaluations & Corrections ✅
**Goal**: Persist field portal AI analysis in the same Cosmos DB `evaluations` container so the triage system can detect existing evaluations and skip re-analysis. Store user corrections in a new `corrections` container for fine-tuning.

**New file** — `field-portal/api/cosmos_client.py` (~280 lines):
- `store_field_portal_evaluation()` — Writes to `evaluations` container with `source: "field-portal"` discriminator after Step 9 (UAT creation). Document is compatible with triage `Evaluation` model; triage-specific fields left empty.
- `store_correction()` — Writes to `corrections` container with `consumed: false` flag for fine-tuning engine pickup.
- `get_existing_evaluation()` — Query helper for triage dedup.
- `get_corrections_for_work_item()` — Query helper.
- Reuses triage `CosmosDBConfig` singleton (shared connection pool).

**Modified files:**
1. **`field-portal/api/routes.py`** — Step 9 (`create_uat`) now generates evaluation summary HTML via `_build_evaluation_summary_html()`, passes it to ADO creation as `evaluation_summary_html`, then stores a full evaluation document in Cosmos after getting the work item ID. Step 4 (`correct_classification`) now calls `store_correction()` to Cosmos before the legacy local JSON backup.
2. **`triage/config/cosmos_config.py`** — Added `corrections` container definition with partition key `/workItemId` and description for fine-tuning.
3. **`ado_integration.py`** — After creating the ADO work item, writes the evaluation summary HTML to `custom.ChallengeDetails` field.
4. **`field-portal/README.md`** — Added Cosmos DB integration section, updated architecture diagram, project structure, prerequisites.
5. **`SYSTEM_ARCHITECTURE.md`** — Added corrections container to data models table, noted shared container architecture.

**Committed**: `0ba2dea` — pushed to `origin main`

---

## Recent Changes (Feb 17-19, 2026) — Field Portal Independence + Auth + UI Fixes

### Feb 19: Analysis AI Fix — corrections.json Path Resolution ✅
**Problem**: Analysis AI always fell back to pattern matching (`source: pattern, ai_available: false`) even though Quality AI worked fine. The Analysis Detail page showed `Source: pattern, AI Available: false, Error: N/A`.

**Root Cause**: `validate_config()` in `ai_config.py` checked `os.path.exists("corrections.json")` — a relative path. The uvicorn server runs from `C:\Projects\Hack\field-portal\` but `corrections.json` lives at `C:\Projects\Hack\corrections.json`. This caused validation to fail with `"Corrections file not found: corrections.json"`, which threw a `ValueError` caught by `HybridContextAnalyzer.__init__()`, permanently disabling AI (`use_ai = False`). Quality evaluator was unaffected because it never calls `validate_config()`.

**Why Quality AI worked but Analysis didn't**: The quality evaluator (`ai_quality_evaluator.py`) only calls `get_config()` to get connection details and creates a fresh `AzureOpenAI` client per call. The analysis path (`hybrid_context_analyzer.py`) calls `validate_config()` during `__init__()` which checks the corrections file path — and that check failed due to the cwd mismatch.

**Fix Applied** (2 files):
1. **`ai_config.py`** (line ~142): `validate()` now resolves `corrections.json` relative to `ai_config.py`'s directory (`os.path.dirname(os.path.abspath(__file__))`) instead of cwd.
2. **`hybrid_context_analyzer.py`** (line ~345): `_load_corrections()` now resolves via `Path(__file__).resolve().parent / 'corrections.json'` instead of relative `Path('corrections.json')`.
3. **`field-portal/api/routes.py`**: Added retry logic — if cached `_hybrid_analyzer` has `use_ai=False` and `_init_error`, reinitialize on next request.

**Verified**: Both Quality AI (`ai_evaluation: True`) and Analysis AI (`source=llm, ai_available=True`) now work on port 8010.

### Feb 19: Field Portal Works Without Old System ✅ (CRITICAL FIX)
**Problem**: The new React field portal's quality engine always returned 100% score unless the old Flask system (:5003) + microservices (:8000-8008) were running. The `submit_issue` endpoint called the API Gateway → enhanced-matching microservice (:8003). When those weren't running, a `GatewayError` catch block fell back to a trivial check: `100 if len(description.split()) >= 5 else 40` — always returning 100% for any reasonable description. The correct score should be ~82% for typical incomplete input.

**Root Cause**: Gateway dependency in `field-portal/api/routes.py` — the field portal API was designed as a thin orchestrator that called everything through the API Gateway, but the gateway and microservices are part of the old system.

**Fix Applied** (3 changes to `field-portal/api/routes.py`):
1. **Quality Scoring** (`submit_issue` endpoint): Now calls `AIAnalyzer.analyze_completeness()` directly — the same static method the microservice wraps, imported from `enhanced_matching.py`. Gateway + trivial fallback only used if the direct call fails.
2. **Context Analysis** (`_local_pattern_analysis` helper): Now tries `HybridContextAnalyzer.analyze()` first (full AI: pattern matching + GPT-4o + vector search + corrective learning from corrections.json), then falls back to `IntelligentContextAnalyzer` (pattern-only) if hybrid fails.
3. **Context Endpoint** (`analyze_context` endpoint): Calls `_local_pattern_analysis()` directly as primary path. Only falls back to the API Gateway when the direct analysis returns a "fallback_minimal" source.
4. **Singleton**: Added `_hybrid_analyzer = None` as module-level cached singleton alongside `_ado_client` and `_ado_searcher`.

**Verified**: 
- Short/incomplete input → Score: 80%, Issues: `["impact_lacks_detail"]`, with helpful suggestion
- Complete well-formed input → Score: 100%, Issues: `[]`
- Matches the old system's behavior (~82% for typical input)

### Feb 17-18: Auth Fix — Reduced 6x Login Prompts to 1 ✅
**Problem**: Opening the field portal triggered 6 separate browser auth prompts because each Python module created its own credential independently.

**Fix Applied** (4 files):
1. **`llm_classifier.py`**: Class-level cached `_credential` with `AzureCliCredential` tried first (no prompt), then `DefaultAzureCredential` as fallback.
2. **`enhanced_matching.py`**: Auth reordered to `AzureCliCredential` first in credential chain for both main and TFT orgs.
3. **`ado_integration.py`**: `get_tft_credential()` tries main cached credential → AzureCli → InteractiveBrowser. Persistent token cache.
4. **`field-portal/api/routes.py`**: Cached `_ado_client` and `_ado_searcher` as module-level singletons (initialized once on first call).

### Feb 17: Field Portal UI Fixes ✅
1. **Blank Detail Page**: `AnalysisDetailPage.jsx` — `data_sources` field contained objects, React can't render objects as children. Fixed to render structured JSX (source name + confidence badge + details list).
2. **Visual Hierarchy**: Improved CSS for analysis results display, card layouts, confidence indicators.
3. **Capitalization**: Fixed inconsistent casing in category/intent display values.
4. **Debug Scaffolding**: Removed console.log statements and debug borders from production components.

---

## Recent Changes (Feb 11-12, 2026) — New Platform Build + Architecture Analysis

### Feb 12: Field Portal Rebuild ✅
Built a completely new React SPA + FastAPI orchestrator for field personnel, replacing the legacy Flask UI without touching any existing code.

**Architecture**: UI (:3001) → Orchestrator API (:8010) → API Gateway (:8000) → Agents (:8001-8007)

**Backend** (`field-portal/api/` — 7 Python files):
- `main.py` — FastAPI entry point with lifespan, CORS
- `routes.py` — 11 endpoints for the full 9-step flow (submit, analyze, correct, search, features, UAT input, related UATs, create UAT, session, health)
- `models.py` — 43 Pydantic models (OpenAPI spec / Copilot-plugin ready)
- `gateway_client.py` — Async httpx client to API Gateway
- `session_manager.py` — In-memory wizard state with TTL
- `guidance.py` — Category-specific rules (tech support, capacity, billing)
- `config.py` — Ports, thresholds, CORS config

**Frontend** (`field-portal/ui/` — 18 source files):
- 10 wizard pages: Submit → QualityReview → Analyzing → Analysis → Searching → SearchResults → UATInput → SearchingUATs → RelatedUATs → CreateUAT
- 4 shared components: ProgressStepper, GuidanceBanner, ConfidenceBar, LoadingSpinner
- Typed API client (`fieldApi.js`), full CSS design system (`global.css`)
- React Router with lazy-loaded routes, Vite dev proxy to :8010

**Launcher**: Added 4th card "Field Portal" to `launcher.py` (starts both API + UI)

**Key Design Decisions**:
- Calls existing API Gateway — does NOT re-wrap agent engines
- OpenAPI spec auto-generated — maps directly to Copilot agent plugin
- Zero changes to existing code (`app.py`, `triage-ui/`, agents all untouched)

### Feb 12: Architecture Analysis ✅
**Key Finding**: The Flask field submission portal (`:5003`) and the React triage UI (`:3000`) serve completely different audiences and must remain separate. The Classify/Corrections/Health pages built on Feb 11 belong in the triage team's React UI (diagnostic tools), NOT as replacements for the field submission flow.

The field submission's correction step (Step 4 above) is integrated inline — the user reviews AI classification, corrects if needed, and the corrected data flows through to search and UAT creation. This is fundamentally different from the triage team's corrections.json admin CRUD.

### Feb 11: Triage Platform Features ✅ (committed: `4fc1f9f`)
Built new triage team features without touching the field submission code:

**Backend** (FastAPI APIRouter modules):
- `triage/api/classify_routes.py` — Standalone classify API: POST /classify, /classify/batch, GET /classify/status, /classify/categories
- `triage/api/admin_routes.py` — Corrections CRUD + comprehensive health dashboard (checks Cosmos, OpenAI, KV, ADO, cache, corrections)
- Both mounted in `routes.py` via `app.include_router()`

**Frontend** (React pages + CSS):
- `ClassifyPage.jsx/css` — Test classifications with confidence bars, source badges, semantic tags
- `CorrectionsPage.jsx/css` — Admin CRUD for corrections.json entries
- `HealthPage.jsx/css` — Component-by-component health dashboard
- `triageApi.js` — Added classify/corrections/health API client functions
- `App.jsx` — Added 3 lazy routes: /classify, /corrections, /health
- `constants.js` — Added 3 nav items with divider

**Docs**: `SYSTEM_ARCHITECTURE.md` updated with all new components

### 1. **Cosmos DB Integration** ✅
Connected Triage Management System to real Azure Cosmos DB (was in-memory).
- **File**: `triage/config/cosmos_config.py` — added `COSMOS_TENANT_ID` support, cross-tenant credential chain, persistent token cache, removed broken `VisualStudioCodeCredential`
- **File**: `keyvault_config.py` — added `COSMOS_ENDPOINT` and `COSMOS_KEY` to `SECRET_MAPPINGS`
- Health endpoint confirms: `auth_mode: "aad"`, all 8 containers ready

### 2. **Desktop Launcher** ✅ (NEW FILE)
- **File**: `launcher.py` — full tkinter GUI launcher (see section above)

### 3. **IssueCategory Enum Serialization Fix** ✅
**Issue**: "Object of type IssueCategory is not JSON serializable" when analyzing work items. All 5 items failed.

**Root Cause**: `IssueCategory` and `IntentType` are Python Enums from `intelligent_context_analyzer.py`. When the hybrid analyzer falls back to pattern matching, these enum objects flow through to `AnalysisResult` fields. Cosmos SDK calls `json.dumps()` on `upsert_item()`, which can't serialize Enums.

**Fixes Applied**:
- **`triage/api/routes.py`**: Added `_enum_val()` helper in `_map_hybrid_to_analysis_result()` — wraps `category`, `intent`, `source`, `patternCategory` fields with enum-to-value conversion
- **`triage/models/analysis_result.py`**: Added recursive `_sanitize()` in `to_dict()` — catches any remaining Enum values in the dict tree before Cosmos serialization

**Debugging Note**: A ghost process (dead PID holding port 8009's socket) served stale code for hours, making it appear the fix didn't work. Moving to port 8010 confirmed the fix was correct. Always kill all Python processes and verify the port is free before restarting.

**Result**: 8/8 work items analyzed successfully (verified in UI)

### 4. **Previous Triage UI Fixes** (committed earlier this session)
- `739a5c5` — Remove Quick Actions section from Dashboard
- `c462403` — Fix health check hitting wrong URL (sidebar always showed API Offline)
- `8d6da2c` — Fix audit change details showing dashes instead of values
- `fc2e279` — Wire up audit log action filter, fix API param mismatch
- `a0d469a` — Cache queue data across navigation (no reload on every visit)

---

## Recent Commits

| Commit | Date | Description |
|--------|------|-------------|
| `0ba2dea` | Feb 20 | Cosmos DB integration — evaluations + corrections storage, ADO ChallengeDetails, new cosmos_client.py |
| `0fe9c49` | Feb 19 | Field portal cleanup, archiving old Flask UI, documentation updates |
| `4fc1f9f` | Feb 11 | Classify API, corrections mgmt, health dashboard, 3 React pages, launcher, Cosmos AAD auth |

---

## Previous Changes (Jan 28, 2026) — Azure OpenAI Auth Fix

### **Azure OpenAI Authentication Overhaul** ✅
**Issue**: AI classification stopped working after Key Vault migration on Jan 20.

**Fixes**: Updated `llm_classifier.py` with tenant-specific Azure AD auth, corrected deployment name (`gpt-4o-standard`), removed `.env` override, assigned Cognitive Services OpenAI User role.

**Committed**: d4f52fd

**Full details**: See `AI_FIX_SUMMARY_2026-01-28.md` and `AZURE_OPENAI_AUTH_SETUP.md`

---

## Previous Changes (Jan 23, 2026)

- TFT Feature Search fix (use `get_ado_client()`)
- Azure OpenAI 10-second timeout in `embedding_service.py`
- Dual authentication caching for main + TFT orgs
- Admin portal moved to port 8008

---

## Known Working Features

✅ Triage Management System — full pipeline: ADO fetch → hybrid analysis → Cosmos DB → React UI
✅ Desktop launcher GUI (`launcher.py`)
✅ Azure Cosmos DB with AAD cross-tenant auth
✅ Persistent token cache (no repeated auth prompts across restarts)
✅ Queue caching across navigation
✅ Audit log with filters, search, change details
✅ Health indicator in sidebar
✅ Azure OpenAI AI classification (0.95 confidence, LLM source)
✅ Pattern matching fallback when LLM unavailable
✅ Web UI with Quick ICA analysis (port 5003)
✅ TFT Feature search for feature_request category
✅ Dual organization authentication (main + TFT)
✅ Admin portal on port 8008

---

## Known Issues

⚠️ **Field Portal: MSAL re-prompts for login during quality submission AND UAT search** (HIGH PRIORITY)
- After initial login, the user is re-prompted to authenticate when submitting for quality review **and** when searching for matching UATs
- Multiple fixes attempted: removed `useMsalAuthentication(Silent)` hook, removed `acquireTokenPopup` fallback, disabled `acquireTokenSilent` entirely, added `inProgress` guard — none resolved the issue
- Root cause suspected: MSAL redirect-based login flow may be interfering with the SPA navigation to `/quality` — the redirect back from AAD lands on the app without the `location.state` that carries quality data, causing a blank page or re-auth loop
- `getToken()` currently returns `null` (token acquisition fully disabled) — backend does not validate tokens
- **TODO**: Investigate MSAL `handleRedirectPromise()` timing, consider switching to popup-based login (not token acquisition) or using `ssoSilent()` to restore sessions after redirect. May need to persist quality submission data to sessionStorage before the redirect.

⚠️ Admin portal shows "AuthorizationFailure" on blob storage access
- Workaround: Use local JSON files for testing

⚠️ Analysis classification accuracy needs tuning
- Some categories/intents are debatable — review corrections, adjust pattern rules and LLM prompt

⚠️ Azure CLI cannot login locally (Conditional Access error 53003)
- Use Cloud Shell for `az` commands, or portal for resource management

---

## Authentication Architecture

### Azure OpenAI
- **Resource**: OpenAI-bp-NorthCentral (North Central US)
- **Endpoint**: https://OpenAI-bp-NorthCentral.openai.azure.com/
- **Tenant**: `16b3c013-d300-468d-ac64-7eda0820b6d3`
- **Auth**: Azure AD only (API keys disabled by policy)
- **Deployments**: `gpt-4o-standard` (classification), `text-embedding-3-large` (embeddings)
- **Role**: Cognitive Services OpenAI User (assigned to Brad.Price@microsoft.com + mi-gcs-dev)
- **Config Source**: Key Vault (`kv-gcs-dev-gg4a6y`)

### Azure Cosmos DB
- **Account**: `cosmos-gcs-dev` (serverless, North Central US)
- **Tenant**: `16b3c013-d300-468d-ac64-7eda0820b6d3` (same as OpenAI)
- **Auth**: AAD only (local auth disabled by Azure Policy)
- **Role**: Cosmos DB Built-in Data Contributor
- **Cross-tenant**: ChainedTokenCredential with SharedTokenCache + InteractiveBrowser

### Key Vault
- **Name**: `kv-gcs-dev-gg4a6y`
- **Auth**: DefaultAzureCredential
- **Secrets**: OpenAI endpoint/deployment, ADO PAT, etc.
- **Note**: COSMOS_ENDPOINT and COSMOS_KEY added to mappings but secrets not yet created in KV (using env vars instead)

### Azure DevOps — Two Orgs
1. **`unifiedactiontracker`** — READ source for work items (production ADO)
2. **`unifiedactiontrackertest`** — WRITE target for created work items

### Key Tenant IDs
| Tenant | ID | Used For |
|--------|----|----------|
| Microsoft Non-Production (fdpo) | `16b3c013-d300-468d-ac64-7eda0820b6d3` | OpenAI, Cosmos DB, Key Vault resources |
| Microsoft Corp | `72f988bf-86f1-41af-91ab-2d7cd011db47` | User's corporate identity |

---

## Important Files

### Triage Management System
| File | Purpose |
|------|---------|
| `triage/api/routes.py` | FastAPI endpoints — analyze, queue, triage, audit, rules, routes, triggers |
| `triage/config/cosmos_config.py` | Cosmos DB connection, AAD auth, container management |
| `triage/models/analysis_result.py` | AnalysisResult dataclass with `to_dict()` sanitization |
| `triage-ui/` | React + Vite frontend (port 3000) |
| `hybrid_context_analyzer.py` | Hybrid analysis engine (pattern + LLM) |
| `intelligent_context_analyzer.py` | Pattern matching with IssueCategory/IntentType enums |
| `llm_classifier.py` | Azure OpenAI GPT-4o classification |
| `launcher.py` | Desktop GUI launcher (tkinter) |

### Configuration
| File | Purpose |
|------|---------|
| `keyvault_config.py` | Key Vault integration, secret mappings |
| `ai_config.py` | OpenAI config with `use_aad` field |
| `ado_integration.py` | ADO client with dual-org auth |

### Field Portal
| File | Purpose |
|------|--------|
| `field-portal/api/main.py` | FastAPI entry point (port 8010) |
| `field-portal/api/routes.py` | 11 endpoints for 9-step flow + evaluation summary HTML helper |
| `field-portal/api/models.py` | 43 Pydantic models (OpenAPI/Copilot ready) |
| `field-portal/api/cosmos_client.py` | Cosmos DB helpers — store evaluations & corrections, query helpers |
| `field-portal/api/gateway_client.py` | Async httpx client to API Gateway |
| `field-portal/api/session_manager.py` | In-memory wizard state with TTL |
| `field-portal/api/guidance.py` | Category-specific rules |
| `field-portal/ui/` | React 18 + Vite frontend (port 3001) |

### Input System (legacy)
| File | Purpose |
|------|---------|
| `app.py` | Main Flask app (port 5003) |
| `admin_service.py` | Admin portal (port 8008) |
| `start_app.ps1` | Legacy startup script |

### Diagnostics
| File | Purpose |
|------|---------|
| `check_token_tenant.py` | Verify token tenant |
| `check_kv_config.py` | Verify Key Vault config |
| `test_ai_integration.py` | Full 6-step OpenAI test |

---

## How to Start

### Recommended: Desktop Launcher
```powershell
python launcher.py
```
Click the cards to start Input, Admin, or Triage processes. Launcher handles env vars, port checks, and browser opening.

### Manual: Triage System Only
```powershell
# Terminal 1 — API
$env:COSMOS_ENDPOINT="https://cosmos-gcs-dev.documents.azure.com:443/"
$env:COSMOS_USE_AAD="true"
$env:COSMOS_TENANT_ID="16b3c013-d300-468d-ac64-7eda0820b6d3"
$env:PYTHONIOENCODING="utf-8"
python -m uvicorn triage.api.routes:app --host 0.0.0.0 --port 8009 --reload

# Terminal 2 — Frontend
cd triage-ui
npm run dev
```

### Manual: Field Portal
```powershell
# Terminal 1 — API
python -m uvicorn "field-portal.api.main:app" --host 0.0.0.0 --port 8010 --reload

# Terminal 2 — UI
cd field-portal/ui
npm run dev
```
API docs: http://localhost:8010/docs  |  UI: http://localhost:3001

### Legacy: Input System
```powershell
.\start_app.ps1
```

---

## Git Status

**Branch**: `main`
**Latest commit**: `0ba2dea` — Cosmos DB integration for field portal evaluations and corrections

**All changes committed** — clean working tree.

---

## Next Steps / TODO

### Decision Needed (Discuss with Brad)
- [ ] **Field Submission Portal**: Keep Flask or rebuild as new React SPA? Either way, it must be a separate URL from the triage UI
- [ ] **Priority**: Build the new field submission React SPA first? Or focus on completing triage features?

### Field Submission Portal ✅ (Built Feb 12, Independent Feb 19, Cosmos Feb 20)
- [x] Build new React SPA for field personnel (separate project/port from triage-ui) — `field-portal/ui/` on :3001
- [x] Replicate complete 9-step field flow (submit → quality → analysis → correction → search → UAT)
- [x] Inline correction UI integrated into the flow (not a separate page)
- [x] Category-specific guidance display (tech support, cost/billing, capacity, etc.)
- [x] TFT Feature search + selection for feature_request category
- [x] Similar UAT search + selection (last 180 days)
- [x] UAT creation with all context (features, related UATs, opportunity/milestone IDs)
- [x] Quality scoring works independently (direct AIAnalyzer call, no gateway needed)
- [x] Context analysis works independently (direct HybridContextAnalyzer call, no gateway needed)
- [x] Auth reduced from 6 prompts to 1 (AzureCliCredential-first, cached singletons)
- [x] UI bug fixes (blank detail page, visual hierarchy, capitalization)
- [x] Cosmos DB integration — evaluations stored at Step 9, corrections stored at Step 4
- [x] ADO ChallengeDetails field — evaluation summary HTML written to work items
- [x] Corrections container for fine-tuning engine consumption
- [ ] End-to-end live testing of full 9-step flow (submit through UAT creation)
- [ ] Add FastAPI bearer-token validation middleware and restore MSAL token flow (redirect-based, not popup)
- [ ] Retire legacy Flask UI (`:5003`) once field portal is fully validated

### Triage Management System
- [ ] Live test the 3 new React pages (ClassifyPage, CorrectionsPage, HealthPage)
- [ ] Classification tuning — review accuracy, refine LLM prompt, add corrections
- [ ] Webhook receiver — ADO pushes events → auto-analyze new items
- [ ] Analytics dashboard — trends, accuracy, volume metrics
- [ ] Full automation mode — trigger → route → ADO write without human review

### Infrastructure
- [x] Commit all field-portal changes (pushed `0ba2dea` — Feb 20)
- [ ] Add COSMOS_ENDPOINT secret to Key Vault (currently using env vars)
- [ ] Copilot API plugin — field portal API already has OpenAPI spec at :8010/docs
- [ ] Container deployment — Dockerize services for Azure
- [ ] Managed Identity — switch from interactive auth to `mi-gcs-dev` in production
- [ ] Legacy Flask UI retirement — retire `:5003` after field portal validation

### Existing Issues
- [ ] Admin portal shows "AuthorizationFailure" on blob storage access
- [x] Analysis AI now works (corrections.json path fix — Feb 19)
- [ ] Analysis classification accuracy needs tuning
- [ ] Azure CLI cannot login locally (Conditional Access error 53003) — use Cloud Shell

---

## Troubleshooting Quick Reference

### Triage System Issues

**"Object of type IssueCategory is not JSON serializable"**
- Fixed Feb 11 — `_enum_val()` in routes.py + `_sanitize()` in analysis_result.py
- If it reappears: ensure the running process has latest code (kill all Python, clear `__pycache__`, restart)

**Port 8009 already in use / ghost socket**
- A dead process can hold the port. Run: `Get-Process -Name python | Stop-Process -Force`
- Wait 30+ seconds for socket to release, or use a different port temporarily
- Launcher detects this and shows "Running (external)"

**Cosmos DB "AuthenticationFailed"**
- Ensure env vars are set: `COSMOS_ENDPOINT`, `COSMOS_USE_AAD=true`, `COSMOS_TENANT_ID`
- Token cache may be stale — delete `~/.msal_token_cache.*` and re-authenticate
- Verify RBAC: user must have "Cosmos DB Built-in Data Contributor" role

**Cosmos DB "create_database_if_not_exists failed"**
- RBAC data-plane role can't create databases — create manually in portal or Cloud Shell

### Azure OpenAI Issues

**"AI service temporarily unavailable" / pattern matching fallback**
- See `AZURE_OPENAI_AUTH_SETUP.md`
- Quick check: `python check_token_tenant.py` (should show `16b3c013-...`)

**"DeploymentNotFound"**
- Deployment name is `gpt-4o-standard` (NOT `gpt-4o-02`)

### General

**Azure CLI login fails locally**
- Error 53003 (Conditional Access) — use Cloud Shell instead
- App still works — it uses InteractiveBrowserCredential, not Azure CLI

---

**STATUS** (Feb 20, 2026): System is fully operational. Three UIs: **Field Portal** (React :3001 + FastAPI :8010, 9-step wizard), **Triage Management** (FastAPI :8009 + React :3000, 13 pages), and **Legacy Input** (Flask :5003). All changes committed and pushed.

**KEY CHANGES**:
1. The Field Portal works INDEPENDENTLY — calls analysis engines directly (no gateway/microservices needed)
2. **Cosmos DB integration** — evaluations stored at Step 9, corrections at Step 4, summary HTML written to ADO ChallengeDetails
3. Field portal and triage share the `evaluations` container (`source` discriminator); new `corrections` container feeds fine-tuning

**HOW TO START** (for new sessions):
- **Field Portal only** (recommended): `cd field-portal; python -m uvicorn api.main:app --host 0.0.0.0 --port 8010 --reload` + `cd field-portal/ui; npm run dev` → UI at http://localhost:3001
- **Triage System**: `python -m uvicorn triage.api.routes:app --host 0.0.0.0 --port 8009 --reload` + `cd triage-ui; npm run dev` → UI at http://localhost:3000
- **Legacy Input + All microservices**: `.\start_app.ps1` → Flask UI at http://localhost:5003
- **All at once**: `python launcher.py` (GUI with 4 cards)

**⚠️ WARNING**: `start_app.ps1` kills ALL Python processes at startup (line 33: `Get-Process python | Stop-Process`). If you have the field portal API running on :8010, starting the old system will kill it. Start the old system first if you need both.

**CRITICAL FILES FOR NEW SESSIONS**: Read this file first (especially the "CRITICAL CONTEXT" section at the top). Key code files:
- `field-portal/api/routes.py` — Field portal API with direct analysis engine calls + Cosmos storage
- `field-portal/api/cosmos_client.py` — Cosmos DB helpers (evaluations + corrections storage & queries)
- `field-portal/ui/src/pages/` — React wizard pages (10 steps)
- `triage/config/cosmos_config.py` — Cosmos DB connection, 9 containers, AAD auth
- `enhanced_matching.py` — AIAnalyzer.analyze_completeness() static method (quality engine)
- `hybrid_context_analyzer.py` — HybridContextAnalyzer.analyze() (full AI: pattern + LLM + vectors + corrections)
- `intelligent_context_analyzer.py` — IntelligentContextAnalyzer (pattern-only fallback)
- `llm_classifier.py` — Azure OpenAI GPT-4o classification with cached credentials
- `ado_integration.py` — ADO client with dual-org auth (main + TFT) + ChallengeDetails HTML
- `SYSTEM_ARCHITECTURE.md` — Component inventory
- `TRIAGE_SYSTEM_DESIGN.md` — Four-layer triage model
- `AZURE_OPENAI_AUTH_SETUP.md` — Auth details

**Git**: All changes committed and pushed. Latest: `0ba2dea` on `main`.
