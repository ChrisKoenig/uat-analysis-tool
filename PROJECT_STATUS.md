# Project Status - Intelligent Context Analysis System
**Last Updated**: March 4, 2026
**Status**: ✅ All systems operational — Local + Azure Container Apps (dev) + **Azure App Service (pre-prod)** — Triage Management + Field Portal **BOTH DEPLOYED** + Cosmos DB (10 containers) + AI classification + ADO dual-org integration (MI auth)

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
- `triage/api/admin_routes.py` — Corrections CRUD (full CRUD: GET, POST, PUT, DELETE) + health dashboard API
- `triage-ui/src/pages/CorrectionsPage.jsx` — Admin CRUD for corrections.json with blade pattern (list + detail panel), edit mode (NOT field correction flow)
- ~~`ClassifyPage.jsx`~~ — Removed Feb 23 (dead feature)
- ~~`HealthPage.jsx`~~ — Merged into Dashboard Feb 23

---

## System Overview

The project has two major subsystems with **different audiences**:

1. **Field Portal** — React SPA + FastAPI orchestrator (local: ports 3001/8010, pre-prod: `app-field-*-nonprod`) where field personnel submit issues through a 9-step wizard: submit → quality review → AI analysis → correction → resource search → TFT features → UAT input → related UATs → UAT creation. **Stores evaluations and corrections to Cosmos DB** for triage dedup and fine-tuning. **Deployed to App Service Mar 2, 2026.**
2. **Triage Management System** — FastAPI + React SPA (local: ports 3000/8009, pre-prod: `app-triage-*-nonprod`) for the corporate triage team to review queued work items, apply rules/triggers/routes, and route to teams. **Deployed to App Service Feb 27, 2026.**
3. **Legacy Input System** — Flask web UI (port 5003) — original field submission portal, still operational locally

All share the Hybrid Analysis Engine (API Gateway :8000 → Agents :8001-8007), Cosmos DB (`triage-management` database), and authentication infrastructure (Key Vault, Azure AD).

---

## Current Architecture

### Triage Management System (PRIMARY — active development)
- **Backend API**: FastAPI on port 8009 (uvicorn, `triage/api/routes.py`)
- **Frontend**: React + Vite on port 3000 (`triage-ui/`)
- **Database**: Azure Cosmos DB (`cosmos-gcs-dev`, serverless, North Central US)
- **Analysis Engine**: Hybrid pattern matching + LLM classification
- **Startup**: `python launcher.py` (GUI launcher) OR manual start
- **Pages** (11): Dashboard (with health), Queue, Evaluate/Analyze, Rules, Triggers, Actions, Routes, Triage Teams, Validation, Audit Log, Eval History, Corrections

### Field Portal (Built Feb 12, deployed to App Service Mar 2)
- **Backend API**: FastAPI on port 8010 locally / port 8000 on App Service (uvicorn, `field-portal/api/main.py`)
- **Frontend**: React 18 + Vite on port 3001 locally / pm2+serve on App Service (`field-portal/ui/`)
- **Pattern**: Calls analysis engines DIRECTLY (no gateway/microservice dependency). Gateway is fallback only.
  - Quality scoring: `AIAnalyzer.analyze_completeness()` called directly from `enhanced_matching.py`
  - Context analysis: `HybridContextAnalyzer.analyze()` called directly from `hybrid_context_analyzer.py`
  - This means the field portal works independently — no need to start the old system or microservices
- **Auth (local)**: AzureCliCredential-first with cached singletons across all 4 key files (no repeated auth prompts)
- **Auth (pre-prod)**: ManagedIdentityCredential (`TechRoB-Automation-DEV`) for Cosmos/KV/OpenAI/ADO
- **OpenAPI**: Full Swagger docs at http://localhost:8010/docs (Copilot-plugin ready)
- **Startup**: `python launcher.py` → "Field Portal" card, or manual start
- **Pre-prod URLs**: `https://app-field-api-nonprod.azurewebsites.net`, `https://app-field-ui-nonprod.azurewebsites.net`

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

## Azure App Service Pre-Prod Deployment (Feb 26-27, 2026) ✅

### Overview
Deployed all 4 services (triage-api, field-api, triage-ui, field-ui) to **Azure App Service** in a new pre-prod subscription. This is a separate environment from dev (Container Apps) with its own Cosmos DB, OpenAI, and Key Vault instances. All 6 health components are **GREEN** (Cosmos DB, Azure OpenAI, Key Vault, ADO, Cache, Corrections).

### Pre-Prod Infrastructure (NEW — separate from dev)

