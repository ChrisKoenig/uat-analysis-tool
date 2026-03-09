<#
.SYNOPSIS
    Configures App Service application settings (environment variables) for all 4 GCS apps.

.DESCRIPTION
    Sets environment variables on each App Service so the Python/Node apps can:
      - Authenticate via Managed Identity (AZURE_CLIENT_ID)
      - Read secrets from Key Vault (KEY_VAULT_NAME)
      - Connect to App Insights (connection string)
      - React UIs serve config.json with correct MSAL settings

    Prerequisites:
      - 01 through 04 scripts have been run
      - MSAL_CLIENT_ID below has been updated with the output from 04

.NOTES
    Run from the repo root: .\infrastructure\deploy\05-configure-appsettings.ps1
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
$_configFile = Join-Path $PSScriptRoot "..\..\shared\config\environments\$_env.ps1"
if (-not (Test-Path $_configFile)) {
    Write-Error "Environment config not found: $_configFile  (valid: dev, preprod, prod)"
    exit 1
}
. $_configFile

# App Service names (from config app_services list)
$TRIAGE_API = $APP_SERVICES | Where-Object { $_ -like "*triage-api*" } | Select-Object -First 1
$FIELD_API  = $APP_SERVICES | Where-Object { $_ -like "*field-api*" }  | Select-Object -First 1
$TRIAGE_UI  = $APP_SERVICES | Where-Object { $_ -like "*triage-ui*" } | Select-Object -First 1
$FIELD_UI   = $APP_SERVICES | Where-Object { $_ -like "*field-ui*" }  | Select-Object -First 1

# ADO organizations
$ADO_WRITE_ORG = $ADO_ORG
$ADO_READ_ORG  = "unifiedactiontracker"

# =============================================================================
# Helper
# =============================================================================
function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Assert-AzSuccess($stepName) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   [FAILED] $stepName (exit code $LASTEXITCODE)" -ForegroundColor Red
        throw "Step failed: $stepName"
    }
}

# =============================================================================
# Pre-flight
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GCS App Service Configuration"         -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($MSAL_CLIENT_ID -eq "<PASTE-CLIENT-ID-FROM-SCRIPT-04>") {
    Write-Host ""
    Write-Host "   [ERROR] You must update `$MSAL_CLIENT_ID with the Client ID" -ForegroundColor Red
    Write-Host "   from the output of 04-create-app-registration.ps1" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Host "   [ERROR] Wrong subscription. Run: az account set --subscription $SUBSCRIPTION" -ForegroundColor Red
    exit 1
}
Write-Ok "Subscription confirmed"

# Get App Service URLs for CORS and config
$triageApiHost = az webapp show --name $TRIAGE_API --resource-group $RG --query "defaultHostName" -o tsv
Assert-AzSuccess "Get $TRIAGE_API hostname"
$fieldApiHost  = az webapp show --name $FIELD_API  --resource-group $RG --query "defaultHostName" -o tsv
Assert-AzSuccess "Get $FIELD_API hostname"
$triageUiHost  = az webapp show --name $TRIAGE_UI  --resource-group $RG --query "defaultHostName" -o tsv
Assert-AzSuccess "Get $TRIAGE_UI hostname"
$fieldUiHost   = az webapp show --name $FIELD_UI   --resource-group $RG --query "defaultHostName" -o tsv
Assert-AzSuccess "Get $FIELD_UI hostname"

Write-Ok "App URLs retrieved"

if ($WhatIf) {
    Write-Host "`n[WHATIF] Would configure app settings for all 4 App Services" -ForegroundColor Yellow
    Write-Host "  AZURE_CLIENT_ID = $MI_CLIENT_ID"
    Write-Host "  KEY_VAULT_NAME  = $KV_NAME"
    Write-Host "  MSAL_CLIENT_ID  = $MSAL_CLIENT_ID"
    exit 0
}

