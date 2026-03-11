# Project Status - Intelligent Context Analysis System
**Last Updated**: March 10, 2026 (Night)
**Status**: ✅ All systems operational — Local + Azure Container Apps (dev) + **Azure App Service (pre-prod)** — Triage Management + Field Portal **BOTH DEPLOYED** + Cosmos DB (16 containers) + AI classification (with retry logic + **dynamic classification config**) + ADO dual-org integration (MI auth) + batch resilience (errorPolicy=Omit) + diagnostics endpoint + **centralized config package (ENG-007)** + **entity export/import (FR-2005)** + **dynamic classification config (ENG-010)** + **Graph user lookup + background prefetch/cache (FR-1998 / PERF-001)** + **AI-powered UAT search via ADO Search API (FR-2020)** + **AI-powered TFT Feature search via ADO Search API (FR-2020b)** + **Correction display override fix (B0008)** + **Evaluate/Queue identity crash + fired-only rules + state persistence (B0009/B0009b/B0010/FR-2055)** + **Enhancement & Error Reporting (FR-2040/FR-2041)** + **Feature branch workflow + CODEOWNERS (ENG-012)** + **Production apply + bulk Apply All + revert/snapshots + ROBTAMS tag + perf fixes (FR-2056/B0011)** + **65 API endpoints**

⚠️ **Known Issue**: `Mail.Send` Graph API permission not yet granted to Managed Identity `TechRoB-Automation-DEV` — requires Entra ID admin (Cloud Application Administrator or Global Admin). Feedback email notifications will silently fail until granted. All other feedback functionality (Cosmos storage, blob upload) works.

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
         └─ User corrections override both slug AND display fields (B0008 fix)
      └─ "Save Corrections Only" → saves to corrections.json for learning
  *** CORRECTION IS PART OF THE USER JOURNEY, NOT A SEPARATE ADMIN FUNCTION ***
  └─ Template: context_evaluation.html (885 lines)

Step 5: Resource Search (/search_resources → /perform_search → /search_results)
  └─ Searches: Microsoft Learn, similar products, regional availability
  └─ Retirement info, capacity guidance
  └─ TFT Features: AI-powered search via ADO Search API (relevance-ranked)
      - 3-phase: raw AI service names → title keywords → WIQL broad fallback
      - 5-signal scoring (service-overlap, title-seq, token-jaccard, desc, exact-boost)
      - ServiceTree resolution for service-overlap scoring signal (not used in search text)
      - Removed/Closed features filtered out before scoring
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
  └─ AI-powered search via ADO Work Item Search API (relevance-ranked)
  └─ 3-phase: Search API with AI service names → Search API with title → WIQL broad fallback
  └─ 5-signal similarity scoring (service-overlap, title-seq, jaccard, description, exact-boost)
  └─ Template: select_related_uats.html

Step 8: UAT Selection
  └─ Checkboxes (max 5), saved via AJAX POST /save_selected_uat
  └─ Template: select_related_uats.html (same page)

Step 9: UAT Created (/create_uat)
  └─ Creates work item in ADO (unifiedactiontracker org — production, switched from test in B0011/FR-2056)
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
- **Pages** (14): Dashboard (with health + AI discoveries count), Queue, Evaluate/Analyze, Rules, Triggers, Actions, Routes, Triage Teams, Validation, Audit Log, Eval History, Corrections, Data Management, Classification Config

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

### Containers (16 total, auto-created)
`rules`, `actions`, `triggers`, `routes`, `evaluations`, `analysis-results`, `field-schema`, `audit-log`, `corrections`, `training-signals`, `queue-cache`, `servicetree-catalog`, `classification-config`, `feedback-reports`, `feedback-attachments`, `apply-snapshots`

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

## Recent Changes (Mar 10, 2026) — FR-2040/FR-2041: Enhancement & Error Reporting + Branching Workflow

### FR-2040 / FR-2041 — Enhancement Reporting & Error Reporting

Added a full feedback system to both the Field Portal and Triage UI, allowing users to submit enhancement requests (FR-2040) and error reports (FR-2041) from anywhere in the application. Reports are stored in Cosmos DB, screenshots/attachments uploaded to Azure Blob Storage, and email notifications sent via Microsoft Graph API.

**Backend (12 files):**
- `triage/services/feedback_service.py` — Core `FeedbackService` class with `submit_enhancement()` and `submit_error_report()` methods. Stores reports in Cosmos DB (`feedback-reports` container, partition key `/reportType`), uploads attachments to Blob Storage (`feedback-attachments` container), and sends email notifications via Graph API.
- `triage/services/email_service.py` — `send_feedback_email()` using MI credential → Graph API `POST /users/{sender}/sendMail`. Sender UPN resolved from Key Vault (`FEEDBACK-SENDER-UPN`) with env var fallback.
- `triage/services/blob_storage_helper.py` — `BlobStorageHelper` for uploading base64-encoded screenshots/attachments to Azure Blob Storage with content type detection and unique blob naming.
- `triage/api/feedback_routes.py` — FastAPI router: `POST /api/v1/feedback/enhancement`, `POST /api/v1/feedback/error-report` (2 new endpoints).
- `field-portal/api/feedback_routes.py` — Same feedback routes for the Field Portal API.
- `triage/config/cosmos_config.py` — Added `feedback-reports` and `feedback-attachments` container definitions (now 16 containers with `apply-snapshots`).
- `keyvault_config.py` — Added `FEEDBACK_SENDER_UPN` to `SECRET_MAPPINGS`.
- `infrastructure/deploy/03-configure-keyvault.ps1` — Added `FEEDBACK-SENDER-UPN` secret to deployment script.

