<#
.SYNOPSIS
    Creates core Azure resources for GCS Triage Management System (pre-prod).
    
.DESCRIPTION
    Creates: Cosmos DB account + database + 10 containers, Azure OpenAI + 2 model deployments,
    App Service Plan + 4 App Services (2 Python APIs, 2 Node UIs).

    Prerequisites:
      - Azure CLI installed and logged in to the correct tenant
      - Subscription set: az account set --subscription a1e66643-8021-4548-8e36-f08076057b6a

.NOTES
    Run from the repo root: .\infrastructure\deploy\01-create-resources.ps1
#>

[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# =============================================================================
# Configuration — loaded from shared environment config file
# =============================================================================
# To target a different environment, set APP_ENV before running:
#   $env:APP_ENV = "preprod"; .\infrastructure\deploy\01-create-resources.ps1
$_env = if ($env:APP_ENV) { $env:APP_ENV } else { "preprod" }
$_configFile = Join-Path $PSScriptRoot "..\..\shared\config\environments\$_env.ps1"
if (-not (Test-Path $_configFile)) {
    Write-Error "Environment config not found: $_configFile  (valid: dev, preprod, prod)"
    exit 1
}
. $_configFile

# Map shared config vars; script-local names kept for readability
$SUBSCRIPTION = $SUBSCRIPTION
$RG = $RG
$LOCATION = $LOCATION
$COSMOS_ACCOUNT = $COSMOS_ACCOUNT
$COSMOS_DB = $COSMOS_DATABASE
$OPENAI_ACCOUNT = $OPENAI_ACCOUNT

# App Service names (preprod-specific; not in shared config)
$APP_PLAN = "plan-aitriage-nonprod"
$APP_PLAN_SKU = "B2"
$TRIAGE_API = "app-triage-api-nonprod"
$FIELD_API = "app-field-api-nonprod"
$TRIAGE_UI = "app-triage-ui-nonprod"
$FIELD_UI = "app-field-ui-nonprod"

# =============================================================================
# Helper
# =============================================================================
function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Write-Skip($msg) { Write-Host "   [SKIP] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "   [ERROR] $msg" -ForegroundColor Red }

function Assert-AzSuccess($stepName) {
    if ($LASTEXITCODE -ne 0) {
        Write-Err "$stepName failed (exit code: $LASTEXITCODE)"
        throw "$stepName failed. Fix the error above before continuing."
    }
}

# =============================================================================
# Pre-flight checks
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GCS Pre-Prod Resource Deployment"      -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Step "Verifying subscription..."
$currentSub = az account show --query "id" -o tsv 2>&1
if ($currentSub -ne $SUBSCRIPTION) {
    Write-Host "   [ERROR] Wrong subscription. Expected: $SUBSCRIPTION" -ForegroundColor Red
    Write-Host "   Current: $currentSub" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Run:  az login --tenant <TENANT_ID>" -ForegroundColor Yellow
    Write-Host "         az account set --subscription $SUBSCRIPTION" -ForegroundColor Yellow
    exit 1
}
Write-Ok "Subscription: $currentSub"

# Verify resource group exists
Write-Step "Verifying resource group '$RG'..."
$rgExists = az group show --name $RG --query "name" -o tsv 2>$null
if (-not $rgExists) {
    Write-Host "   [ERROR] Resource group '$RG' does not exist." -ForegroundColor Red
    exit 1
}
Write-Ok "Resource group exists"

if ($WhatIf) {
    Write-Host "`n[WHATIF] Would create the following resources:" -ForegroundColor Yellow
    Write-Host "  - Cosmos DB: $COSMOS_ACCOUNT (database: $COSMOS_DB, 10 containers)"
    Write-Host "  - Azure OpenAI: $OPENAI_ACCOUNT (gpt-4o-standard, text-embedding-3-large)"
    Write-Host "  - App Service Plan: $APP_PLAN ($APP_PLAN_SKU Linux)"
    Write-Host "  - App Services: $TRIAGE_API, $FIELD_API, $TRIAGE_UI, $FIELD_UI"
    exit 0
}

# =============================================================================
# 1. Cosmos DB
# =============================================================================
Write-Step "Creating Cosmos DB account '$COSMOS_ACCOUNT'..."
$cosmosExists = az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $RG --query "name" -o tsv 2>$null
if ($cosmosExists) {
    Write-Skip "Cosmos DB account already exists"
}
else {
    az cosmosdb create `
        --name $COSMOS_ACCOUNT `
        --resource-group $RG `
        --locations regionName=$LOCATION failoverPriority=0 isZoneRedundant=false `
        --kind GlobalDocumentDB `
        --default-consistency-level Session `
        --enable-analytical-storage false `
        --capabilities EnableServerless `
        --output none
    Assert-AzSuccess "Cosmos DB account creation"
    Write-Ok "Cosmos DB account created (serverless)"
}

Write-Step "Creating database '$COSMOS_DB'..."
$dbExists = az cosmosdb sql database show --account-name $COSMOS_ACCOUNT --resource-group $RG --name $COSMOS_DB --query "name" -o tsv 2>$null
if ($dbExists) {
    Write-Skip "Database already exists"
}
else {
    az cosmosdb sql database create `
        --account-name $COSMOS_ACCOUNT `
        --resource-group $RG `
        --name $COSMOS_DB `
        --output none
    Assert-AzSuccess "Database creation"
    Write-Ok "Database created"
}

# Container definitions: name -> partition key
$containers = @(
    @{ name = "rules"; partitionKey = "/status" }
    @{ name = "actions"; partitionKey = "/status" }
    @{ name = "triggers"; partitionKey = "/status" }
    @{ name = "routes"; partitionKey = "/status" }
    @{ name = "evaluations"; partitionKey = "/workItemId" }
    @{ name = "analysis-results"; partitionKey = "/workItemId" }
    @{ name = "field-schema"; partitionKey = "/source" }
    @{ name = "audit-log"; partitionKey = "/entityType" }
    @{ name = "corrections"; partitionKey = "/workItemId" }
    @{ name = "triage-teams"; partitionKey = "/status" }
)

foreach ($c in $containers) {
    Write-Step "Creating container '$($c.name)' (partition: $($c.partitionKey))..."
    $cExists = az cosmosdb sql container show `
        --account-name $COSMOS_ACCOUNT `
        --resource-group $RG `
        --database-name $COSMOS_DB `
        --name $c.name `
        --query "name" -o tsv 2>$null
    if ($cExists) {
        Write-Skip "Container '$($c.name)' already exists"
    }
    else {
        az cosmosdb sql container create `
            --account-name $COSMOS_ACCOUNT `
            --resource-group $RG `
            --database-name $COSMOS_DB `
            --name $c.name `
            --partition-key-path $c.partitionKey `
            --output none
        Assert-AzSuccess "Container '$($c.name)' creation"
        Write-Ok "Container '$($c.name)' created"
    }
}

# =============================================================================
# 2. Azure OpenAI
# =============================================================================
Write-Step "Creating Azure OpenAI account '$OPENAI_ACCOUNT'..."
$oaiExists = az cognitiveservices account show --name $OPENAI_ACCOUNT --resource-group $RG --query "name" -o tsv 2>$null
if ($oaiExists) {
    Write-Skip "OpenAI account already exists"
}
else {
    az cognitiveservices account create `
        --name $OPENAI_ACCOUNT `
        --resource-group $RG `
        --location $LOCATION `
        --kind OpenAI `
        --sku S0 `
        --custom-domain $OPENAI_ACCOUNT `
        --output none
    Assert-AzSuccess "OpenAI account creation"
    Write-Ok "OpenAI account created"
}

# Deploy GPT-4o
Write-Step "Deploying model 'gpt-4o-standard' (GPT-4o)..."
$gpt4Exists = az cognitiveservices account deployment show `
    --name $OPENAI_ACCOUNT `
    --resource-group $RG `
    --deployment-name "gpt-4o-standard" `
    --query "name" -o tsv 2>$null
if ($gpt4Exists) {
    Write-Skip "gpt-4o-standard deployment already exists"
}
else {
    az cognitiveservices account deployment create `
        --name $OPENAI_ACCOUNT `
        --resource-group $RG `
        --deployment-name "gpt-4o-standard" `
        --model-name "gpt-4o" `
        --model-version "2024-11-20" `
        --model-format OpenAI `
        --sku-capacity 30 `
        --sku-name "Standard" `
        --output none
    Assert-AzSuccess "gpt-4o-standard deployment"
    Write-Ok "gpt-4o-standard deployed"
}

# Deploy text-embedding-3-large
Write-Step "Deploying model 'text-embedding-3-large'..."
$embExists = az cognitiveservices account deployment show `
    --name $OPENAI_ACCOUNT `
    --resource-group $RG `
    --deployment-name "text-embedding-3-large" `
    --query "name" -o tsv 2>$null
if ($embExists) {
    Write-Skip "text-embedding-3-large deployment already exists"
}
else {
    az cognitiveservices account deployment create `
        --name $OPENAI_ACCOUNT `
        --resource-group $RG `
        --deployment-name "text-embedding-3-large" `
        --model-name "text-embedding-3-large" `
        --model-version "1" `
        --model-format OpenAI `
        --sku-capacity 120 `
        --sku-name "GlobalStandard" `
        --output none
    Assert-AzSuccess "text-embedding-3-large deployment"
    Write-Ok "text-embedding-3-large deployed"
}

# =============================================================================
# 3. App Service Plan
# =============================================================================
Write-Step "Creating App Service Plan '$APP_PLAN' ($APP_PLAN_SKU Linux)..."
$planExists = az appservice plan show --name $APP_PLAN --resource-group $RG --query "name" -o tsv 2>$null
if ($planExists) {
    Write-Skip "App Service Plan already exists"
}
else {
    az appservice plan create `
        --name $APP_PLAN `
        --resource-group $RG `
        --location $LOCATION `
        --sku $APP_PLAN_SKU `
        --is-linux `
        --output none
    Assert-AzSuccess "App Service Plan creation"
    Write-Ok "App Service Plan created"
}

# =============================================================================
# 4. App Services
# =============================================================================
$apps = @(
    @{ name = $TRIAGE_API; runtime = "PYTHON:3.13" }
    @{ name = $FIELD_API; runtime = "PYTHON:3.13" }
    @{ name = $TRIAGE_UI; runtime = "NODE:20-lts" }
    @{ name = $FIELD_UI; runtime = "NODE:20-lts" }
)

foreach ($app in $apps) {
    Write-Step "Creating App Service '$($app.name)' ($($app.runtime))..."
    $appExists = az webapp show --name $app.name --resource-group $RG --query "name" -o tsv 2>$null
    if ($appExists) {
        Write-Skip "App '$($app.name)' already exists"
    }
    else {
        az webapp create `
            --name $app.name `
            --resource-group $RG `
            --plan $APP_PLAN `
            --runtime $app.runtime `
            --output none
        Assert-AzSuccess "App '$($app.name)' creation"
        Write-Ok "App '$($app.name)' created"
    }
}

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Resource Creation Complete"             -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$cosmosEndpoint = az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $RG --query "documentEndpoint" -o tsv 2>$null
$oaiEndpoint = az cognitiveservices account show --name $OPENAI_ACCOUNT --resource-group $RG --query "properties.endpoint" -o tsv 2>$null

Write-Host "Cosmos DB Endpoint:  $cosmosEndpoint"
Write-Host "OpenAI Endpoint:     $oaiEndpoint"
Write-Host ""
Write-Host "App Service URLs:"
foreach ($app in $apps) {
    $url = az webapp show --name $app.name --resource-group $RG --query "defaultHostName" -o tsv 2>$null
    Write-Host "  $($app.name): https://$url"
}
Write-Host ""
Write-Host "Next step: Run 02-configure-rbac.ps1" -ForegroundColor Yellow
