<#
.SYNOPSIS
    One-stop setup for chkoenig's dev environment: firewalls + Key Vault secrets.

.DESCRIPTION
    Performs three steps in order:
      1. Ensures your public IP is in the Cosmos DB firewall
      2. Ensures your public IP is in the Key Vault firewall
      3. Populates Key Vault secrets (Cosmos endpoint, OpenAI, App Insights)

    All endpoints are retrieved dynamically from the deployed Azure resources.
    Uses AAD auth throughout — no API keys stored.

    Prerequisites:
      - Azure CLI (az) logged in
      - Subscription f23858ca-... selected (or script will tell you)
      - Key Vault Secrets Officer role on kv-gcs-dev-6wo7gxoupztdm

.NOTES
    Run from the repo root:  .\chkoenig-configure.ps1
    Preview mode:            .\chkoenig-configure.ps1 -WhatIf
#>

[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# =============================================================================
# Configuration
# =============================================================================
$SUBSCRIPTION = "f23858ca-331b-4f31-89c1-e2ffa9e5c17c"
$RG = "rg-gcs-chkoenig"
$COSMOS_ACCOUNT = "cosmos-gcs-dev-6wo7gxoupztdm"
$KV_NAME = "kv-gcs-dev-6wo7gxoupztdm"
$OPENAI_ACCOUNT = "oai-gcs-dev"

# App Insights (from chkoenig environment)
$APP_INSIGHTS_KEY = "a007dab4-95ca-4be0-be5c-e5aefe09b9a8"
$APP_INSIGHTS_CS = "InstrumentationKey=a007dab4-95ca-4be0-be5c-e5aefe09b9a8;IngestionEndpoint=https://northcentralus-0.in.applicationinsights.azure.com/;LiveEndpoint=https://northcentralus.livediagnostics.monitor.azure.com/;ApplicationId=28d198d9-6471-425a-b52f-5a6340098088"

# =============================================================================
# Helpers
# =============================================================================
function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Err($msg) { Write-Host "   [ERROR] $msg" -ForegroundColor Red }
function Write-Skip($msg) { Write-Host "   [SKIP] $msg" -ForegroundColor DarkGray }

function Assert-AzSuccess($stepName) {
    if ($LASTEXITCODE -ne 0) {
        Write-Err "$stepName failed (exit code: $LASTEXITCODE)"
        throw "$stepName failed. Fix the error above before continuing."
    }
}

# =============================================================================
# Pre-flight
# =============================================================================
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  chkoenig Dev Environment Configuration"                   -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"               -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Err "Wrong subscription ($currentSub)."
    Write-Host "   Run: az account set --subscription $SUBSCRIPTION" -ForegroundColor Yellow
    exit 1
}
Write-Ok "Subscription confirmed ($SUBSCRIPTION)"

# =============================================================================
# Step 1 — Get public IP
# =============================================================================
Write-Step "Fetching your public IP..."
try {
    $myIp = (Invoke-RestMethod -Uri "https://api.ipify.org?format=text" -TimeoutSec 10).Trim()
}
catch {
    Write-Err "Could not determine public IP. Check your internet connection."
    exit 1
}
$myIpCidr = "$myIp/32"
Write-Ok "Your public IP: $myIp"

# =============================================================================
# Step 2 — Cosmos DB firewall
# =============================================================================
Write-Step "Checking Cosmos DB firewall ($COSMOS_ACCOUNT)..."

$currentFilter = az cosmosdb show `
    --subscription $SUBSCRIPTION `
    --resource-group $RG `
    --name $COSMOS_ACCOUNT `
    --query "ipRules[].ipAddressOrRange" `
    -o tsv 2>&1
Assert-AzSuccess "Cosmos DB firewall read"

$existingCosmosIps = @()
if ($currentFilter) {
    $existingCosmosIps = ($currentFilter -split "`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

