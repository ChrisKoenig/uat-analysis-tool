# Deployment & Operations Guide

How to deploy, configure, and operate the Triage Management System.

---

## Deployment Options

### Local Development (Default)

No external services required. The system auto-detects the environment:

| Component | How to Start | Port |
|-----------|-------------|------|
| Triage API | `python -m triage.triage_service` | 8009 |
| Triage UI | `cd triage-ui && npm run dev` | 3000 |
| Field Portal API | `python -m uvicorn field-portal.api.main:app --port 8010` | 8010 |
| Field Portal UI | `cd field-portal/ui && npm run dev` | 3001 |
| Storage | In-memory (automatic when `COSMOS_ENDPOINT` is not set) | — |

### With Cosmos DB

For persistent storage:

1. Create an Azure Cosmos DB account (NoSQL API)
2. Add endpoint URL to Azure Key Vault (or set `COSMOS_ENDPOINT` env var)
3. Start the API — it auto-creates the database and all 10 containers

### Azure App Service (Pre-Prod)

Deployed Feb 2026. Four App Services on a shared B1 plan in `rg-nonprod-aitriage`.

#### Infrastructure

| App Service | Runtime | Port | Startup Command |
|-------------|---------|------|------------------|
| `app-triage-api-nonprod` | Python 3.12 | 8000 | `gunicorn --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker --timeout 300 --workers 1 triage.triage_service:app` |
| `app-triage-ui-nonprod` | Node 20 LTS | 8080 | `npx pm2 start npx -- -y serve -s /home/site/wwwroot/dist -l 8080 --no-clipboard` |
| `app-field-api-nonprod` | Python 3.12 | 8000 | (same pattern — pending startup fixes) |
| `app-field-ui-nonprod` | Node 20 LTS | 8080 | (same pattern as triage-ui) |

#### Build & Deploy

```powershell
# 1. Build deployment package (local machine)
.\infrastructure\deploy\build-packages.ps1 -Target triage-api

# 2. Upload zip to Cloud Shell (required — local CLI is dev tenant)
# Use Cloud Shell upload button or Azure Storage

# 3. Deploy from Cloud Shell
az webapp deploy --resource-group rg-nonprod-aitriage \
  --name app-triage-api-nonprod --src-path ./triage-api.zip --type zip
```

The build script copies `triage/`, `api/`, `agents/` directories plus 12 shared
root Python modules. It does NOT include `.env` files — all config comes from
App Settings and Key Vault.

#### Auth: Managed Identity

All services use `TechRoB-Automation-DEV` (client ID: `0fe9d340-a359-4849-8c0f-d3c9640017ee`):
- Set as user-assigned MI on each App Service
- `AZURE_CLIENT_ID` env var in App Settings
- Roles: Key Vault Secrets User, Cosmos DB Built-in Data Contributor, Cognitive Services OpenAI User

#### Key App Settings (Triage API)

