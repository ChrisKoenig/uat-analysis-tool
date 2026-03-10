# Field Portal — React SPA + FastAPI Backend

A 9-step guided wizard for field personnel to submit issues, get AI-powered
quality analysis, search across Azure DevOps organizations, and create UAT work
items — all from a single-page React application backed by FastAPI.

## Architecture

```
┌─────────────────────┐        ┌─────────────────────┐       ┌──────────────────┐
│  React SPA (Vite)   │  HTTP  │  FastAPI Backend     │       │  Azure Cosmos DB │
│  localhost:3001      ├───────►│  localhost:8010      ├──────►│  triage-mgmt DB  │
│                     │        │                      │       │                  │
│  MSAL auth (Entra)  │        │  Session state       │       │  evaluations     │
│  9-step wizard      │        │  ADO integration     │       │  corrections     │
│  Lazy-loaded pages  │        │  Cosmos DB client    │       └──────────────────┘
└─────────────────────┘        └──────────┬───────────┘
                                          │ HTTP
                                ┌─────────▼──────────┐
                                │ Microservice Gateway│
                                │ localhost:8000      │
                                │                     │
                                │ Quality analysis    │
                                │ Context analysis    │
                                │ Embedding service   │
                                │ Vector search       │
                                └─────────────────────┘
```

### Three Credential Domains

| Domain             | ADO Org                      | Tenant                                   |
|--------------------|------------------------------|------------------------------------------|
| Azure OpenAI       | —                            | `16b3c013-d300-468d-ac64-7eda0820b6d3`   |
| UAT (test org)     | `unifiedactiontrackertest`   | (default / no tenant override)           |
| TFT (prod org)     | `unifiedactiontracker`       | `72f988bf-86f1-41af-91ab-2d7cd011db47`   |

## 9-Step Wizard Flow

| Step | Page Component           | API Endpoint              | Description                                      |
|------|--------------------------|---------------------------|--------------------------------------------------|
| 1    | `SubmitPage`             | `POST /api/submit`        | User enters title, description, impact           |
| 2    | `QualityReviewPage`      | `POST /api/quality`       | AI scores input quality; user may revise          |
| 3    | `AnalyzingPage`          | `POST /api/analyze`       | AI context analysis (spinner page)                |
| 4    | `AnalysisPage`           | `POST /api/correct`       | Review analysis results; store corrections to Cosmos |
| 5    | `SearchingPage`          | `POST /api/search`        | Search ADO for matching features (spinner page)   |
| 6    | `SearchResultsPage`      | (reads session data)      | Review search results; enter UAT IDs              |
| 7    | `UATInputPage`           | —                         | Enter specific UAT work-item IDs                  |
| 8    | `SearchingUATsPage`      | `POST /api/search-uats`   | Look up related UATs (spinner page)               |
| 8b   | `RelatedUATsPage`        | (reads session data)      | Select related UATs to link                        |
| 9    | `CreateUATPage`          | `POST /api/create-uat`    | Create UAT + store evaluation in Cosmos DB        |

Additional analysis detail is available via `AnalysisDetailPage`.

## Project Structure

```
apps/field-portal/
├── api/                         # FastAPI backend (Python)
│   ├── main.py                  # App entry, lifespan, CORS middleware
│   ├── config.py                # Central configuration constants
│   ├── routes.py                # All 9-step API endpoints (~1 170 lines)
│   ├── models.py                # Pydantic request/response models (~350 lines)
│   ├── session_manager.py       # Thread-safe in-memory session store w/ TTL
│   ├── gateway_client.py        # Async HTTP client for gateway (:8000)
│   ├── cosmos_client.py         # Cosmos DB helpers (evaluations & corrections)
│   ├── guidance.py              # Category-specific guidance rules
│   └── ai_quality_evaluator.py  # AI quality evaluation helpers
│
├── ui/                          # React SPA (Vite + React 18)
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx             # ReactDOM entry, MSAL provider
│       ├── App.jsx              # BrowserRouter, AuthGate, lazy routes
│       ├── auth/
│       │   ├── authConfig.js    # MSAL configuration (Entra ID)
│       │   ├── AuthGate.jsx     # Login/logout wrapper
│       │   └── WizardContext.jsx # React context for wizard state
│       ├── api/
│       │   └── fieldApi.js      # API client (token injection, typed helpers)
│       ├── components/
│       │   ├── ProgressStepper.jsx
│       │   ├── LoadingSpinner.jsx
│       │   ├── ConfidenceBar.jsx
│       │   └── GuidanceBanner.jsx
│       ├── pages/               # One file per wizard step (see table above)
│       │   ├── SubmitPage.jsx
│       │   ├── QualityReviewPage.jsx
│       │   ├── AnalyzingPage.jsx
│       │   ├── AnalysisPage.jsx
│       │   ├── AnalysisDetailPage.jsx
│       │   ├── SearchingPage.jsx
│       │   ├── SearchResultsPage.jsx
│       │   ├── UATInputPage.jsx
│       │   ├── SearchingUATsPage.jsx
│       │   ├── RelatedUATsPage.jsx
│       │   └── CreateUATPage.jsx
│       └── styles/
│           └── global.css       # App-wide styles
│
└── cache/                       # Runtime cache (gitignored)
```

## Cosmos DB Integration

The field portal shares a Cosmos DB database (`triage-management`) with the
triage system so both systems can see each other's evaluations and corrections.

### Data Flow