if ($existingCosmosIps -contains $myIp) {
    Write-Ok "IP already in Cosmos DB firewall"
}
else {
    if ($WhatIf) {
        Write-Host "   [WHATIF] Would add $myIp to Cosmos DB firewall" -ForegroundColor Yellow
    }
    else {
        Write-Host "   Adding $myIp to Cosmos DB firewall..." -ForegroundColor Yellow
        $newFilter = ($existingCosmosIps + $myIp) -join ","
        az cosmosdb update `
            --subscription $SUBSCRIPTION `
            --resource-group $RG `
            --name $COSMOS_ACCOUNT `
            --ip-range-filter $newFilter `
            --output none 2>&1
        Assert-AzSuccess "Cosmos DB firewall update"
        Write-Ok "IP added to Cosmos DB firewall"
    }
}

# =============================================================================
# Step 3 — Key Vault firewall
# =============================================================================
Write-Step "Checking Key Vault firewall ($KV_NAME)..."

$kvNetworkRules = az keyvault network-rule list `
    --name $KV_NAME `
    --resource-group $RG `
    --query "ipRules[].value" `
    -o tsv 2>&1
Assert-AzSuccess "Key Vault firewall read"

$existingKvIps = @()
if ($kvNetworkRules) {
    $existingKvIps = ($kvNetworkRules -split "`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

$kvHasIp = ($existingKvIps -contains $myIp) -or ($existingKvIps -contains $myIpCidr)

if ($kvHasIp) {
    Write-Ok "IP already in Key Vault firewall"
}
else {
    if ($WhatIf) {
        Write-Host "   [WHATIF] Would add $myIpCidr to Key Vault firewall" -ForegroundColor Yellow
    }
    else {
        Write-Host "   Adding $myIp to Key Vault firewall..." -ForegroundColor Yellow
        az keyvault network-rule add `
            --name $KV_NAME `
            --resource-group $RG `
            --ip-address $myIpCidr `
            --output none 2>&1
        Assert-AzSuccess "Key Vault firewall update"
        Write-Ok "IP added to Key Vault firewall"
    }
}

# =============================================================================
# Step 4 — Retrieve endpoints from deployed resources
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

# =============================================================================
# Step 5 — Seed Key Vault secrets
# =============================================================================
$secrets = @(
    @{ name = "COSMOS-ENDPOINT"; value = $cosmosEndpoint }
    @{ name = "AZURE-OPENAI-ENDPOINT"; value = $oaiEndpoint }
    @{ name = "AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT"; value = "gpt-4o-standard" }
    @{ name = "AZURE-OPENAI-EMBEDDING-DEPLOYMENT"; value = "text-embedding-3-large" }
    @{ name = "AZURE-OPENAI-USE-AAD"; value = "true" }
    @{ name = "azure-app-insights-instrumentation-key"; value = $APP_INSIGHTS_KEY }
    @{ name = "azure-app-insights-connection-string"; value = $APP_INSIGHTS_CS }
)

if ($WhatIf) {
    Write-Host "`n[WHATIF] Would set the following secrets in '$KV_NAME':" -ForegroundColor Yellow
    foreach ($s in $secrets) {
        Write-Host "  $($s.name) = $($s.value)" -ForegroundColor Yellow
    }
}
else {
    # Azure CLI routes secret-set requests through Azure-side IPs that differ
    # from your public IP, so IP-based firewall rules alone aren't enough.
    # Temporarily open the default action, write secrets, then lock it back down.
    Write-Step "Temporarily allowing Key Vault access for secret writes..."
    az keyvault update `
        --name $KV_NAME `
        --resource-group $RG `
        --default-action Allow `
        --output none 2>&1
    Assert-AzSuccess "Key Vault default-action Allow"
    Write-Ok "Key Vault default action set to Allow"

    # Brief pause for the policy change to propagate
    Start-Sleep -Seconds 5

    $secretWriteFailed = $false
    foreach ($s in $secrets) {
        Write-Step "Setting secret '$($s.name)'..."
        az keyvault secret set `
            --vault-name $KV_NAME `
            --name $s.name `
            --value $s.value `
            --output none
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Setting secret '$($s.name)' failed"
            $secretWriteFailed = $true
            break
        }
        Write-Ok "$($s.name) set"
    }

    # Always restore the firewall — even if a secret write failed
    Write-Step "Restoring Key Vault firewall (default action → Deny)..."
    az keyvault update `
        --name $KV_NAME `
        --resource-group $RG `
        --default-action Deny `
        --output none 2>&1
    Assert-AzSuccess "Key Vault default-action Deny"
    Write-Ok "Key Vault default action restored to Deny"

    if ($secretWriteFailed) {
        throw "One or more secrets failed to write. Re-run the script to retry."
    }
}

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  chkoenig Environment Configuration Complete"              -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  IP:        $myIp"
Write-Host "  Cosmos DB: $COSMOS_ACCOUNT"
Write-Host "  Key Vault: $KV_NAME"
Write-Host "  OpenAI:    $OPENAI_ACCOUNT"
Write-Host ""
Write-Host "  Secrets stored in Key Vault:"
foreach ($s in $secrets) {
    Write-Host "    - $($s.name)"
}
Write-Host ""
Write-Host "  No COSMOS-KEY or AZURE-OPENAI-API-KEY stored."
Write-Host "  All auth uses DefaultAzureCredential (AAD tokens)."
Write-Host ""
Write-Host "To run the app with this environment:" -ForegroundColor Yellow
Write-Host '  $env:KEY_VAULT_NAME = "kv-gcs-dev-6wo7gxoupztdm"' -ForegroundColor Yellow
Write-Host "  .\start_dev.ps1" -ForegroundColor Yellow
Write-Host ""