| Resource | Name | Details |
|----------|------|---------|
| **Subscription** | `a1e66643-8021-4548-8e36-f08076057b6a` | Pre-prod (different from dev `13267e8e-...`) |
| **Resource Group** | `rg-nonprod-aitriage` | North Central US |
| **App Service Plan** | `asp-aitriage-nonprod` | Linux, Python 3.12, B1 |
| **Triage API** | `app-triage-api-nonprod` | `https://app-triage-api-nonprod.azurewebsites.net` |
| **Field API** | `app-field-api-nonprod` | `https://app-field-api-nonprod.azurewebsites.net` |
| **Triage UI** | `app-triage-ui-nonprod` | `https://app-triage-ui-nonprod.azurewebsites.net` |
| **Field UI** | `app-field-ui-nonprod` | `https://app-field-ui-nonprod.azurewebsites.net` |
| **Cosmos DB** | `cosmos-aitriage-nonprod` | NoSQL, serverless, AAD auth, DB: `triage-management`, 10 containers |
| **Azure OpenAI** | `openai-aitriage-nonprod` | Deployments: `gpt-4o-standard`, `text-embedding-3-large` |
| **Key Vault** | `kv-aitriage` | Stores OpenAI config, Cosmos endpoint/key, ADO PATs |
| **App Registration** | `GCS-Triage-NonProd` | Client ID: `6257f944-71eb-49b9-8ef6-ab006383d54c` |
| **Managed Identity** | `TechRoB-Automation-DEV` | Client ID: `0fe9d340-a359-4849-8c0f-d3c9640017ee` |
| **App Insights** | (configured) | Instrumentation Key `766a42c9-...` |

### Deployment Scripts (infrastructure/deploy/)

| Script | Purpose |
|--------|---------|
| `01-create-resource-group.ps1` | Create RG + App Service Plan |
| `02-create-azure-resources.ps1` | Create Cosmos DB, OpenAI, Key Vault |
| `03-configure-rbac.ps1` | RBAC assignments for MI on Cosmos, KV, OpenAI |
| `04-create-app-registration.ps1` | MSAL App Registration for UI auth |
| `05-configure-appsettings.ps1` | Environment variables on all 4 App Services |
| `06-deploy-code.ps1` | Zip-deploy code packages to App Services |
| `build-packages.ps1` | Local build — creates 4 zip packages |

### Startup Command (App Service)
```
gunicorn --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker --timeout 300 --workers 1 triage.triage_service:app
```

### Build & Deploy Process
```powershell
# Build locally (creates packages/ dir with 4 zips)
.\infrastructure\deploy\build-packages.ps1 -Target triage-api   # copies triage/, api/, agents/ + 12 shared .py modules
.\infrastructure\deploy\build-packages.ps1 -Target triage-ui    # npm build + dist
.\infrastructure\deploy\build-packages.ps1 -Target field-api
.\infrastructure\deploy\build-packages.ps1 -Target field-ui

# Upload zips to Cloud Shell, then deploy (must use Cloud Shell — local az CLI is dev tenant)
az webapp deploy --resource-group rg-nonprod-aitriage --name app-triage-api-nonprod --src-path triage-api.zip --type zip
```

### Issues Found & Fixed During Deployment

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | **Python 3.13 build failure** | `pydantic-core` couldn't compile on Python 3.13 | Set App Service runtime to **Python 3.12** |
| 2 | **Port binding error** | App Service expects port 8000, startup used 8009/8010 | Changed startup command to `--bind 0.0.0.0:8000` |
| 3 | **Field API startup hang** | Gateway health check outside try/except blocked startup | Wrapped health check in try/except |
| 4 | **UI startup hang** | `npx serve` hung forever | Changed to `pm2 serve` for static file serving |
| 5 | **MSAL wrong client ID** | triage-ui had dev client ID hardcoded | Fixed `authConfig.js` to use pre-prod: `6257f944-...` |
| 6 | **Blank screen after login** | `triageApi.js` hardcoded `http://localhost:8009` | Changed to **relative API paths** (e.g., `/api/v1/...`) |
| 7 | **Cosmos DB in-memory mode** | Key Vault secrets not set for Cosmos | Manually set `COSMOS-ENDPOINT` and `COSMOS-KEY` secrets in KV |
| 8 | **Missing OpenAI dependencies** | `openai`, `numpy`, `scikit-learn` not in requirements.txt | Added `openai==1.52.0`, `numpy>=1.26.0`, `scikit-learn>=1.3.0` |
| 9 | **ADO auth failure (MI)** | `get_credential()` only tried `ADO_MANAGED_IDENTITY_CLIENT_ID` | Added fallback to `AZURE_CLIENT_ID` env var in `ado_integration.py` |
| 10 | **Missing gunicorn** | `gunicorn` not in requirements.txt — App Service can't start without WSGI server | Added `gunicorn==21.2.0` to `triage/requirements.txt` |
| 11 | **App stuck in stopped state** | Multiple failed starts caused Azure auto-stop; `restart` doesn't work on stopped apps | Used Azure Portal → Start (not restart) |
| 12 | **corrections.json not found** | `ai_config.py validate()` checked for file-system corrections.json on App Service | **Removed** file-system check — corrections are in Cosmos DB |
| 13 | **httpx/openai incompatibility** | `openai==1.52.0` passes `proxies=` to httpx.Client(), but `httpx==0.28.0` removed that param | Pinned `httpx>=0.25.0,<0.28.0` |
| 14 | **Hardcoded dev OpenAI resource** | `admin_routes.py` diagnostics had `openai-bp-northcentral` hardcoded | Changed to dynamic extraction from endpoint URL |
| 15 | **Cloud Shell AuthorizationFailed** | Stale credential in Cloud Shell session | Used Azure Portal as workaround for some operations |