| Setting | Value / Pattern |
|---------|-----------------|
| `AZURE_CLIENT_ID` | MI client ID |
| `AZURE_KEYVAULT_URL` | `https://kv-aitriage.vault.azure.net/` |
| `COSMOS_ENDPOINT` | `https://cosmos-aitriage-nonprod.documents.azure.com:443/` |
| `COSMOS_DATABASE` | `triage-management` |
| `COSMOS_USE_AAD` | `true` |
| `AZURE_OPENAI_ENDPOINT` | `https://openai-aitriage-nonprod.openai.azure.com/` |
| `AZURE_OPENAI_USE_AAD` | `true` |
| `ADO_USE_TOKEN` / `ADO_PAT_TOKEN` | PAT for ADO orgs |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` (runs `pip install`) |
| `WEBSITES_PORT` | `8000` |

#### Health Check

```
https://app-triage-api-nonprod.azurewebsites.net/admin/health
```

Returns component-by-component status: `cosmos_db`, `azure_openai`, `ado_connection`, `key_vault`, `rule_engine`, `analysis_engine`.

---

## Service Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌───────────────┐
│ Triage UI       │────▶│ Triage API      │────▶│ Cosmos DB     │
│ (port 3000)     │     │ (port 8009)     │     │ 10 containers │
└─────────────────┘     │ FastAPI/Uvicorn │     └───────────────┘
                        └────────┬────────┘
                                 │
┌─────────────────┐     ┌────────▼────────┐
│ Field Portal UI │────▶│ Field Portal API│
│ (port 3001)     │     │ (port 8010)     │
└─────────────────┘     └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │ Azure DevOps    │
                        │ (read/write)    │
                        └─────────────────┘

Pre-Prod (App Service):
┌─────────────────┐     ┌─────────────────┐     ┌───────────────┐
│ triage-ui       │────▶│ triage-api      │────▶│ Cosmos DB     │
│ (:443/8080)     │     │ (:443/8000)     │     │ cosmo-aitriage│
│ pm2 + serve     │     │ gunicorn+uvicorn│     │ -nonprod      │
└─────────────────┘     └────────┬────────┘     └───────────────┘
                                 │
                        ┌────────▼────────┐
                        │ Azure OpenAI    │
                        │ openai-aitriage │
                        │ -nonprod (MI)   │
                        └─────────────────┘
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRIAGE_LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `COSMOS_ENDPOINT` | _(none)_ | Cosmos DB endpoint. If unset, uses in-memory storage |

### Azure Key Vault

The system loads configuration from Azure Key Vault via `keyvault_config.py`. Key Vault is the preferred configuration source for:
- Cosmos DB endpoint and credentials
- Other sensitive configuration

Fallback: environment variables when Key Vault is unavailable.

### Cosmos DB Setup

**Database**: `triage-management`  
**Containers** (auto-created):

| Container | Partition Key | Description |
|-----------|---------------|-------------|
| `rules` | `/status` | Rule entities |
| `actions` | `/status` | Action entities |
| `triggers` | `/status` | Trigger entities |
| `routes` | `/status` | Route entities |
| `evaluations` | `/workItemId` | Evaluation results |
| `analysis-results` | `/workItemId` | Analysis output |
| `field-schema` | `/source` | ADO field definitions |
| `audit-log` | `/entityType` | Change history |

---

## Starting Services

### PowerShell (All Services)

```powershell
.\start_services.ps1
```

### Individual Services

```bash
# Triage Backend
python -m triage.triage_service

# Triage Frontend
cd triage-ui && npm run dev

# Field Portal Backend
python -m uvicorn field-portal.api.main:app --port 8010 --reload

# Field Portal Frontend
cd field-portal/ui && npm run dev

# Backend with debug logging
$env:TRIAGE_LOG_LEVEL = "DEBUG"
python -m triage.triage_service
```

### Verify Startup

```bash
# Triage API health check
curl http://localhost:8009/health

# Field Portal API health check
curl http://localhost:8010/health

# Swagger UIs
# Triage: http://localhost:8009/docs
# Field Portal: http://localhost:8010/docs

# Frontends
# Triage UI: http://localhost:3000
# Field Portal: http://localhost:3001
```

---

## Monitoring

### Logging

All logging goes through Python's standard `logging` module under the `triage` namespace:

| Logger | Component |
|--------|-----------|
| `triage.engines.rules` | Rules engine evaluation |
| `triage.engines.trigger` | Trigger engine walk |
| `triage.engines.routes` | Routes engine execution |
| `triage.services.eval` | Evaluation pipeline orchestration |
| `triage.services.crud` | CRUD operations |
| `triage.services.ado` | ADO API calls |
| `triage.services.audit` | Audit trail |
| `triage.services.webhook` | Webhook processing |
| `triage.api` | API request handling |
| `triage.config.cosmos` | Database connection |
| `triage.config.memory` | In-memory store operations |

**Log format**: `YYYY-MM-DD HH:MM:SS - logger.name - LEVEL - message`

### Debug Tracing

Set `TRIAGE_LOG_LEVEL=DEBUG` to see:
- Every rule evaluation (field, operator, value, result)
- Every trigger expression node evaluation
- Every action execution and field change computation
- Pipeline orchestration steps
- Cosmos DB queries and timing

### Health Endpoints

| Endpoint | What It Checks |
|----------|---------------|
| `GET /health` | API status + Cosmos DB connection |
| `GET /api/v1/ado/status` | ADO authentication + connectivity |

Health check returns `"degraded"` (not error) when Cosmos DB is unavailable — the API still responds, and list endpoints return empty results.

---

## Troubleshooting

### Local Development

#### API Won't Start

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: azure.cosmos` | Missing dependencies | `pip install -r triage/requirements.txt` |
| Port 8009 in use | Another service running | Stop conflicting process or change port |
| Key Vault errors | Not logged in | Run `az login` |