# =============================================================================
# 1. Triage API settings
# =============================================================================
Write-Step "Configuring $TRIAGE_API..."
az webapp config appsettings set `
    --name $TRIAGE_API `
    --resource-group $RG `
    --settings `
        AZURE_CLIENT_ID=$MI_CLIENT_ID `
        KEY_VAULT_NAME=$KV_NAME `
        APPLICATIONINSIGHTS_CONNECTION_STRING=$APP_INSIGHTS_CS `
        ADO_ORGANIZATION=$ADO_WRITE_ORG `
        ADO_PROJECT=$ADO_PROJECT `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true `
        WEBSITES_PORT=8009 `
    --output none
Assert-AzSuccess "$TRIAGE_API app settings"
Write-Ok "$TRIAGE_API configured"

# Set startup command
az webapp config set `
    --name $TRIAGE_API `
    --resource-group $RG `
    --startup-file "gunicorn --bind 0.0.0.0:8009 --worker-class uvicorn.workers.UvicornWorker --timeout 120 triage.triage_service:app" `
    --output none
Assert-AzSuccess "$TRIAGE_API startup command"
Write-Ok "$TRIAGE_API startup command set"

# =============================================================================
# 2. Field Portal API settings
# =============================================================================
Write-Step "Configuring $FIELD_API..."
az webapp config appsettings set `
    --name $FIELD_API `
    --resource-group $RG `
    --settings `
        AZURE_CLIENT_ID=$MI_CLIENT_ID `
        KEY_VAULT_NAME=$KV_NAME `
        APPLICATIONINSIGHTS_CONNECTION_STRING=$APP_INSIGHTS_CS `
        ADO_ORGANIZATION=$ADO_WRITE_ORG `
        ADO_PROJECT=$ADO_PROJECT `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true `
        WEBSITES_PORT=8010 `
    --output none
Assert-AzSuccess "$FIELD_API app settings"
Write-Ok "$FIELD_API configured"

az webapp config set `
    --name $FIELD_API `
    --resource-group $RG `
    --startup-file "gunicorn --bind 0.0.0.0:8010 --worker-class uvicorn.workers.UvicornWorker --timeout 120 api.main:app" `
    --output none
Assert-AzSuccess "$FIELD_API startup command"
Write-Ok "$FIELD_API startup command set"

# =============================================================================
# 3. Triage UI settings
# =============================================================================
Write-Step "Configuring $TRIAGE_UI..."
az webapp config appsettings set `
    --name $TRIAGE_UI `
    --resource-group $RG `
    --settings `
        VITE_MSAL_CLIENT_ID=$MSAL_CLIENT_ID `
        VITE_MSAL_TENANT_ID=$MSAL_TENANT_ID `
        VITE_MSAL_REDIRECT_URI="https://$triageUiHost" `
        VITE_API_BASE_URL="https://$triageApiHost" `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true `
    --output none
Assert-AzSuccess "$TRIAGE_UI app settings"
Write-Ok "$TRIAGE_UI configured"

az webapp config set `
    --name $TRIAGE_UI `
    --resource-group $RG `
    --startup-file "npx serve -s dist -l 3000" `
    --output none
Assert-AzSuccess "$TRIAGE_UI startup command"
Write-Ok "$TRIAGE_UI startup command set"

# =============================================================================
# 4. Field Portal UI settings
# =============================================================================
Write-Step "Configuring $FIELD_UI..."
az webapp config appsettings set `
    --name $FIELD_UI `
    --resource-group $RG `
    --settings `
        VITE_MSAL_CLIENT_ID=$MSAL_CLIENT_ID `
        VITE_MSAL_TENANT_ID=$MSAL_TENANT_ID `
        VITE_MSAL_REDIRECT_URI="https://$fieldUiHost" `
        VITE_API_BASE_URL="https://$fieldApiHost" `
        SCM_DO_BUILD_DURING_DEPLOYMENT=true `
    --output none
Assert-AzSuccess "$FIELD_UI app settings"
Write-Ok "$FIELD_UI configured"

az webapp config set `
    --name $FIELD_UI `
    --resource-group $RG `
    --startup-file "npx serve -s dist -l 3001" `
    --output none
Assert-AzSuccess "$FIELD_UI startup command"
Write-Ok "$FIELD_UI startup command set"

# =============================================================================
# 5. CORS — allow UIs to call APIs
# =============================================================================
Write-Step "Configuring CORS on API services..."
az webapp cors add --name $TRIAGE_API --resource-group $RG `
    --allowed-origins "https://$triageUiHost" "http://localhost:3000" `
    --output none
Assert-AzSuccess "$TRIAGE_API CORS"
Write-Ok "$TRIAGE_API CORS set"

az webapp cors add --name $FIELD_API --resource-group $RG `
    --allowed-origins "https://$fieldUiHost" "http://localhost:3001" `
    --output none
Assert-AzSuccess "$FIELD_API CORS"
Write-Ok "$FIELD_API CORS set"

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  App Configuration Complete"             -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "All 4 App Services configured:"
Write-Host "  Triage API:  https://$triageApiHost"
Write-Host "  Field API:   https://$fieldApiHost"
Write-Host "  Triage UI:   https://$triageUiHost"
Write-Host "  Field UI:    https://$fieldUiHost"
Write-Host ""
Write-Host "MSAL Client ID: $MSAL_CLIENT_ID"
Write-Host "MI Client ID:   $MI_CLIENT_ID"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Deploy code to each App Service (zip deploy or CI/CD)"
Write-Host "  2. For React UIs: build locally, then deploy the 'dist' folder"
Write-Host "  3. Test authentication flow end-to-end"