### Source Files Modified for Pre-Prod

| File | Changes |
|------|---------|
| `triage/requirements.txt` | +`gunicorn==21.2.0`, +`openai==1.52.0`, +`numpy>=1.26.0`, +`scikit-learn>=1.3.0`, `httpx` pinned to `>=0.25.0,<0.28.0` |
| `ai_config.py` | Removed file-system corrections.json validation from `validate()` — corrections are in Cosmos DB |
| `hybrid_context_analyzer.py` | `get_ai_status()` now returns `_init_error`, `endpoint`, and `use_aad` for better diagnostics |
| `triage/api/admin_routes.py` | Dynamic OpenAI resource name extraction in `_build_diagnostics()` instead of hardcoded `openai-bp-northcentral` |
| `ado_integration.py` | `get_credential()` and `get_tft_credential()` fall back to `AZURE_CLIENT_ID` env var |
| `triage-ui/src/auth/authConfig.js` | Pre-prod MSAL client ID: `6257f944-71eb-49b9-8ef6-ab006383d54c` |
| `triage-ui/src/api/triageApi.js` | Relative API paths instead of hardcoded localhost URLs |

### Pre-Prod Health Check (Confirmed Feb 27, 2026)
```json
{
  "overall": "healthy",
  "components": {
    "cosmos_db":     { "status": "healthy", "auth_mode": "aad", "containers": 10 },
    "azure_openai":  { "status": "healthy", "enabled": true, "mode": "AI-Powered" },
    "key_vault":     { "status": "healthy", "vault": "kv-aitriage" },
    "ado_connection": { "status": "healthy", "read": "unifiedactiontracker", "write": "unifiedactiontrackertest" },
    "local_cache":   { "status": "healthy" },
    "corrections":   { "status": "healthy" }
  }
}
```

### Key Differences: App Service vs Container Apps (Dev)

| Aspect | Dev (Container Apps) | Pre-Prod (App Service) |
|--------|---------------------|----------------------|
| **Platform** | Azure Container Apps | Azure App Service (Linux) |
| **Python** | 3.11 (Docker) | 3.12 (App Service runtime) |
| **WSGI Server** | uvicorn (in Docker) | gunicorn + uvicorn workers |
| **Subscription** | `13267e8e-...` | `a1e66643-...` |
| **Cosmos DB** | `cosmos-gcs-dev` | `cosmos-aitriage-nonprod` |
| **OpenAI** | `OpenAI-bp-NorthCentral` | `openai-aitriage-nonprod` |
| **Key Vault** | `kv-gcs-dev-gg4a6y` | `kv-aitriage` |
| **MI** | `id-gcs-containerapp` | `TechRoB-Automation-DEV` |
| **Tenant** | `16b3c013-...` (fdpo) | `72f988bf-...` (Microsoft Corp) |
| **Auth** | Dual PATs for ADO | MI for Cosmos/KV/OpenAI, PATs for ADO |
| **Networking** | Internal/External ingress | Public App Service URLs |
| **UI Auth** | Basic auth (nginx) | MSAL (App Registration) |
| **Build** | ACR + Docker build | Local zip build + `az webapp deploy` |

---

## Recent Changes (Mar 4, 2026) — FR-1999: Tabbed Analysis Detail Views

### Tabbed Interface for Analysis Detail Pages (commits `b640e7b`, `4b06cff`)

Reduced scrolling on analysis detail pages by organizing content into a 4-tab pill-style interface (Overview / Analysis / Decision / Evaluate) with entity count badges and fade-in panel animation. Applied to:

| View | UI | Approach |
|------|----|----------|
| **AnalysisDetailPage** | Field Portal | 4-tab layout (`activeTab` state) |
| **EvaluatePage** | Triage UI | Per-work-item 4-tab layout (`activeDetailTabs` map) |
| **QueuePage blade** | Triage UI | Linear layout with "No data" placeholders (tabs tested & reverted per user feedback) |

**Files changed:**
- `field-portal/ui/src/pages/AnalysisDetailPage.jsx` — Tab state + 4-tab content split
- `field-portal/ui/src/styles/global.css` — Tab CSS (90 lines)
- `triage-ui/src/pages/EvaluatePage.jsx` — Per-item tab state + `renderAnalysisDetail` rewrite
- `triage-ui/src/pages/EvaluatePage.css` — Tab CSS (80 lines)
- `triage-ui/src/pages/QueuePage.jsx` — Always-render sections + "No data" spans
- `triage-ui/src/pages/QueuePage.css` — `.no-data` style

---

## Recent Changes (Mar 2, 2026) — Field Portal Pre-Prod Deployment

### 12 Issues Found & Fixed (commit `b7cb0fd`)

