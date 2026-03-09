<#
.SYNOPSIS
    Deploy GCS services to Azure Container Apps.

.DESCRIPTION
    Builds 4 container images via ACR Tasks (no local Docker needed) and
    deploys them as Container Apps in the existing cae-gcs-dev environment.

    Services:
      ca-gcs-triage-api  — FastAPI triage backend          (internal, :8009)
      ca-gcs-field-api   — FastAPI field portal backend     (internal, :8010)
      ca-gcs-triage-ui   — React triage admin + nginx       (external, :80)
      ca-gcs-field-ui    — React field portal + nginx       (external, :80)

.NOTES
    Prerequisites:
      - Azure CLI logged in (az login)
      - Existing resources: rg-gcs-dev, acrgcsdevgg4a6y, cae-gcs-dev
#>

param(
    [switch]$BuildOnly,      # Only build images, don't deploy
    [switch]$DeployOnly,     # Only deploy (images must already exist)
    [switch]$SkipIdentity    # Skip managed identity creation (already exists)
)

$ErrorActionPreference = "Stop"

# ============================================================================
# Configuration — loaded from shared environment config file
# ============================================================================
# To target a different environment, set APP_ENV before running:
#   $env:APP_ENV = "preprod"; .\containers\deploy.ps1
$_env = if ($env:APP_ENV) { $env:APP_ENV } else { "dev" }
$_configFile = Join-Path $PSScriptRoot "..\..\shared\config\environments\$_env.ps1"
if (-not (Test-Path $_configFile)) {
    Write-Error "Environment config not found: $_configFile  (valid: dev, preprod, prod)"
    exit 1
}
. $_configFile

# Map shared config vars to the names used in this script
$SUBSCRIPTION = $SUBSCRIPTION  # loaded by environment file
$LOCATION = $LOCATION
$ACR = $ACR
$ENV_NAME = $ENV_NAME
$KV_NAME = $KV_NAME
$COSMOS_ACCOUNT = $COSMOS_ACCOUNT

# Container-Apps-specific vars (not in shared config)
$IDENTITY_NAME = if ($IDENTITY_NAME) { $IDENTITY_NAME }  else { "id-gcs-containerapp" }
$COSMOS_ROLE_ID = "00000000-0000-0000-0000-000000000002"  # Built-in Cosmos Data Contributor

# Image tags
$TAG = "latest"
$TRIAGE_API_IMG = "$ACR.azurecr.io/gcs/triage-api:$TAG"
$FIELD_API_IMG = "$ACR.azurecr.io/gcs/field-api:$TAG"
$TRIAGE_UI_IMG = "$ACR.azurecr.io/gcs/triage-ui:$TAG"
$FIELD_UI_IMG = "$ACR.azurecr.io/gcs/field-ui:$TAG"

# ============================================================================
# Helper
# ============================================================================
function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }

# ============================================================================
# Step 1: Create User-Assigned Managed Identity
# ============================================================================
if (-not $DeployOnly -and -not $SkipIdentity) {
    Write-Step "Creating managed identity: $IDENTITY_NAME"
    az identity create `
        --name $IDENTITY_NAME `
        --resource-group $RG `
        --location $LOCATION `
        --output table

    # Wait for propagation
    Start-Sleep -Seconds 15
}

# Retrieve identity properties
Write-Step "Retrieving managed identity details"
$IDENTITY_ID = az identity show --name $IDENTITY_NAME --resource-group $RG --query id -o tsv
$IDENTITY_CLIENT_ID = az identity show --name $IDENTITY_NAME --resource-group $RG --query clientId -o tsv
$IDENTITY_PRINCIPAL_ID = az identity show --name $IDENTITY_NAME --resource-group $RG --query principalId -o tsv

Write-Host "  Identity Resource ID : $IDENTITY_ID"
Write-Host "  Client ID            : $IDENTITY_CLIENT_ID"
Write-Host "  Principal ID         : $IDENTITY_PRINCIPAL_ID"

