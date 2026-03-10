# Developer Setup Guide

How to get the Triage Management System and Field Portal running locally.

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.13+ | Backend API |
| Node.js | 18+ | React frontend |
| Azure CLI | Latest | ADO authentication (`az login`) |
| Git | Latest | Version control |

Optional:
- **Cosmos DB Emulator** — for local persistent storage (without it, the system uses in-memory storage automatically)

---

## Clone & Install

```bash
git clone <repo-url>
cd uat-analysis-tool
```

### Backend Dependencies

```bash
# Triage API
pip install -r apps/triage/requirements.txt

# Field Portal API (shared deps, plus httpx)
pip install httpx
```

Key packages: `fastapi`, `uvicorn`, `azure-cosmos`, `azure-identity`, `azure-keyvault-secrets`, `pydantic`, `pytest`, `httpx`

### Frontend Dependencies

```bash
# Triage UI
cd apps/triage/ui
npm install
cd ../../..

# Field Portal UI
cd apps/field-portal/ui
npm install
cd ../../..
```

---

## Configuration

### Azure CLI Login

The system authenticates to Azure DevOps using your Azure CLI credentials:

```bash
az login
```

No PAT tokens are needed. The credential chain is:
1. `AzureCliCredential` (preferred)
2. `InteractiveBrowserCredential` (browser fallback)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Active non-secret config profile: `dev`, `preprod`, or `prod` |
| `TRIAGE_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `COSMOS_ENDPOINT` | _(none)_ | Cosmos DB endpoint URL. If not set, uses in-memory storage |

### Environment Profile Files

Configuration profiles are stored in:
- `shared/config/environments/dev.ps1`
- `shared/config/environments/preprod.ps1`
- `shared/config/environments/prod.ps1`

Inspect effective values for a profile:

```powershell
.\infra\scripts\show-config.ps1 -Env dev
```

Select a profile for local run:

```powershell
$env:APP_ENV="dev"
```

**In-memory mode** (no configuration needed): If `COSMOS_ENDPOINT` is not set, the system automatically uses an in-memory storage backend. All data lives in memory and is lost when the service stops — ideal for development and demos.

### Cosmos DB (Optional)

If you want persistent storage, set up Cosmos DB:

1. Create a Cosmos DB account (NoSQL API)
2. Store the endpoint URL in Azure Key Vault or set the `COSMOS_ENDPOINT` environment variable
3. The system auto-creates the database (`triage-management`) and all 13 containers on first startup

---

## Running the Application

### Start Triage API

```bash
python -m triage.triage_service
```

Or via uvicorn directly:

```bash
uvicorn triage.triage_service:app --port 8009 --reload
```

The API starts on **port 8009** with:
- Swagger UI: http://localhost:8009/docs
- Health check: http://localhost:8009/health

### Start Triage UI

```bash
cd apps/triage/ui
npm run dev
```

The React app starts on **port 3000** and proxies API calls to port 8009.

### Start Field Portal API

```bash
python -m uvicorn field-portal.api.main:app --host 0.0.0.0 --port 8010 --reload
```

The API starts on **port 8010** with:
- Swagger UI: http://localhost:8010/docs
- Health check: http://localhost:8010/health

### Start Field Portal UI

```bash
cd apps/field-portal/ui
npm run dev
```

The React app starts on **port 3001** and proxies API calls to port 8010.

### Start All (PowerShell)

```powershell
.\start_dev.ps1
```

---

## Project Structure

```
uat-analysis-tool/
├── apps/
│   ├── triage/                  # Triage Backend (Python package)
│   │   ├── api/                 #   FastAPI routes + Pydantic schemas
│   │   ├── config/              #   Configuration (Cosmos DB, logging)
│   │   ├── engines/             #   Core evaluation engines
│   │   ├── models/              #   Data models (dataclasses)
│   │   ├── services/            #   Business logic services
│   │   ├── tests/               #   Triage test suite (313+ tests)
│   │   ├── ui/                  #   Triage Frontend (React)
│   │   │   ├── src/
│   │   │   │   ├── pages/       #   14 page components
│   │   │   │   ├── components/  #   Shared UI components
│   │   │   │   └── api/triageApi.js  # API client
│   │   │   └── vite.config.js
│   │   └── requirements.txt     #   Python dependencies
│   │
│   └── field-portal/            # Field Portal
│       ├── api/                 #   FastAPI backend (9-step wizard)
│       │   ├── main.py          #   App entry, CORS, lifespan
│       │   ├── routes.py        #   All wizard API endpoints
│       │   └── cosmos_client.py #   Cosmos DB integration
│       └── ui/                  #   React SPA (9-step wizard)
│           ├── src/pages/       #   Wizard step components
│           └── vite.config.js
│
├── shared/                      # Shared Python library modules
│   ├── config/                  #   Environment-specific configuration
│   └── *.py                     #   17 shared modules (AI, ADO, KV, etc.)
│
├── services/                    # Microservice agents & gateway
├── infra/                       # Azure Bicep templates & deploy scripts
├── tests/                       # Root test suites (unit, integration, security)
├── docs/                        # Documentation
├── data/                        # JSON data fixtures
└── scripts/                     # Admin & setup scripts
```

---

## Verifying Your Setup

### Run Tests

```bash
# All tests (uses pyproject.toml config)
python -m pytest -q

# Triage tests only
python -m pytest apps/triage/tests/ -q
```

Expected: `313 passed` for triage tests (runs in ~2 seconds).

### Build Frontends

```bash
# Triage UI
cd apps/triage/ui
npx vite build

# Field Portal UI
cd apps/field-portal/ui
npx vite build
```

Expected: `76 modules transformed` with no errors.

### Check API Health

Start the backend, then:

```bash
curl http://localhost:8009/health
```

Expected: `{"status":"healthy","service":"triage-api","version":"1.0.0",...}`

---

## Development Tips

- **Debug logging**: Set `TRIAGE_LOG_LEVEL=DEBUG` to see every rule evaluation, trigger walk step, and engine decision
- **In-memory mode**: No Cosmos DB setup needed — the system auto-detects and uses in-memory storage
- **Hot reload**: Both `uvicorn --reload` and `npm run dev` support hot reload
- **Swagger UI**: Use http://localhost:8009/docs to test API endpoints interactively
- **Graceful degradation**: If Cosmos DB is unavailable, list endpoints return empty results instead of 500 errors
