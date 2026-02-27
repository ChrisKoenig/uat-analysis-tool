<#
.SYNOPSIS
    Builds deployment zip packages LOCALLY for upload to Cloud Shell.

.DESCRIPTION
    Creates 4 zip files in infrastructure/deploy/packages/:
      - triage-api.zip     (Python API + shared modules)
      - field-api.zip      (Python API + shared modules)
      - triage-ui.zip      (React build output)
      - field-ui.zip       (React build output)

    After running, upload all 4 zips to Cloud Shell, then run:
      az webapp deploy --name <app> --resource-group rg-nonprod-aitriage --src-path <zip> --type zip

.NOTES
    Run from the repo root: .\infrastructure\deploy\build-packages.ps1
#>

[CmdletBinding()]
param(
    [ValidateSet("all", "triage-api", "field-api", "triage-ui", "field-ui")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"

# MSAL config baked into UI builds
$MSAL_CLIENT_ID = "6257f944-71eb-49b9-8ef6-ab006383d54c"
$MSAL_TENANT_ID = "72f988bf-86f1-41af-91ab-2d7cd011db47"

$repoRoot = $PSScriptRoot | Split-Path | Split-Path
$outDir   = Join-Path $PSScriptRoot "packages"

if (-not (Test-Path $outDir)) { New-Item -Path $outDir -ItemType Directory | Out-Null }

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }

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
    "cache_manager.py"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build Deployment Packages"              -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Repo root: $repoRoot"
Write-Host "  Output:    $outDir"

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

    # Copy shared root modules
    foreach ($f in $sharedFiles) {
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
        # Write config.json into public/ before build
        $publicDir = "public"
        if (-not (Test-Path $publicDir)) { New-Item $publicDir -ItemType Directory | Out-Null }

        $configJson = @{
            msal = @{
                clientId    = $MSAL_CLIENT_ID
                tenantId    = $MSAL_TENANT_ID
                redirectUri = "https://app-triage-ui-nonprod.azurewebsites.net"
            }
            api = @{
                baseUrl = "https://app-triage-api-nonprod.azurewebsites.net"
            }
        } | ConvertTo-Json -Depth 3

        $configJson | Set-Content -Path (Join-Path $publicDir "config.json") -Encoding UTF8
        Write-Ok "config.json written"

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

        $configJson = @{
            msal = @{
                clientId    = $MSAL_CLIENT_ID
                tenantId    = $MSAL_TENANT_ID
                redirectUri = "https://app-field-ui-nonprod.azurewebsites.net"
            }
            api = @{
                baseUrl = "https://app-field-api-nonprod.azurewebsites.net"
            }
        } | ConvertTo-Json -Depth 3

        $configJson | Set-Content -Path (Join-Path $publicDir "config.json") -Encoding UTF8
        Write-Ok "config.json written"

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
Write-Host "  `$RG = `"rg-nonprod-aitriage`"" -ForegroundColor White
Write-Host "  az webapp deploy --name app-triage-api-nonprod --resource-group `$RG --src-path triage-api.zip --type zip" -ForegroundColor White
Write-Host "  az webapp deploy --name app-field-api-nonprod  --resource-group `$RG --src-path field-api.zip  --type zip" -ForegroundColor White
Write-Host "  az webapp deploy --name app-triage-ui-nonprod  --resource-group `$RG --src-path triage-ui.zip  --type zip" -ForegroundColor White
Write-Host "  az webapp deploy --name app-field-ui-nonprod   --resource-group `$RG --src-path field-ui.zip   --type zip" -ForegroundColor White