# ============================================================================
# Step 2: RBAC — Cosmos DB Data Contributor
# ============================================================================
if (-not $DeployOnly -and -not $SkipIdentity) {
    Write-Step "Assigning Cosmos DB SQL role (Data Contributor)"
    $COSMOS_ID = az cosmosdb show --name $COSMOS_ACCOUNT --resource-group $RG --query id -o tsv

    az cosmosdb sql role assignment create `
        --account-name $COSMOS_ACCOUNT `
        --resource-group $RG `
        --role-definition-id $COSMOS_ROLE_ID `
        --principal-id $IDENTITY_PRINCIPAL_ID `
        --scope $COSMOS_ID `
        --output table 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (Role assignment may already exist — continuing)" -ForegroundColor Yellow
    }
}

# ============================================================================
# Step 3: RBAC — Key Vault Secrets User
# ============================================================================
if (-not $DeployOnly -and -not $SkipIdentity) {
    Write-Step "Assigning Key Vault Secrets User role"
    $KV_ID = az keyvault show --name $KV_NAME --resource-group $RG --query id -o tsv

    az role assignment create `
        --role "Key Vault Secrets User" `
        --assignee-object-id $IDENTITY_PRINCIPAL_ID `
        --assignee-principal-type ServicePrincipal `
        --scope $KV_ID `
        --output table 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (Role assignment may already exist — continuing)" -ForegroundColor Yellow
    }
}

# ============================================================================
# Step 4: RBAC — Cognitive Services OpenAI User (for Azure OpenAI AAD auth)
# ============================================================================
if (-not $DeployOnly -and -not $SkipIdentity) {
    Write-Step "Assigning Cognitive Services OpenAI User role"

    # Find the OpenAI resource in the subscription
    $OPENAI_ID = az cognitiveservices account list --resource-group $RG --query "[?kind=='OpenAI'].id | [0]" -o tsv 2>$null
    if (-not $OPENAI_ID) {
        # Try the known resource name directly
        $OPENAI_ID = az cognitiveservices account show --name "OpenAI-bp-NorthCentral" --resource-group $RG --query id -o tsv 2>$null
    }

    if ($OPENAI_ID) {
        az role assignment create `
            --role "Cognitive Services OpenAI User" `
            --assignee-object-id $IDENTITY_PRINCIPAL_ID `
            --assignee-principal-type ServicePrincipal `
            --scope $OPENAI_ID `
            --output table 2>$null
        Write-Host "  Assigned on: $OPENAI_ID"
    }
    else {
        Write-Host "  OpenAI resource not found in $RG — skipping (you may need to assign manually)" -ForegroundColor Yellow
    }
}

# ============================================================================
# Step 5: Build images via ACR Tasks
# ============================================================================
if (-not $DeployOnly) {
    Write-Step "Building triage-api image"
    az acr build --registry $ACR --image "gcs/triage-api:$TAG" `
        --file infra/docker/triage-api.Dockerfile . --no-logs

    Write-Step "Building field-api image"
    az acr build --registry $ACR --image "gcs/field-api:$TAG" `
        --file infra/docker/field-api.Dockerfile . --no-logs

    Write-Step "Building triage-ui image"
    az acr build --registry $ACR --image "gcs/triage-ui:$TAG" `
        --file infra/docker/triage-ui.Dockerfile . --no-logs

    Write-Step "Building field-ui image"
    az acr build --registry $ACR --image "gcs/field-ui:$TAG" `
        --file infra/docker/field-ui.Dockerfile . --no-logs

    Write-Host "`nAll 4 images built successfully." -ForegroundColor Green
}

if ($BuildOnly) {
    Write-Host "`n-BuildOnly specified — skipping deployment." -ForegroundColor Yellow
    exit 0
}

# ============================================================================
# Step 6: Grant ACR pull to the managed identity
# ============================================================================
Write-Step "Granting AcrPull role to managed identity"
$ACR_ID = az acr show --name $ACR --resource-group $RG --query id -o tsv

