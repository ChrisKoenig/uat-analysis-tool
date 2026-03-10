# Project Structure

This document describes the organization of the UAT Analysis Tool monorepo.

## Root Directory

```
uat-analysis-tool/
│
├── launcher.py                 # Desktop GUI for starting all services
├── api_gateway.py              # FastAPI API Gateway (central routing)
├── admin_service.py            # Flask admin microservice (port 8008)
├── start_dev.ps1               # Start all dev services
│
├── README.md                   # Project overview
├── QUICKSTART.md               # Get running in 5 minutes
│
├── api/                        # Flask API endpoint definitions
│
├── apps/                       # Application frontends & backends
│   ├── field-portal/           #   Field Portal (api/ + ui/)
│   └── triage/                 #   Triage system (api/ + ui/ + engines/ + models/)
│
├── services/                   # Microservice containers & gateway
│   ├── context-analyzer/       #   Context analysis agent
│   ├── embedding-service/      #   Embedding generation agent
│   ├── enhanced-matching/      #   Enhanced matching agent
│   ├── gateway/                #   FastAPI API Gateway routing layer
│   ├── llm-classifier/         #   GPT-4 classification agent
│   ├── search-service/         #   Resource search agent
│   ├── uat-management/         #   UAT management agent
│   └── vector-search/          #   Semantic search agent
│
├── shared/                     # Shared Python service modules (package)
│   ├── config/                 #   Environment-specific configuration
│   └── *.py                    #   17 shared library modules
│
├── infra/                      # Infrastructure & deployment
│   ├── bicep/                  #   Azure Bicep IaC templates
│   ├── deploy/                 #   Step-by-step deployment scripts
│   ├── docker/                 #   Dockerfiles & nginx configs
│   └── scripts/                #   Infrastructure management utilities
│
├── tests/                      # Test suites
│   ├── unit/                   #   Unit tests
│   ├── integration/            #   Integration & end-to-end tests
│   └── security/               #   Security compliance tests (OWASP)
│
├── data/                       # JSON data fixtures & reference data
├── docs/                       # All project documentation
├── scripts/                    # Admin, setup & migration scripts
├── logs/                       # Application log files (gitignored)
```

## `shared/` — Shared Python Services

A proper Python package containing all shared library modules. Imported
across the codebase by `api/`, `apps/`, `services/`,
and the root entry points as `from shared.<module> import ...`.

| Module | Purpose |
|--------|---------|
| `shared/ai_config.py` | Centralized AI/OpenAI configuration |
| `shared/ado_integration.py` | Azure DevOps REST API client |
| `shared/blob_storage_helper.py` | Azure Blob Storage read/write |
| `shared/cache_manager.py` | Smart cache with TTL |
| `shared/embedding_service.py` | Azure OpenAI text embedding generation |
| `shared/enhanced_matching.py` | Central orchestrator — AI + ADO matching |
| `shared/graph_user_lookup.py` | Microsoft Graph user lookup |
| `shared/hybrid_context_analyzer.py` | Hybrid pattern + LLM + vector analysis |
| `shared/intelligent_context_analyzer.py` | Pattern-based 10-step analysis pipeline |
| `shared/keyvault_config.py` | Azure Key Vault secret management |
| `shared/llm_classifier.py` | GPT-4 classification with reasoning |
| `shared/microservices_client.py` | HTTP client for microservice calls |
| `shared/search_service.py` | Multi-source resource search |
| `shared/servicetree_service.py` | ServiceTree BFF API integration |
| `shared/shared_auth.py` | Azure credential singleton |
| `shared/vector_search.py` | Semantic similarity search |
| `shared/weight_tuner.py` | Pattern engine weight tuner |

## Key Subdirectories

### `api/` — API Endpoints
Flask blueprints for the field-portal API microservice:
- `uat_api.py` — UAT work item management
- `ado_api.py` — Azure DevOps operations
- `context_api.py` — AI context analysis
- `quality_api.py` — Quality evaluation
- `search_api.py` — Resource search

### `shared/config/` — Environment Configuration
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
- `unit/` — Unit tests
- `integration/` — Integration & end-to-end tests across all microservices
- `security/` — Security compliance tests (OWASP Top 10)
- Triage-specific tests live in `apps/triage/tests/`

### `services/` — Microservice Agents & Gateway
Containerized microservice wrappers and API gateway:
- `gateway/` — FastAPI route handlers that proxy to microservices
- `context-analyzer/`, `embedding-service/`, `enhanced-matching/`
- `llm-classifier/`, `search-service/`, `uat-management/`, `vector-search/`

### `infra/docker/` — Docker Build Configs
Dockerfiles and nginx configs for production deployment.

### `infra/` — Infrastructure as Code
- `bicep/` — Azure Bicep templates
- `deploy/` — Step-by-step deployment scripts & packaging
- `docker/` — Dockerfiles, nginx configs, container deploy script
- `scripts/` — Infrastructure management utilities (deploy, permissions, config)

### `apps/field-portal/` — Field Portal Application
- `api/` — FastAPI backend (9-step field submission flow)
- `ui/` — Vite + React frontend

### `apps/triage/` — Triage Management System
- `api/` — FastAPI routes (classify, admin, data management)
- `engines/` — Rules, routes, and trigger engines
- `models/` — Data models (actions, rules, routes, triggers)
- `services/` — Business logic (ADO client, audit, CRUD, evaluation)
- `config/` — Cosmos DB & logging configuration
- `tests/` — Triage-specific test suite

### `apps/triage/ui/` — Triage Frontend
Vite + React frontend for the triage management portal.

### `logs/` — Application Logs
Runtime log files (gitignored). Log paths default to `logs/` at project root.
