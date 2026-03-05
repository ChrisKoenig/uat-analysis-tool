# Dev environment — PowerShell variables
# Dot-source this file at the top of any script that needs env-specific values:
#
#   . $PSScriptRoot\..\config\environments\dev.ps1
#
# Or from the repo root:
#   . .\config\environments\dev.ps1

$APP_ENV = "dev"
$SUBSCRIPTION = "13267e8e-b8f0-41c3-ba3e-509b3c7c8482"
$TENANT_ID = "16b3c013-d300-468d-ac64-7eda0820b6d3"
$RG = "rg-gcs-dev"
$LOCATION = "northcentralus"

# Key Vault
$KV_NAME = "kv-gcs-dev-gg4a6y"

# Cosmos DB
$COSMOS_ACCOUNT = "cosmos-gcs-dev"
$COSMOS_DATABASE = "triage-management"

# Azure OpenAI
$OPENAI_ACCOUNT = "OpenAI-bp-NorthCentral"
$OPENAI_CLASSIFICATION_DEPLOYMENT = "gpt-4o-02"
$OPENAI_EMBEDDING_DEPLOYMENT = "text-embedding-3-large"

# Storage
$STORAGE_ACCOUNT = "stgcsdevgg4a6y"
$STORAGE_CONTAINER = "gcs-data"

# Container Apps
$ACR = "acrgcsdevgg4a6y"
$IDENTITY_NAME = "mi-gcs-dev"
$ENV_NAME = "cae-gcs-dev"

# Azure DevOps
$ADO_ORG = "unifiedactiontrackertest"
$ADO_PROJECT = "Unified Action Tracker Test"
$ADO_TFT_ORG = "acrblockers"

Write-Host "[config] Loaded dev environment (sub: $SUBSCRIPTION, rg: $RG)" -ForegroundColor Cyan