**Frontend — Triage UI (6 files):**
- `triage-ui/src/hooks/useFeedback.js` — Custom React hook managing modal state, form data, screenshot capture, and API submission.
- `triage-ui/src/api/feedbackApi.js` — API client functions for enhancement and error report submission.
- `triage-ui/src/components/feedback/FeedbackCluster.jsx` + `.css` — Floating action button cluster (bottom-right) with expand/collapse animation, "Enhancement" and "Error Report" buttons.
- `triage-ui/src/components/feedback/FeedbackModal.jsx` + `.css` — Dual-mode modal (enhancement / error report) with form fields, severity picker, screenshot capture via `html2canvas`, file attachments, and submission state management.
- `App.jsx` — Wired `FeedbackCluster` + `FeedbackModal` + `useFeedback` hook into the app shell.

**Frontend — Field Portal (6 files):**
- Same component structure as Triage UI: `useFeedback.js`, `feedbackApi.js`, `FeedbackCluster.jsx/.css`, `FeedbackModal.jsx/.css`, wired into `App.jsx`.

**Totals:** 35 files, ~2,600 lines of new code. 2 new API endpoints per app (4 total). 2 new Cosmos containers. Both builds clean.

### Branching Workflow + CODEOWNERS

- **Feature branch**: `feature/FR-2040-2041-feedback` created from `main` — all feedback code on this branch (3 commits: `55c2192`, `7754ce1`, `00d27d2`).
- **PR #4**: Created on GitHub (`Price-Is-Right/uat-analysis-tool`) for review.
- **CODEOWNERS**: `.github/CODEOWNERS` created with `* @Price-Is-Right` — all files require owner review.
- **Branch protection**: Configured on `main` — require PR before merging.

### Infrastructure — Key Vault & RBAC

- **MI RBAC**: `TechRoB-Automation-DEV` granted **Key Vault Secrets Officer** at resource group level (`rg-nonprod-aitriage`). ServicePrincipal type bypasses MCAPS SFI Deny Policy that blocks persistent User RBAC assignments.
- **KV Secret**: `FEEDBACK-SENDER-UPN` = `TechRob@microsoft.com` stored in `kv-aitriage` (confirmed at `2026-03-10T22:49:30`).
- **Cloud Shell Firewall**: IP `40.118.133.244` added to KV firewall to allow Cloud Shell access (cleanup: remove when no longer needed).

### Known Issue — Mail.Send Permission Blocked

The email notification feature requires `Mail.Send` application permission on the MI's service principal in Microsoft Graph. Granting this permission requires an Entra ID directory role (Cloud Application Administrator or Global Admin) which the current user does not have. The "Grant admin consent" button in Enterprise Applications is grayed out, and `az rest` calls to the Graph appRoleAssignments endpoint return "Insufficient privileges".

**Impact**: Feedback reports save to Cosmos DB and Blob Storage successfully. Email notifications silently fail (returns `false`). No user-facing error.

**Resolution**: Requires an Entra admin to run:
```
az rest --method POST --uri "https://graph.microsoft.com/v1.0/servicePrincipals/309baa86-f939-4fc3-ab3e-e2d3d0d4e475/appRoleAssignments" --body "{\"principalId\":\"309baa86-f939-4fc3-ab3e-e2d3d0d4e475\",\"resourceId\":\"b19d498e-6687-4156-869a-2e8a95a9d659\",\"appRoleId\":\"b633e1c5-b582-4048-a93e-9f11b44c7e96\"}"
```
Or via Enterprise Apps → TechRoB-Automation-DEV → Permissions → Grant admin consent for Mail.Send.

---

## Recent Changes (Mar 8-9, 2026) — Field Portal Bug Fixes, Performance Root Cause, Design Audit

### Context
The triage portal was deployed to prod for a demo (Mar 8). After the demo, focus shifted to the field portal where Step 5 (Resource Search) was taking 116+ seconds. Investigation uncovered both immediate bugs and a fundamental design gap.

### Bug Fixes Completed (Mar 8)

#### UAT Search AND→OR Fix (enhanced_matching.py)
**Problem**: UAT search returned 0 results because WIQL key terms were joined with `AND` — requiring ALL keywords to appear in a single work item title.
**Fix**: Changed `" AND ".join(...)` to `" OR ".join(...)` in `search_uat_items()` in `enhanced_matching.py`.
**Debug logging added**: `[UAT-DEBUG]` prefix throughout `search_uat_items()`.

#### Duplicate API Call Prevention (3 UI pages)
**Problem**: React `useEffect` hooks fired twice (StrictMode + missing guards), causing duplicate search/create API calls.
**Fix**: Added `useRef` guards (`hasStarted.current`) in:
- `field-portal/ui/src/pages/SearchingPage.jsx` (Step 5 search)
- `field-portal/ui/src/pages/SearchingUATsPage.jsx` (Step 7 UAT search)
- `field-portal/ui/src/pages/CreateUATPage.jsx` (Step 9 UAT creation)