The field portal had 12 issues preventing it from running on Azure App Service. All were identified during a pre-deployment audit and fixed in a single commit:

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | **Missing gunicorn** | `field-portal/api/requirements.txt` didn't include WSGI server | Added `gunicorn==21.2.0` |
| 2 | **httpx/openai incompatibility** | `openai==1.52.0` passes `proxies=` to httpx 0.28+ which removed it | Pinned `httpx>=0.25.0,<0.28.0` |
| 3 | **Missing AI deps** | `numpy`, `scikit-learn` not in requirements | Added `numpy>=1.26.0`, `scikit-learn>=1.3.0` |
| 4 | **Port mismatch** | FastAPI config defaulted to 8010, App Service expects 8000 | Changed default to `int(os.getenv("PORT", "8000"))` |
| 5 | **No health endpoint** | No `/health` root endpoint for App Service probes | Added health endpoint with gateway/KV/AI checks |
| 6 | **Missing Cosmos config** | `from triage.config.cosmos_config import ...` but triage package not in field-api build | Build script copies `triage/__init__.py` + `triage/config/` |
| 7 | **Hardcoded localhost UI** | `fieldApi.js` hardcoded `http://localhost:8010` | Changed to `getApiBaseUrl()` reading `/config.json` |
| 8 | **CORS missing pre-prod** | Only localhost origins in CORS | Added `app-field-ui-nonprod.azurewebsites.net` |
| 9 | **MI auth not supported** | `cosmos_client.py` only used `DefaultAzureCredential` | Added `ManagedIdentityCredential(client_id)` when `AZURE_CLIENT_ID` set |
| 10 | **corrections.json write on read-only FS** | `_save_correction_feedback()` wrote to filesystem | Wrapped in try/except — Cosmos DB is primary store |
| 11 | **ADO credential chain incomplete** | `enhanced_matching.py` MI support missing | Added `AZURE_CLIENT_ID` fallback in `get_uat_credential()` and full MI chain in `get_tft_credential()` |
| 12 | **config.json not generated** | Field UI had no runtime config injection | Build script generates `config.json` with `FIELD_API_BASE_URL` |

### Files Modified
| File | Changes |
|------|--------|
| `field-portal/api/requirements.txt` | +gunicorn, +numpy, +scikit-learn, httpx pinned |
| `field-portal/api/config.py` | Port default 8000, CORS pre-prod domains, updated docstring |
| `field-portal/api/main.py` | Added `/health` endpoint with component checks |
| `field-portal/api/routes.py` | `_save_correction_feedback()` wrapped in try/except |
| `field-portal/api/cosmos_client.py` | ManagedIdentityCredential support |
| `field-portal/ui/src/api/fieldApi.js` | `getApiBaseUrl()` reads `/config.json` |
| `enhanced_matching.py` | MI credential chain in `get_uat_credential()` and `get_tft_credential()` |
| `infrastructure/deploy/build-packages.ps1` | Field-api copies `triage/config/`, generates `config.json` for UI |

### Deployment Verification
- **Field API**: `https://app-field-api-nonprod.azurewebsites.net/health`
  ```json
  {"status":"ok","components":{"gateway":"ok","key_vault":"ok","ai":"ok"},"response_time_ms":62}
  ```
- **Field UI**: `https://app-field-ui-nonprod.azurewebsites.net` — loads successfully
- **Triage API**: `https://app-triage-api-nonprod.azurewebsites.net/health` — all 10 Cosmos containers ready, AAD auth
- **Triage UI**: `https://app-triage-ui-nonprod.azurewebsites.net` — loads with MSAL auth

---

## Recent Changes (Feb 24, 2026) — Queue UX Overhaul: Dynamic Columns, Filtering, Analysis & Evaluation

### Dynamic Grid Columns (`797c889`)
- Queue table columns now **load dynamically** from the ADO saved query associated with each tab
- Removed hardcoded 18-column layout — grid adapts to whatever fields ADO returns
- Added **step-by-step loading progress** indicator (Authenticating → Fetching queries → Loading items → Processing)

### Column Resize Handles + Excel-Like Filtering (`b6fc456`)
- All columns are **resizable** via drag handles on the header right edge
- Each column header has a **funnel icon (▼)** that opens an Excel-like filter dropdown
- Filter dropdowns show checkboxes for each unique value in the column
- **Clear All Filters (✕)** button appears in the toolbar when any filter is active

### Filter Display Values (`480543f`)
- Filter dropdown values now show **formatted display text** matching the grid cells (e.g., "Requesting Feature" instead of `requesting_feature`)
- Added `displayValue()` and `rawCellValue()` helpers for consistent value formatting

### Unicode Fixes (`9b919f8`, `01a21d3`)
- Fixed filter button and clear-filters button rendering raw unicode strings instead of symbols
- Changed to JSX expressions using `'\u25BC'` / `'\u2715'` syntax

### Analyze Selected — Instant Feedback (`f17ca41`)
- **Instant button feedback**: `analyzing=true` set immediately on click (before AI status check)
- **Non-blocking AI status**: Replaced `window.confirm()` popup with toast notification + inline warning banner
- **Smart cache update**: After analysis completes, results are merged into cached data via `updateCachedAnalysis()` instead of clearing the entire cache and forcing a full ADO reload
- Grid scroll position and selection state are preserved after analysis

