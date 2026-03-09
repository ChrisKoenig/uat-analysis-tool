<#
.SYNOPSIS
    Checks your current public IP and ensures it's in the Cosmos DB firewall rules.
.DESCRIPTION
    Fetches your public IP, reads the current Cosmos DB IP filter, and adds your IP if missing.
.NOTES
    Requires: Azure CLI (az) logged in with appropriate permissions.
#>

param(
    [string]$SubscriptionId,
    [string]$ResourceGroup,
    [string]$AccountName
)

# Apply environment-config defaults for any params not explicitly supplied.
$_env = if ($env:APP_ENV) { $env:APP_ENV } else { "preprod" }
$_configFile = Join-Path $PSScriptRoot "config\environments\$_env.ps1"
if (Test-Path $_configFile) {
    . $_configFile
} else {
    $SUBSCRIPTION = "a1e66643-8021-4548-8e36-f08076057b6a"
    $RG = "rg-nonprod-aitriage"
    $COSMOS_ACCOUNT = "cosmos-aitriage-nonprod"
}
if (-not $SubscriptionId) { $SubscriptionId = $SUBSCRIPTION }
if (-not $ResourceGroup)  { $ResourceGroup  = $RG }
if (-not $AccountName)    { $AccountName    = $COSMOS_ACCOUNT }

$ErrorActionPreference = "Stop"

# 1. Get current public IP
Write-Host "Fetching your public IP..." -ForegroundColor Cyan
try {
    $myIp = (Invoke-RestMethod -Uri "https://api.ipify.org?format=text" -TimeoutSec 10).Trim()
} catch {
    Write-Host "ERROR: Could not determine public IP. Check your internet connection." -ForegroundColor Red
    exit 1
}
Write-Host "Your public IP: $myIp" -ForegroundColor Green

# 2. Get current Cosmos DB firewall rules
Write-Host "Reading Cosmos DB firewall rules..." -ForegroundColor Cyan
try {
    $currentFilter = az cosmosdb show `
        --subscription $SubscriptionId `
        --resource-group $ResourceGroup `
        --name $AccountName `
        --query "ipRules[].ipAddressOrRange" `
        -o tsv 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to read Cosmos DB config. Make sure you're logged in (az login)." -ForegroundColor Red
        Write-Host $currentFilter -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Parse existing IPs into an array
$existingIps = @()
if ($currentFilter) {
    $existingIps = ($currentFilter -split "`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

Write-Host "Current firewall IPs ($($existingIps.Count)):" -ForegroundColor Cyan
$existingIps | ForEach-Object { Write-Host "  $_" }

# 3. Check if IP already present
if ($existingIps -contains $myIp) {
    Write-Host "`nYour IP ($myIp) is already in the Cosmos DB firewall. No changes needed." -ForegroundColor Green
    exit 0
}

# 4. Add the IP
Write-Host "`nYour IP ($myIp) is NOT in the firewall. Adding it now..." -ForegroundColor Yellow
$newFilter = ($existingIps + $myIp) -join ","

try {
    $result = az cosmosdb update `
        --subscription $SubscriptionId `
        --resource-group $ResourceGroup `
        --name $AccountName `
        --ip-range-filter $newFilter `
        --query "ipRules[].ipAddressOrRange" `
        -o tsv 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to update Cosmos DB firewall." -ForegroundColor Red
        Write-Host $result -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`nDone! Your IP ($myIp) has been added to the Cosmos DB firewall." -ForegroundColor Green
Write-Host "Updated firewall IPs:" -ForegroundColor Cyan
($result -split "`n") | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" } | ForEach-Object { Write-Host "  $_" }
