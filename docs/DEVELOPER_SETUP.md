# Developer Setup Guide

How to get the Triage Management System running locally.

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
cd Hack
```

### Backend Dependencies

```bash
pip install -r triage/requirements.txt
```

Key packages: `fastapi`, `uvicorn`, `azure-cosmos`, `azure-identity`, `azure-keyvault-secrets`, `pydantic`, `pytest`

### Frontend Dependencies

```bash
cd triage-ui
npm install
cd ..
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
| `TRIAGE_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `COSMOS_ENDPOINT` | _(none)_ | Cosmos DB endpoint URL. If not set, uses in-memory storage |

**In-memory mode** (no configuration needed): If `COSMOS_ENDPOINT` is not set, the system automatically uses an in-memory storage backend. All data lives in memory and is lost when the service stops — ideal for development and demos.

### Cosmos DB (Optional)

If you want persistent storage, set up Cosmos DB:

1. Create a Cosmos DB account (NoSQL API)
2. Store the endpoint URL in Azure Key Vault or set the `COSMOS_ENDPOINT` environment variable
3. The system auto-creates the database (`triage-management`) and all 8 containers on first startup

---

## Running the Application

### Start Backend API

```bash
python -m triage.triage_service
```

Or via uvicorn directly:

```bash
uvicorn triage.triage_service:app --port 8009 --reload
```

The API starts on **port 8009** with:
- Swagger UI: http://localhost:8009/docs
- ReDoc: http://localhost:8009/redoc
- Health check: http://localhost:8009/health

### Start Frontend

```bash
cd triage-ui
npm run dev
```

The React app starts on **port 3000** and proxies API calls to port 8009.

### Start Both (PowerShell)

```powershell
.\start_services.ps1
```

---

## Project Structure

```
Hack/
├── triage/                      # Backend Python package
│   ├── api/                     #   FastAPI routes + Pydantic schemas
│   │   ├── routes.py            #   All API endpoints
│   │   └── schemas.py           #   Request/response models
│   ├── config/                  #   Configuration
│   │   ├── cosmos_config.py     #   Cosmos DB connection + containers
│   │   ├── memory_store.py      #   In-memory fallback storage
│   │   └── logging_config.py    #   Centralized logging setup
│   ├── engines/                 #   Core evaluation engines
│   │   ├── rules_engine.py      #   Layer 1: Rule evaluation (16 operators)
│   │   ├── trigger_engine.py    #   Layer 2: Trigger walking (AND/OR/NOT)
│   │   └── routes_engine.py     #   Layer 3: Route action execution
│   ├── models/                  #   Data models (dataclasses)
│   │   ├── rule.py              #   Rule entity
│   │   ├── trigger.py           #   Trigger entity
│   │   ├── action.py            #   Action entity
│   │   ├── route.py             #   Route entity
│   │   ├── evaluation.py        #   Evaluation result
│   │   ├── analysis_result.py   #   Analysis engine output
│   │   ├── field_schema.py      #   ADO field definitions
│   │   └── audit_entry.py       #   Audit log record
│   ├── services/                #   Business logic services
│   │   ├── crud_service.py      #   Generic CRUD operations
│   │   ├── evaluation_service.py#   Evaluation pipeline orchestration
│   │   ├── audit_service.py     #   Audit trail logging
│   │   ├── ado_client.py        #   ADO API adapter (dual-org)
│   │   ├── ado_writer.py        #   ADO write operations
│   │   └── webhook_receiver.py  #   Service Hook processor
│   ├── tests/                   #   Test suite (313 tests)
│   ├── triage_service.py        #   Entry point (uvicorn startup)
│   └── requirements.txt         #   Python dependencies
│
├── triage-ui/                   # Frontend React application
│   ├── src/
│   │   ├── App.jsx              #   Root component + routing
│   │   ├── pages/               #   10 page components
│   │   ├── components/          #   Shared UI components
│   │   ├── api/triageApi.js     #   API client functions
│   │   └── utils/               #   Constants, helpers
│   ├── package.json
│   └── vite.config.js
│
├── docs/                        # Documentation
├── TRIAGE_SYSTEM_DESIGN.md      # System design document
└── keyvault_config.py           # Azure Key Vault configuration
```

---

## Verifying Your Setup

### Run Tests

```bash
python -m pytest triage/tests/ -q
```

Expected: `313 passed` (runs in ~2 seconds).

### Build Frontend

```bash
cd triage-ui
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
