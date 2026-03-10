# Quick Start Guide — GCS Triage & Field Portal

Get up and running in under 5 minutes.

## Prerequisites

```powershell
python --version    # Python 3.12
node --version      # Node.js 20 LTS
npm --version       # npm 9+
```

### Install Dependencies
```powershell
pip install -r apps/triage/requirements.txt

cd apps\triage\ui && npm install && cd ..\..\..
cd apps\field-portal\ui && npm install && cd ..\..\..\
```

---

## Option 1: Desktop Launcher (Recommended)

```powershell
.\start_dev.ps1

# Or use the GUI launcher:
python launcher.py
```

The startup script (or launcher GUI) starts **Triage**, **Field Portal**, and other services. The launcher handles environment variables, port checks, and opens browsers automatically.

---

## Option 2: Manual Start — Triage System

### Terminal 1 — Triage API (port 8009)
```powershell
$env:COSMOS_ENDPOINT="https://cosmos-gcs-dev.documents.azure.com:443/"
$env:COSMOS_USE_AAD="true"
$env:COSMOS_TENANT_ID="16b3c013-d300-468d-ac64-7eda0820b6d3"
$env:PYTHONIOENCODING="utf-8"
python -m uvicorn triage.api.routes:app --host 0.0.0.0 --port 8009 --reload
```

### Terminal 2 — Triage UI (port 3000)
```powershell
cd apps\triage\ui
npm run dev
```

Open **http://localhost:3000** — Dashboard with health status, Queue, Rules, Corrections, etc.

---

## Option 3: Manual Start — Field Portal

### Terminal 1 — Field Portal API (port 8010)
```powershell
python -m uvicorn "field-portal.api.main:app" --host 0.0.0.0 --port 8010 --reload
```

### Terminal 2 — Field Portal UI (port 3001)
```powershell
cd apps\field-portal\ui
npm run dev
```

Open **http://localhost:3001** — 9-step issue submission wizard.  
API docs at **http://localhost:8010/docs**.

---

## Service Overview

| Service              | Port  | URL                          |
|----------------------|-------|------------------------------|
| **Triage UI**        | 3000  | http://localhost:3000         |
| **Triage API**       | 8009  | http://localhost:8009/health  |
| **Field Portal UI**  | 3001  | http://localhost:3001         |
| **Field Portal API** | 8010  | http://localhost:8010/docs    |
| **API Gateway**      | 8000  | http://localhost:8000/health  |

## Triage UI Pages

| Page | Description |
|------|-------------|
| Dashboard | Health status, component indicators |
| Queue | Work item queue with filters |
| Evaluate/Analyze | AI evaluation with history |
| Rules / Triggers / Actions / Routes | Configuration blade panels |
| Triage Teams | Team management |
| Corrections | Corrective learning CRUD (create, edit, delete) |
| Validation | Rule validation |
| Audit Log | Change history |
| Eval History | Historical evaluations |

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 8009 in use | `Get-Process python \| Stop-Process -Force` — wait 30s |
| Cosmos "AuthenticationFailed" | Check env vars: `COSMOS_ENDPOINT`, `COSMOS_USE_AAD`, `COSMOS_TENANT_ID` |
| AI returns pattern-only | Verify Azure OpenAI config — see [`AZURE_OPENAI_AUTH_SETUP.md`](docs/AZURE_OPENAI_AUTH_SETUP.md) |
| 6 login prompts | Fixed — uses AzureCliCredential + cached singletons |
| Azure CLI login fails (53003) | Use Cloud Shell instead — app uses InteractiveBrowserCredential |

---

For full details see [`PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

---

## Pre-Prod Deployment (App Service)

The pre-prod environment is already deployed. To redeploy after code changes:

### Build
```powershell
.\infra\deploy\build-packages.ps1 -Target triage-api
# Creates: infra\deploy\packages\triage-api.zip
```

### Deploy (from Cloud Shell — NOT local CLI)
```powershell
az account set -s a1e66643-8021-4548-8e36-f08076057b6a
az webapp deploy --resource-group rg-nonprod-aitriage \
  --name app-triage-api-nonprod --src-path ./triage-api.zip --type zip
```

### Pre-Prod URLs

| Service | URL |
|---------|-----|
| Triage UI | https://app-triage-ui-nonprod.azurewebsites.net |
| Triage API | https://app-triage-api-nonprod.azurewebsites.net/health |
| Field UI | https://app-field-ui-nonprod.azurewebsites.net |
| Field API | https://app-field-api-nonprod.azurewebsites.net/health |

> **Important**: All `az` commands for pre-prod must run in **Cloud Shell**.
> The local Azure CLI is authenticated to the dev tenant.

See [`DEPLOYMENT_OPERATIONS.md`](docs/DEPLOYMENT_OPERATIONS.md) for full App Service details.

**Last Updated**: March 2, 2026