### Evaluation Result Visibility (`10e9713`)
- **Auto-expand**: All evaluated rows expand automatically after dry run completes — no scrolling to find results
- **Rule names**: Rule chips display human-readable names (e.g., "Retirement Match") from the backend `ruleNames` map instead of raw IDs like `rule-8f7d5486`. Tooltip shows the ID for reference.
- **Row click toggles expansion**: Click any row with results to toggle it open/closed
- **Multi-expand**: Converted from single `expandedId` to `expandedIds` Set — multiple rows can be expanded simultaneously
- **Expand All / Collapse All**: Toggle button in the bulk summary header
- **Visual indicators**: Rows with results show pointer cursor + hover highlight; expanded rows get a green left border

**Commits**: `797c889` → `b6fc456` → `9b919f8` → `01a21d3` → `480543f` → `f17ca41` → `10e9713` — all pushed to `origin/main`

---

## Recent Changes (Feb 23, 2026) — Dashboard Merge, Corrections CRUD, Teams, Cleanup

### Feb 23: Major UI Cleanup & Feature Additions ✅

**Dashboard + Health Merge**:
- Merged HealthPage into Dashboard — single unified view with status cards and health indicators
- Fixed Key Vault showing "Vault: unknown" — now displays actual vault name (`kv-gcs-dev-gg4a6y`) by importing `KEY_VAULT_URI` constant
- Added Dashboard CSS for unified layout

**Corrections Page Rewrite**:
- Rewrote to blade pattern (list + detail panel) matching Rules/Triggers/Actions/Routes
- Added full edit/update capability — new `PUT /admin/corrections/{index}` backend endpoint
- Form fields display human-readable values ("Business Engagement" not `business_engagement`), converts back to snake_case on save
- Full CRUD: create, read, update, delete corrections
- Category dropdowns now use grouped CATEGORY_OPTIONS (22 values in 6 groups: Core, Service, Capacity, Business, Support, Specialized) matching the Evaluate page exactly
- Renamed "Pattern" field to "Original Intent" — both intent fields are grouped INTENT_OPTIONS dropdowns (15 values in 4 groups) matching the Evaluate page
- Table columns: Original Category, Corrected Category, Original Intent, Corrected Intent, Notes
- `categoryLabel()` and `intentLabel()` helpers for accurate display (e.g., "AOAI Capacity", "Business Engagement")

**Classify Page Removed**:
- Removed entirely — dead feature, nav item, route, and source file deleted

**Triage Teams** (new):
- Added TriageTeamsPage with team management UI
- Added TeamFilter and TeamScopeSelect shared components
- Added `triage_team` model

**Evaluate Page Expansion**:
- Major expansion with evaluation history and detail views

**Queue Enhancements**:
- Enhanced queue management with caching and filters

**Entity Pages** (Rules, Triggers, Actions, Routes):
- FieldCombobox improvements for better field selection
- Form refinements across all entity types

**Field Portal**:
- Auth context + NoAuthProvider for flexible auth
- AnalysisDetailPage enhancements

**Backend**:
- ADO integration enhancements
- Cosmos DB config improvements
- CRUD service and schema updates
- Admin routes: vault health fix, corrections PUT endpoint

**Infrastructure**:
- Added Docker containers (Dockerfiles, nginx configs, deploy script)
- Added `.dockerignore` and `start_dev.ps1` convenience script
- Updated `.gitignore` — cache dirs, build logs, debug logs now excluded
- Removed tracked cache/log files from repo

**Dead Code Cleanup**:
- Deleted: `ClassifyPage.jsx`, `HealthPage.jsx`, `HealthPage.css`
- Untracked: `cache/ai_cache/classifications_cache.json`, `debug_ica.log`

**Commits**: `52179c2` (main feature commit) + `6b5088f` (corrections display fix) — pushed to `origin/main`

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
| `6f4e634` | Feb 23 | Rename Pattern → Original Intent, intent dropdowns matching Evaluate page |
| `cb92bb1` | Feb 23 | Corrections categories now match Evaluate page (22 grouped options) |
| `80eb7c8` | Feb 23 | Docs: updated PROJECT_STATUS, README, QUICKSTART for Feb 23 changes |
| `6b5088f` | Feb 23 | Corrections display fix — human-readable Pattern/Intent fields |
| `52179c2` | Feb 23 | Dashboard merge, corrections CRUD, teams, containers, cleanup (63 files) |
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
✅ Triage UI — 11 pages: Dashboard (with health), Queue, Evaluate/Analyze, Rules, Triggers, Actions, Routes, Triage Teams, Validation, Audit Log, Eval History, Corrections
✅ Corrections — full CRUD with blade pattern, edit mode, human-readable display
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
✅ **Pre-prod App Service deployment** — all 4 services running, all 6 health components GREEN
✅ **Pre-prod MSAL auth** — App Registration `GCS-Triage-NonProd` with correct client ID
✅ **Pre-prod Cosmos DB** — `cosmos-aitriage-nonprod` with AAD auth, 10 containers
✅ **Pre-prod Azure OpenAI** — `openai-aitriage-nonprod` with AI-Powered analysis enabled
✅ **Pre-prod ADO integration** — read: unifiedactiontracker, write: unifiedactiontrackertest

---

## Known Issues

