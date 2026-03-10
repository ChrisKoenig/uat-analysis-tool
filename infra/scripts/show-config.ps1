<#
.SYNOPSIS
    Prints every configuration value for the active (or specified) environment.

.DESCRIPTION
    Loads config/environments/<env>.ps1 and displays all settings in grouped,
    colour-coded sections.  Sensitive values (subscription IDs, tenant IDs,
    managed-identity client/object IDs) are shown in full so you can verify
    they are correct — do NOT run this script in a shared terminal session or
    pipe its output to a log file that others can read.

.PARAMETER Environment
    Target environment: dev | preprod | prod.
    Defaults to the APP_ENV environment variable, or "dev" if that is not set.

.EXAMPLE
    # Show dev config (default)
    .\infra\scripts\show-config.ps1

    # Show preprod config explicitly
    .\infra\scripts\show-config.ps1 -Environment preprod
#>

param(
    [Alias("Env")]
    [string]$Environment
)

# ── Resolve which environment to show ────────────────────────────────────────
if (-not $Environment) {
    $Environment = if ($env:APP_ENV) { $env:APP_ENV } else { "dev" }
}
$Env = $Environment
$Env = $Env.ToLower()

$configFile = Join-Path $PSScriptRoot "..\..\shared\config\environments\$Env.ps1"
if (-not (Test-Path $configFile)) {
    Write-Error "Config file not found: $configFile`nValid environments: dev, preprod, prod"
    exit 1
}

# Dot-source the environment file so all variables land in this scope
. $configFile

# ── Helpers ──────────────────────────────────────────────────────────────────
function Show-Section([string]$Title) {
    Write-Host ""
    Write-Host "  $Title" -ForegroundColor DarkCyan
    Write-Host "  $('─' * ($Title.Length))" -ForegroundColor DarkGray
}

function Show-Value([string]$Label, $Value, [string]$Color = "White") {
    $display = if ($null -eq $Value -or $Value -eq "") { "(not set)" } else { $Value }
    $displayColor = if ($null -eq $Value -or $Value -eq "") { "DarkGray" } else { $Color }
    Write-Host ("    {0,-42} {1}" -f $Label, $display) -ForegroundColor $displayColor
}

function Show-List([string]$Label, $Items) {
    if (-not $Items -or $Items.Count -eq 0) {
        Show-Value $Label $null
    }
    else {
        Write-Host ("    {0,-42} {1}" -f $Label, $Items[0]) -ForegroundColor White
        for ($i = 1; $i -lt $Items.Count; $i++) {
            Write-Host ("    {0,-42} {1}" -f "", $Items[$i]) -ForegroundColor White
        }
    }
}

# ── Header ────────────────────────────────────────────────────────────────────
$envColor = switch ($Env) {
    "dev" { "Cyan" }
    "preprod" { "Yellow" }
    "prod" { "Green" }
    default { "White" }
}

Write-Host ""
Write-Host " ╔══════════════════════════════════════════════════════════════╗" -ForegroundColor $envColor
Write-Host (" ║  UAT Analysis Tool — Config Dump ({0,-27}║" -f "$Env)") -ForegroundColor $envColor
Write-Host " ╚══════════════════════════════════════════════════════════════╝" -ForegroundColor $envColor

# ── Azure Identity ────────────────────────────────────────────────────────────
Show-Section "Azure Identity"
Show-Value "Environment"        $APP_ENV          $envColor
Show-Value "Subscription ID"    $SUBSCRIPTION
Show-Value "Tenant ID"          $TENANT_ID
Show-Value "Resource Group"     $RG
Show-Value "Azure Location"     $LOCATION

# ── Key Vault ─────────────────────────────────────────────────────────────────
Show-Section "Key Vault"
Show-Value "Key Vault Name"     $KV_NAME
Show-Value "Key Vault URL"      "https://$KV_NAME.vault.azure.net/"  "DarkYellow"

# ── Cosmos DB ─────────────────────────────────────────────────────────────────
Show-Section "Cosmos DB"
Show-Value "Cosmos Account"     $COSMOS_ACCOUNT
Show-Value "Cosmos Database"    $COSMOS_DATABASE
Show-Value "Cosmos Endpoint"    "https://$COSMOS_ACCOUNT.documents.azure.com:443/"  "DarkYellow"

# ── Azure OpenAI ──────────────────────────────────────────────────────────────
Show-Section "Azure OpenAI"
Show-Value "OpenAI Account"     $OPENAI_ACCOUNT
Show-Value "OpenAI Endpoint"    "https://$OPENAI_ACCOUNT.openai.azure.com/"  "DarkYellow"
Show-Value "Classification Deployment"  $OPENAI_CLASSIFICATION_DEPLOYMENT
Show-Value "Embedding Deployment"       $OPENAI_EMBEDDING_DEPLOYMENT

# ── Azure Storage ─────────────────────────────────────────────────────────────
Show-Section "Azure Storage"
Show-Value "Storage Account"    $STORAGE_ACCOUNT
Show-Value "Storage Container"  $STORAGE_CONTAINER

# ── Azure DevOps ──────────────────────────────────────────────────────────────
Show-Section "Azure DevOps"
Show-Value "ADO Organization"   $ADO_ORG
Show-Value "ADO Project"        $ADO_PROJECT
Show-Value "TFT Organization"   $ADO_TFT_ORG

# ── Managed Identity ──────────────────────────────────────────────────────────
Show-Section "Managed Identity"
Show-Value "MI Name"            $MI_NAME
Show-Value "MI Client ID"       $MI_CLIENT_ID
Show-Value "MI Object ID"       $MI_OBJECT_ID

# ── Container Apps / ACR ──────────────────────────────────────────────────────
Show-Section "Container Apps / ACR"
Show-Value "ACR Name"           $ACR
Show-Value "Container Env Name" $ENV_NAME
Show-Value "Container Identity" $IDENTITY_NAME

# ── App Services (preprod/prod only) ──────────────────────────────────────────
if ($APP_SERVICES -and $APP_SERVICES.Count -gt 0) {
    Show-Section "App Services"
    Show-List    "App Service Names" $APP_SERVICES
}

# ── Active env-var overrides in current shell ─────────────────────────────────
$overrides = @{}
$watchVars = @(
    "APP_ENV", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "RESOURCE_GROUP",
    "KEY_VAULT_NAME", "AZURE_KEY_VAULT_NAME", "COSMOS_ACCOUNT", "COSMOS_DATABASE",
    "OPENAI_ACCOUNT", "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "STORAGE_ACCOUNT", "STORAGE_CONTAINER",
    "ADO_ORGANIZATION", "ADO_PROJECT", "ADO_TFT_ORGANIZATION",
    "AZURE_CLIENT_ID", "APP_DEBUG", "LOG_LEVEL", "CORS_ORIGINS"
)
foreach ($v in $watchVars) {
    $val = [System.Environment]::GetEnvironmentVariable($v)
    if ($val) { $overrides[$v] = $val }
}

if ($overrides.Count -gt 0) {
    Show-Section "Active Shell Overrides (env vars that will override config)"
    foreach ($kv in $overrides.GetEnumerator() | Sort-Object Name) {
        Show-Value $kv.Name $kv.Value "Magenta"
    }
}
else {
    Show-Section "Active Shell Overrides"
    Write-Host "    (none — config file values will be used as-is)" -ForegroundColor DarkGray
}

Write-Host ""
