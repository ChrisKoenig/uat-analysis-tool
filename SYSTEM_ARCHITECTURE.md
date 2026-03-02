# GCS Platform — System Architecture

**Created**: February 11, 2026  
**Status**: Current as-built (not aspirational)  
**Purpose**: Single reference showing how every component connects

---

## Table of Contents

1. [What This System Does](#what-this-system-does)
2. [Full System Diagram](#full-system-diagram)
3. [Component Inventory](#component-inventory)
4. [End-to-End Data Flows](#end-to-end-data-flows)
5. [Authentication Architecture](#authentication-architecture)
6. [Azure Resource Map](#azure-resource-map)
7. [Codebase Layout](#codebase-layout)
8. [How to Start Everything](#how-to-start-everything)
9. [What's Built vs. Planned](#whats-built-vs-planned)

---

## What This System Does

The Global Customer Success (GCS) platform automates the analysis and triage of
Azure DevOps Action items. It takes incoming work items, classifies them using
AI + pattern matching, applies business rules to determine routing, and writes
the results back to ADO — with human review at the decision point.

**Three subsystems**, one platform:

| Subsystem | What It Does | Status |
|-----------|-------------|--------|
| **Input System** | Ad-hoc analysis via web form or Teams bot — user pastes title/description, gets classification | Built (legacy Flask app) |
| **Analysis Engine** | Hybrid AI classifier — pattern matching + GPT-4o + vector search + corrective learning | Built, shared by both systems |
| **Triage Management** | Queue-based batch processing — pull items from ADO, analyze, apply rules/triggers/routes, write back | Built (FastAPI + React) |

---

## Full System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                │
│                                                                             │
│  ┌──────────────────┐   ┌────────────────────────────────────────────────┐   │
│  │  Input Web App   │   │  Triage Management SPA                        │   │
│  │  Flask :5003     │   │  React + Vite :3000                           │   │
│  │                  │   │                                                │   │
│  │  - Quick ICA     │   │  - Dashboard        - Rules Admin             │   │
│  │  - Submit form   │   │  - Queue (ADO view)  - Actions Admin          │   │
│  │  - Results view  │   │  - Evaluate page     - Triggers Admin         │   │
│  │                  │   │  - Audit Log         - Routes Admin           │   │
│  │                  │   │  - Eval History      - Validation             │   │
│  └────────┬─────────┘   └──────────────────────┬─────────────────────────┘   │
│           │                                     │                            │
│  ┌────────┴─────────┐                           │                            │
│  │  Teams Bot       │                           │                            │
│  │  :3978           │                           │                            │
│  └────────┬─────────┘                           │                            │
└───────────┼─────────────────────────────────────┼────────────────────────────┘
            │                                     │
            ▼                                     ▼
┌───────────────────────┐          ┌──────────────────────────────────────────┐
│  API Gateway :8000    │          │  Triage API (FastAPI) :8009              │
│                       │          │                                          │
│  Routes to micro-     │          │  /api/v1/rules      CRUD                │
│  services by path     │          │  /api/v1/actions     CRUD                │
│                       │          │  /api/v1/triggers    CRUD                │
│  /analyze → :8001     │          │  /api/v1/routes      CRUD                │
│  /search  → :8002     │          │  /api/v1/evaluate    Run evaluation      │
│  /embed   → :8006     │          │  /api/v1/analyze     Run AI analysis     │
│  /vector  → :8007     │          │  /api/v1/ado/*       Queue, apply, state │
│                       │          │  /api/v1/audit       Audit log           │
│                       │          │  /api/v1/validation  Warnings            │
│                       │          │  /api/v1/classify    Standalone classify  │
│                       │          │  /api/v1/admin/*     Corrections, health  │
│                       │          │  /health             Health + Cosmos     │
└───────────┬───────────┘          └──────────┬───────────────────────────────┘
            │                                  │
            ▼                                  │
┌───────────────────────────────────┐          │
│  MICROSERVICES                    │          │
│                                   │          │
│  Context Analyzer  :8001          │          │
│  Search Service    :8002          │          │
│  Enhanced Matching :8003          │          │
│  UAT Management    :8004          │          │
│  LLM Classifier    :8005          │          │
│  Embedding Service :8006          │◀─────────┤ (shared Analysis Engine)
│  Vector Search     :8007          │          │
│  Admin Portal      :8008          │          │
└───────────┬───────────────────────┘          │
            │                                  │
            ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         SHARED ANALYSIS ENGINE                               │
│                                                                              │
│  ┌─────────────────────────┐   ┌──────────────────────┐                      │
│  │ hybrid_context_analyzer │   │ intelligent_context   │                      │
│  │                         │   │ _analyzer             │                      │
│  │  Orchestrates:          │   │                       │                      │
│  │  1. Pattern matching ───┼──▶│  IssueCategory enum   │                      │
│  │  2. Vector similarity   │   │  IntentType enum      │                      │
│  │  3. LLM classification  │   │  Pattern rules        │                      │
│  │  4. Corrective learning │   │  Product detection    │                      │
│  │                         │   │  Keyword extraction   │                      │
│  │  Falls back gracefully  │   └──────────────────────┘                      │
│  │  if AI unavailable      │                                                 │
│  └──────────┬──────────────┘   ┌──────────────────────┐                      │
│             │                  │ llm_classifier        │                      │
│             ├─────────────────▶│                       │                      │
│             │                  │  Azure OpenAI GPT-4o  │                      │
│             │                  │  AAD auth (tenant-    │                      │
│             │                  │  specific)            │                      │
│             │                  │  10s timeout          │                      │
│             │                  └──────────────────────┘                      │
│             │                  ┌──────────────────────┐                      │
│             └─────────────────▶│ embedding_service     │                      │
│                                │  text-embedding-3-    │                      │
│                                │  large (3072 dim)     │                      │
│                                └──────────────────────┘                      │
└──────────────────────────────────────────────────────────────────────────────┘
            │                                  │
            ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      TRIAGE ENGINES (deterministic)                          │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                    │
│  │ Rules Engine │───▶│ Trigger      │───▶│ Routes       │                    │
│  │              │    │ Engine       │    │ Engine       │                    │
│  │ 15 operators │    │              │    │              │                    │
│  │ Evaluates    │    │ AND/OR/NOT   │    │ 5 operations │                    │
│  │ field vs     │    │ combos       │    │ set, copy,   │                    │
│  │ value → T/F  │    │ Priority     │    │ append,      │                    │
│  │              │    │ ordered      │    │ template,    │                    │
│  │              │    │ 1st TRUE     │    │ set_computed  │                    │
│  │              │    │ wins         │    │              │                    │
│  └──────────────┘    └──────────────┘    └──────────────┘                    │
│                                                                              │
│  Location: triage/engines/                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
            │                                  │
            ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DATA & SERVICES LAYER                              │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Azure Cosmos DB  │  │ Azure Key Vault  │  │ Azure OpenAI     │            │
│  │ cosmos-gcs-dev   │  │ kv-gcs-dev-gg4a6y│  │ OpenAI-bp-       │            │
│  │ (serverless)     │  │ (dev)            │  │ NorthCentral     │            │
│  │                  │  │                  │  │ (dev)            │            │
│  │ PRE-PROD:        │  │ PRE-PROD:        │  │ PRE-PROD:        │            │
│  │ cosmos-aitriage- │  │ kv-aitriage      │  │ openai-aitriage- │            │
│  │ nonprod          │  │                  │  │ nonprod          │            │
│  │                  │  │ Secrets:         │  │                  │            │
│  │ DB: triage-      │  │ - OpenAI config  │  │ Deployments:     │            │
│  │   management     │  │ - ADO PAT        │  │ - gpt-4o-standard│            │
│  │                  │  │ - Storage keys   │  │ - text-embedding-│            │
│  │ 10 containers:   │  │ - App Insights   │  │   3-large        │            │
│  │ rules, actions,  │  │                  │  │                  │            │
│  │ triggers, routes,│  │ Auth: Default    │  │ Auth: AAD only   │            │
│  │ analysis-results,│  │ AzureCredential  │  │ (keys disabled)  │            │
│  │ audit-log,       │  │ (dev) / MI       │  │                  │            │
│  │ evaluations,     │  │ (pre-prod)       │  │                  │            │
│  │ queue-cache,     │  │                  │  │                  │            │
│  │ corrections,     │  │                  │  │                  │            │
│  │ field-schema     │  │                  │  │                  │            │
│  │                  │  │                  │  │                  │            │
│  │ Auth: AAD only   │  │                  │  │                  │            │
│  │ (keys disabled)  │  │                  │  │                  │            │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘            │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐            │
│  │ Azure DevOps     │  │ Azure DevOps     │  │ Local Cache      │            │
│  │ (READ)           │  │ (WRITE)          │  │                  │            │
│  │ unifiedaction-   │  │ unifiedaction-   │  │ cache/ai_cache/  │            │
│  │ tracker          │  │ trackertest      │  │ 7-day TTL        │            │
│  │                  │  │                  │  │ LLM responses    │            │
│  │ Production work  │  │ Safe test org    │  │ Embeddings       │            │
│  │ items source     │  │ for writes       │  │                  │            │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘            │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Inventory

### Port Map (all local development)

| Port | Service | Framework | Status |
|------|---------|-----------|--------|
| 3000 | Triage React UI | Vite + React | Built |
| 3978 | Teams Bot | Bot Framework | Built |
| 5003 | Input Web App | Flask | Built (legacy) |
| 8000 | API Gateway | FastAPI | Built |
| 8001 | Context Analyzer | Flask | Built |
| 8002 | Search Service | Flask | Built |
| 8003 | Enhanced Matching | Flask | Built |
| 8004 | UAT Management | Flask | Built |
| 8005 | LLM Classifier | Flask | Built |
| 8006 | Embedding Service | Flask | Built |
| 8007 | Vector Search | Flask | Built |
| 8008 | Admin Portal | Flask | Built |
| 8009 | Triage API | FastAPI + uvicorn | Built |

> **App Service (pre-prod):** The Triage API runs on port **8000** behind gunicorn
> (`gunicorn --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker`).
> Local development still uses port 8009.

### Shared Modules (no port — imported as libraries)

| Module | File | Used By |
|--------|------|---------|
| Hybrid Analyzer | `hybrid_context_analyzer.py` | Triage API, Input App |
| Pattern Analyzer | `intelligent_context_analyzer.py` | Hybrid Analyzer |
| LLM Classifier | `llm_classifier.py` | Hybrid Analyzer |
| Embedding Service | `embedding_service.py` | Hybrid Analyzer, Vector Search |
| ADO Client (root) | `ado_integration.py` | Input App, Admin Portal |
| ADO Client (triage) | `triage/services/ado_client.py` | Triage API (wraps root client) |
| Key Vault Config | `keyvault_config.py` | All services |
| AI Config | `ai_config.py` | LLM Classifier, Embedding Service |
| Cosmos Config | `triage/config/cosmos_config.py` | Triage API |
| Cache Manager | `cache_manager.py` | LLM Classifier |

### Triage Engines (deterministic logic, no AI)

| Engine | File | Purpose |
|--------|------|---------|
| Rules Engine | `triage/engines/rules_engine.py` | Evaluates atomic conditions (15 operators) |
| Trigger Engine | `triage/engines/trigger_engine.py` | Chains rules with AND/OR/NOT, priority-ordered |
| Routes Engine | `triage/engines/routes_engine.py` | Executes field changes (set, copy, append, template, set_computed) |

### Triage Services (business logic layer)

| Service | File | Purpose |
|---------|------|---------|
| CRUD Service | `triage/services/crud_service.py` | Generic Cosmos CRUD for all entity types |
| Evaluation Service | `triage/services/evaluation_service.py` | Orchestrates rules → triggers → routes |
| Audit Service | `triage/services/audit_service.py` | Logs all changes to audit-log container |
| ADO Writer | `triage/services/ado_writer.py` | Converts route output to ADO JSON Patch |
| Webhook Receiver | `triage/services/webhook_receiver.py` | Future: receive ADO webhook events |

### Triage Data Models

| Model | File | Cosmos Container |
|-------|------|-----------------|
| Rule | `triage/models/rule.py` | `rules` |
| Action | `triage/models/action.py` | `actions` |
| Trigger | `triage/models/trigger.py` | `triggers` |
| Route | `triage/models/route.py` | `routes` |
| Evaluation | `triage/models/evaluation.py` | `evaluations` |
| AnalysisResult | `triage/models/analysis_result.py` | `analysis-results` |
| AuditEntry | `triage/models/audit_entry.py` | `audit-log` |
| FieldSchema | `triage/models/field_schema.py` | `field-schema` |
| Correction | *(schema in cosmos_client.py)* | `corrections` |

> **Shared containers:** The `evaluations` container is written by both the
> triage system (`source: "triage"`) and the field portal (`source: "field-portal"`).
> The `corrections` container is written by the field portal and consumed by
> the fine-tuning engine.

### Frontend Pages (React)

| Page | File | Function |
|------|------|----------|
| Dashboard | `triage-ui/src/pages/Dashboard.jsx` | Overview stats, health indicator |
| Queue | `triage-ui/src/pages/QueuePage.jsx` | ADO work items, batch analyze |
| Evaluate | `triage-ui/src/pages/EvaluatePage.jsx` | Run triggers on items |
| Rules | `triage-ui/src/pages/RulesPage.jsx` | CRUD for rules |
| Actions | `triage-ui/src/pages/ActionsPage.jsx` | CRUD for actions |
| Triggers | `triage-ui/src/pages/TriggersPage.jsx` | CRUD for triggers |
| Routes | `triage-ui/src/pages/RoutesPage.jsx` | CRUD for routes |
| Validation | `triage-ui/src/pages/ValidationPage.jsx` | Check for broken refs |
| Audit Log | `triage-ui/src/pages/AuditPage.jsx` | Change history |
| Eval History | `triage-ui/src/pages/EvalHistoryPage.jsx` | Past evaluation results |
| Classify | `triage-ui/src/pages/ClassifyPage.jsx` | ~~Removed~~ — merged into Dashboard quick-classify |
| Corrections | `triage-ui/src/pages/CorrectionsPage.jsx` | Corrective learning management |
| Health | `triage-ui/src/pages/HealthPage.jsx` | ~~Removed~~ — health indicator integrated into Dashboard |

---

## End-to-End Data Flows

### Flow 1: Batch Analysis (Queue → Analyze → Cosmos)

This is the primary workflow — analyzing work items from the triage queue.

```
User clicks "Analyze Selected" in Queue page
         │
         ▼
React UI ──POST /api/v1/analyze {workItemIds: [698510, 698894, ...]}──▶ Triage API
         │
         ▼
Triage API fetches work items from ADO (READ org)
    ├── Single item: GET work item by ID
    └── Batch: POST _apis/wit/workitemsbatch (200-item chunks)
         │
         ▼
For each work item:
    ├── Strip HTML from description
    ├── Call hybrid_context_analyzer.analyze(title, description)
    │       │
    │       ├── 1. Pattern matching (always runs, fast)
    │       │       → IssueCategory enum, IntentType enum, confidence
    │       │
    │       ├── 2. Vector similarity search (find related issues)
    │       │       → Similar historical items
    │       │
    │       ├── 3. LLM classification (if AI available)
    │       │       → GPT-4o with pattern features as context
    │       │       → category, intent, confidence, reasoning
    │       │
    │       └── 4. Corrective learning (apply user corrections)
    │               → corrections.json hints in LLM prompt
    │
    ├── Map result to AnalysisResult dataclass
    │       → _enum_val() converts IssueCategory/IntentType to strings
    │
    ├── Store in Cosmos DB (analysis-results container)
    │       → to_dict() with recursive _sanitize() for enum safety
    │
    └── Return summary to frontend
         │
         ▼
React UI updates queue table (green dots = analyzed)
```

### Flow 2: Trigger Evaluation (Analyze → Rules → Route → ADO)

After analysis, the triage engines apply business rules.

```
User clicks "Evaluate" on an analyzed item
         │
         ▼
POST /api/v1/evaluate {workItemId, triggerIds?}
         │
         ▼
1. Fetch work item fields from ADO + analysis result from Cosmos
         │
         ▼
2. Rules Engine evaluates ALL rules against the combined data
   ├── Each rule: field + operator + value → True/False
   ├── 15 operators: equals, contains, is_null, greater_than, regex, etc.
   └── Store results: {rule_id: bool, ...}
         │
         ▼
3. Trigger Engine walks triggers in priority order
   ├── Each trigger: AND/OR/NOT expression referencing rule IDs
   ├── Uses stored T/F results (no re-evaluation)
   ├── First TRUE match wins → identifies the winning route
   └── If no match → "No Match" state (manual triage)
         │
         ▼
4. Routes Engine executes the winning route's actions
   ├── set:          Direct field assignment
   ├── set_computed:  Dynamic value (current_date, etc.)
   ├── copy:         Copy one field to another
   ├── append:       Append text to Discussion thread
   └── template:     Jinja-style string interpolation
         │
         ▼
5. ADO Writer converts field changes to JSON Patch
   └── PATCH to ADO (WRITE org) with revision check
         │
         ▼
6. Log evaluation result to Cosmos (evaluations container)
   └── Includes: all rule results, winning trigger, route applied, field changes
```

### Flow 3: Ad-Hoc Analysis (Input System, Legacy)

```
User pastes title + description into Flask web form (:5003)
    OR sends message to Teams bot (:3978)
         │
         ▼
Flask app calls hybrid_context_analyzer.analyze()
    (same engine as triage system)
         │
         ▼
Results displayed in web UI:
    - Category, Intent, Confidence
    - Business impact, Urgency
    - Detected products, Key concepts
    - Similar issues (if vector search available)
    - Category-specific guidance:
        ├── Feature Request → TFT Feature search
        ├── Technical Support → CSS guidance
        ├── Capacity → Capacity guidelines
        └── Cost/Billing → Out of scope message
```

### Flow 4: Field Portal Wizard → Cosmos + ADO

```
User completes 9-step wizard (React SPA :3001 → FastAPI :8010)
         │
Step 1-3 │ Submit → Quality check → AI analysis via gateway (:8000)
         │
Step 4   ▼ User reviews analysis, optionally corrects classification
         ├── store_correction() → Cosmos "corrections" container
         │   (consumed=false; fine-tuning engine reads these later)
         └── Legacy backup → corrections.json (local file)
         │
Step 5-8 │ Search ADO, select features/UATs
         │
Step 9   ▼ Create UAT work item in ADO
         ├── _build_evaluation_summary_html() → HTML summary
         ├── create_work_item_from_issue() → ADO (+ ChallengeDetails field)
         └── store_field_portal_evaluation() → Cosmos "evaluations" container
              └── source: "field-portal" (triage can detect & skip re-analysis)
```

---

## Authentication Architecture

All Azure resources use AAD authentication — no API keys anywhere.

### Environments

| Environment | Subscription | Resource Group | Auth Mechanism |
|-------------|-------------|----------------|----------------|
| **Dev (local)** | `13267e8e-b8f0-41c3-ba3e-569b3b7c8482` | `rg-gcs-dev` | InteractiveBrowserCredential (cross-tenant fdpo) |
| **Pre-Prod (App Service)** | `a1e66643-8021-4548-8e36-f08076057b6a` | `rg-nonprod-aitriage` | ManagedIdentityCredential (`TechRoB-Automation-DEV`) |

### Tenant Complexity (Dev Environment)

The user's corporate identity and the **dev** Azure resources live in **different tenants**:

| Tenant | ID | Contains |
|--------|----|----------|
| Microsoft Corp | `72f988bf-86f1-41af-91ab-2d7cd011db47` | User identity (Brad.Price@microsoft.com) |
| Microsoft Non-Production (fdpo) | `16b3c013-d300-468d-ac64-7eda0820b6d3` | Dev Azure resources (OpenAI, Cosmos, KV) |

> **Pre-prod** resources are in the Corp tenant (`72f988bf-...`), so Managed Identity
> works without cross-tenant complexity.

This cross-tenant setup requires tenant-specific credentials everywhere.

### Credential Strategy — Dev (Local)

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEV AUTHENTICATION FLOWS                      │
│                                                                  │
│  Key Vault (kv-gcs-dev-gg4a6y)                                  │
│  └── DefaultAzureCredential (works cross-tenant automatically)  │
│                                                                  │
│  Azure OpenAI (OpenAI-bp-NorthCentral)                          │
│  └── InteractiveBrowserCredential                               │
│      └── tenant_id = 16b3c013-... (fdpo)                       │
│      └── Role: Cognitive Services OpenAI User                   │
│                                                                  │
│  Cosmos DB (cosmos-gcs-dev)                                     │
│  └── ChainedTokenCredential                                     │
│      ├── SharedTokenCacheCredential (tenant_id = 16b3c013-...)  │
│      └── InteractiveBrowserCredential (tenant_id = 16b3c013-...) │
│      └── TokenCachePersistenceOptions(name="gcs-cosmos-auth")   │
│      └── Role: Cosmos DB Built-in Data Contributor              │
│                                                                  │
│  ADO — READ org (unifiedactiontracker)                          │
│  └── AzureCliCredential → InteractiveBrowserCredential fallback │
│      └── Scope: 499b84ac-1321-427f-aa17-267ca6975798            │
│      └── Cached in: AzureDevOpsConfig._cached_credential        │
│                                                                  │
│  ADO — TFT org (unifiedactiontracker/Technical Feedback)        │
│  └── InteractiveBrowserCredential                               │
│      └── tenant_id = microsoft.com                              │
│      └── Cached in: AzureDevOpsConfig._cached_tft_credential   │
└─────────────────────────────────────────────────────────────────┘
```

### Credential Strategy — Pre-Prod (App Service)

```
┌─────────────────────────────────────────────────────────────────┐
│                PRE-PROD AUTHENTICATION FLOWS                     │
│                                                                  │
│  Managed Identity: TechRoB-Automation-DEV                       │
│  └── Client ID: 0fe9d340-a359-4849-8c0f-d3c9640017ee           │
│  └── Set via AZURE_CLIENT_ID env var on each App Service        │
│                                                                  │
│  Key Vault (kv-aitriage)                                        │
│  └── ManagedIdentityCredential (via DefaultAzureCredential)     │
│      └── Role: Key Vault Secrets User                           │
│                                                                  │
│  Azure OpenAI (openai-aitriage-nonprod)                         │
│  └── ManagedIdentityCredential                                  │
│      └── Role: Cognitive Services OpenAI User                   │
│                                                                  │
│  Cosmos DB (cosmos-aitriage-nonprod)                            │
│  └── ManagedIdentityCredential                                  │
│      └── Role: Cosmos DB Built-in Data Contributor              │
│                                                                  │
│  ADO — READ & TFT orgs                                          │
│  └── ManagedIdentityCredential (via AZURE_CLIENT_ID fallback)  │
│      └── See ado_integration.py get_credential()                │
│                                                                  │
│  MSAL (triage-ui SPA)                                           │
│  └── App Registration: GCS-Triage-NonProd                       │
│      └── Client ID: 6257f944-71eb-49b9-8ef6-ab006383d54c       │
│      └── Authority: https://login.microsoftonline.com/          │
│          72f988bf-86f1-41af-91ab-2d7cd011db47                   │
└─────────────────────────────────────────────────────────────────┘
```

### Token Cache Persistence

Cosmos DB and OpenAI credentials use persistent disk caching to avoid
repeated browser prompts across restarts:
- Cache name: `gcs-cosmos-auth`
- Uses `TokenCachePersistenceOptions` from `azure.identity`
- First launch: browser prompt → token cached to disk
- Subsequent launches: silent token refresh from cache

### Constraint: No Azure CLI Locally

`az login` fails with Conditional Access error 53003. The system works
around this by using `InteractiveBrowserCredential` directly (not
`AzureCliCredential`). Cloud Shell can be used for `az` commands.

---

## Azure Resource Map

### Dev Environment

Subscription `13267e8e-b8f0-41c3-ba3e-569b3b7c8482` (fdpo tenant),
resource group `rg-gcs-dev`, North Central US.

| Resource | Type | Key Detail |
|----------|------|------------|
| `cosmos-gcs-dev` | Cosmos DB (NoSQL, serverless) | AAD-only, local auth disabled by policy |
| `kv-gcs-dev-gg4a6y` | Key Vault | Stores OpenAI config, ADO PAT, storage keys |
| `OpenAI-bp-NorthCentral` | Azure OpenAI | gpt-4o-standard + text-embedding-3-large |
| `mi-gcs-dev` | Managed Identity | For production deployment (not used locally) |

### Pre-Prod Environment (Feb 2026)

Subscription `a1e66643-8021-4548-8e36-f08076057b6a` (Corp tenant),
resource group `rg-nonprod-aitriage`, North Central US.

| Resource | Type | Key Detail |
|----------|------|------------|
| `cosmos-aitriage-nonprod` | Cosmos DB (NoSQL, serverless) | AAD-only, 10 containers |
| `kv-aitriage` | Key Vault | OpenAI, Cosmos, ADO secrets via MI |
| `openai-aitriage-nonprod` | Azure OpenAI | gpt-4o-standard + text-embedding-3-large |
| `TechRoB-Automation-DEV` | User-Assigned Managed Identity | Assigned to all 4 App Services |
| `app-triage-api-nonprod` | App Service (Python 3.12, B1) | Triage API — gunicorn + uvicorn |
| `app-triage-ui-nonprod` | App Service (Node 20, B1) | React SPA — pm2 + serve |
| `app-field-api-nonprod` | App Service (Python 3.12, B1) | Field API (future) |
| `app-field-ui-nonprod` | App Service (Node 20, B1) | Field Portal SPA (future) |
| `plan-aitriage-nonprod` | App Service Plan (B1) | Shared plan, 4 apps |
| `GCS-Triage-NonProd` | App Registration | MSAL SPA auth, redirect URIs configured |

### Cosmos DB Containers

Database: `triage-management`

| Container | Partition Key | Content |
|-----------|--------------|---------|
| `rules` | `/id` | Atomic conditions |
| `actions` | `/id` | Atomic field assignments |
| `triggers` | `/id` | Rule chains with route targets |
| `routes` | `/id` | Action collections |
| `analysis-results` | `/id` | AI classification output |
| `evaluations` | `/id` | Trigger evaluation history |
| `audit-log` | `/id` | Change tracking |
| `queue-cache` | `/id` | Cached queue data |
| `corrections` | `/id` | AI classification corrections (fine-tuning) |
| `field-schema` | `/id` | Field Portal schema definitions |

---

## Codebase Layout

```
C:\Projects\Hack\
│
├── SYSTEM_ARCHITECTURE.md        ← This file (holistic view)
├── TRIAGE_SYSTEM_DESIGN.md       ← Triage four-layer model detail
├── PROJECT_STATUS.md             ← Current state + troubleshooting
├── AZURE_OPENAI_AUTH_SETUP.md    ← OpenAI auth deep dive
│
├── launcher.py                   ← Desktop GUI launcher (tkinter)
│
├── ─── INPUT SYSTEM (legacy) ─────────────────────────
├── app.py                        ← Flask web app (:5003)
├── start_app.ps1                 ← Legacy startup script
├── admin_service.py              ← Admin portal (:8008)
│
├── ─── SHARED ANALYSIS ENGINE ────────────────────────
├── hybrid_context_analyzer.py    ← Orchestrator: pattern + AI + vectors
├── intelligent_context_analyzer.py ← Pattern matching, enums, detection
├── llm_classifier.py             ← Azure OpenAI GPT-4o classifier
├── embedding_service.py          ← text-embedding-3-large service
├── vector_search.py              ← Similarity search
├── cache_manager.py              ← LLM response caching (7-day TTL)
├── corrections.json              ← User feedback for corrective learning
│
├── ─── CONFIGURATION ─────────────────────────────────
├── keyvault_config.py            ← Key Vault integration
├── ai_config.py                  ← OpenAI settings (endpoint, deployment, use_aad)
├── ado_integration.py            ← ADO client (root, dual-org auth)
│
├── ─── TRIAGE MANAGEMENT SYSTEM ──────────────────────
├── triage/
│   ├── api/
│   │   ├── routes.py             ← FastAPI app, core triage endpoints (:8009)
│   │   ├── schemas.py            ← Pydantic request/response models
│   │   ├── classify_routes.py    ← Standalone classify API (new platform)
│   │   └── admin_routes.py       ← Corrections + health API (new platform)
│   ├── config/
│   │   └── cosmos_config.py      ← Cosmos DB connection + AAD auth
│   ├── engines/
│   │   ├── rules_engine.py       ← Evaluate rules → T/F
│   │   ├── trigger_engine.py     ← AND/OR/NOT priority walk
│   │   └── routes_engine.py      ← Execute field changes
│   ├── models/
│   │   ├── rule.py, action.py, trigger.py, route.py
│   │   ├── analysis_result.py    ← AnalysisResult with _sanitize()
│   │   ├── evaluation.py, audit_entry.py, field_schema.py
│   │   └── base.py               ← Base model utilities
│   ├── services/
│   │   ├── ado_client.py         ← Triage ADO adapter (wraps root)
│   │   ├── ado_writer.py         ← JSON Patch writer
│   │   ├── crud_service.py       ← Generic Cosmos CRUD
│   │   ├── evaluation_service.py ← Orchestrates engines
│   │   ├── audit_service.py      ← Change logger
│   │   └── webhook_receiver.py   ← Future: ADO webhooks
│   └── tests/
│
├── ─── TRIAGE FRONTEND ───────────────────────────────
├── triage-ui/
│   ├── src/
│   │   ├── pages/                ← 13 page components (10 triage + classify, corrections, health)
│   │   ├── components/           ← Shared UI components
│   │   ├── api/                  ← API client functions
│   │   ├── App.jsx               ← Router + layout
│   │   └── main.jsx              ← Entry point
│   ├── vite.config.js            ← Dev server config (proxy → 8009)
│   └── package.json
│
├── ─── MICROSERVICES ─────────────────────────────────
├── agents/
│   ├── context-analyzer/         ← :8001
│   ├── search-service/           ← :8002
│   ├── enhanced-matching/        ← :8003
│   ├── uat-management/           ← :8004
│   ├── llm-classifier/           ← :8005
│   ├── embedding-service/        ← :8006
│   └── vector-search/            ← :8007
├── api_gateway.py                ← :8000
│
├── ─── SUPPORTING FILES ──────────────────────────────
├── cache/ai_cache/               ← LLM response cache
├── issues_actions.json           ← Historical issue data
├── retirements.json              ← Product retirement data
├── context_evaluations.json      ← Evaluation benchmarks
└── __pycache__/
```

---

## How to Start Everything

### Option A: Desktop Launcher (recommended)

```powershell
python launcher.py
```

Presents a GUI with three cards. Click to start/stop:
- **Input Process**: Flask app on :5003
- **Admin Process**: Admin service on :8008
- **Triage Process**: API on :8009 + React on :3000

The launcher automatically:
- Checks Key Vault access on startup
- Sets Cosmos DB env vars for the Triage API
- Waits for HTTP readiness before opening browser
- Detects port conflicts (shows "Running (external)")
- Uses persistent token cache (no repeated auth prompts)

### Option B: Manual Start (Triage only)

```powershell
# Terminal 1 — Backend
$env:COSMOS_ENDPOINT = "https://cosmos-gcs-dev.documents.azure.com:443/"
$env:COSMOS_USE_AAD = "true"
$env:COSMOS_TENANT_ID = "16b3c013-d300-468d-ac64-7eda0820b6d3"
$env:PYTHONIOENCODING = "utf-8"
python -m uvicorn triage.api.routes:app --host 0.0.0.0 --port 8009 --reload

# Terminal 2 — Frontend
cd triage-ui
npm run dev
```

### Option C: Legacy Input System

```powershell
.\start_app.ps1
```

---

## What's Built vs. Planned

### Built and Working

| Component | Notes |
|-----------|-------|
| Triage API (FastAPI :8009) | Full CRUD, evaluate, analyze, ADO integration |
| React SPA (:3000) | 11 pages (ClassifyPage removed, HealthPage merged into Dashboard) |
| Cosmos DB persistence | 10 containers, AAD cross-tenant auth (dev) / MI auth (pre-prod) |
| Hybrid Analysis Engine | Pattern + LLM + vectors + corrections |
| Rules Engine (15 operators) | Full evaluation logic |
| Trigger Engine (AND/OR/NOT) | Priority-ordered, first-match-wins |
| Routes Engine (5 operations) | set, set_computed, copy, append, template |
| ADO Integration (dual-org) | READ from production, WRITE to test |
| Audit logging | All CRUD changes tracked |
| Desktop launcher | GUI with process management |
| Queue caching | Cached across navigation |
| Standalone Classify API | Decoupled from ADO — raw text in, classification out |
| Corrections management UI | CRUD for corrective learning entries |
| Health dashboard | Comprehensive component-by-component status |
| Input Web App (:5003) | Legacy Flask UI |
| Admin Portal (:8008) | Config management |
| 7 Microservices (:8001-8007) | Independently deployable |

### Deployed to Pre-Prod (Feb-Mar 2026)

| Component | Notes |
|-----------|-------|
| App Service deployment | 4 App Services on shared B1 plan — **all 4 healthy** |
| Triage API + UI | Deployed Feb 27, all health components GREEN |
| Field API + UI | Deployed Mar 2 after 12 fixes (commit `b7cb0fd`) |
| Managed Identity auth | `TechRoB-Automation-DEV` assigned to all services |
| Key Vault secrets | Cosmos, OpenAI, ADO config stored in `kv-aitriage` |
| MSAL SPA auth | `GCS-Triage-NonProd` app registration, Corp tenant |
| Pre-prod OpenAI | `openai-aitriage-nonprod` with MI-based AAD auth |
| Pre-prod Cosmos DB | `cosmos-aitriage-nonprod`, 10 containers, MI auth |

### Planned / Not Yet Built

| Component | Description |
|-----------|-------------|
| Webhook receiver | ADO pushes events → auto-analyze new items |
| Analytics dashboard | Trends, accuracy, volume metrics |
| Full automation mode | Trigger → route → ADO write without human review |
| Container deployment | Docker images for each service (alternative to App Service) |
| Classification tuning | Review accuracy, refine LLM prompt, add corrections |
| Copilot API plugin | Expose classify/search endpoints as Copilot agent skills |
| Legacy UI retirement | Migrate remaining Flask pages to React, retire :5003/:8008 |
| End-to-end pre-prod testing | Full 9-step field flow and triage workflow through App Services |
| Production environment | Prod subscription, prod RBAC, custom domain, TLS |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate Triage API** (FastAPI :8009) rather than extending Flask :5003 | Clean separation of concerns; FastAPI provides async, Pydantic validation, auto OpenAPI docs |
| **Four-layer model** (Rules → Triggers → Routes → Actions) | Maximum composability — admins can reconfigure routing without code changes |
| **AAD-only auth** (no API keys anywhere) | Azure Policy enforces this; also better security posture |
| **Cross-tenant credential chain** with persistent cache | Avoids repeated browser prompts; handles corp↔resource tenant mismatch |
| **Dual ADO orgs** (read production, write test) | Safe development — never accidentally modify production work items |
| **Cosmos DB serverless** | Cost-effective for dev/test; no provisioned RU overhead |
| **Shared Analysis Engine** (not duplicated) | Same hybrid analyzer used by both Input and Triage systems |
| **Engines not Agents** | Rules/Triggers/Routes are deterministic pipelines, not autonomous AI entities |
| **React SPA with Vite** | Fast dev experience, code splitting, clean component model |
| **Desktop launcher** (tkinter) | Simpler than managing multiple terminal windows manually |

---

*For detailed triage four-layer model design, see [TRIAGE_SYSTEM_DESIGN.md](TRIAGE_SYSTEM_DESIGN.md).*  
*For current operational status and troubleshooting, see [PROJECT_STATUS.md](PROJECT_STATUS.md).*  
*For Azure OpenAI auth deep dive, see [AZURE_OPENAI_AUTH_SETUP.md](AZURE_OPENAI_AUTH_SETUP.md).*
