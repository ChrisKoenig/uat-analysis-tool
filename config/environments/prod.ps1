# Production environment — PowerShell variables
# Dot-source this file at the top of any script that needs env-specific values:
#
#   . $PSScriptRoot\..\config\environments\prod.ps1
#
# All values are read from environment variables.  Set them in your shell or
# CI/CD pipeline before running any script.

$APP_ENV = "prod"

# Required — scripts will fail fast if these are not set
$SUBSCRIPTION = $env:AZURE_SUBSCRIPTION_ID
$TENANT_ID = $env:AZURE_TENANT_ID
$RG = $env:RESOURCE_GROUP
$KV_NAME = $env:KEY_VAULT_NAME
$COSMOS_ACCOUNT = $env:COSMOS_ACCOUNT
$OPENAI_ACCOUNT = $env:OPENAI_ACCOUNT
$STORAGE_ACCOUNT = $env:STORAGE_ACCOUNT

# Optional — sensible defaults
$LOCATION = if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION }  else { "northcentralus" }
$COSMOS_DATABASE = if ($env:COSMOS_DATABASE) { $env:COSMOS_DATABASE } else { "triage-management" }
$STORAGE_CONTAINER = if ($env:STORAGE_CONTAINER) { $env:STORAGE_CONTAINER } else { "gcs-data" }
$OPENAI_CLASSIFICATION_DEPLOYMENT = if ($env:AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT) { $env:AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT } else { "gpt-4o-standard" }
$OPENAI_EMBEDDING_DEPLOYMENT = if ($env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT) { $env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT }      else { "text-embedding-3-large" }
$ADO_ORG = $env:ADO_ORGANIZATION
$ADO_PROJECT = $env:ADO_PROJECT

# Validate required values
$missing = @()
if (-not $SUBSCRIPTION) { $missing += "AZURE_SUBSCRIPTION_ID" }
if (-not $TENANT_ID) { $missing += "AZURE_TENANT_ID" }
if (-not $RG) { $missing += "RESOURCE_GROUP" }
if (-not $KV_NAME) { $missing += "KEY_VAULT_NAME" }
if (-not $COSMOS_ACCOUNT) { $missing += "COSMOS_ACCOUNT" }
if (-not $OPENAI_ACCOUNT) { $missing += "OPENAI_ACCOUNT" }

if ($missing.Count -gt 0) {
    Write-Error "[config/prod] Missing required environment variables: $($missing -join ', ')"
    exit 1
}

Write-Host "[config] Loaded prod environment (sub: $SUBSCRIPTION, rg: $RG)" -ForegroundColor Green
