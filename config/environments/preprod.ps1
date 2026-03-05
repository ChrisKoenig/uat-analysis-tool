# Pre-prod environment — PowerShell variables
# Dot-source this file at the top of any script that needs env-specific values:
#
#   . $PSScriptRoot\..\config\environments\preprod.ps1
#
# Or from the repo root:
#   . .\config\environments\preprod.ps1

$APP_ENV = "preprod"
$SUBSCRIPTION = "a1e66643-8021-4548-8e36-f08076057b6a"
$TENANT_ID = "16b3c013-d300-468d-ac64-7eda0820b6d3"
$RG = "rg-nonprod-aitriage"
$LOCATION = "northcentralus"

# Key Vault
$KV_NAME = "kv-aitriage"

# Cosmos DB
$COSMOS_ACCOUNT = "cosmos-aitriage-nonprod"
$COSMOS_DATABASE = "triage-management"

# Azure OpenAI
$OPENAI_ACCOUNT = "openai-aitriage-nonprod"
$OPENAI_CLASSIFICATION_DEPLOYMENT = "gpt-4o-standard"
$OPENAI_EMBEDDING_DEPLOYMENT = "text-embedding-3-large"

# Storage (set before running scripts if needed)
$STORAGE_ACCOUNT = ""
$STORAGE_CONTAINER = "gcs-data"

# App Services
$APP_SERVICES = @(
    "app-triage-api-nonprod",
    "app-field-api-nonprod",
    "app-triage-ui-nonprod",
    "app-field-ui-nonprod"
)

# Managed Identity
$MI_NAME = "TechRoB-Automation-DEV"
$MI_CLIENT_ID = "0fe9d340-a359-4849-8c0f-d3c9640017ee"
$MI_OBJECT_ID = "309baa86-f939-4fc3-ab3e-e2d3d0d4e475"

# Azure DevOps
$ADO_ORG = "unifiedactiontrackertest"
$ADO_PROJECT = "Unified Action Tracker Test"
$ADO_TFT_ORG = "acrblockers"

Write-Host "[config] Loaded preprod environment (sub: $SUBSCRIPTION, rg: $RG)" -ForegroundColor Yellow