⚠️ **Field Portal: MSAL re-prompts for login during quality submission AND UAT search** (HIGH PRIORITY)
- After initial login, the user is re-prompted to authenticate when submitting for quality review **and** when searching for matching UATs
- Multiple fixes attempted: removed `useMsalAuthentication(Silent)` hook, removed `acquireTokenPopup` fallback, disabled `acquireTokenSilent` entirely, added `inProgress` guard — none resolved the issue
- Root cause suspected: MSAL redirect-based login flow may be interfering with the SPA navigation to `/quality` — the redirect back from AAD lands on the app without the `location.state` that carries quality data, causing a blank page or re-auth loop
- `getToken()` currently returns `null` (token acquisition fully disabled) — backend does not validate tokens
- **TODO**: Investigate MSAL `handleRedirectPromise()` timing, consider switching to popup-based login (not token acquisition) or using `ssoSilent()` to restore sessions after redirect. May need to persist quality submission data to sessionStorage before the redirect.

✅ ~~**Field API may need same fixes as Triage API**~~ — **RESOLVED Mar 2**: All 12 issues identified and fixed in commit `b7cb0fd`. Field API deployed and healthy.

⚠️ Admin portal shows "AuthorizationFailure" on blob storage access
- Workaround: Use local JSON files for testing

⚠️ Analysis classification accuracy needs tuning
- Some categories/intents are debatable — review corrections, adjust pattern rules and LLM prompt

⚠️ Azure CLI cannot login locally (Conditional Access error 53003)
- Use Cloud Shell for `az` commands, or portal for resource management

⚠️ **DEBUG print statements in hybrid_context_analyzer.py** (CLEANUP)
- Lines 248-297 contain 17 `[DEBUG HYBRID N]` print statements from deployment troubleshooting
- Should be removed or converted to proper logging before next release

---

## Authentication Architecture

### Azure OpenAI
- **Dev Resource**: OpenAI-bp-NorthCentral (North Central US) — Tenant: `16b3c013-...` (fdpo)
- **Pre-Prod Resource**: openai-aitriage-nonprod (North Central US) — Tenant: `72f988bf-...` (Microsoft Corp)
- **Deployments**: `gpt-4o-standard` (classification), `text-embedding-3-large` (embeddings) — same names in both environments
- **Auth**: Azure AD only (API keys disabled by policy)
- **Role**: Cognitive Services OpenAI User
- **Config Source**: Key Vault (dev: `kv-gcs-dev-gg4a6y`, pre-prod: `kv-aitriage`)

### Azure Cosmos DB
- **Dev Account**: `cosmos-gcs-dev` (serverless, North Central US) — Tenant: `16b3c013-...` (fdpo)
- **Pre-Prod Account**: `cosmos-aitriage-nonprod` (serverless, North Central US) — Tenant: `72f988bf-...` (Microsoft Corp)
- **Database**: `triage-management` (both environments)
- **Auth**: AAD only (local auth disabled by Azure Policy)
- **Role**: Cosmos DB Built-in Data Contributor
- **Pre-Prod**: 10 containers (includes `corrections` and `queue-cache`)

### Key Vault
- **Dev**: `kv-gcs-dev-gg4a6y` — Auth: DefaultAzureCredential
- **Pre-Prod**: `kv-aitriage` — Auth: Managed Identity (`TechRoB-Automation-DEV`)
- **Secrets**: OpenAI endpoint/deployment, Cosmos endpoint/key, ADO PATs

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
**Latest commit**: `b7cb0fd` — fix: field portal pre-prod deployment (12 issues)
**Previous**: `8114c35` — docs + code: comprehensive documentation and code comment updates
**Previous**: `d1534cc` — chore: add *.zip to .gitignore

**All changes committed** — clean working tree (pending this documentation update commit).

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
- [x] ClassifyPage — removed (dead feature), HealthPage — merged into Dashboard, CorrectionsPage — rewritten with blade pattern + edit mode
- [ ] Classification tuning — review accuracy, refine LLM prompt, add corrections
- [ ] Webhook receiver — ADO pushes events → auto-analyze new items
- [ ] Analytics dashboard — trends, accuracy, volume metrics
- [ ] Full automation mode — trigger → route → ADO write without human review

### Infrastructure
- [x] Commit all field-portal changes (pushed `0ba2dea` — Feb 20)
- [x] Container deployment — All 4 apps deployed to Azure Container Apps (Feb 21-22)
- [x] Managed Identity — `id-gcs-containerapp` used for Cosmos + OpenAI AAD auth in containers
- [x] ADO integration in containers — Dual PAT approach (test org write, production org read)
- [x] AI analysis in containers — OpenAI env vars set, AI-Powered mode confirmed
- [x] **App Service pre-prod deployment** — All 4 services deployed to Azure App Service (Feb 26-27)
- [x] **Pre-prod health: ALL GREEN** — Cosmos, OpenAI, KV, ADO, Cache, Corrections all healthy
- [x] **Field API pre-prod fixes** — 12 issues fixed in commit `b7cb0fd` (Mar 2, 2026)
- [ ] **End-to-end pre-prod testing** — Full 9-step field flow and triage workflow through App Services
- [ ] **Remove DEBUG print statements** — 17 `[DEBUG HYBRID N]` lines in hybrid_context_analyzer.py
- [ ] **Cosmos DB private networking** — Public access disabled per company policy (Feb 24). Local dev and Container Apps need Private Endpoint or VNet integration to reach `cosmos-gcs-dev`. Current workaround: none (blocked).
- [ ] **Key Vault private networking** — Public access disabled per company policy (Feb 24). Local dev and Container Apps need Private Endpoint or VNet integration to reach `kv-gcs-dev-gg4a6y`. Container Apps currently use env vars as workaround.
- [ ] Rebuild container images — debug log hardcoded path fix needs redeployment
- [ ] Add COSMOS_ENDPOINT secret to Key Vault (currently using env vars)
- [ ] Copilot API plugin — field portal API already has OpenAPI spec at :8010/docs
- [ ] Custom domain / SSL for container apps and App Services
- [ ] CI/CD pipeline — automate build/deploy on push
- [ ] Legacy Flask UI retirement — retire `:5003` after field portal validation

