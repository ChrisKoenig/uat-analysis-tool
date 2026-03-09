# Project Structure

This document describes the organization of the UAT Analysis Tool monorepo.

## Root Directory

```
uat-analysis-tool/
│
├── launcher.py                 # Desktop GUI for starting all services
├── api_gateway.py              # FastAPI API Gateway (central routing)
├── admin_service.py            # Flask admin microservice (port 8008)
├── server.js                   # Bundled Node.js Express server
├── start_dev.ps1               # Start all dev services
│
├── README.md                   # Project overview
├── QUICKSTART.md               # Get running in 5 minutes
├── .env.template               # Environment variable template
├── .env.azure.clean            # Azure env template (secrets removed)
│
├── api/                        # Flask API endpoint definitions
├── config/                     # Environment-specific configuration
├── data/                       # JSON data fixtures & reference data
├── docs/                       # All project documentation
├── scripts/                    # Admin, setup & migration scripts
├── tests/                      # Test suites
│
├── services/                   # Shared Python service modules (package)
├── agents/                     # Microservice agent containers
├── containers/                 # Dockerfile definitions for deployment
├── gateway/                    # API Gateway routing layer
├── infrastructure/             # Bicep IaC & deployment scripts
│
├── field-portal/               # Field Portal (frontend + API)
├── triage/                     # Triage backend (models, engines, services)
├── triage-ui/                  # Triage frontend (Vite + React)
│
├── cache/                      # Runtime cache files
```

## `services/` — Shared Python Services

A proper Python package containing all shared library modules. Imported
across the codebase by `api/`, `field-portal/`, `triage/`, `agents/`,
and the root entry points as `from services.<module> import ...`.

| Module | Purpose |
|--------|---------|
| `services/ai_config.py` | Centralized AI/OpenAI configuration |
| `services/ado_integration.py` | Azure DevOps REST API client |
| `services/blob_storage_helper.py` | Azure Blob Storage read/write |
| `services/cache_manager.py` | Smart cache with TTL |
| `services/embedding_service.py` | Azure OpenAI text embedding generation |
| `services/enhanced_matching.py` | Central orchestrator — AI + ADO matching |
| `services/graph_user_lookup.py` | Microsoft Graph user lookup |
| `services/hybrid_context_analyzer.py` | Hybrid pattern + LLM + vector analysis |
| `services/intelligent_context_analyzer.py` | Pattern-based 10-step analysis pipeline |
| `services/keyvault_config.py` | Azure Key Vault secret management |
| `services/llm_classifier.py` | GPT-4 classification with reasoning |
| `services/microservices_client.py` | HTTP client for microservice calls |
| `services/search_service.py` | Multi-source resource search |
| `services/servicetree_service.py` | ServiceTree BFF API integration |
| `services/shared_auth.py` | Azure credential singleton |
| `services/vector_search.py` | Semantic similarity search |
| `services/weight_tuner.py` | Pattern engine weight tuner |

## Key Subdirectories

### `api/` — API Endpoints
Flask blueprints for the field-portal API microservice:
- `uat_api.py` — UAT work item management
- `ado_api.py` — Azure DevOps operations
- `context_api.py` — AI context analysis
- `quality_api.py` — Quality evaluation
- `search_api.py` — Resource search

### `config/` — Environment Configuration
Per-environment Python config plus shell/JSON config files:
- `dev.py`, `preprod.py`, `prod.py` — Python environment configs
- `environments/` — Shell scripts and JSON per environment

### `data/` — Data Fixtures
JSON reference data used by analyzers:
- `retirements.json` — Microsoft service retirement database
- `corrections.json` — User feedback for corrective learning
- `issues_actions.json` — Issue-to-action mapping data
- `context_evaluations.json` — System analysis accuracy records

### `docs/` — Documentation
All project documentation (architecture, setup, operations, user guides).

### `scripts/` — Admin & Setup Scripts
One-off and administrative utilities:
- Key Vault configuration & migration scripts
- Azure identity & RBAC setup
- Cosmos DB firewall management
- Data migration tools

### `tests/` — Test Suites
- `test_end_to_end.py` — Integration tests across all microservices
- Triage-specific tests live in `triage/tests/`

### `agents/` — Microservice Agents
Containerized microservice wrappers for individual services:
- `context-analyzer/`, `embedding-service/`, `enhanced-matching/`
- `llm-classifier/`, `search-service/`, `uat-management/`, `vector-search/`

### `containers/` — Docker Build Configs
Dockerfiles and nginx configs for production deployment.

### `gateway/` — API Gateway Routes
FastAPI route handlers that proxy to microservices via HTTP.

### `infrastructure/` — Infrastructure as Code
- `bicep/` — Azure Bicep templates
- `deploy/` — Step-by-step deployment scripts
- `scripts/` — Infrastructure management utilities

### `field-portal/` — Field Portal Application
- `api/` — FastAPI backend (9-step field submission flow)
- `ui/` — Vite + React frontend

### `triage/` — Triage Management System
- `api/` — FastAPI routes (classify, admin, data management)
- `engines/` — Rules, routes, and trigger engines
- `models/` — Data models (actions, rules, routes, triggers)
- `services/` — Business logic (ADO client, audit, CRUD, evaluation)
- `config/` — Cosmos DB & logging configuration
- `tests/` — Triage-specific test suite

### `triage-ui/` — Triage Frontend
Vite + React frontend for the triage management portal.