| Event | Container | Purpose |
|-------|-----------|---------|
| Step 4 — user corrects AI classification | `corrections` | Stored for fine-tuning engine consumption |
| Step 9 — UAT work item created | `evaluations` | Triage system detects existing evaluation, skips re-analysis |
| Step 9 — ADO creation | ADO `ChallengeDetails` field | HTML summary of the AI evaluation written to the work item |

### Schema Compatibility

Field portal evaluations carry `source: "field-portal"` while triage evaluations
use `source: "triage"`. Both use `workItemId` as the partition key.

Triage-specific fields (`ruleResults`, `matchedTrigger`, `appliedRoute`, etc.)
are left empty in field portal documents — they are only populated by the triage
pipeline.

### Corrections & Fine-Tuning

The `corrections` container (partition key `/workItemId`) stores every user
correction made at Step 4. Each document includes:

- Original AI prediction (category, intent, confidence, etc.)
- User-supplied corrected values
- A `consumed: false` flag that the fine-tuning engine sets to `true` once processed

A legacy local `corrections.json` file is also written as a backup.

### Connection

The field portal reuses the triage system's `CosmosDBConfig` singleton
(`apps/triage/config/cosmos_config.py`) via the helper module `api/cosmos_client.py`.
AAD authentication (Entra ID) is used with the same tenant as the rest of the
system (`16b3c013-d300-468d-ac64-7eda0820b6d3`).

## Prerequisites

- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`
- Azure OpenAI endpoint + credentials (via Key Vault or env vars)
- Azure Cosmos DB access (AAD credentials with read/write on `triage-management` DB)

## Quick Start

### 1. Install Python dependencies (from repo root)

```powershell
pip install fastapi uvicorn httpx pydantic azure-identity azure-keyvault-secrets azure-cosmos
```

### 2. Install UI dependencies

```powershell
cd field-portal\ui
npm install
```

### 3. Start the FastAPI backend (port 8010)

```powershell
cd C:\Projects\Hack
python -m uvicorn field-portal.api.main:app --host 0.0.0.0 --port 8010 --reload
```

### 4. Start the React dev server (port 3001)

```powershell
cd field-portal\ui
npm run dev
```

### 5. Open the app

Navigate to **http://localhost:3001** in your browser.

## Authentication

The UI includes MSAL integration (`@azure/msal-browser` / `@azure/msal-react`)
configured for Entra ID app `2e7ef202-d148-4388-be40-651321742402`. The
`AuthGate` component handles login/logout, and `fieldApi.js` has a
`setTokenGetter()` hook for injecting bearer tokens into API calls.

**Current state:** `getToken()` returns `null` — bearer token validation on the
backend is not yet wired up. MSAL redirect flow causes re-auth prompts during
the wizard — see Known Issues in `PROJECT_STATUS.md`.

## Configuration

All backend configuration lives in [`api/config.py`](api/config.py):

| Setting                     | Default | Description                                   |
|-----------------------------|---------|-----------------------------------------------|
| `API_GATEWAY_URL`           | `http://localhost:8000` | API Gateway URL (fallback only — field portal calls engines directly) |
| `FIELD_PORTAL_PORT`         | `8010`  | This API's port                               |
| `TEMP_STORAGE_TTL`          | `3600`  | Session expiry (seconds)                      |
| `QUALITY_BLOCK_THRESHOLD`   | `50`    | Quality score below this blocks submission    |
| `QUALITY_WARN_THRESHOLD`    | `80`    | Quality score below this shows warning        |
| `UAT_SEARCH_DAYS`           | `180`   | How far back to search for UATs               |
| `UAT_MAX_SELECTED`          | `5`     | Max related UATs a user can link              |
| `TFT_SIMILARITY_THRESHOLD`  | `0.6`   | Cosine-similarity cutoff for TFT features     |

## Azure App Service Deployment (Pre-Prod)

Deployed Mar 2, 2026 to `rg-nonprod-aitriage` (subscription `a1e66643-...`).

| App Service | URL | Runtime |
|-------------|-----|--------|
| `app-field-api-nonprod` | https://app-field-api-nonprod.azurewebsites.net | Python 3.12, gunicorn+uvicorn on port 8000 |
| `app-field-ui-nonprod` | https://app-field-ui-nonprod.azurewebsites.net | Node 20, pm2+serve on port 8080 |

**Health check**: `GET /health` returns `{"status":"ok","components":{"gateway":"ok","key_vault":"ok","ai":"ok"}}`

**Auth**: Managed Identity (`TechRoB-Automation-DEV`, client ID `0fe9d340-...`) for Cosmos DB, Key Vault, and OpenAI.

### Build & Deploy
```powershell
# Build (from repo root)
.\infrastructure\deploy\build-packages.ps1 -Target field-api
.\infrastructure\deploy\build-packages.ps1 -Target field-ui

# Deploy (from Cloud Shell — NOT local CLI)
az account set -s a1e66643-8021-4548-8e36-f08076057b6a
az webapp deploy --resource-group rg-nonprod-aitriage --name app-field-api-nonprod --src-path ./field-api.zip --type zip
az webapp deploy --resource-group rg-nonprod-aitriage --name app-field-ui-nonprod --src-path ./field-ui.zip --type zip
```

See [`DEPLOYMENT_OPERATIONS.md`](../docs/DEPLOYMENT_OPERATIONS.md) for full details.

## License

Internal use only — see organizational policies for Azure DevOps API usage and
data handling requirements.