#### TFT Feature Search — Removed Embedding Dependency (ado_integration.py)
**Problem**: `search_tft_features()` in `ado_integration.py` used `embedding_service.py` (Azure OpenAI text-embedding-3-large) for similarity scoring. This added latency and an extra Azure dependency.
**Fix**: Replaced embedding-based scoring with keyword overlap + `difflib.SequenceMatcher`:
- Score formula: `score = (seq_sim * 0.6) + (overlap * 0.4)`, threshold >= 0.15
- WIQL cap=50, item limit=20, timeout=30s on all HTTP requests
- No more dependency on embedding_service.py for TFT search
- **Debug logging added**: `[TFT-DEBUG]` prefix in `ado_integration.py`, `[TFT-ROUTE-DEBUG]` prefix in `routes.py`

#### DiagnosticsPanel Removed from Both UIs
- Removed `<DiagnosticsPanel />` import and render from `field-portal/ui/src/App.jsx`
- Removed `<DiagnosticsPanel />` import and render from `triage-ui/src/components/layout/AppLayout.jsx`
- **Note**: The component files still exist (`field-portal/ui/src/components/DiagnosticsPanel.jsx` and `.css`) — they are just not imported/rendered anywhere. Can be deleted as cleanup.

#### SearchingPage Phase Messages Updated
- Removed references to embeddings and diagnostics from the progress messages in `SearchingPage.jsx`

### Performance Root Cause — IDENTIFIED, NOT YET FIXED

**Symptom**: Step 5 (Resource Search) takes 60-120 seconds for most categories.

**Root Cause**: The API Gateway (port 8000) is NOT running. In `field-portal/api/routes.py` (line ~992), there is a `skip_categories` list:
```python
skip_categories = ["technical_support", "feature_request", "cost_billing", "aoai_capacity", "capacity"]
```

For these 5 categories, the gateway call is skipped. For ALL OTHER categories (~17 of the 22 IssueCategory values), the code calls `gw.search_resources()` which POSTs to `http://localhost:8000/api/search/` via `field-portal/api/gateway_client.py`. This has a **60-second timeout** (`SEARCH_TIMEOUT = 60.0` at line 20 of gateway_client.py). Since the gateway isn't running, the request hangs for 60s before a `GatewayError` is caught and the code continues with empty results.

**The field portal was designed to work WITHOUT the gateway** (per this doc: "Calls analysis engines DIRECTLY (no gateway/microservice dependency). Gateway is fallback only."). The quality scoring and context analysis already call engines directly. But the search route still has the gateway dependency for non-skip categories.

**Fix needed**: Either expand `skip_categories` to include ALL categories (making the gateway call dead code), or remove the gateway call entirely from the search route. The `_generate_learn_docs()` function already generates Learn docs locally when the gateway doesn't return any.

### Design Audit — CRITICAL GAP IDENTIFIED

A full design discussion was held about **what the application is supposed to do**. The core purpose is:

> **Subvert the need to create a UAT (Unified Action Tracker) work item** by providing AI-guided deflection, self-service links, and feature matching — only creating a UAT as a last resort when no other path is appropriate.

#### Intended Flow Branching (NOT YET IMPLEMENTED)

Based on the AI-classified category, the wizard should branch into 3 paths after Step 4 (Analysis Review):