### ADO Connection Fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| 503 on evaluation | No Azure CLI credential | Run `az login` |
| 502 on queue query | ADO API error | Check `GET /api/v1/ado/status` |
| Empty queue results | Wrong state filter | Try without `?state=` filter |

### Evaluation Returns "No Match"

1. Check that rules exist and are `active`
2. Check that triggers reference those rules
3. Check trigger expressions match the work item data
4. Use `POST /api/v1/evaluate/test` for dry-run with debug logging
5. Set `TRIAGE_LOG_LEVEL=DEBUG` to see the trigger walk trace

### Optimistic Locking (409 Conflict)

### App Service (Pre-Prod)

| Symptom | Cause | Fix |
|---------|-------|-----|
| App stuck in "Stopped" state | Startup crash or timeout | Check Logs → Application logs; fix startup command; restart |
| `ModuleNotFoundError: gunicorn` | Missing from requirements.txt | Add `gunicorn==21.2.0` to `triage/requirements.txt` |
| `httpx.HTTPStatusError` on OpenAI calls | httpx 0.28+ breaks openai proxies | Pin `httpx>=0.25.0,<0.28.0` |
| AI shows "disabled" in health | Wrong OpenAI resource name in diagnostics | Fixed: dynamic extraction from endpoint URL (admin_routes.py) |
| `ValidationError: corrections_file` | corrections.json not in deployment zip | Fixed: removed file-system check from ai_config.py validate() |
| MSAL blank screen | Wrong client ID or hardcoded localhost URLs | Update authConfig.js client ID; use relative API paths in triageApi.js |
| ADO auth fails with MI | `ADO_MANAGED_IDENTITY_CLIENT_ID` not set | Code falls back to `AZURE_CLIENT_ID` env var |
| Cloud Shell `AuthorizationFailed` | Wrong subscription context | `az account set -s <subscription-id>` |
| Python 3.13 `pydantic-core` build fail | No pre-built wheel for 3.13 | Use Python 3.12 runtime |

> **Tip**: All pre-prod Azure operations must run from Cloud Shell — the local
> `az` CLI is authenticated to the dev tenant, not the pre-prod subscription.

### Optimistic Locking (409 Conflict)

The update was rejected because another edit changed the entity's version. Solution:
1. Re-fetch the entity to get the current version
2. Retry the update with the new version number

### Cosmos DB Unavailable

The system gracefully degrades:
- List endpoints return empty results (not 500)
- Create/update/delete return 500 with clear error message
- Health check returns `status: "degraded"`
- In-memory mode requires no Cosmos DB at all

---

## Backup & Recovery

### In-Memory Mode

Data is ephemeral — lost on service restart. Suitable for development only.

### Cosmos DB Mode

Data is persisted in Azure Cosmos DB:
- Azure handles replication and backups
- Configure backup policy in Azure Portal
- Point-in-time restore available (depends on Cosmos DB tier)

---

## Security Considerations

- **No PAT tokens in code** — uses Azure CLI / Interactive Browser credentials (dev), Managed Identity (pre-prod)
- **Key Vault** — all secrets in `kv-gcs-dev-gg4a6y` (dev) / `kv-aitriage` (pre-prod)
- **Dual-org pattern** — production data is read-only; writes go to test org
- **No secrets in code** — configuration loaded from Azure Key Vault
- **CORS restricted** — only `localhost:3000` and `localhost:5003` allowed
- **Webhook validation** — payload structure validation (HMAC signing planned for production)
- **Soft delete** — entities are disabled by default, not permanently removed
- **Audit trail** — every mutation is logged with who/when/what
