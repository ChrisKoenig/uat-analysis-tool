# Enhanced Issue Tracker System

A 9-step guided wizard for field personnel to submit issues, get AI-powered
quality analysis, search across Azure DevOps organizations, and create UAT work
items.

> **The active application is in [`field-portal/`](field-portal/README.md)** —
> a React SPA (Vite, port 3001) backed by a FastAPI API (port 8010) that
> delegates to a microservice gateway (port 8000).

## Quick Start

See the full setup instructions in [`field-portal/README.md`](field-portal/README.md).

```powershell
# 1. Gateway (port 8000)
python api_gateway.py

# 2. FastAPI backend (port 8010)
python -m uvicorn field-portal.api.main:app --host 0.0.0.0 --port 8010 --reload

# 3. React UI (port 3001)
cd field-portal\ui && npm run dev
```

## Repository Layout

```
C:\Projects\Hack\
├── field-portal/          # ★ Active application (React + FastAPI)
│   ├── api/               #   FastAPI backend (Python)
│   ├── ui/                #   React SPA (Vite + React 18)
│   └── README.md          #   Full architecture & setup docs
│
├── api_gateway.py         # Microservice gateway (port 8000)
├── enhanced_matching.py   # AI analysis and matching engine
├── ado_integration.py     # Azure DevOps API client
├── search_service.py      # Search and embedding services
├── ai_config.py           # Azure OpenAI / KeyVault configuration
├── keyvault_config.py     # KeyVault helper utilities
│
├── agents/                # AI agent experiments
├── admin-service/         # Admin dashboard microservice
│
├── archive/               # Archived code (old Flask UI, backups, phase summaries)
│   ├── old_flask_ui/      #   Original Flask/Jinja2 monolith
│   └── backup_*/          #   Historical snapshots
│
└── *.md                   # Project documentation
```

## Key Services

| Service              | Port  | Entry Point                        |
|----------------------|-------|------------------------------------|
| **React UI**         | 3001  | `field-portal/ui/` (`npm run dev`) |
| **Field Portal API** | 8010  | `field-portal/api/main.py`         |
| **Gateway**          | 8000  | `api_gateway.py`                   |
| **Admin Service**    | 8020  | `admin-service/`                   |

## Wizard Flow (9 Steps)

1. **Submit** — enter title, description, impact
2. **Quality Review** — AI scores input quality; user may revise
3. **Analyzing** — AI context analysis (spinner)
4. **Analysis** — review results, apply corrections
5. **Searching** — search ADO for matching features (spinner)
6. **Search Results** — review matches; enter UAT IDs
7. **UAT Input** — enter specific work-item IDs
8. **Related UATs** — look up & select related UATs
9. **Create UAT** — confirm and create work item in ADO

## Authentication (TODO)

MSAL auth for Entra ID is scaffolded in the React UI but not yet enforced.
Bearer token validation on the backend is the next planned feature.

## Documentation

| Document                                       | Description                        |
|------------------------------------------------|------------------------------------|
| [`field-portal/README.md`](field-portal/README.md) | Full architecture & setup guide |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)           | System architecture overview       |
| [`QUICKSTART.md`](QUICKSTART.md)               | Quick-start guide                  |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)     | Common issues & solutions          |
| [`AI_SETUP.md`](AI_SETUP.md)                   | Azure OpenAI configuration         |
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)   | Deployment procedures              |

## License

Internal use only — see organizational policies for Azure DevOps API usage and
data handling requirements.

---

**Last Updated**: February 2026  
**Version**: 4.0 (React SPA + FastAPI rewrite)  
**Compatibility**: Python 3.10+, Node.js 18+, Modern Browsers
