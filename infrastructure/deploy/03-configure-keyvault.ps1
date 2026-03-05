<#
.SYNOPSIS
    Populates Key Vault secrets for all GCS services.

.DESCRIPTION
    Sets secrets in the existing kv-aitriage Key Vault:
      - Cosmos DB endpoint (from deployed account)
      - Azure OpenAI endpoint + deployment names
      - App Insights instrumentation key + connection string
    
    Uses Managed Identity auth (no API keys stored for Cosmos or OpenAI).

    Prerequisites:
      - 01-create-resources.ps1 has been run
      - 02-configure-rbac.ps1 has been run (MI needs Key Vault Secrets Officer to write)
      - You have Key Vault Secrets Officer role on kv-aitriage

.NOTES
    Run from the repo root: .\infrastructure\deploy\03-configure-keyvault.ps1
#>

[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# =============================================================================
# Configuration — loaded from shared environment config file
# =============================================================================
$_env = if ($env:APP_ENV) { $env:APP_ENV } else { "preprod" }
$_configFile = Join-Path $PSScriptRoot "..\..\config\environments\$_env.ps1"
if (-not (Test-Path $_configFile)) {
    Write-Error "Environment config not found: $_configFile  (valid: dev, preprod, prod)"
    exit 1
}
. $_configFile

# =============================================================================
# Helper
# =============================================================================
function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "   [ERROR] $msg" -ForegroundColor Red }

function Assert-AzSuccess($stepName) {
    if ($LASTEXITCODE -ne 0) {
        Write-Err "$stepName failed (exit code: $LASTEXITCODE)"
        throw "$stepName failed. Fix the error above before continuing."
    }
}

# =============================================================================
# Pre-flight
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GCS Key Vault Secret Configuration"    -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Host "   [ERROR] Wrong subscription. Run: az account set --subscription $SUBSCRIPTION" -ForegroundColor Red
    exit 1
}
Write-Ok "Subscription confirmed"

# =============================================================================
# Retrieve dynamic values from deployed resources
# =============================================================================
Write-Step "Retrieving Cosmos DB endpoint..."
$cosmosEndpoint = az cosmosdb show `
    --name $COSMOS_ACCOUNT `
    --resource-group $RG `
    --query "documentEndpoint" -o tsv
Assert-AzSuccess "Cosmos DB endpoint retrieval"
Write-Ok "Cosmos: $cosmosEndpoint"

Write-Step "Retrieving Azure OpenAI endpoint..."
$oaiEndpoint = az cognitiveservices account show `
    --name $OPENAI_ACCOUNT `
    --resource-group $RG `
    --query "properties.endpoint" -o tsv
Assert-AzSuccess "OpenAI endpoint retrieval"
Write-Ok "OpenAI: $oaiEndpoint"

if ($WhatIf) {
    Write-Host "`n[WHATIF] Would set the following secrets in '$KV_NAME':" -ForegroundColor Yellow
    Write-Host "  COSMOS-ENDPOINT                          = $cosmosEndpoint"
    Write-Host "  AZURE-OPENAI-ENDPOINT                    = $oaiEndpoint"
    Write-Host "  AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT   = gpt-4o-standard"
    Write-Host "  AZURE-OPENAI-EMBEDDING-DEPLOYMENT        = text-embedding-3-large"
    Write-Host "  AZURE-OPENAI-USE-AAD                     = true"
    Write-Host "  azure-app-insights-instrumentation-key   = $APP_INSIGHTS_KEY"
    Write-Host "  azure-app-insights-connection-string      = $APP_INSIGHTS_CS"
    exit 0
}

# =============================================================================
# Set secrets
# =============================================================================
$secrets = @(
    @{ name = "COSMOS-ENDPOINT";                         value = $cosmosEndpoint }
    @{ name = "AZURE-OPENAI-ENDPOINT";                   value = $oaiEndpoint }
    @{ name = "AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT";  value = $OPENAI_CLASSIFICATION_DEPLOYMENT }
    @{ name = "AZURE-OPENAI-EMBEDDING-DEPLOYMENT";       value = $OPENAI_EMBEDDING_DEPLOYMENT }
    @{ name = "AZURE-OPENAI-USE-AAD";                    value = "true" }
    @{ name = "azure-app-insights-instrumentation-key";  value = $APP_INSIGHTS_KEY }
    @{ name = "azure-app-insights-connection-string";     value = $APP_INSIGHTS_CS }
)

foreach ($s in $secrets) {
    Write-Step "Setting secret '$($s.name)'..."
    az keyvault secret set `
        --vault-name $KV_NAME `
        --name $s.name `
        --value $s.value `
        --output none
    Assert-AzSuccess "Setting secret '$($s.name)'"
    Write-Ok "$($s.name) set"
}

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Key Vault Secrets Set"                  -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Secrets stored in '$KV_NAME':"
foreach ($s in $secrets) {
    Write-Host "  - $($s.name)"
}
Write-Host ""
Write-Host "Note: No COSMOS-KEY or AZURE-OPENAI-API-KEY stored."
Write-Host "      All auth uses Managed Identity (AAD tokens)."
Write-Host ""
Write-Host "Next step: Run 04-create-app-registration.ps1" -ForegroundColor Yellow
