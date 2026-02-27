<#
.SYNOPSIS
    Deploys application code to all 4 App Services.

.DESCRIPTION
    Builds and deploys:
      - Python APIs: zip deploys the project with requirements.txt
      - React UIs: runs npm build, then zip deploys the dist folder

    Prerequisites:
      - Scripts 01-05 have been run
      - Node.js and npm installed locally
      - Python installed locally

.NOTES
    Run from the repo root: .\infrastructure\deploy\06-deploy-code.ps1
#>

[CmdletBinding()]
param(
    [switch]$WhatIf,
    [ValidateSet("all", "triage-api", "field-api", "triage-ui", "field-ui")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

# =============================================================================
# Configuration
# =============================================================================
$SUBSCRIPTION   = "a1e66643-8021-4548-8e36-f08076057b6a"
$RG             = "rg-nonprod-aitriage"
$TRIAGE_API     = "app-triage-api-nonprod"
$FIELD_API      = "app-field-api-nonprod"
$TRIAGE_UI      = "app-triage-ui-nonprod"
$FIELD_UI       = "app-field-ui-nonprod"

# MSAL config for UI builds — UPDATE if different
$MSAL_CLIENT_ID = "6257f944-71eb-49b9-8ef6-ab006383d54c"
$MSAL_TENANT_ID = "72f988bf-86f1-41af-91ab-2d7cd011db47"

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

$repoRoot = $PSScriptRoot | Split-Path | Split-Path  # Up from infrastructure/deploy/

# =============================================================================
# Pre-flight
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GCS Code Deployment"                    -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($MSAL_CLIENT_ID -eq "<PASTE-CLIENT-ID-FROM-SCRIPT-04>") {
    Write-Host ""
    Write-Host "   [ERROR] Update `$MSAL_CLIENT_ID in this script first." -ForegroundColor Red
    exit 1
}

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Host "   [ERROR] Wrong subscription." -ForegroundColor Red
    exit 1
}
Write-Ok "Subscription confirmed"

# Get App Service URLs for config.json
$triageApiHost = az webapp show --name $TRIAGE_API --resource-group $RG --query "defaultHostName" -o tsv
$fieldApiHost  = az webapp show --name $FIELD_API  --resource-group $RG --query "defaultHostName" -o tsv
$triageUiHost  = az webapp show --name $TRIAGE_UI  --resource-group $RG --query "defaultHostName" -o tsv
$fieldUiHost   = az webapp show --name $FIELD_UI   --resource-group $RG --query "defaultHostName" -o tsv

# =============================================================================
# Deploy Triage API
# =============================================================================
if ($Target -eq "all" -or $Target -eq "triage-api") {
    Write-Step "Deploying Triage API..."

    if ($WhatIf) {
        Write-Host "   [WHATIF] Would zip deploy triage API code to $TRIAGE_API"
    } else {
        Push-Location $repoRoot
        try {
            # Create deployment package (exclude UI folders, __pycache__, etc.)
            $zipFile = Join-Path $env:TEMP "triage-api-deploy.zip"
            if (Test-Path $zipFile) { Remove-Item $zipFile }

            # Include: triage/, api/, root .py files, requirements.txt
            $includes = @(
                "triage/*", "api/*", "agents/*",
                "*.py", "requirements.txt",
                "keyvault_config.py", "ai_config.py", "ado_integration.py",
                "enhanced_matching.py", "shared_auth.py"
            )

            Compress-Archive -Path (
                Get-ChildItem -Path . -Include "triage","api","agents" -Directory |
                    ForEach-Object { $_.FullName }
            ) -DestinationPath $zipFile -Force

            # Also add root Python files and requirements
            Get-ChildItem -Path . -Filter "*.py" -File |
                Compress-Archive -DestinationPath $zipFile -Update
            Get-ChildItem -Path . -Filter "requirements*.txt" -File |
                Compress-Archive -DestinationPath $zipFile -Update

            az webapp deploy `
                --name $TRIAGE_API `
                --resource-group $RG `
                --src-path $zipFile `
                --type zip `
                --output none
            Assert-AzSuccess "Deploy Triage API"
            Write-Ok "Triage API deployed"
        } finally {
            Pop-Location
        }
    }
}

# =============================================================================
# Deploy Field Portal API
# =============================================================================
if ($Target -eq "all" -or $Target -eq "field-api") {
    Write-Step "Deploying Field Portal API..."

    if ($WhatIf) {
        Write-Host "   [WHATIF] Would zip deploy field portal API code to $FIELD_API"
    } else {
        Push-Location $repoRoot
        try {
            $zipFile = Join-Path $env:TEMP "field-api-deploy.zip"
            if (Test-Path $zipFile) { Remove-Item $zipFile }

            Compress-Archive -Path (
                Get-ChildItem -Path . -Include "field-portal","api","agents" -Directory |
                    ForEach-Object { $_.FullName }
            ) -DestinationPath $zipFile -Force

            Get-ChildItem -Path . -Filter "*.py" -File |
                Compress-Archive -DestinationPath $zipFile -Update
            Get-ChildItem -Path . -Filter "requirements*.txt" -File |
                Compress-Archive -DestinationPath $zipFile -Update

            az webapp deploy `
                --name $FIELD_API `
                --resource-group $RG `
                --src-path $zipFile `
                --type zip `
                --output none
            Assert-AzSuccess "Deploy Field Portal API"
            Write-Ok "Field Portal API deployed"
        } finally {
            Pop-Location
        }
    }
}