az role assignment create `
    --role AcrPull `
    --assignee-object-id $IDENTITY_PRINCIPAL_ID `
    --assignee-principal-type ServicePrincipal `
    --scope $ACR_ID `
    --output table 2>$null

# ============================================================================
# Step 7: Deploy API containers (internal ingress)
# ============================================================================
Write-Step "Deploying ca-gcs-triage-api (internal)"
az containerapp create `
    --name ca-gcs-triage-api `
    --resource-group $RG `
    --environment $ENV_NAME `
    --image $TRIAGE_API_IMG `
    --registry-server "$ACR.azurecr.io" `
    --registry-identity $IDENTITY_ID `
    --user-assigned $IDENTITY_ID `
    --target-port 8009 `
    --ingress internal `
    --transport auto `
    --cpu 1.0 --memory 2.0Gi `
    --min-replicas 0 --max-replicas 2 `
    --env-vars `
    "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" `
    "AZURE_OPENAI_USE_AAD=true" `
    --output table

Write-Step "Deploying ca-gcs-field-api (internal)"
az containerapp create `
    --name ca-gcs-field-api `
    --resource-group $RG `
    --environment $ENV_NAME `
    --image $FIELD_API_IMG `
    --registry-server "$ACR.azurecr.io" `
    --registry-identity $IDENTITY_ID `
    --user-assigned $IDENTITY_ID `
    --target-port 8010 `
    --ingress internal `
    --transport auto `
    --cpu 1.0 --memory 2.0Gi `
    --min-replicas 0 --max-replicas 2 `
    --env-vars `
    "AZURE_CLIENT_ID=$IDENTITY_CLIENT_ID" `
    "AZURE_OPENAI_USE_AAD=true" `
    "API_GATEWAY_URL=http://ca-gcs-triage-api" `
    --output table

# ============================================================================
# Step 8: Deploy UI containers (external ingress)
# ============================================================================

# Get the internal FQDN of the API containers for nginx proxy_pass
$TRIAGE_API_FQDN = az containerapp show --name ca-gcs-triage-api --resource-group $RG `
    --query "properties.configuration.ingress.fqdn" -o tsv
$FIELD_API_FQDN = az containerapp show --name ca-gcs-field-api --resource-group $RG `
    --query "properties.configuration.ingress.fqdn" -o tsv

# For internal ingress, the URL is https://<fqdn>
$TRIAGE_API_URL = "https://$TRIAGE_API_FQDN"
$FIELD_API_URL = "https://$FIELD_API_FQDN"

Write-Host "  Triage API internal URL: $TRIAGE_API_URL"
Write-Host "  Field API internal URL : $FIELD_API_URL"

Write-Step "Deploying ca-gcs-triage-ui (external)"
az containerapp create `
    --name ca-gcs-triage-ui `
    --resource-group $RG `
    --environment $ENV_NAME `
    --image $TRIAGE_UI_IMG `
    --registry-server "$ACR.azurecr.io" `
    --registry-identity $IDENTITY_ID `
    --user-assigned $IDENTITY_ID `
    --target-port 80 `
    --ingress external `
    --transport auto `
    --cpu 0.25 --memory 0.5Gi `
    --min-replicas 0 --max-replicas 2 `
    --env-vars "API_URL=$TRIAGE_API_URL" `
    --output table

Write-Step "Deploying ca-gcs-field-ui (external)"
az containerapp create `
    --name ca-gcs-field-ui `
    --resource-group $RG `
    --environment $ENV_NAME `
    --image $FIELD_UI_IMG `
    --registry-server "$ACR.azurecr.io" `
    --registry-identity $IDENTITY_ID `
    --user-assigned $IDENTITY_ID `
    --target-port 80 `
    --ingress external `
    --transport auto `
    --cpu 0.25 --memory 0.5Gi `
    --min-replicas 0 --max-replicas 2 `
    --env-vars "API_URL=$FIELD_API_URL" `
    --output table

# ============================================================================
# Step 9: Print URLs
# ============================================================================
Write-Step "Deployment complete!"

$TRIAGE_UI_FQDN = az containerapp show --name ca-gcs-triage-ui --resource-group $RG `
    --query "properties.configuration.ingress.fqdn" -o tsv
$FIELD_UI_FQDN = az containerapp show --name ca-gcs-field-ui --resource-group $RG `
    --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "Triage Admin UI : https://$TRIAGE_UI_FQDN" -ForegroundColor Green
Write-Host "Field Portal    : https://$FIELD_UI_FQDN" -ForegroundColor Green
Write-Host ""
Write-Host "Login: gcs / TriageGCS2026!" -ForegroundColor Yellow
Write-Host ""
Write-Host "To update after code changes:"
Write-Host "  az acr build -r $ACR -f infra/docker/<dockerfile> -t gcs/<image>:latest ."
Write-Host "  az containerapp update -n <app-name> -g $RG --image <full-image-tag>"
