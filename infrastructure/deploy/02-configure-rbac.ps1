<#
.SYNOPSIS
    Assigns RBAC roles to the Managed Identity for all GCS resources.

.DESCRIPTION
    Grants TechRoB-Automation-DEV managed identity access to:
      - Cosmos DB (Built-in Data Contributor)
      - Azure OpenAI (Cognitive Services OpenAI User)
      - Key Vault (Key Vault Secrets User)
      - Assigns user-assigned MI to all 4 App Services

    Prerequisites:
      - 01-create-resources.ps1 has been run
      - You have Owner or User Access Administrator role on the resource group

.NOTES
    Run from the repo root: .\infrastructure\deploy\02-configure-rbac.ps1
#>

[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# =============================================================================
# Configuration
# =============================================================================
$SUBSCRIPTION   = "a1e66643-8021-4548-8e36-f08076057b6a"
$RG             = "rg-nonprod-aitriage"

# Managed Identity
$MI_NAME        = "TechRoB-Automation-DEV"
$MI_CLIENT_ID   = "0fe9d340-a359-4849-8c0f-d3c9640017ee"
$MI_OBJECT_ID   = "309baa86-f939-4fc3-ab3e-e2d3d0d4e475"

# Resources
$COSMOS_ACCOUNT = "cosmos-aitriage-nonprod"
$OPENAI_ACCOUNT = "openai-aitriage-nonprod"
$KV_NAME        = "kv-aitriage"

# App Services
$APP_SERVICES   = @(
    "app-triage-api-nonprod",
    "app-field-api-nonprod",
    "app-triage-ui-nonprod",
    "app-field-ui-nonprod"
)

# =============================================================================
# Helper
# =============================================================================
function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Skip($msg) { Write-Host "   [SKIP] $msg" -ForegroundColor Yellow }

# =============================================================================
# Pre-flight
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GCS RBAC Configuration"                -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Host "   [ERROR] Wrong subscription. Run: az account set --subscription $SUBSCRIPTION" -ForegroundColor Red
    exit 1
}
Write-Ok "Subscription confirmed"

if ($WhatIf) {
    Write-Host "`n[WHATIF] Would assign the following roles to MI '$MI_NAME':" -ForegroundColor Yellow
    Write-Host "  - Cosmos DB Built-in Data Contributor on $COSMOS_ACCOUNT"
    Write-Host "  - Cognitive Services OpenAI User on $OPENAI_ACCOUNT"
    Write-Host "  - Key Vault Secrets User on $KV_NAME"
    Write-Host "  - User-assigned MI on 4 App Services"
    exit 0
}

# =============================================================================
# Get resource IDs
# =============================================================================
Write-Step "Looking up resource IDs..."

$miResourceId = az identity show `
    --name $MI_NAME `
    --resource-group $RG `
    --query "id" -o tsv 2>$null

if (-not $miResourceId) {
    # MI might be in a different resource group — search subscription
    $miResourceId = az identity list `
        --query "[?name=='$MI_NAME'].id" -o tsv 2>$null
}
if (-not $miResourceId) {
    Write-Host "   [ERROR] Managed Identity '$MI_NAME' not found" -ForegroundColor Red
    exit 1
}
Write-Ok "MI Resource ID: $miResourceId"

$cosmosId = az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $RG --query "id" -o tsv
Write-Ok "Cosmos DB ID found"

$openaiId = az cognitiveservices account show --name $OPENAI_ACCOUNT --resource-group $RG --query "id" -o tsv
Write-Ok "OpenAI ID found"

$kvId = az keyvault show --name $KV_NAME --resource-group $RG --query "id" -o tsv 2>$null
if (-not $kvId) {
    # Key Vault might be in a different resource group
    $kvId = az keyvault show --name $KV_NAME --query "id" -o tsv 2>$null
}
if (-not $kvId) {
    Write-Host "   [ERROR] Key Vault '$KV_NAME' not found" -ForegroundColor Red
    exit 1
}
Write-Ok "Key Vault ID found"

# =============================================================================
# 1. Cosmos DB — Built-in Data Contributor
# =============================================================================
# Note: Cosmos DB RBAC uses its own role system, not standard Azure RBAC.
# The built-in "Cosmos DB Built-in Data Contributor" role definition ID is:
#   00000000-0000-0000-0000-000000000002
Write-Step "Assigning Cosmos DB Built-in Data Contributor to MI..."

$cosmosRoleExists = az cosmosdb sql role assignment list `
    --account-name $COSMOS_ACCOUNT `
    --resource-group $RG `
    --query "[?principalId=='$MI_OBJECT_ID']" -o json 2>$null | ConvertFrom-Json

if ($cosmosRoleExists -and $cosmosRoleExists.Count -gt 0) {
    Write-Skip "Cosmos DB role already assigned"
} else {
    az cosmosdb sql role assignment create `
        --account-name $COSMOS_ACCOUNT `
        --resource-group $RG `
        --role-definition-id "00000000-0000-0000-0000-000000000002" `
        --principal-id $MI_OBJECT_ID `
        --scope "/" `
        --output none
    Write-Ok "Cosmos DB Data Contributor role assigned"
}

# =============================================================================
# 2. Azure OpenAI — Cognitive Services OpenAI User
# =============================================================================
Write-Step "Assigning Cognitive Services OpenAI User to MI on OpenAI..."

az role assignment create `
    --assignee-object-id $MI_OBJECT_ID `
    --assignee-principal-type ServicePrincipal `
    --role "Cognitive Services OpenAI User" `
    --scope $openaiId `
    --output none 2>$null
Write-Ok "Cognitive Services OpenAI User role assigned"

# =============================================================================
# 3. Key Vault — Key Vault Secrets User
# =============================================================================
Write-Step "Assigning Key Vault Secrets User to MI on Key Vault..."

az role assignment create `
    --assignee-object-id $MI_OBJECT_ID `
    --assignee-principal-type ServicePrincipal `
    --role "Key Vault Secrets User" `
    --scope $kvId `
    --output none 2>$null
Write-Ok "Key Vault Secrets User role assigned"

# =============================================================================
# 4. Assign User-Assigned Managed Identity to App Services
# =============================================================================
Write-Step "Assigning MI to App Services..."

foreach ($appName in $APP_SERVICES) {
    Write-Host "   Assigning MI to $appName..." -NoNewline
    az webapp identity assign `
        --name $appName `
        --resource-group $RG `
        --identities $miResourceId `
        --output none 2>$null
    Write-Host " done" -ForegroundColor Green
}
Write-Ok "All App Services have MI assigned"

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  RBAC Configuration Complete"           -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Managed Identity '$MI_NAME' now has:"
Write-Host "  - Cosmos DB Built-in Data Contributor"
Write-Host "  - Cognitive Services OpenAI User"
Write-Host "  - Key Vault Secrets User"
Write-Host "  - Assigned to all 4 App Services"
Write-Host ""
Write-Host "Next step: Run 03-configure-keyvault.ps1" -ForegroundColor Yellow