# =============================================================================
# Deploy Triage UI
# =============================================================================
if ($Target -eq "all" -or $Target -eq "triage-ui") {
    Write-Step "Building & deploying Triage UI..."

    if ($WhatIf) {
        Write-Host "   [WHATIF] Would build triage-ui and deploy dist to $TRIAGE_UI"
    } else {
        Push-Location (Join-Path $repoRoot "triage-ui")
        try {
            # Write runtime config.json into public/ before build
            $configJson = @{
                msal = @{
                    clientId    = $MSAL_CLIENT_ID
                    tenantId    = $MSAL_TENANT_ID
                    redirectUri = "https://$triageUiHost"
                }
                api = @{
                    baseUrl = "https://$triageApiHost"
                }
            } | ConvertTo-Json -Depth 3

            $configJson | Set-Content -Path "public/config.json" -Encoding UTF8

            npm ci --silent
            npm run build

            $zipFile = Join-Path $env:TEMP "triage-ui-deploy.zip"
            if (Test-Path $zipFile) { Remove-Item $zipFile }
            Compress-Archive -Path "dist/*" -DestinationPath $zipFile -Force

            az webapp deploy `
                --name $TRIAGE_UI `
                --resource-group $RG `
                --src-path $zipFile `
                --type zip `
                --output none
            Assert-AzSuccess "Deploy Triage UI"
            Write-Ok "Triage UI deployed"
        } finally {
            Pop-Location
        }
    }
}

# =============================================================================
# Deploy Field Portal UI
# =============================================================================
if ($Target -eq "all" -or $Target -eq "field-ui") {
    Write-Step "Building & deploying Field Portal UI..."

    if ($WhatIf) {
        Write-Host "   [WHATIF] Would build field-portal UI and deploy dist to $FIELD_UI"
    } else {
        Push-Location (Join-Path $repoRoot "field-portal" "ui")
        try {
            $configJson = @{
                msal = @{
                    clientId    = $MSAL_CLIENT_ID
                    tenantId    = $MSAL_TENANT_ID
                    redirectUri = "https://$fieldUiHost"
                }
                api = @{
                    baseUrl = "https://$fieldApiHost"
                }
            } | ConvertTo-Json -Depth 3

            $configJson | Set-Content -Path "public/config.json" -Encoding UTF8

            npm ci --silent
            npm run build

            $zipFile = Join-Path $env:TEMP "field-ui-deploy.zip"
            if (Test-Path $zipFile) { Remove-Item $zipFile }
            Compress-Archive -Path "dist/*" -DestinationPath $zipFile -Force

            az webapp deploy `
                --name $FIELD_UI `
                --resource-group $RG `
                --src-path $zipFile `
                --type zip `
                --output none
            Assert-AzSuccess "Deploy Field Portal UI"
            Write-Ok "Field Portal UI deployed"
        } finally {
            Pop-Location
        }
    }
}

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Code Deployment Complete"               -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Deployed apps:"
Write-Host "  Triage API:  https://$triageApiHost"
Write-Host "  Field API:   https://$fieldApiHost"
Write-Host "  Triage UI:   https://$triageUiHost"
Write-Host "  Field UI:    https://$fieldUiHost"
Write-Host ""
Write-Host "Test the deployment by visiting the UI URLs above." -ForegroundColor Yellow