### Existing Issues
- [ ] Admin portal shows "AuthorizationFailure" on blob storage access
- [x] Analysis AI now works (corrections.json path fix — Feb 19)
- [ ] Analysis classification accuracy needs tuning
- [ ] Azure CLI cannot login locally (Conditional Access error 53003) — use Cloud Shell

---

## Troubleshooting Quick Reference

### App Service (Pre-Prod) Issues

**502 Bad Gateway / App won't start**
- Check App Service logs: Portal → App Service → Log stream
- Most common: missing dependency in `requirements.txt` — ensure `gunicorn`, `openai`, `numpy`, `scikit-learn` are present
- Startup command must bind to port 8000: `gunicorn --bind 0.0.0.0:8000 ...`
- App may be in "stopped" state after repeated failures — use Portal → Start (restart won't work on stopped apps)

**"Client.__init__() got an unexpected keyword argument 'proxies'"**
- `openai==1.52.0` passes `proxies=` to httpx.Client(), but httpx 0.28+ removed that parameter
- Fix: Pin `httpx>=0.25.0,<0.28.0` in requirements.txt

**"Corrections file not found" health failure**
- Old `ai_config.py` validation checked for file-system `corrections.json`
- Fixed Feb 27: Removed file-system check — corrections are in Cosmos DB now
- If still appearing, ensure you have the latest `ai_config.py` deployed

**Diagnostics show wrong OpenAI resource name**
- Old `admin_routes.py` had `openai-bp-northcentral` hardcoded in diagnostics
- Fixed Feb 27: Now extracts dynamically from endpoint URL
- If still appearing, ensure latest `admin_routes.py` is deployed

**"ModuleNotFoundError: No module named 'gunicorn'"**
- `gunicorn` must be in `triage/requirements.txt` — App Service uses gunicorn as WSGI server
- Without gunicorn, the startup command fails before even loading uvicorn

**Cloud Shell "AuthorizationFailed"**
- Cloud Shell credential can become stale, especially across subscription switches
- Workaround: Use Azure Portal for the specific operation, or restart Cloud Shell

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

**STATUS** (Mar 2, 2026): System is fully operational locally, deployed to Azure Container Apps (dev), AND deployed to **Azure App Service (pre-prod)**. Pre-prod: 4 App Services in `rg-nonprod-aitriage` — **BOTH Triage and Field Portal deployed and healthy**. Cosmos DB (`cosmos-aitriage-nonprod`) with 10 containers, OpenAI (`openai-aitriage-nonprod`), Key Vault (`kv-aitriage`). MSAL auth via App Registration `GCS-Triage-NonProd`. Triage UI has 11 pages. Field Portal had 12 deployment issues fixed in commit `b7cb0fd` (Mar 2). Next: end-to-end pre-prod testing.

---

## Azure Container Apps Deployment (Feb 21-22, 2026) ✅

### Infrastructure
| Resource | Name | Details |
|----------|------|---------|
| **Resource Group** | `rg-gcs-dev` | North Central US |
| **ACR** | `acrgcsdevgg4a6y` | All 4 images built and pushed |
| **Container Apps Env** | `cae-gcs-dev` | Domain: `gentleisland-16a66e4f.northcentralus.azurecontainerapps.io` |
| **Cosmos DB** | `cosmos-gcs-dev` | AAD auth, serverless, database `triage-management`, all 9 containers |
| **Key Vault** | `kv-gcs-dev-gg4a6y` | Contains OpenAI, Cosmos, storage secrets |
| **Managed Identity** | `id-gcs-containerapp` | ClientId `5e7fe4e7-9be7-4768-a077-ebae7f29bc20` — Cosmos, KV, OpenAI, AcrPull |
| **Managed Identity** | `id-gcs-ado` | ClientId `ae84f7b5-9f04-47d2-a990-b6ae1053d8a8` — assigned but unusable for ADO (cross-tenant) |

### Container Apps (4 apps, all running)
| App | FQDN | Ingress | Image |
|-----|------|---------|-------|
| `ca-gcs-triage-ui` | `ca-gcs-triage-ui.gentleisland-16a66e4f.northcentralus.azurecontainerapps.io` | **External** | `gcs/triage-ui:latest` |
| `ca-gcs-triage-api` | `ca-gcs-triage-api.internal.gentleisland-16a66e4f...` | **Internal** | `gcs/triage-api:latest` |
| `ca-gcs-field-ui` | `ca-gcs-field-ui.gentleisland-16a66e4f.northcentralus.azurecontainerapps.io` | **External** | `gcs/field-ui:latest` |
| `ca-gcs-field-api` | `ca-gcs-field-api.internal.gentleisland-16a66e4f...` | **Internal** | `gcs/field-api:latest` |

**Access URLs** (basic auth: `gcs` / `TriageGCS2026!`):
- **Triage UI**: https://ca-gcs-triage-ui.gentleisland-16a66e4f.northcentralus.azurecontainerapps.io
- **Field UI**: https://ca-gcs-field-ui.gentleisland-16a66e4f.northcentralus.azurecontainerapps.io
- API containers are internal-only (proxied through UI nginx)

### ADO Integration — Dual PAT Approach ✅
Managed Identity approach failed (MI in fdpo tenant, ADO orgs in Microsoft tenant). Switched to PAT tokens:
- `ADO_PAT` → test org (`unifiedactiontrackertest`) for writes
- `ADO_PAT_READ` → production org (`unifiedactiontracker`) for reads
- Updated `ado_integration.py` with `self._pat_read` from `ADO_PAT_READ`
- Updated `triage/services/ado_client.py` with `_pat_for_org()` helper — all 8 HTTP call sites use correct org
- Status confirmed: `{"connected":true,"organization":"unifiedactiontrackertest","message":"Write: unifiedactiontrackertest, Read: unifiedactiontracker"}`

### AI Analysis — Enabled ✅
- Container initially reported `{"aiAvailable":false,"mode":"Pattern Only"}` because Key Vault was blocked by IP firewall
- Fixed by adding env vars directly to `ca-gcs-triage-api`:
  - `AZURE_OPENAI_ENDPOINT=https://OpenAI-bp-NorthCentral.openai.azure.com/`
  - `AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT=gpt-4o-standard`
  - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large`
  - `AZURE_OPENAI_USE_AAD=true` (was already set)
- MI `id-gcs-containerapp` has `Cognitive Services OpenAI User` role on the OpenAI resource
- Status now: `{"available":true,"aiAvailable":true,"mode":"AI-Powered"}`

### Triage API Env Vars (ca-gcs-triage-api)
```
AZURE_CLIENT_ID=5e7fe4e7-9be7-4768-a077-ebae7f29bc20
AZURE_OPENAI_USE_AAD=true
AZURE_OPENAI_ENDPOINT=https://OpenAI-bp-NorthCentral.openai.azure.com/
AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT=gpt-4o-standard
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
COSMOS_ENDPOINT=https://cosmos-gcs-dev.documents.azure.com:443/
COSMOS_USE_AAD=true
COSMOS_DATABASE=triage-management
ADO_MANAGED_IDENTITY_CLIENT_ID=ae84f7b5-9f04-47d2-a990-b6ae1053d8a8
ADO_PAT=<test-org-pat>
ADO_PAT_READ=<production-org-pat>
```

### Dockerfiles
| File | Purpose |
|------|---------|
| `containers/triage-api.Dockerfile` | Triage API — Python + uvicorn |
| `containers/triage-ui.Dockerfile` | Triage UI — Node build + nginx with basic auth + API proxy |
| `containers/field-api.Dockerfile` | Field API — Python + uvicorn |
| `containers/field-ui.Dockerfile` | Field UI — Node build + nginx with basic auth + API proxy |

### Build/Deploy Commands
```powershell
# Build (use --no-logs to avoid charmap encoding errors)
$env:PYTHONIOENCODING = "utf-8"
az acr build -r acrgcsdevgg4a6y -f containers/triage-api.Dockerfile -t gcs/triage-api:latest . --no-logs

# Deploy (bump FORCE_REDEPLOY to force new revision)
az containerapp update --name ca-gcs-triage-api --resource-group rg-gcs-dev `
  --set-env-vars "FORCE_REDEPLOY=N" `
  --image acrgcsdevgg4a6y.azurecr.io/gcs/triage-api:latest
```

### Remaining Container Deployment Items
- [ ] **Rebuild container images** — debug_ica.log hardcoded path fix needs redeployment (wrapped in try/except locally)
- [ ] **Key Vault networking** — Container Apps get `Forbidden` from KV due to IP firewall. Not blocking (using env vars), but should fix for cleaner config
- [ ] **Field API env vars** — field-api container may need OpenAI env vars too (same as triage-api)
- [ ] **End-to-end testing** — Full 9-step field flow and triage workflow through container apps
- [ ] **Custom domain / SSL** — Currently using Azure-generated FQDNs
- [ ] **CI/CD pipeline** — Automate build/deploy on push

---

**KEY CHANGES (Feb 22)**:
1. All 4 Container Apps deployed and running with nginx basic auth
2. Cosmos DB connected (AAD auth via Managed Identity)
3. ADO dual PAT integration fully working (both orgs)
4. AI analysis enabled (AI-Powered mode) via direct env vars
5. Fixed hardcoded `debug_ica.log` and `debug_context.log` paths (local only, container redeploy needed)

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

**Git**: All changes committed and pushed. Latest: `b7cb0fd` on `main`.
