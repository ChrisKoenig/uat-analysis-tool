<#
.SYNOPSIS
    Builds deployment zip packages LOCALLY for upload to Cloud Shell.

.DESCRIPTION
    Creates 4 zip files in infrastructure/deploy/packages/:
      - triage-api.zip     (Python API + shared modules)
      - field-api.zip      (Python API + shared modules)
      - triage-ui.zip      (React build output)
      - field-ui.zip       (React build output)

    Use the -Env flag to select the configuration:
      - local:  MSAL redirects to localhost, API calls to localhost (no baseUrl)
      - prod:   MSAL redirects to Azure App Service URLs, API baseUrl set

    After running, upload all 4 zips to Cloud Shell, then run:
      az webapp deploy --name <app> --resource-group rg-nonprod-aitriage --src-path <zip> --type zip

.NOTES
    Run from the repo root: .\infrastructure\deploy\build-packages.ps1
    Run from the repo root: .\infrastructure\deploy\build-packages.ps1 -Env local
#>

[CmdletBinding()]
param(
    [ValidateSet("all", "triage-api", "field-api", "triage-ui", "field-ui")]
    [string]$Target = "all",

    [ValidateSet("local", "prod")]
    [string]$Env = "prod"
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

$repoRoot = $PSScriptRoot | Split-Path | Split-Path
$outDir   = Join-Path $PSScriptRoot "packages"

if (-not (Test-Path $outDir)) { New-Item -Path $outDir -ItemType Directory | Out-Null }

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }

# --- Resolve config template suffix from -Env flag ---
$configSuffix = $Env  # "local" or "prod"

# --- Shared root modules that both APIs import ---
$sharedFiles = @(
    "keyvault_config.py",
    "ai_config.py",
    "shared_auth.py",
    "ado_integration.py",
    "enhanced_matching.py",
    "embedding_service.py",
    "search_service.py",
    "vector_search.py",
    "llm_classifier.py",
    "hybrid_context_analyzer.py",
    "intelligent_context_analyzer.py",
    "cache_manager.py",
    "servicetree_service.py",
    "weight_tuner.py"
)