| Path | Categories | Behavior |
|------|-----------|----------|
| **Deflect** | `capacity`, `aoai_capacity`, `cost_billing`, `technical_support`, `support`, `support_escalation` | Show guidance + self-service links + "I still want to create a UAT" override button (with reiteration that it's not the best path). If no override → "Done" page. |
| **Feature/Service Search** | `feature_request`, `service_availability`, plus `requesting_service` intent | Search TFT Features in ADO, show similar items, then proceed to Steps 6-9 (UAT creation) |
| **Create UAT** | Everything else | Show Learn docs → proceed to Steps 6-9 (UAT creation) |

#### Current State (What's Missing)
1. **No flow branching exists** — The wizard always follows all 9 steps regardless of category. `SearchResultsPage.jsx` `handleContinue` always navigates to `/uat-input`.
2. **No "Done/Exit" page** — There's no way for deflect categories to exit the wizard without creating a UAT.
3. **No override mechanism** — Users who get deflected can't say "I still want to create a UAT anyway."
4. **TFT search only for `feature_request`** — The `if category == "feature_request":` gate at line ~1053 of `routes.py` needs to also include `service_availability` and check for `requesting_service` intent.
5. **guidance.py only has 5 entries** — `technical_support`, `cost_billing`, `aoai_capacity`, `capacity`, `feature_request`. Missing guidance for: `support`, `support_escalation`, `sustainability`, `retirements`, `service_availability`, and many others.
6. **Performance must be 5-10 seconds** — User emphasized the old system was fast (5-10 seconds for search). Current: 60-120 seconds due to dead gateway.

### IssueCategory Enum Values (22 total — intelligent_context_analyzer.py line 93)
```
compliance_regulatory, technical_support, feature_request, migration_modernization,
security_governance, performance_optimization, integration_connectivity, cost_billing,
training_documentation, service_retirement, service_availability, data_sovereignty,
product_roadmap, aoai_capacity, business_desk, capacity, retirements, roadmap,
support, support_escalation, sustainability
```

### IntentType Enum Values (16 total — intelligent_context_analyzer.py line 118)
```
seeking_guidance, reporting_issue, requesting_feature, need_migration_help,
compliance_support, troubleshooting, configuration_help, best_practices,
requesting_service, sovereignty_concern, roadmap_inquiry, capacity_request,
escalation_request, business_engagement, sustainability_inquiry, regional_availability
```

### Guidance Categories Currently Defined (guidance.py — 5 total)
| Category | Title | Variant | Key Links |
|----------|-------|---------|-----------|
| `technical_support` | Technical Support Issue Detected | warning | CSS Compass, Reactive Escalation, GetHelp |
| `cost_billing` | Billing Issue - Out of Scope | danger | GetHelp Portal |
| `aoai_capacity` | Azure OpenAI Capacity Request | info | AI Capacity Hub |
| `capacity` | Capacity Request Guidelines | info | AI Capacity Hub, SharePoint guidelines |
| `feature_request` | Feature Request - TFT System | info | TFT Feature tracking info |

### Key Files for Next Session

| File | Lines | What's There | What Needs to Change |
|------|-------|-------------|---------------------|
| `field-portal/api/routes.py` | ~1536 | `skip_categories` at L990, gateway call at L1002, TFT gate at L1053, guidance at L1092 | Remove/bypass gateway call; expand TFT gate; add flow branching logic to search response |
| `field-portal/api/gateway_client.py` | ~178 | `SEARCH_TIMEOUT = 60.0` at L20, `search_resources()` at L161 | May become dead code if gateway call is removed |
| `field-portal/api/guidance.py` | ~80 | 5 category guidance entries | Add guidance for `support`, `support_escalation`, and other deflect categories |
| `field-portal/ui/src/pages/SearchResultsPage.jsx` | ~400 | `handleContinue` always → `/uat-input` | Branch based on category: deflect → Done page, feature → continue, other → continue |
| `field-portal/ui/src/App.jsx` | ~100 | 10 routes, all always available | May need new `/done` route for deflect exit |
| `enhanced_matching.py` | ~2646 | UAT search with `[UAT-DEBUG]` logging, AND→OR fix | Working correctly now |
| `ado_integration.py` | ~1088 | TFT search with keyword+SequenceMatcher, `[TFT-DEBUG]` logging | Working correctly now |
| `intelligent_context_analyzer.py` | ~1800 | IssueCategory (22) and IntentType (16) enums | Reference only — no changes needed |

### Server Configuration (Local Dev)
- **Field Portal API**: Port 8010, started with `python -m uvicorn api.main:app --host 0.0.0.0 --port 8010 --reload` from `C:\Projects\Hack` (NOT from `field-portal/` — the `--reload` watcher needs the root dir to pick up changes to shared modules like `ado_integration.py` and `enhanced_matching.py`)
- **Field Portal UI**: Port 3001, `npm run dev` from `field-portal/ui/`
- **API Gateway**: Port 8000 — **NOT RUNNING and NOT NEEDED** for field portal (quality + analysis work without it; search should too)
- **Triage API**: Port 8009
- **Triage UI**: Port 3000

---

### THREE-PHASE IMPLEMENTATION PLAN (Approved in Discussion, Not Yet Started)

**User explicitly said "Do nothing till I sign off"** — all code changes below are pending approval.

#### Phase 1: Performance Fix — Remove Gateway Dependency from Search
- Make ALL categories skip the gateway call (or remove it entirely)
- The `_generate_learn_docs()` function already handles Learn doc generation locally
- `similar_products`, `regional_options` from gateway are not displayed in the current UI anyway
- Expected result: Step 5 goes from 60-120s → 5-10s for non-feature categories

#### Phase 2: Flow Branching — Deflect vs Feature Search vs Create UAT
- **Backend** (`routes.py`): Add a `flow_path` field to the `SearchResponse` model (values: `deflect`, `feature_search`, `create_uat`) based on category/intent
- **UI** (`SearchResultsPage.jsx`): Branch `handleContinue` based on `flow_path`:
  - `deflect` → new `/done` page (guidance + links + "I still want to create a UAT" override button)
  - `feature_search` / `create_uat` → existing `/uat-input` flow
- **New page**: `DonePage.jsx` — shows category guidance, reiteration message, self-service links, and override button ("Continue to UAT Creation Anyway")
- **TFT gate expansion**: Add `service_availability` category and `requesting_service` intent to the TFT search condition

#### Phase 3: Guidance Completeness
- Add `guidance.py` entries for all deflect categories that don't have them yet (`support`, `support_escalation`)
- Review and potentially add guidance for other categories like `sustainability`, `retirements`, `service_availability`
- Ensure every deflect category has meaningful links and actionable text

---

### B0004 — ServiceTree Stats Key Mismatch
`servicetree_service.py` `get_catalog_stats()` returned camelCase keys (`totalServices`, `totalOfferings`) but all 7 consumers in `admin_routes.py` expected snake_case (`total_services`, `total_offerings`). Dashboard showed 0 services despite 1439 loaded. **Fixed** by changing return keys to snake_case.

### B0005 — Classification Config Cosmos ORDER BY BadRequest
Two Cosmos queries in `admin_routes.py` used multi-field `ORDER BY` clauses requiring composite indexes not defined on the container. Cosmos returned `(BadRequest) One of the input values is invalid`. **Fixed** by removing `ORDER BY` and sorting in Python.

### ENG-011 — Dashboard UI Improvements
Compact 5-across count cards, validation warnings promoted to inline health card, 3-column responsive health grid. Files: `Dashboard.jsx`, `Dashboard.css`.

### Classification Config Seed Data
Ran `seed_classification_config.py` — 40 items seeded into Cosmos (20 categories, 16 intents, 4 business impacts). Verified via API: all 40 items returned correctly grouped by configType.

---

## Recent Changes (Mar 7, 2026) — ENG-010: Dynamic Classification Config

### Dynamic Classification Config — AI Auto-Discovery + Admin Review

Replaced hardcoded classification lists in `llm_classifier.py` with a fully dynamic, Cosmos DB-backed configuration system. Categories, intents, and business-impact values are now loaded at runtime from the `classification-config` container (5-minute cache, thread-safe). When the AI returns a value not in the official list, it is automatically recorded as a "discovered" item for admin review — instead of raising a ValueError that blocked analysis.

**Backend:**
- `triage/config/cosmos_config.py` — Added `classification-config` container definition (partition key `/configType`, now 13 containers total)
- `llm_classifier.py` — Major refactor: hardcoded `VALID_CATEGORIES`/`VALID_INTENTS`/`VALID_BUSINESS_IMPACTS` replaced with `_FALLBACK_*` constants + dynamic `_load_dynamic_config()` from Cosmos (5-min TTL, `_config_lock` for thread safety). New `_record_discovery()` persists AI-found values. Validation no longer raises ValueError; unknown values are recorded and analysis continues.
- `triage/api/admin_routes.py` — 3 new endpoints:
  - `GET /admin/classification-config` — List all config items (filterable by `config_type` and `status`)
  - `GET /admin/classification-config/discoveries` — Only AI-discovered items, sorted by `discoveredCount` DESC
  - `PUT /admin/classification-config/{id}` — Accept/reject/redirect discovered values (update status, displayName, keywords, redirectTo)
- `seed_classification_config.py` — One-time migration script to seed 40 documents (20 categories + 16 intents + 4 business impacts) from hardcoded fallback lists. Safe to re-run (skips existing docs).

**Frontend:**
- `ClassificationConfigPage.jsx` + `.css` (new) — Full management page with filterable table (type/status), status badges (official/discovered/rejected), quick accept/reject buttons, detail/edit panel with redirect dropdown, stat chips
- `Dashboard.jsx` — New "AI Discoveries" count card with pulse animation when discoveries > 0, links to Classification Config page
- `Dashboard.css` — `.dashboard-count-highlight` with `disco-pulse` keyframe
- `triageApi.js` — 3 new API functions: `listClassificationConfig()`, `listClassificationDiscoveries()`, `updateClassificationConfig()`
- `App.jsx` — Lazy import `ClassificationConfigPage`, new route `/classification`
- `constants.js` — New nav item: 🧠 Classification

**Classification Config Document Schema:**
```json
{
  "id": "cat_technical_support",
  "configType": "category | intent | business_impact",
  "value": "technical_support",
  "status": "official | discovered | rejected",
  "displayName": "Technical Support",
  "keywords": [],
  "discoveredFrom": null,
  "discoveredCount": 0,
  "redirectTo": null,
  "source": "seed | ai",
  "createdAt": "...",
  "updatedAt": "..."
}
```

---

## Recent Changes (Mar 5, 2026) — ServiceTree Routing Integration

### ServiceTree Catalog Integration — Backend + UI Inline Edit

Integrated the ServiceTree service catalog API to enrich triage analysis results with routing metadata (solution area, CSU DRI, ADO area path). Routing fields are displayed inline on triage records with admin override support.

**Backend:**
- `servicetree_service.py` — Core ServiceTree service with 5-tier cache fallback, fuzzy lookup (exact→substring→fuzzy), admin overrides, singleton via `get_servicetree_service()`
- `PATCH /api/v1/analysis/{work_item_id}/routing` — Per-record routing field override endpoint with `_RoutingPatch` Pydantic model
- `AnalysisResult` model extended with 7 new fields: `serviceTreeMatch`, `serviceTreeOffering`, `solutionArea`, `csuDri`, `areaPathAdo`, `releaseManager`, `devContact`
- ServiceTree enrichment wired into `_map_hybrid_to_analysis_result()` in the analysis pipeline
- 6 admin API routes for catalog management: catalog summary, search, list services, refresh, apply/remove overrides
- `servicetree-catalog` Cosmos container (partition key `/solutionArea`)
- ServiceTree health component in health dashboard + diagnostics

**Frontend:**
- `ServiceTreeRouting.jsx` + `ServiceTreeRouting.css` — Reusable component with display/edit/compact modes
- `patchAnalysisRouting()` API function in `triageApi.js`
- QueuePage: Routing section in analysis detail blade (between Classification and AI Reasoning)
- EvaluatePage: Dedicated **ServiceTree** tab with visual routing flow, grouped cards (Service Match / Routing Assignment / Contacts), inline editing, empty state, and override audit trail
- Override badge shown when `routingOverrideBy` is set

**ServiceTree BFF:** `tf-servicetree-api.azurewebsites.net` — Express.js proxy to `F051-PRD-Automation` Function App, auth via `api://73b8d7d8-5640-4047-879f-7f0a0298905b` (corp tenant)

**Git:** `e22e29c`

---

## Recent Changes (Mar 5, 2026) — FR-2005: Entity Export/Import (Data Management)

### FR-2005 — Data Management Service + UI

New Data Management page and API for exporting and importing Rules, Triggers, Routes, and Actions.

**Backend:**
- `triage/services/data_management_service.py` — `DataManagementService` with export, preview, execute, auto-backup, dependency resolution, ID remapping
- `triage/api/data_management_routes.py` — FastAPI router: `POST export`, `POST import/preview`, `POST import/execute`
- Import order: Rules → Actions → Routes → Triggers (leaves first)
- Name-based upsert: matches by name (natural key), not UUID
- Auto-includes dependencies: Trigger → Rules + Route; Route → Actions
- Auto-backup of all affected entity types before every import

**Frontend:**
- `DataManagementPage.jsx` — tabbed Export/Import UI with per-record checkboxes
- Export: load entity types, select individual records, download JSON bundle
- Import: upload JSON, preview create/update actions, execute with result summary
- Dependency display shows auto-included entities with reason and requiredBy
- Sidebar nav entry: 📦 Data Mgmt

**Git:** `099b45f`

---

## Recent Changes (Mar 7, 2026) — ENG-007: Centralized Config Package (PR #1, ChrisKoenig)

### ENG-007 — Environment-Aware Configuration Package

**PR #1** from ChrisKoenig — squash-merged as commit `437bf75`.

Replaces scattered `os.getenv()` calls and hardcoded values with a centralized `config/` Python package.

**New files (config package):**
- `config/__init__.py` — `AppConfig` dataclass (~40 fields), `get_app_config()` entry point, `_apply_env_overrides()` for container/App Service
- `config/dev.py` — Dev defaults (Cosmos, OpenAI, ADO, ports)
- `config/preprod.py` — Nonprod Azure resource config
- `config/prod.py` — Production config (requires env vars for all critical fields — safety feature)
- `config/environments/dev.ps1`, `preprod.ps1`, `prod.ps1` — PowerShell environment profiles for deployment scripts

**New utility:**
- `infrastructure/scripts/show-config.ps1` — Diagnostic script: `show-config.ps1 -Env dev|preprod|prod`

**Refactored services (7 files):**
| File | Change |
|------|--------|
| `shared_auth.py` | `TENANT_ID` from `_get_tenant_id()` → env var → config → hardcoded fallback |
| `keyvault_config.py` | KV name from `_resolve_kv_name()` → env var → config → fallback with warning |
| `ado_integration.py` | ADO org/project from config with env var override; TFT org/project from config |
| `enhanced_matching.py` | ADO orgs, Microsoft tenant ID from config via `_load_ado_config()` |
| `launcher.py` | All ports and Cosmos endpoint/tenant from config with try/except fallback |
| `admin_service.py` | Port map from `_app_cfg.service_port_map`, service port from config |
| `api_gateway.py` | CORS origins from config (no more wildcard `["*"]`), service URLs from config |

**Other changes:**
- `field-portal/api/config.py` — ADO orgs and CORS origins from config
- `containers/deploy.ps1` — Dot-sources environment PS1 file instead of inline vars
- `README.md` — Updated quick-start and configuration sections
- `docs/CHANGE_LOG.md` — Added ENG-007 entry
- Dependency bumps: `azure-identity 1.21.0`, `azure-keyvault-secrets 4.9.0`

**Key design:** Set `APP_ENV=dev|preprod|prod` → reduces ~10 env vars to 1. Env var overrides still apply on top.

---

## Recent Changes (Mar 6, 2026) — Bug Fixes, Retry Logic, Diagnostics, Batch Resilience

### Bug Fixes (B0002, B0003)

**B0002 — Hybrid source not recognized as LLM:**
- `EvaluatePage.jsx` only matched `source === "llm"` for LLM-specific UI. Items with `source: "hybrid"` (LLM primary + pattern features) appeared as pattern-only.
- Fix: Changed `isLLM` check to `source === "llm" || source === "hybrid"`.

**B0003 — Comparison crash on pattern-only fallback:**
- When LLM unavailable, `agreement` was unset (`undefined`). Pattern Engine Comparison section assumed it was always boolean, causing render crash.
- Fix (backend): `hybrid_context_analyzer.py` sets `agreement=None` on pattern-only fallback.
- Fix (frontend): `EvaluatePage.jsx` gates comparison section on `agreement !== null && agreement !== undefined`.

### ENG-004 — LLM Classifier Retry Logic

Added exponential backoff retry to `LLMClassifier.classify()` for transient Azure OpenAI failures:
- 3 retries, 1s base backoff (doubles each retry), 5s for 429 rate limits
- Jitter prevents thundering herd
- Retryable: 429, 500, 502, 503, 504, `APIConnectionError`, `APITimeoutError`

**File:** `llm_classifier.py` — `MAX_RETRIES=3`, `BASE_BACKOFF_SECONDS=1.0`, `RATE_LIMIT_BACKOFF=5.0`

### ENG-005 — Diagnostics Endpoint + Inline Diagnostics UI

**Backend:** New `GET /api/v1/diagnostics` endpoint returning AI config, Cosmos, ADO, and cache status.

**Frontend:**
- `DiagnosticsPanel.jsx` / `.css` (new) — Floating diagnostics icon accessible from `AppLayout`
- `EvaluatePage.jsx` — Inline "Show Diagnostics" button in yellow "AI Unavailable" banner. Expands collapsible panel with AI status, OpenAI config, error details.
- `EvaluatePage.css` — ~120 lines of inline diagnostics CSS
- `triageApi.js` — `getDiagnostics()` API function

### ENG-006 — Batch Fetch Resilience (errorPolicy=Omit)

**Problem:** ADO batch API returned HTTP 404 for entire batch when any single work item ID was invalid. "Batch fetch failed" for all items.

**Fix (2 parts in `triage/services/ado_client.py`):**
1. `_read_batch_url()`: Added `&errorPolicy=Omit` — ADO returns 200 with null placeholders instead of 404
2. `get_work_items_batch()`: Added null-safe iteration (`if item is None: continue`), `fetched_ids` tracking set, per-ID omission detection

**Verified:** Batch `[713010, 731001, 712931, 712918]` → 3 valid items analyzed, 1 invalid gracefully reported as `"Failed to fetch #731001"`.

### Files Modified This Session (12 files, 537 insertions)

| File | Changes |
|------|---------|
| `hybrid_context_analyzer.py` | B0001 enum `.value` normalization + B0003 `agreement=None` for pattern-only fallback |
| `llm_classifier.py` | ENG-004: Retry logic with exponential backoff (3 retries, jitter) |
| `triage/services/ado_client.py` | ENG-006: `errorPolicy=Omit` in batch URL + null-safe iteration + `fetched_ids` tracking |
| `triage/api/routes.py` | ENG-005: `GET /api/v1/diagnostics` endpoint |
| `triage-ui/src/pages/EvaluatePage.jsx` | B0002 isLLM includes "hybrid", B0003 comparison guard, ENG-005 inline diagnostics |
| `triage-ui/src/pages/EvaluatePage.css` | ENG-005: ~120 lines inline diagnostics CSS |
| `triage-ui/src/api/triageApi.js` | ENG-005: `getDiagnostics()` |
| `triage-ui/src/components/common/DiagnosticsPanel.jsx` | ENG-005: Floating diagnostics panel (new) |
| `triage-ui/src/components/common/DiagnosticsPanel.css` | ENG-005: Diagnostics panel styles (new) |
| `triage-ui/src/components/layout/AppLayout.jsx` | ENG-005: Import DiagnosticsPanel |
| `docs/CHANGE_LOG.md` | Added entries 6-10, bugs B0002-B0003, detail sections ENG-004/005/006 |
| `docs/ADO_INTEGRATION.md` | Documented errorPolicy=Omit behavior in batch fetch section |

---

## Recent Changes (Mar 4, 2026) — FR-1994, FR-1999: Tabbed Analysis Detail Views

### Tabbed Interface for Analysis Detail Pages (commits `b640e7b`, `4b06cff`)

Reduced scrolling on analysis detail pages by organizing content into a 5-tab pill-style interface (Overview / Analysis / Decision / ServiceTree / Correct & Reanalyze) with entity count badges and fade-in panel animation. Applied to:

| View | UI | Approach |
|------|----|----------|
| **AnalysisDetailPage** | Field Portal | 5-tab layout (`activeTab` state) |
| **EvaluatePage** | Triage UI | Per-work-item 5-tab layout (`activeDetailTabs` map) |
| **QueuePage blade** | Triage UI | Linear layout with "No data" placeholders (tabs tested & reverted per user feedback) |

**Files changed:**
- `field-portal/ui/src/pages/AnalysisDetailPage.jsx` — Tab state + 5-tab content split
- `field-portal/ui/src/styles/global.css` — Tab CSS (90 lines)
- `triage-ui/src/pages/EvaluatePage.jsx` — Per-item tab state + `renderAnalysisDetail` rewrite + dedicated ServiceTree tab
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
✅ Triage UI — 14 pages: Dashboard (with health + AI discoveries), Queue, Evaluate/Analyze, Rules, Triggers, Actions, Routes, Triage Teams, Validation, Audit Log, Eval History, Corrections, Data Management, Classification Config
✅ Corrections — full CRUD with blade pattern, edit mode, human-readable display
✅ Desktop launcher GUI (`launcher.py`)
✅ Azure Cosmos DB with AAD cross-tenant auth
✅ Persistent token cache (no repeated auth prompts across restarts)
✅ Queue caching across navigation
✅ Audit log with filters, search, change details
✅ Health indicator in sidebar
✅ Azure OpenAI AI classification (0.95 confidence, LLM source)
✅ LLM classifier retry logic (3 retries, exponential backoff, jitter)
✅ Pattern matching fallback when LLM unavailable
✅ Batch ADO fetch with errorPolicy=Omit (resilient to invalid IDs)
✅ Diagnostics endpoint (`GET /api/v1/diagnostics`) + inline UI in AI Unavailable banner
✅ Web UI with Quick ICA analysis (port 5003)
✅ TFT Feature search for feature_request category (keyword+SequenceMatcher — no embedding dependency)
✅ UAT search with OR-joined keywords (fixed Mar 8)
✅ Duplicate API call prevention (useRef guards in SearchingPage, SearchingUATsPage, CreateUATPage)
✅ Dual organization authentication (main + TFT)
✅ Admin portal on port 8008
✅ Centralized config package (`config/`) — `AppConfig` dataclass, per-env configs (dev/preprod/prod), `get_app_config()`
✅ PowerShell environment profiles (`config/environments/`) + `show-config.ps1` diagnostic script
✅ Data Management — entity export/import with auto-backup, name-based upsert, dependency resolution, per-record selection
✅ Dynamic Classification Config — Cosmos-backed categories/intents/impacts with 5-min cache, AI auto-discovery, admin review workflow, seed migration script
✅ Graph user lookup — resolve email → displayName/jobTitle/department via Microsoft Graph API (`/api/v1/graph/user`)
✅ Background prefetch + cache for Graph user data — eliminates 5-second blade delay (useRef Map cache, 80ms stagger)
✅ Collapsible accordion blade sections in Queue analysis blade
✅ Requestor field fix — reads `Custom.Requestors` / `Custom.Requestor` instead of only `System.CreatedBy`
✅ **Pre-prod App Service deployment** — all 4 services running, all 6 health components GREEN
✅ **Pre-prod MSAL auth** — App Registration `GCS-Triage-NonProd` with correct client ID
✅ **Pre-prod Cosmos DB** — `cosmos-aitriage-nonprod` with AAD auth, 10 containers
✅ **Pre-prod Azure OpenAI** — `openai-aitriage-nonprod` with AI-Powered analysis enabled
✅ **Pre-prod ADO integration** — read: unifiedactiontracker, write: unifiedactiontrackertest

---

## Known Issues

⚠️ **Field Portal Step 5: 60-120s delay for non-skip categories** (HIGH PRIORITY — root cause found)
- Gateway (port 8000) is NOT running. Non-skip categories call `gw.search_resources()` which hangs for 60s timeout.
- `skip_categories` = `["technical_support", "feature_request", "cost_billing", "aoai_capacity", "capacity"]` — only 5 of 22 categories skip the gateway
- **Fix**: Remove/bypass gateway call entirely (Phase 1 of implementation plan). See Mar 8-9 section above.

⚠️ **Field Portal: No flow branching by category** (HIGH PRIORITY — design gap)
- Wizard always follows all 9 steps regardless of category. Deflect categories (capacity, billing, support) should exit early with guidance links.
- No "Done" page, no override mechanism, no exit ramp.
- **Fix**: Phase 2 of implementation plan. See Mar 8-9 section above.

⚠️ **Field Portal: MSAL re-prompts for login during quality submission AND UAT search** (MEDIUM)
- After initial login, the user is re-prompted to authenticate when submitting for quality review **and** when searching for matching UATs
- `getToken()` currently returns `null` (token acquisition fully disabled) — backend does not validate tokens
- **TODO**: Investigate MSAL `handleRedirectPromise()` timing, consider switching to popup-based login

⚠️ **Field Portal: DiagnosticsPanel files still exist but are unused**
- `field-portal/ui/src/components/DiagnosticsPanel.jsx` and `.css` — component removed from App.jsx but files remain
- Safe to delete as cleanup

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

⚠️ **Debug logging in 3 files** (CLEANUP — added Mar 8 for investigation, can remove after fixes confirmed)
- `enhanced_matching.py`: `[UAT-DEBUG]` prefix in `search_uat_items()`
- `ado_integration.py`: `[TFT-DEBUG]` prefix in `search_tft_features()`
- `field-portal/api/routes.py`: `[UAT-ROUTE-DEBUG]` and `[TFT-ROUTE-DEBUG]` prefixes

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
**Latest commit**: `437bf75` — ENG-007: centralized config package (PR #1 squash-merged from ChrisKoenig)
**Previous**: `950abf3` — fix: B0002/B0003 bugs, ENG-004 retry logic, ENG-005 diagnostics, ENG-006 batch resilience
**Previous**: `b7cb0fd` — fix: field portal pre-prod deployment (12 issues)
**Previous**: `8114c35` — docs + code: comprehensive documentation and code comment updates

**Working tree**: Clean.

---

## Next Steps / TODO

### IMMEDIATE — Field Portal Flow Overhaul (Mar 9 Plan — Pending Sign-Off)
- [ ] **Phase 1**: Remove gateway dependency from search route — make Step 5 fast (5-10s target)
- [ ] **Phase 2**: Flow branching by category — deflect/feature-search/create-UAT paths
- [ ] **Phase 3**: Add missing guidance entries for all deflect categories
- [ ] Delete unused DiagnosticsPanel files from field-portal
- [ ] Remove debug logging (`[UAT-DEBUG]`, `[TFT-DEBUG]`, `[UAT-ROUTE-DEBUG]`, `[TFT-ROUTE-DEBUG]`) after fixes confirmed

### Field Submission Portal (Completed Items)
- [x] Build new React SPA for field personnel — `field-portal/ui/` on :3001
- [x] Replicate complete 9-step field flow
- [x] Category-specific guidance display
- [x] TFT Feature search + selection for feature_request category
- [x] Similar UAT search + selection (last 180 days)
- [x] UAT creation with all context
- [x] Quality scoring works independently (direct AIAnalyzer call)
- [x] Context analysis works independently (direct HybridContextAnalyzer call)
- [x] Auth reduced from 6 prompts to 1
- [x] Cosmos DB integration — evaluations + corrections
- [x] TFT search migrated from embeddings to keyword+SequenceMatcher (Mar 8)
- [x] UAT WIQL AND→OR fix (Mar 8)
- [x] Duplicate API call prevention with useRef guards (Mar 8)
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

**STATUS** (Mar 10, 2026): System is fully operational locally, deployed to Azure Container Apps (dev), AND deployed to **Azure App Service (pre-prod)**. Pre-prod: 4 App Services in `rg-nonprod-aitriage` — **BOTH Triage and Field Portal deployed and healthy**. Cosmos DB with 16 containers (added `apply-snapshots`), OpenAI (`openai-aitriage-nonprod`), Key Vault (`kv-aitriage`). MSAL auth via App Registration `GCS-Triage-NonProd`. Triage UI has 14 pages, **65 API endpoints**. **Mar 10 session**: FR-2056/B0011 — Production apply target switch, ProductionConfirmDialog two-step confirmation, bulk Apply All (batch endpoint), pre-apply snapshots in Cosmos, revert capability, ROBTAMS auto-tag. PERF — Analysis batch query optimized (N serial queries → single ARRAY_CONTAINS), asyncio.to_thread() wrappers for non-blocking FastAPI, Graph user TTL cache. Total: 10 files changed (8 modified + 2 new). **Merged to main (`c5178ac`) and deployment packages built** (triage-api.zip 0.5 MB, triage-ui.zip 0.9 MB). Ready for Cloud Shell deploy to pre-prod.

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
