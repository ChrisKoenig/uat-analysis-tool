# Quick Start Guide — GCS Triage & Field Portal

Get up and running in under 5 minutes.

## Prerequisites

```powershell
python --version    # Python 3.10+
node --version      # Node.js 18+
npm --version       # npm 9+
```

### Install Dependencies
```powershell
cd C:\Projects\Hack
pip install -r requirements-gateway.txt

cd triage-ui && npm install && cd ..
cd field-portal\ui && npm install && cd ..
```

---

## Option 1: Desktop Launcher (Recommended)

```powershell
python launcher.py
```

Click cards to start **Triage**, **Field Portal**, **Input** (legacy), or **Admin**. The launcher handles environment variables, port checks, and opens browsers automatically.

---

## Option 2: Manual Start — Triage System

### Terminal 1 — Triage API (port 8009)
```powershell
$env:COSMOS_ENDPOINT="https://cosmos-gcs-dev.documents.azure.com:443/"
$env:COSMOS_USE_AAD="true"
$env:COSMOS_TENANT_ID="16b3c013-d300-468d-ac64-7eda0820b6d3"
$env:PYTHONIOENCODING="utf-8"
cd C:\Projects\Hack
python -m uvicorn triage.api.routes:app --host 0.0.0.0 --port 8009 --reload
```

### Terminal 2 — Triage UI (port 3000)
```powershell
cd C:\Projects\Hack\triage-ui
npm run dev
```

Open **http://localhost:3000** — Dashboard with health status, Queue, Rules, Corrections, etc.

---

## Option 3: Manual Start — Field Portal

### Terminal 1 — Field Portal API (port 8010)
```powershell
cd C:\Projects\Hack
python -m uvicorn "field-portal.api.main:app" --host 0.0.0.0 --port 8010 --reload
```

### Terminal 2 — Field Portal UI (port 3001)
```powershell
cd C:\Projects\Hack\field-portal\ui
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
| AI returns pattern-only | Verify Azure OpenAI config — see [`AI_SETUP.md`](AI_SETUP.md) |
| 6 login prompts | Fixed — uses AzureCliCredential + cached singletons |
| Azure CLI login fails (53003) | Use Cloud Shell instead — app uses InteractiveBrowserCredential |

---

For full details see [`PROJECT_STATUS.md`](PROJECT_STATUS.md) and [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

**Last Updated**: February 2026
