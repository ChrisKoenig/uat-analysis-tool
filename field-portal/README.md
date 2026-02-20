# Field Portal — React SPA + FastAPI Backend

A 9-step guided wizard for field personnel to submit issues, get AI-powered
quality analysis, search across Azure DevOps organizations, and create UAT work
items — all from a single-page React application backed by FastAPI.

## Architecture

```
┌─────────────────────┐        ┌─────────────────────┐
│  React SPA (Vite)   │  HTTP  │  FastAPI Backend     │
│  localhost:3001      ├───────►│  localhost:8010      │
│                     │        │                      │
│  MSAL auth (Entra)  │        │  Session state       │
│  9-step wizard      │        │  ADO integration     │
│  Lazy-loaded pages  │        │  Guidance rules      │
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
| 4    | `AnalysisPage`           | (reads session data)      | Review analysis results; apply corrections        |
| 5    | `SearchingPage`          | `POST /api/search`        | Search ADO for matching features (spinner page)   |
| 6    | `SearchResultsPage`      | (reads session data)      | Review search results; enter UAT IDs              |
| 7    | `UATInputPage`           | —                         | Enter specific UAT work-item IDs                  |
| 8    | `SearchingUATsPage`      | `POST /api/search-uats`   | Look up related UATs (spinner page)               |
| 8b   | `RelatedUATsPage`        | (reads session data)      | Select related UATs to link                        |
| 9    | `CreateUATPage`          | `POST /api/create-uat`    | Final confirmation & UAT work-item creation       |

Additional analysis detail is available via `AnalysisDetailPage`.

## Project Structure

```
field-portal/
├── api/                         # FastAPI backend (Python)
│   ├── main.py                  # App entry, lifespan, CORS middleware
│   ├── config.py                # Central configuration constants
│   ├── routes.py                # All 9-step API endpoints (~1 170 lines)
│   ├── models.py                # Pydantic request/response models (~350 lines)
│   ├── session_manager.py       # Thread-safe in-memory session store w/ TTL
│   ├── gateway_client.py        # Async HTTP client for gateway (:8000)
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

## Prerequisites

- **Python 3.10+** with `pip`
- **Node.js 18+** with `npm`
- Azure DevOps PAT tokens for UAT and TFT organizations
- Azure OpenAI endpoint + credentials (via KeyVault or env vars)
- Microservice gateway running on port 8000 (for quality/context/search)

## Quick Start

### 1. Install Python dependencies (from repo root)

```powershell
pip install fastapi uvicorn httpx pydantic azure-identity azure-keyvault-secrets
```

### 2. Install UI dependencies

```powershell
cd field-portal\ui
npm install
```

### 3. Start the microservice gateway (port 8000)

```powershell
cd C:\Projects\Hack
python api_gateway.py
```

### 4. Start the FastAPI backend (port 8010)

```powershell
cd C:\Projects\Hack
python -m uvicorn field-portal.api.main:app --host 0.0.0.0 --port 8010 --reload
```

### 5. Start the React dev server (port 3001)

```powershell
cd field-portal\ui
npm run dev
```

### 6. Open the app

Navigate to **http://localhost:3001** in your browser.

## Authentication (TODO)

The UI includes MSAL integration (`@azure/msal-browser` / `@azure/msal-react`)
configured for Entra ID app `2e7ef202-d148-4388-be40-651321742402`. The
`AuthGate` component handles login/logout, and `fieldApi.js` has a
`setTokenGetter()` hook for injecting bearer tokens into API calls.

**Current state:** `getToken()` returns `null` — bearer token validation on the
backend is not yet wired up. This is the next item on the roadmap.

## Configuration

All backend configuration lives in [`api/config.py`](api/config.py):

| Setting                     | Default | Description                                   |
|-----------------------------|---------|-----------------------------------------------|
| `API_GATEWAY_URL`           | `:8000` | Microservice gateway base URL                 |
| `FIELD_PORTAL_PORT`         | `8010`  | This API's port                               |
| `TEMP_STORAGE_TTL`          | `3600`  | Session expiry (seconds)                      |
| `QUALITY_BLOCK_THRESHOLD`   | `50`    | Quality score below this blocks submission    |
| `QUALITY_WARN_THRESHOLD`    | `80`    | Quality score below this shows warning        |
| `UAT_SEARCH_DAYS`           | `180`   | How far back to search for UATs               |
| `UAT_MAX_SELECTED`          | `5`     | Max related UATs a user can link              |
| `TFT_SIMILARITY_THRESHOLD`  | `0.6`   | Cosine-similarity cutoff for TFT features     |

## Archived UI

The original Flask/Jinja2 monolith UI has been archived to
`archive/old_flask_ui/` and is no longer used. It is kept for reference only.

## License

Internal use only — see organizational policies for Azure DevOps API usage and
data handling requirements.
