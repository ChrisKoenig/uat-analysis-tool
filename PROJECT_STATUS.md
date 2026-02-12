# Project Status - Intelligent Context Analysis System
**Last Updated**: February 11, 2026
**Status**: ✅ All systems operational — Triage Management System with Cosmos DB, AI classification, desktop launcher

---

## System Overview

The project has two major subsystems:

1. **Input/Analysis System** — Flask-based web UI (port 5003) for ad-hoc ICA analysis, Teams bot, and microservices
2. **Triage Management System** — FastAPI + React SPA for queue-based work item triage with Cosmos DB persistence

Both share authentication infrastructure (Key Vault, Azure AD) and the hybrid analysis engine.

---

## Current Architecture

### Triage Management System (PRIMARY — active development)
- **Backend API**: FastAPI on port 8009 (uvicorn, `triage/api/routes.py`)
- **Frontend**: React + Vite on port 3000 (`triage-ui/`)
- **Database**: Azure Cosmos DB (`cosmos-gcs-dev`, serverless, North Central US)
- **Analysis Engine**: Hybrid pattern matching + LLM classification
- **Startup**: `python launcher.py` (GUI launcher) OR manual start

### Input/Analysis System (legacy)
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

### Containers (8 total, auto-created)
`analysis-results`, `queue-cache`, `triage-decisions`, `rules`, `routes`, `triggers`, `audit-log`, `evaluation-history`

### Key Limitation
- Azure CLI login fails locally (Conditional Access policy error 53003) — use Cloud Shell for `az` commands
- Database/container creation requires portal or Cloud Shell (RBAC data-plane role doesn't cover control-plane)

---

## Recent Changes (Feb 11, 2026) — Cosmos DB + Launcher + Serialization Fix

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

## Uncommitted Changes (as of Feb 11, 2026)

**Must commit these files:**
| File | Change |
|------|--------|
| `triage/config/cosmos_config.py` | Cross-tenant AAD auth, COSMOS_TENANT_ID, persistent token cache |
| `triage/models/analysis_result.py` | Recursive `_sanitize()` for Enum serialization |
| `triage/api/routes.py` | `_enum_val()` helper, cleaned up error handler |
| `keyvault_config.py` | COSMOS_ENDPOINT/COSMOS_KEY in SECRET_MAPPINGS |
| `launcher.py` | NEW — desktop GUI launcher |

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

### Legacy: Input System
```powershell
.\start_app.ps1
```

---

## Git Status

**Branch**: `main`
**Latest commit**: `739a5c5` — Remove Quick Actions section from Dashboard

**Recent commits** (newest first):
- `739a5c5` — Remove Quick Actions section from Dashboard
- `c462403` — Fix: health check hitting wrong URL
- `8d6da2c` — Fix: audit change details showing dashes instead of values
- `fc2e279` — Fix audit log: wire up action filter, fix API param mismatch
- `a0d469a` — Cache queue data across navigation

**Uncommitted**: cosmos_config.py, analysis_result.py, routes.py, keyvault_config.py, launcher.py (NEW)

---

## Next Steps / TODO

- [ ] Commit all uncommitted changes (Cosmos DB, serialization fix, launcher)
- [ ] Tune analysis classification accuracy (review categories, adjust LLM prompt)
- [ ] Add COSMOS_ENDPOINT secret to Key Vault (currently using env vars)
- [ ] Fix admin portal blob storage authorization
- [ ] Test managed identity (mi-gcs-dev) in Azure deployment
- [ ] Update launcher.py to also kill ghost processes on port before starting
- [ ] Add credential refresh logic for long sessions
- [ ] Document the full TFT search flow

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

**STATUS**: System is fully operational. Triage pipeline works end-to-end (ADO → analysis → Cosmos DB → React UI). Cosmos DB connected with AAD cross-tenant auth. Desktop launcher available. Uncommitted changes need to be committed.

**CRITICAL FILES FOR NEW SESSIONS**: Read this file + `AZURE_OPENAI_AUTH_SETUP.md` + `TRIAGE_SYSTEM_DESIGN.md`
