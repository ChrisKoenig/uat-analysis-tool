# ─────────────────────────────────────────────────────────────────────────────
# Shared JSON → PowerShell variable loader
# ─────────────────────────────────────────────────────────────────────────────
# Reads a JSON config file (dev.json / preprod.json) and sets the PS1
# variables that all infrastructure and utility scripts expect.
#
# Usage — set $_configJsonPath before dot-sourcing:
#
#   $_configJsonPath = Join-Path $PSScriptRoot "dev.json"
#   . (Join-Path $PSScriptRoot "_load-config.ps1")
#
# The caller receives the same variables that the old hand-written PS1 files
# exported ($SUBSCRIPTION, $TENANT_ID, $RG, $KV_NAME, …).
# ─────────────────────────────────────────────────────────────────────────────

if (-not $_configJsonPath -or -not (Test-Path $_configJsonPath)) {
    Write-Error "Config JSON not found: $_configJsonPath"
    exit 1
}

$_cfg = Get-Content $_configJsonPath -Raw | ConvertFrom-Json

# ── Core identity ─────────────────────────────────────────────────────────────
$APP_ENV = $_cfg.app_env
$SUBSCRIPTION = $_cfg.subscription_id
$TENANT_ID = $_cfg.tenant_id
$RG = $_cfg.resource_group
$LOCATION = $_cfg.azure_location

# ── Key Vault ─────────────────────────────────────────────────────────────────
$KV_NAME = $_cfg.key_vault_name

# ── Cosmos DB ─────────────────────────────────────────────────────────────────
$COSMOS_ACCOUNT = $_cfg.cosmos_account
$COSMOS_DATABASE = $_cfg.cosmos_database

# ── Azure OpenAI ──────────────────────────────────────────────────────────────
$OPENAI_ACCOUNT = $_cfg.openai_account
$OPENAI_CLASSIFICATION_DEPLOYMENT = $_cfg.classification_deployment
$OPENAI_EMBEDDING_DEPLOYMENT = $_cfg.embedding_deployment

# ── Storage ───────────────────────────────────────────────────────────────────
$STORAGE_ACCOUNT = $_cfg.storage_account
$STORAGE_CONTAINER = $_cfg.storage_container

# ── Azure DevOps ──────────────────────────────────────────────────────────────
$ADO_ORG = $_cfg.ado_organization
$ADO_PROJECT = $_cfg.ado_project
$ADO_TFT_ORG = $_cfg.ado_tft_organization

# ── Managed Identity ──────────────────────────────────────────────────────────
$MI_NAME = $_cfg.managed_identity_name
$MI_CLIENT_ID = $_cfg.managed_identity_client_id
$MI_OBJECT_ID = $_cfg.managed_identity_object_id
$IDENTITY_NAME = $_cfg.managed_identity_name          # alias used by containers/deploy.ps1

# ── Container / ACR ───────────────────────────────────────────────────────────
$ACR = $_cfg.acr_name
$ENV_NAME = $_cfg.container_env_name

# ── Optional PS1-only fields (present in some environments) ───────────────────
if ($_cfg.PSObject.Properties.Name -contains "app_services") {
    $APP_SERVICES = @($_cfg.app_services)
}
if ($_cfg.PSObject.Properties.Name -contains "app_plan_name") {
    $APP_PLAN = $_cfg.app_plan_name
    $APP_PLAN_SKU = $_cfg.app_plan_sku
}
if ($_cfg.PSObject.Properties.Name -contains "msal_client_id") {
    $MSAL_CLIENT_ID = $_cfg.msal_client_id
    $MSAL_TENANT_ID = $_cfg.microsoft_tenant_id
}
if ($_cfg.PSObject.Properties.Name -contains "app_insights_connection_string") {
    $APP_INSIGHTS_CS = $_cfg.app_insights_connection_string
}
if ($_cfg.PSObject.Properties.Name -contains "app_insights_key") {
    $APP_INSIGHTS_KEY = $_cfg.app_insights_key
}

# ── Colour-coded confirmation ─────────────────────────────────────────────────
$_color = switch ($APP_ENV) { "dev" { "Cyan" } "preprod" { "Yellow" } "prod" { "Green" } default { "White" } }
Write-Host "[config] Loaded $APP_ENV environment from JSON (sub: $SUBSCRIPTION, rg: $RG)" -ForegroundColor $_color