# --- Runtime JSON data files that modules load via Path(__file__).parent ---
$dataFiles = @(
    "retirements.json",
    "servicetree_offerings.json",
    "corrections.json"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Deployment Packages ($Env)"     -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Subscription: $SUBSCRIPTION"
Write-Host "  Resource Grp: $RG"
Write-Host "  Repo root:    $repoRoot"
Write-Host "  Output:       $outDir"
Write-Host "  Config:       config.$configSuffix.json"

# =============================================================================
# 1. Triage API
# =============================================================================
if ($Target -eq "all" -or $Target -eq "triage-api") {
    Write-Step "Packaging Triage API..."

    $zipFile = Join-Path $outDir "triage-api.zip"
    if (Test-Path $zipFile) { Remove-Item $zipFile }

    $staging = Join-Path $env:TEMP "triage-api-staging"
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    New-Item $staging -ItemType Directory | Out-Null

    # Copy triage package
    Copy-Item (Join-Path $repoRoot "triage") (Join-Path $staging "triage") -Recurse
    # Copy api package (shared API modules)
    Copy-Item (Join-Path $repoRoot "api") (Join-Path $staging "api") -Recurse
    # Copy agents package
    Copy-Item (Join-Path $repoRoot "agents") (Join-Path $staging "agents") -Recurse

    # Copy shared root modules
    foreach ($f in $sharedFiles) {
        $src = Join-Path $repoRoot $f
        if (Test-Path $src) { Copy-Item $src $staging }
    }

    # Copy runtime JSON data files
    foreach ($f in $dataFiles) {
        $src = Join-Path $repoRoot $f
        if (Test-Path $src) { Copy-Item $src $staging }
    }

    # Copy requirements
    Copy-Item (Join-Path $repoRoot "triage" "requirements.txt") $staging

    # Remove __pycache__, test files
    Get-ChildItem $staging -Recurse -Directory -Filter "__pycache__" |
        Remove-Item -Recurse -Force
    Get-ChildItem $staging -Recurse -Directory -Filter "tests" |
        Remove-Item -Recurse -Force

    Compress-Archive -Path "$staging\*" -DestinationPath $zipFile -Force
    Remove-Item $staging -Recurse -Force

    $size = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
    Write-Ok "triage-api.zip ($size MB)"
}

# =============================================================================
# 2. Field Portal API
# =============================================================================
if ($Target -eq "all" -or $Target -eq "field-api") {
    Write-Step "Packaging Field Portal API..."

    $zipFile = Join-Path $outDir "field-api.zip"
    if (Test-Path $zipFile) { Remove-Item $zipFile }

    $staging = Join-Path $env:TEMP "field-api-staging"
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    New-Item $staging -ItemType Directory | Out-Null

    # Copy field-portal/api/ as "api/" package at root
    Copy-Item (Join-Path $repoRoot "field-portal" "api") (Join-Path $staging "api") -Recurse

    # Copy triage config package (cosmos_client.py imports triage.config.cosmos_config)
    $triageConfigDst = Join-Path $staging "triage" "config"
    New-Item $triageConfigDst -ItemType Directory -Force | Out-Null
    Copy-Item (Join-Path $repoRoot "triage" "__init__.py") (Join-Path $staging "triage" "__init__.py")
    Copy-Item (Join-Path $repoRoot "triage" "config" "__init__.py") (Join-Path $triageConfigDst "__init__.py")
    Copy-Item (Join-Path $repoRoot "triage" "config" "cosmos_config.py") (Join-Path $triageConfigDst "cosmos_config.py")
    Write-Ok "triage/config/ copied for Cosmos access"

    # Copy shared root modules
    foreach ($f in $sharedFiles) {
        $src = Join-Path $repoRoot $f
        if (Test-Path $src) { Copy-Item $src $staging }
    }

    # Copy runtime JSON data files
    foreach ($f in $dataFiles) {
        $src = Join-Path $repoRoot $f
        if (Test-Path $src) { Copy-Item $src $staging }
    }

    # Copy requirements (use triage's — same deps apply)
    Copy-Item (Join-Path $repoRoot "triage" "requirements.txt") $staging

    # Remove __pycache__
    Get-ChildItem $staging -Recurse -Directory -Filter "__pycache__" |
        Remove-Item -Recurse -Force

    Compress-Archive -Path "$staging\*" -DestinationPath $zipFile -Force
    Remove-Item $staging -Recurse -Force

    $size = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
    Write-Ok "field-api.zip ($size MB)"
}

# =============================================================================
# 3. Triage UI
# =============================================================================
if ($Target -eq "all" -or $Target -eq "triage-ui") {
    Write-Step "Building Triage UI..."

    Push-Location (Join-Path $repoRoot "triage-ui")
    try {
        # Copy the environment-specific config template into public/config.json
        $publicDir = "public"
        if (-not (Test-Path $publicDir)) { New-Item $publicDir -ItemType Directory | Out-Null }

        $templateFile = Join-Path $publicDir "config.$configSuffix.json"
        if (-not (Test-Path $templateFile)) {
            throw "Config template not found: $templateFile"
        }
        Copy-Item $templateFile (Join-Path $publicDir "config.json") -Force
        Write-Ok "config.json written from config.$configSuffix.json"

        npm ci --silent 2>&1 | Out-Null
        Write-Ok "npm ci complete"

        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
        Write-Ok "Build complete"

        $zipFile = Join-Path $outDir "triage-ui.zip"
        if (Test-Path $zipFile) { Remove-Item $zipFile }
        Compress-Archive -Path "dist\*" -DestinationPath $zipFile -Force

        $size = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
        Write-Ok "triage-ui.zip ($size MB)"
    } finally {
        Pop-Location
    }
}

# =============================================================================
# 4. Field Portal UI
# =============================================================================
if ($Target -eq "all" -or $Target -eq "field-ui") {
    Write-Step "Building Field Portal UI..."

    Push-Location (Join-Path $repoRoot "field-portal" "ui")
    try {
        $publicDir = "public"
        if (-not (Test-Path $publicDir)) { New-Item $publicDir -ItemType Directory | Out-Null }

        $templateFile = Join-Path $publicDir "config.$configSuffix.json"
        if (-not (Test-Path $templateFile)) {
            throw "Config template not found: $templateFile"
        }
        Copy-Item $templateFile (Join-Path $publicDir "config.json") -Force
        Write-Ok "config.json written from config.$configSuffix.json"

        npm ci --silent 2>&1 | Out-Null
        Write-Ok "npm ci complete"

        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
        Write-Ok "Build complete"

        $zipFile = Join-Path $outDir "field-ui.zip"
        if (Test-Path $zipFile) { Remove-Item $zipFile }
        Compress-Archive -Path "dist\*" -DestinationPath $zipFile -Force

        $size = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
        Write-Ok "field-ui.zip ($size MB)"
    } finally {
        Pop-Location
    }
}

# =============================================================================
# Summary
# =============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Packages Ready"                         -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Get-ChildItem $outDir -Filter "*.zip" | ForEach-Object {
    Write-Host "  $($_.Name) — $([math]::Round($_.Length / 1MB, 1)) MB"
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Upload all 4 zips to Cloud Shell"
Write-Host "  2. Run these commands in Cloud Shell:"
Write-Host ""
Write-Host "  az account set --subscription $SUBSCRIPTION" -ForegroundColor White
Write-Host "  `$RG = `"$RG`"" -ForegroundColor White
Write-Host "  az webapp deploy --name $TRIAGE_API --resource-group `$RG --src-path triage-api.zip --type zip" -ForegroundColor White
Write-Host "  az webapp deploy --name $FIELD_API  --resource-group `$RG --src-path field-api.zip  --type zip" -ForegroundColor White
Write-Host "  az webapp deploy --name $TRIAGE_UI  --resource-group `$RG --src-path triage-ui.zip  --type zip" -ForegroundColor White
Write-Host "  az webapp deploy --name $FIELD_UI   --resource-group `$RG --src-path field-ui.zip   --type zip" -ForegroundColor White
Write-Host ""
Write-Host "  Subscription: $SUBSCRIPTION" -ForegroundColor DarkGray
