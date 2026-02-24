# GCS Intelligent Triage & Field Submission Platform

A dual-portal platform for field personnel issue submission (9-step wizard) and
corporate triage team management (rules, routing, AI classification).

> **Two separate UIs for two audiences:**
> - **Field Portal** ([`field-portal/`](field-portal/README.md)) — React SPA (port 3001) + FastAPI (port 8010) for field personnel
> - **Triage Admin** ([`triage-ui/`](triage-ui/)) — React SPA (port 3000) + FastAPI (port 8009) for the corporate triage team

## Quick Start

```powershell
# All-in-one GUI launcher (recommended)
python launcher.py
```

### Manual: Triage System
```powershell
# Terminal 1 — API (set env vars for Cosmos DB)
$env:COSMOS_ENDPOINT="https://cosmos-gcs-dev.documents.azure.com:443/"
$env:COSMOS_USE_AAD="true"
$env:COSMOS_TENANT_ID="16b3c013-d300-468d-ac64-7eda0820b6d3"
python -m uvicorn triage.api.routes:app --host 0.0.0.0 --port 8009 --reload

# Terminal 2 — Frontend
cd triage-ui && npm run dev
```

### Manual: Field Portal
```powershell
# Terminal 1 — API
python -m uvicorn "field-portal.api.main:app" --host 0.0.0.0 --port 8010 --reload

# Terminal 2 — UI
cd field-portal\ui && npm run dev
```

## Repository Layout

```
C:\Projects\Hack\
├── triage-ui/             # ★ Triage Admin UI (React + Vite, port 3000)
│   └── src/pages/         #   11 pages: Dashboard, Queue, Evaluate, Rules,
│                          #   Triggers, Actions, Routes, Teams, Validation,
│                          #   Audit Log, Eval History, Corrections
├── triage/                # ★ Triage API (FastAPI, port 8009)
│   ├── api/               #   Routes, admin routes, schemas
│   ├── config/            #   Cosmos DB config
│   ├── models/            #   Data models
│   └── services/          #   ADO client, CRUD service
│
├── field-portal/          # ★ Field Portal (React + FastAPI)
│   ├── api/               #   FastAPI backend (port 8010)
│   ├── ui/                #   React SPA (port 3001)
│   └── README.md          #   Full architecture & setup docs
│
├── containers/            # Docker deployment (Dockerfiles, nginx, deploy script)
├── api_gateway.py         # Microservice gateway (port 8000)
├── enhanced_matching.py   # AI analysis and matching engine
├── hybrid_context_analyzer.py  # Hybrid AI: pattern + LLM + vectors + corrections
├── ado_integration.py     # Azure DevOps API client (dual-org)
├── ai_config.py           # Azure OpenAI / KeyVault configuration
├── keyvault_config.py     # KeyVault helper utilities
├── launcher.py            # Desktop GUI launcher (tkinter)
├── corrections.json       # Corrective learning data
│
├── agents/                # AI agent experiments
├── admin-service/         # Admin dashboard microservice (port 8008)
├── archive/               # Archived code (old Flask UI, backups)
└── *.md                   # Project documentation
```

## Key Services

| Service              | Port  | Entry Point                                    |
|----------------------|-------|------------------------------------------------|
| **Triage UI**        | 3000  | `triage-ui/` (`npm run dev`)                   |
| **Triage API**       | 8009  | `triage/api/routes.py` (uvicorn)               |
| **Field Portal UI**  | 3001  | `field-portal/ui/` (`npm run dev`)             |
| **Field Portal API** | 8010  | `field-portal/api/main.py` (uvicorn)           |
| **API Gateway**      | 8000  | `api_gateway.py`                               |
| **Admin Service**    | 8008  | `admin-service/`                               |

## Triage Admin Pages (11)

| Page | Description |
|------|-------------|
| **Dashboard** | System health, status cards, component health indicators |
| **Queue** | Work item queue with caching and filters |
| **Evaluate/Analyze** | AI evaluation with history and detail views |
| **Rules** | Classification rule management (blade pattern) |
| **Triggers** | Event trigger configuration (blade pattern) |
| **Actions** | Action definitions (blade pattern) |
| **Routes** | Routing rules (blade pattern) |
| **Triage Teams** | Team management and assignment |
| **Validation** | Rule validation checks |
| **Audit Log** | Change history with filters and search |
| **Eval History** | Historical evaluation results |
| **Corrections** | Corrective learning CRUD (blade pattern with edit mode) |

## Field Portal Wizard Flow (9 Steps)

1. **Submit** — enter title, description, impact
2. **Quality Review** — AI scores input quality; user may revise
3. **Analyzing** — AI context analysis (spinner)
4. **Analysis** — review results, apply corrections
5. **Searching** — search ADO for matching features (spinner)
6. **Search Results** — review matches; enter UAT IDs
7. **UAT Input** — enter specific work-item IDs
8. **Related UATs** — look up & select related UATs
9. **Create UAT** — confirm and create work item in ADO

## Azure Container Apps Deployment

All 4 apps deployed to Azure Container Apps in `rg-gcs-dev` (North Central US):
- Triage UI / API — external + internal ingress
- Field UI / API — external + internal ingress
- Cosmos DB (AAD auth), ADO dual-org PAT, AI-Powered analysis enabled

See [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) and the Container Apps section in [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for details.

## Authentication

- **Cosmos DB**: AAD only (cross-tenant, `16b3c013-...` / fdpo tenant)
- **Azure OpenAI**: AAD only (Cognitive Services OpenAI User role)
- **Key Vault**: `kv-gcs-dev-gg4a6y` (DefaultAzureCredential)
- **ADO**: Dual PAT (test org write, production org read)
- **Field Portal MSAL**: Scaffolded but not yet enforced

## Documentation

| Document                                       | Description                        |
|------------------------------------------------|------------------------------------|
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md)           | Full project status & change log    |
| [`field-portal/README.md`](field-portal/README.md) | Field portal architecture & setup   |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)               | Microservices architecture overview  |
| [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) | Component inventory                  |
| [`QUICKSTART.md`](QUICKSTART.md)                   | Quick-start guide                    |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)         | Common issues & solutions            |
| [`AI_SETUP.md`](AI_SETUP.md)                       | Azure OpenAI configuration           |
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)       | Deployment procedures                |

## License

Internal use only — see organizational policies for Azure DevOps API usage and
data handling requirements.

---

**Last Updated**: February 2026  
**Version**: 5.0 (Dual React SPA + FastAPI + Cosmos DB + Azure Container Apps)  
**Compatibility**: Python 3.10+, Node.js 18+, Modern Browsers
