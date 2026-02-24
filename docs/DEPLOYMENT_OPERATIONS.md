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
3. Start the API — it auto-creates the database and all 8 containers

---

## Service Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Triage UI       │────▶│ Triage API      │────▶│ Cosmos DB    │
│ (port 3000)     │     │ (port 8009)     │     │ 8 containers │
└─────────────────┘     │ FastAPI/Uvicorn │     └──────────────┘
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

### API Won't Start

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

- **No PAT tokens** — uses Azure CLI / Interactive Browser credentials
- **Dual-org pattern** — production data is read-only; writes go to test org
- **No secrets in code** — configuration loaded from Azure Key Vault
- **CORS restricted** — only `localhost:3000` and `localhost:5003` allowed
- **Webhook validation** — payload structure validation (HMAC signing planned for production)
- **Soft delete** — entities are disabled by default, not permanently removed
- **Audit trail** — every mutation is logged with who/when/what
