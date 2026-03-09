<#
.SYNOPSIS
    Creates an Entra ID (Azure AD) App Registration for MSAL authentication.

.DESCRIPTION
    Creates a new app registration for the pre-prod GCS Triage system with:
      - SPA redirect URIs pointing to the 4 App Service URLs
      - API permission: Microsoft Graph User.Read
      - Outputs the client ID to use in 05-configure-appsettings.ps1

    Prerequisites:
      - 01-create-resources.ps1 has been run (App Service URLs needed)
      - You have Application Developer or Global Admin role in Entra ID

.NOTES
    Run from the repo root: .\infrastructure\deploy\04-create-app-registration.ps1
#>

[CmdletBinding()]
param(
    [switch]$WhatIf,
    [Parameter(Mandatory=$false)]
    [string]$ServiceTreeId
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

$APP_REG_NAME   = "GCS-Triage-NonProd"

# App Service names (from config — falls back for environments that don't define them)
$TRIAGE_UI      = if ($APP_SERVICES) { $APP_SERVICES | Where-Object { $_ -like "*triage-ui*" } | Select-Object -First 1 } else { "app-triage-ui-nonprod" }
$FIELD_UI       = if ($APP_SERVICES) { $APP_SERVICES | Where-Object { $_ -like "*field-ui*" }  | Select-Object -First 1 } else { "app-field-ui-nonprod" }

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
Write-Host "  GCS App Registration (MSAL)"           -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Host "   [ERROR] Wrong subscription. Run: az account set --subscription $SUBSCRIPTION" -ForegroundColor Red
    exit 1
}
Write-Ok "Subscription confirmed"

# Get App Service hostnames
Write-Step "Retrieving App Service URLs..."
$triageUiHost = az webapp show --name $TRIAGE_UI --resource-group $RG --query "defaultHostName" -o tsv 2>$null
$fieldUiHost  = az webapp show --name $FIELD_UI  --resource-group $RG --query "defaultHostName" -o tsv 2>$null

if (-not $triageUiHost -or -not $fieldUiHost) {
    Write-Host "   [ERROR] Could not find App Service URLs. Run 01-create-resources.ps1 first." -ForegroundColor Red
    exit 1
}

$redirectUris = @(
    "https://$triageUiHost",
    "https://$fieldUiHost",
    "http://localhost:3000",
    "http://localhost:3001"
)

Write-Ok "Redirect URIs:"
foreach ($uri in $redirectUris) {
    Write-Host "     $uri"
}

if ($WhatIf) {
    Write-Host "`n[WHATIF] Would create App Registration '$APP_REG_NAME' with:" -ForegroundColor Yellow
    Write-Host "  - SPA redirect URIs: $($redirectUris -join ', ')"
    Write-Host "  - API Permission: Microsoft Graph User.Read"
    exit 0
}

# =============================================================================
# Create App Registration
# =============================================================================
Write-Step "Checking if App Registration '$APP_REG_NAME' already exists..."
$existingApp = az ad app list --display-name $APP_REG_NAME --query "[0].appId" -o tsv 2>$null

if ($existingApp) {
    Write-Host "   App Registration already exists. Client ID: $existingApp" -ForegroundColor Yellow
    $appId = $existingApp
} else {
    Write-Step "Creating App Registration '$APP_REG_NAME'..."

    # Build the redirect URI JSON for SPA
    $redirectUriJson = $redirectUris | ForEach-Object { "`"$_`"" }
    $redirectUriArray = "[" + ($redirectUriJson -join ",") + "]"

    # Build az ad app create command
    $createArgs = @(
        "ad", "app", "create",
        "--display-name", $APP_REG_NAME,
        "--sign-in-audience", "AzureADMyOrg",
        "--web-redirect-uris"
    ) + $redirectUris + @("--output", "json")

    # Microsoft corporate tenant requires serviceManagementReference
    if ($ServiceTreeId) {
        $createArgs += @("--service-management-reference", $ServiceTreeId)
    }

    $appJson = az @createArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        if ($appJson -match 'ServiceManagementReference') {
            Write-Err "Microsoft corporate tenant requires a Service Tree ID."
            Write-Host "   Re-run with: .\04-create-app-registration.ps1 -ServiceTreeId <YOUR-SERVICE-TREE-GUID>" -ForegroundColor Yellow
            Write-Host "   Find your Service Tree ID at: https://servicetree.msftcloudes.com" -ForegroundColor Yellow
            throw "App Registration creation failed — Service Tree ID required."
        }
        Write-Err "App Registration creation failed"
        Write-Host $appJson -ForegroundColor Red
        throw "App Registration creation failed."
    }

    $app = $appJson | ConvertFrom-Json
    $appId = $app.appId
    $objectId = $app.id
    Write-Ok "App Registration created. Client ID: $appId"

    # Update to use SPA platform instead of web (for PKCE/implicit)
    Write-Step "Configuring SPA platform..."
    az ad app update `
        --id $objectId `
        --set spa.redirectUris=$redirectUriArray `
        --output none 2>$null
    Assert-AzSuccess "SPA redirect URI configuration"

    # Remove the web redirect URIs (we want SPA only)
    az ad app update `
        --id $objectId `
        --set web.redirectUris='[]' `
        --output none 2>$null

    Write-Ok "SPA platform configured"

    # Add Microsoft Graph User.Read permission (delegated)
    # Microsoft Graph appId: 00000003-0000-0000-c000-000000000000
    # User.Read permission ID: e1fe6dd8-ba31-4d61-89e7-88639da4683d
    Write-Step "Adding API permission: Microsoft Graph User.Read..."
    az ad app permission add `
        --id $objectId `
        --api 00000003-0000-0000-c000-000000000000 `
        --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope `
        --output none
    Assert-AzSuccess "User.Read permission addition"
    Write-Ok "User.Read permission added"

    # Grant admin consent
    Write-Step "Granting admin consent..."
    az ad app permission admin-consent --id $objectId --output none 2>$null
    Write-Ok "Admin consent granted (if you have permissions; otherwise ask a Global Admin)"
}

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  App Registration Complete"              -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "App Registration: $APP_REG_NAME"
Write-Host "Client ID:        $appId" -ForegroundColor White
Write-Host ""
Write-Host "IMPORTANT: Copy the Client ID above." -ForegroundColor Yellow
Write-Host "You will need it in the next step (05-configure-appsettings.ps1)." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Update the `$MSAL_CLIENT_ID variable in 05-configure-appsettings.ps1"
Write-Host "  before running it."
Write-Host ""
Write-Host "Next step: Run 05-configure-appsettings.ps1" -ForegroundColor Yellow
